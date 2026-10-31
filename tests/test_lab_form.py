"""Tests for reading the Word lab form (vibro_ifc/lab_form.py)."""
import io

import pytest

pytest.importorskip("docx")
from docx import Document

from vibro_ifc import lab_form as lf

LINES = [
    "Metadatensatz für unsere Messungen",
    "Quelle -> Eigene Erhebung",
    "Datum der Messung, Jahr der Datenerhebung -> 2024/2025",
    "Ort der Messung -> ZFB der HfT Stuttgart",
    "Prüfstand -> Wandprüfstand",
    "Maße der Wand -> B*H = 4,13 m * 2,75 m = 11,4, m2; Dicke = 416 mm",
    "Raumtemperatur -> 20,2 °C",
    "Luftfeuchtigkeit -> 27,3 %",
    "Luftdruck -> 974,6 hPa",
    "Art der Anregung",
    "Luftschallanregung (Lautsprecher/Rosa Rauschen) – Position der Anregung",
    "Ansprechperson / Autor / Verantwortlicher -> Peter Perivoitos",
]


def _docx(lines):
    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def test_reads_the_lab_facts():
    facts = lf.read_form(_docx(LINES))
    assert facts["wall_size"]["value"] == {"width_m": 4.13, "height_m": 2.75, "depth_mm": 416.0}
    assert (facts["temperature"]["value"], facts["humidity"]["value"], facts["pressure"]["value"]) == (20.2, 27.3, 974.6)
    assert facts["excitation"]["value"] == "Luftschallanregung (Lautsprecher/Rosa Rauschen)"
    assert facts["year"]["value"] == "2024/2025" and facts["location"]["value"] == "ZFB der HfT Stuttgart"


def test_missing_facts_are_absent_and_nothing_old_is_carried_over():
    import json

    kept = [ln for ln in LINES if not ln.startswith(("Raumtemperatur", "Ort der Messung", "Maße"))]
    template, absent = lf.apply_to_template(lf.read_form(_docx(kept)))
    assert {"temperature", "location", "wallDimensions"} <= set(absent)
    text = json.dumps(template, ensure_ascii=False)
    assert "20.2" not in text and "ZFB der HfT Stuttgart" not in text and "4.13" not in text


def test_changed_form_changes_the_facts():
    changed = [ln.replace("20,2", "18,5").replace("Wandprüfstand", "Fensterprüfstand") for ln in LINES]
    template, _ = lf.apply_to_template(lf.read_form(_docx(changed)))
    used = {c["rdfs:label"]: c["qudt:numericValue"] for c in template["foaf:primaryTopic"]["prov:used"]}
    assert used["air temperature"] == 18.5
    assert template["foaf:primaryTopic"]["sosa:madeBySensor"]["sosa:isHostedBy"]["rdfs:label"] == "Fensterprüfstand"


def test_excitation_conflict_with_file_name_is_flagged():
    template, _ = lf.apply_to_template(lf.read_form(_docx(LINES)), ["scan_Shaker_1.txt"])
    status = template["foaf:primaryTopic"]["sosa:usedProcedure"]["dqv:hasQualityMeasurement"][0]["dqv:value"]
    assert status == "unresolved"
    template, _ = lf.apply_to_template(lf.read_form(_docx(LINES)), ["scan_1.txt"])
    assert template["foaf:primaryTopic"]["sosa:usedProcedure"]["dqv:hasQualityMeasurement"][0]["dqv:value"] == "stated in the lab form"
