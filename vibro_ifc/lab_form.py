"""Read the laboratory's Word form and turn it into the lab facts of a record.

The form is a list of lines such as "Raumtemperatur -> 20,2 °C".  Each fact is found
by its German label.  A fact that is not in the form is left out of the record and
listed as absent: nothing from an earlier test is carried over.
"""
from __future__ import annotations

import copy
import io
import json
import re
from pathlib import Path
from typing import Any

from vibro_ifc.build_service import DEFAULT_TEMPLATE

# status of a fact in the record
STORED, READ_ONLY, MISSING = "stored in the record", "read, not stored yet", "not found in the form"


def _num(text: str) -> float:
    return float(text.replace(",", "."))


def _text_of(docx_bytes: bytes) -> list[str]:
    from docx import Document

    doc = Document(io.BytesIO(docx_bytes))
    lines = [p.text.strip() for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            seen = []
            for cell in row.cells:
                if cell.text.strip() and cell.text.strip() not in seen:
                    seen.append(cell.text.strip())
            if seen:
                lines.append(" -> ".join(seen))
    return [ln for ln in lines if ln]


def _after(lines: list[str], label: str) -> str:
    """Value after 'label ->' on the same line, else the next non-empty line."""
    for i, ln in enumerate(lines):
        if re.search(label, ln, re.I):
            tail = re.split(r"->", ln, maxsplit=1)
            if len(tail) == 2 and tail[1].strip():
                return tail[1].strip()
            if i + 1 < len(lines):
                nxt = lines[i + 1]
                return nxt.split("->", 1)[-1].strip() if nxt.startswith("->") else nxt
    return ""


def read_form(docx_bytes: bytes) -> dict[str, Any]:
    """Return {fact: {"value": ..., "label": german label, "status": ...}} for every known fact."""
    lines = _text_of(docx_bytes)
    full = "\n".join(lines)
    facts: dict[str, dict[str, Any]] = {}

    def put(key: str, label: str, value: Any, status: str = STORED) -> None:
        facts[key] = {"label": label, "value": value if value not in ("", None) else None,
                      "status": status if value not in ("", None) else MISSING}

    years = re.search(r"Datum der Messung[^\n]*?->\s*(\d{4})(?:\s*/\s*(\d{4}))?", full, re.I)
    put("year", "Datum der Messung", f"{years[1]}/{years[2]}" if years and years[2] else (years[1] if years else ""))
    put("location", "Ort der Messung", _after(lines, r"^Ort der Messung"))
    put("test_rig", "Prüfstand", _after(lines, r"^Prüfstand"))
    put("data_origin", "Herkunftsart der Daten", _after(lines, r"Herkunftsart der Daten"), READ_ONLY)
    put("source", "Quelle", _after(lines, r"^Quelle"), READ_ONLY)
    put("responsible", "Ansprechperson / Autor", _after(lines, r"Ansprechperson|Verantwortlicher"))
    dims = re.search(r"B\s*\*\s*H\s*=\s*([\d,\.]+)\s*m\s*\*\s*([\d,\.]+)\s*m", full)
    thick = re.search(r"Dicke\s*=\s*([\d,\.]+)\s*mm", full)
    put("wall_size", "Maße der Wand", {"width_m": _num(dims[1]), "height_m": _num(dims[2]), "depth_mm": _num(thick[1]) if thick else None} if dims else "")
    for key, label, pat in (("temperature", "Raumtemperatur", r"Raumtemperatur\s*->\s*([\d,\.]+)"),
                            ("humidity", "Luftfeuchtigkeit", r"Luftfeuchtigkeit\s*->\s*([\d,\.]+)"),
                            ("pressure", "Luftdruck", r"Luftdruck\s*->\s*([\d,\.]+)")):
        m = re.search(pat, full, re.I)
        put(key, label, _num(m[1]) if m else "")
    exc = ""
    for i, ln in enumerate(lines):
        if re.match(r"Art der Anregung", ln, re.I):
            exc = ln.split("->", 1)[1].strip() if "->" in ln and ln.split("->", 1)[1].strip() else (lines[i + 1] if i + 1 < len(lines) else "")
            break
    put("excitation", "Art der Anregung", re.sub(r"\s*[–-]\s*Position der Anregung.*$", "", exc))
    sketch = re.search(r"Skizze:\s*(\S+\.(?:png|jpe?g))", full, re.I)
    put("sketch", "Skizze", sketch[1] if sketch else "")
    # read from the form but the profile has no place for them yet
    layers = re.search(r"Schichten:\s*([^\n]+)", full)
    put("layers", "Aufbau der Wand", layers[1].strip() if layers else "", READ_ONLY)
    mass = re.search(r"=\s*([\d,\.]+)\s*kg/m2\s*$", full, re.M)
    put("area_mass", "Flächenbezogene Masse", f"{mass[1]} kg/m²" if mass else "", READ_ONLY)
    rooms = re.findall(r"(Senderaum|Empfangsraum):\s*([^\n]+)", full)
    put("room_volumes", "Volumen der Messräume", "; ".join(f"{a}: {b}" for a, b in rooms), READ_ONLY)
    return facts


def _qv(node: dict, key: str, value: float, unit: str) -> None:
    node[key] = {"@type": "schema:QuantitativeValue", "schema:value": value, "schema:unitCode": unit}


def apply_to_template(facts: dict[str, Any], txt_names: list[str] | None = None, base: dict | None = None) -> tuple[dict, list[str]]:
    """Fill the lab facts of the base template from the form.  Returns (template, absent fact names)."""
    t = copy.deepcopy(base if base is not None else json.loads(DEFAULT_TEMPLATE.read_text(encoding="utf-8")))
    pt = t["foaf:primaryTopic"]
    val = lambda k: facts.get(k, {}).get("value")
    absent: list[str] = []

    # dimensions
    hp = pt["sosa:hasFeatureOfInterest"]["sosa:isSampleOf"]["prov:hadPrimarySource"]
    for k in ("schema:width", "schema:height", "schema:depth"):
        hp.pop(k, None)
    size = val("wall_size")
    if size:
        _qv(hp, "schema:width", size["width_m"], "MTR"); _qv(hp, "schema:height", size["height_m"], "MTR")
        if size.get("depth_mm"):
            _qv(hp, "schema:depth", size["depth_mm"], "MMT")
    else:
        absent.append("wallDimensions")

    # test rig, location, responsible person
    host = pt["sosa:madeBySensor"]["sosa:isHostedBy"]
    if val("test_rig"):
        host["rdfs:label"] = val("test_rig"); host["@id"] = "ex:platform/" + re.sub(r"\W+", "", val("test_rig"))
    else:
        pt["sosa:madeBySensor"].pop("sosa:isHostedBy", None); absent.append("testRig")
    if val("location"):
        pt["prov:atLocation"]["rdfs:label"] = val("location"); pt["prov:atLocation"]["@id"] = "ex:location/" + re.sub(r"\W+", "", val("location"))
    else:
        pt.pop("prov:atLocation", None); absent.append("location")
    if val("responsible"):
        t["dcterms:creator"]["rdfs:label"] = val("responsible")
    else:
        t["dcterms:creator"]["rdfs:label"] = "unknown"; absent.append("responsiblePerson")

    # date: the form gives years only
    years = (val("year") or "").split("/")
    if years and years[0]:
        pt["dcterms:temporal"]["dcat:startDate"]["@value"] = years[0]
        pt["dcterms:temporal"]["dcat:endDate"]["@value"] = years[-1]
        pt["dcterms:temporal"]["rdfs:comment"] = f"Reported as {val('year')} in the lab form; exact date unknown"
    else:
        pt.pop("dcterms:temporal", None)

    # ambient conditions
    keep = []
    for cond, key in (("air temperature", "temperature"), ("relative humidity", "humidity"), ("air pressure", "pressure")):
        item = next((c for c in pt["prov:used"] if c.get("rdfs:label") == cond), None)
        if item is not None and val(key) is not None:
            item["qudt:numericValue"] = val(key); keep.append(item)
        elif val(key) is None:
            absent.append(key)
    pt["prov:used"] = keep
    if not keep:
        pt.pop("prov:used")

    # excitation
    proc = pt["sosa:usedProcedure"]
    proc["dcterms:description"] = "reference channel as exported; unit m/s per N"
    status = proc["dqv:hasQualityMeasurement"][0]
    if val("excitation"):
        proc["dcterms:source"] = val("excitation")
        conflict = any("shaker" in n.lower() for n in (txt_names or [])) and re.search(r"lautsprecher|luft", val("excitation"), re.I)
        status["dqv:value"] = "unresolved" if conflict else "stated in the lab form"
        proc["dcterms:description"] += ("; the file name says 'Shaker', the form says loudspeaker" if conflict else "")
    else:
        proc["dcterms:source"] = "not stated"; status["dqv:value"] = "unresolved"; absent.append("excitation")

    # sketch
    if val("sketch"):
        pt["dcterms:references"]["@id"] = "data/" + val("sketch")
    else:
        pt.pop("dcterms:references", None); absent.append("setupSketch")
    if not val("data_origin"):
        absent.append("dataOrigin")

    for m in t["dqv:hasQualityMeasurement"]:
        if m["dqv:isMeasurementOf"]["@id"] == "ldvm:absentFields":
            m["dqv:value"] = list(dict.fromkeys(list(m["dqv:value"]) + absent))
    return t, absent


def template_from_form(docx_bytes: bytes, txt_names: list[str] | None = None) -> tuple[bytes, dict[str, Any], list[str]]:
    facts = read_form(docx_bytes)
    template, absent = apply_to_template(facts, txt_names)
    return json.dumps(template, ensure_ascii=False, indent=2).encode("utf-8"), facts, absent
