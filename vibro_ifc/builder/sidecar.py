"""sidecar.py - profile v0.6 <-> flat view.   No Blender, no network.

v0.6 records use existing vocabularies (SOSA, PROV-O, DCAT, DQV, SPDX, GeoSPARQL, schema.org, SKOS, ICDD linkset, ifcOWL names).
Only a handful of terms remain in the profile namespace `ldv:` (see CUSTOM_TERMS).

view(rec)   -> the flat, field-named dict the validator, viewer and builder work with (keys ldv:tier1Integrity ... ldv:completeness).
              A v0.5 record (tier layout) is returned unchanged, so old packages keep loading.
to_v06(L)   -> a v0.6 record from that flat dict (used by the builder and tools/migrate_v06.py).
view(to_v06(L)) gives back every field the tools use (tests/test_sidecar.py).
"""
import re, copy

EX = "https://example.org/ldv/id/"
PROFILE = "https://example.org/ldv/profile/v0.6"
CUSTOM_TERMS = ["ldv:RegistrationHypothesis", "ldv:transform", "ldv:referenceFace", "ldv:registration", "ldv:associationLevel",
                "ldv:frequencyAxis", "ldv:step", "ldv:binCount"]
NEW_CTX = {"foaf": "http://xmlns.com/foaf/0.1/", "dqv": "http://www.w3.org/ns/dqv#", "geo": "http://www.opengis.net/ont/geosparql#",
           "schema": "https://schema.org/", "skos": "http://www.w3.org/2004/02/skos/core#",
           "ls": "https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset#", "ifc": "https://standards.buildingsmart.org/IFC/DEV/IFC4/ADD2_TC1/OWL#",
           "ssn-system": "http://www.w3.org/ns/ssn/systems/", "ldvc": "https://example.org/ldv/concept/", "ldvm": "https://example.org/ldv/metric/"}
IFC_SCHEMA_IRI = {"IFC4X3_ADD2": "https://standards.buildingsmart.org/IFC/DEV/IFC4_3/ADD2", "IFC4": "https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1",
                  "IFC2X3": "https://standards.buildingsmart.org/IFC/RELEASE/IFC2x3/TC1"}
TIER_KEYS = ("ldv:tier1Integrity", "ldv:tier2Measurement", "ldv:tier3Lineage", "ldv:tier4Binding", "ldv:completeness")
SHA = {"@id": "spdx:checksumAlgorithm_sha256"}

def _v(x):
    if isinstance(x, dict):
        if "@value" in x: return x["@value"]
        if "@id" in x: return x["@id"]
    return x
def _list(x): return [] if x is None else (x if isinstance(x, list) else [x])
def _types(n): return [str(t) for t in _list((n or {}).get("@type"))]
def _expand(i, ex=EX): return ex + i[3:] if str(i).startswith("ex:") else str(i)
def _slug(s): return re.sub(r"[^\w.-]+", "-", str(s)).strip("-") or "x"
def dq(metric, value): return {"@type": "dqv:QualityMeasurement", "dqv:isMeasurementOf": {"@id": "ldvm:" + metric}, "dqv:value": value}
def meas(node, metric, default=None):
    for m in _list((node or {}).get("dqv:hasQualityMeasurement")):
        mo = m.get("dqv:isMeasurementOf"); i = mo.get("@id") if isinstance(mo, dict) else mo
        if str(i).split(":")[-1].split("/")[-1] == metric:
            v = m.get("dqv:value"); return [_v(a) for a in v] if isinstance(v, list) else _v(v)
    return default
def qv(value, unit): return {"@type": "schema:QuantitativeValue", "schema:value": value, "schema:unitCode": unit}
def _qv_m(n):                                                     # -> metres
    if not isinstance(n, dict): return None
    v = _v(n.get("schema:value")); u = _v(n.get("schema:unitCode"))
    try: v = float(v)
    except (TypeError, ValueError): return None
    return v / 1000.0 if u == "MMT" else v
def _cs(h): return {"@type": "spdx:Checksum", "spdx:algorithm": dict(SHA), "spdx:checksumValue": h}
WKT = re.compile(r"^\s*(?:<([^>]*)>\s*)?POINT\s*Z?\s*\(\s*([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s*\)\s*$", re.I)

def is_record(doc):
    return isinstance(doc, dict) and ("ldv:tier2Measurement" in doc or "foaf:primaryTopic" in doc)
def point_index(doc):
    return int(view(doc)["ldv:tier2Measurement"]["ldv:point"]["ldv:index"])

# ------------------------------------------------------------------ flat dict -> v0.6
def to_v06(L, ex=EX):
    L = copy.deepcopy(L); g = lambda k: L.get(k) or {}
    t1, t2, t3, t4, cp = (g(k) for k in TIER_KEYS)
    obs_id = t2.get("@id") or "ex:observation/x"
    # data file (sosa:hasResult)
    f = {k: v for k, v in t1.items() if not k.startswith("ldv:")}
    f["dcterms:type"] = {"@id": "ldvc:" + str(t1.get("ldv:dataStatus", "raw"))}
    cdoc = (f.get("csvw:tableSchema") or {}).get("csvw:column")
    for c in (cdoc.get("@list", []) if isinstance(cdoc, dict) else _list(cdoc)):
        if "ldv:unitText" in c: c["schema:unitText"] = c.pop("ldv:unitText")
        if "ldv:unitStatus" in c: c["dqv:hasQualityMeasurement"] = [dq("unitStatus", c.pop("ldv:unitStatus"))]
    # sample = the scan point, on the specimen
    pt = t2.get("ldv:point") or {}; fr = pt.get("ldv:scanFrame") or {}
    geom = {"@type": "geo:Geometry"}
    if fr.get("rdfs:label"): geom["rdfs:label"] = fr["rdfs:label"]
    if all(k in pt for k in ("ldv:x", "ldv:y", "ldv:z")):
        geom["geo:asWKT"] = {"@value": "<%s> POINT Z (%r %r %r)" % (_expand(fr.get("@id", "ex:frame/scan"), ex), float(pt["ldv:x"]), float(pt["ldv:y"]), float(pt["ldv:z"])), "@type": "geo:wktLiteral"}
    gm = [dq(m, fr["ldv:" + m]) for m in ("unitStatus", "definitionStatus") if "ldv:" + m in fr]
    if gm: geom["dqv:hasQualityMeasurement"] = gm
    T = t4.get("ldv:target") or {}
    def el6(e):
        n = {"@id": e.get("@id"), "@type": ["bot:Element"] + (["ifc:" + e["ldv:ifcClass"]] if e.get("ldv:ifcClass") else [])}
        if "rdfs:label" in e: n["rdfs:label"] = e["rdfs:label"]
        if "ldv:ifcGlobalId" in e: n["dcterms:identifier"] = e["ldv:ifcGlobalId"]
        if "ldv:wallCode" in e: n["skos:notation"] = e["ldv:wallCode"]
        if "ldv:elementFingerprint" in e: n["spdx:checksum"] = _cs(e["ldv:elementFingerprint"])
        return n
    spec = el6(T)
    if T.get("bot:hasSubElement"): spec["bot:hasSubElement"] = [el6(s) for s in _list(T["bot:hasSubElement"])]
    ls_ = T.get("ldv:layerStack")
    if ls_ is not None:
        items = ls_.get("@list", []) if isinstance(ls_, dict) else _list(ls_); out = []
        for l in items:
            if set(l) <= {"@id"}: out.append(l); continue
            out.append({"@id": l.get("@id"), "@type": "ifc:IfcMaterialLayer", "rdfs:label": l.get("rdfs:label", l.get("ldv:materialName")), "schema:depth": qv(l.get("ldv:thicknessM"), "MTR")})
        spec["dcterms:hasPart"] = {"@list": out}
    lab = T.get("ldv:reportedByLab")
    if lab:
        spec["prov:hadPrimarySource"] = {"@type": "prov:Entity", "rdfs:label": "Dimensions as reported in the lab form",
                                         "schema:width": qv(lab.get("ldv:widthM"), "MTR"), "schema:height": qv(lab.get("ldv:heightM"), "MTR"), "schema:depth": qv(lab.get("ldv:thicknessMm"), "MMT")}
    if T.get("ldv:modelUnitNote"): spec["skos:note"] = T["ldv:modelUnitNote"]
    samp_id = obs_id.replace("observation/", "point/") if "observation/" in obs_id else obs_id + "-point"
    samp = {"@id": samp_id, "@type": "sosa:Sample", "dcterms:identifier": pt.get("ldv:index"), "geo:hasGeometry": geom, "sosa:isSampleOf": spec}
    # sensor / procedure / platform
    sen = {k: v for k, v in (t2.get("sosa:madeBySensor") or {}).items() if not k.startswith("ldv:")}
    if "ldv:modelStatus" in (t2.get("sosa:madeBySensor") or {}): sen["dqv:hasQualityMeasurement"] = [dq("modelStatus", t2["sosa:madeBySensor"]["ldv:modelStatus"])]
    if t3.get("ldv:testRig"): sen["sosa:isHostedBy"] = {"@id": "ex:platform/" + _slug(t3["ldv:testRig"]), "@type": "sosa:Platform", "rdfs:label": t3["ldv:testRig"]}
    P0 = t2.get("sosa:usedProcedure") or {}
    proc = {k: v for k, v in P0.items() if not k.startswith("ldv:")}
    if "ldv:reportedInLabForm" in P0: proc["dcterms:source"] = P0["ldv:reportedInLabForm"]
    if "ldv:indicatedByFile" in P0: proc["dcterms:description"] = P0["ldv:indicatedByFile"]
    if "ldv:status" in P0: proc["dqv:hasQualityMeasurement"] = [dq("status", P0["ldv:status"])]
    fa = t2.get("ldv:frequencyAxis") or {}
    fa6 = {"@type": "schema:QuantitativeValue", "schema:minValue": fa.get("ldv:min"), "schema:maxValue": fa.get("ldv:max"), "ldv:step": fa.get("ldv:step"), "ldv:binCount": fa.get("ldv:binCount")}
    if "qudt:hasUnit" in fa: fa6["qudt:hasUnit"] = fa["qudt:hasUnit"]
    env = []
    for e in _list(t3.get("ldv:environment")):
        e = dict(e); e["@type"] = ["qudt:QuantityValue", "ssn-system:Condition"]; env.append(e)
    obs = {"@id": obs_id, "@type": t2.get("@type", ["sosa:Observation", "prov:Activity"]), "sosa:hasFeatureOfInterest": samp,
           "sosa:observedProperty": t2.get("sosa:observedProperty"), "sosa:madeBySensor": sen, "sosa:usedProcedure": proc, "sosa:hasResult": f, "ldv:frequencyAxis": fa6}
    for k in ("dcterms:temporal",):
        if t2.get(k): obs[k] = t2[k]
    for k in ("prov:wasAssociatedWith", "prov:atLocation", "dcterms:references"):
        if t3.get(k): obs[k] = t3[k]
    if env: obs["prov:used"] = env
    # binding = ICDD-style directed link from the sample to the IFC elements, with the IFC file as the document
    ifc = t4.get("ldv:ifcFile") or {}
    doc = {"@id": ifc.get("@id"), "@type": ["dcat:Distribution", "prov:Entity"]}
    for k in ("dcterms:title", "dcterms:modified", "spdx:checksum", "dcat:downloadURL"):
        if k in ifc: doc[k] = ifc[k]
    if ifc.get("ldv:schema"):
        sc = ifc["ldv:schema"]; doc["dcterms:conformsTo"] = ({"@id": IFC_SCHEMA_IRI[sc], "rdfs:label": sc} if sc in IFC_SCHEMA_IRI else {"rdfs:label": sc})
    to = []
    for e in ([T] if "ldv:ifcGlobalId" in T else []) + _list(T.get("bot:hasSubElement")):
        to.append({"@type": "ls:LinkElement", "ls:hasDocument": ({"@id": doc["@id"]} if to else doc),
                   "ls:hasIdentifier": {"@type": "ls:StringBasedIdentifier", "ls:identifierField": "Guid", "ls:identifier": e["ldv:ifcGlobalId"]}})
    if not to: to.append({"@type": "ls:LinkElement", "ls:hasDocument": doc})
    bind = {"@id": t4.get("@id"), "@type": "ls:DirectedLink",
            "ls:hasFromLinkElement": {"@type": "ls:LinkElement", "ls:hasDocument": {"@id": L.get("@id")}, "ls:hasIdentifier": {"@type": "ls:UriBasedIdentifier", "ls:uri": {"@value": _expand(samp_id, ex), "@type": "xsd:anyURI"}}},
            "ls:hasToLinkElement": to}
    for k in ("ldv:associationLevel", "ldv:registration"):
        if k in t4: bind[k] = t4[k]
    h = t4.get("ldv:registrationHypothesis")
    if h:
        bind["prov:wasInfluencedBy"] = {"@id": h.get("@id"), "@type": "ldv:RegistrationHypothesis", "dcterms:source": h.get("ldv:source"), "ldv:transform": h.get("ldv:mapping"),
                                              "ldv:referenceFace": h.get("ldv:referenceFace"), "dcterms:description": h.get("ldv:origin"), "skos:note": h.get("ldv:zAxis"),
                                              "dqv:hasQualityMeasurement": [dq("status", h.get("ldv:status"))]}
    if t4.get("ldv:fingerprintMethod") or t4.get("ldv:verifiedAt"):
        act = {"@type": "prov:Activity"}
        if t4.get("ldv:verifiedAt"): act["prov:endedAtTime"] = t4["ldv:verifiedAt"]
        if t4.get("ldv:fingerprintMethod"): act["prov:used"] = {"@id": "ex:plan/element-fingerprint", "@type": "prov:Plan", "dcterms:description": t4["ldv:fingerprintMethod"]}
        bind["prov:wasGeneratedBy"] = act
    if "ldv:bindingStatus" in t4: bind["dqv:hasQualityMeasurement"] = [dq("bindingStatus", t4["ldv:bindingStatus"])]
    ctx = dict(L.get("@context") or {}); ctx.update({k: v for k, v in NEW_CTX.items() if k not in ctx})
    R = {"@context": ctx, "@id": L.get("@id"), "@type": "dcat:CatalogRecord", "dcterms:conformsTo": {"@id": PROFILE}, "owl:versionInfo": "0.6",
         "foaf:primaryTopic": obs, "dcterms:relation": bind,
         "dqv:hasQualityMeasurement": [dq("absentFields", cp.get("ldv:absent", [])), dq("unresolvedFields", cp.get("ldv:unresolved", []))]}
    skip = set(TIER_KEYS) | {"@context", "@id", "@type", "dcterms:conformsTo", "owl:versionInfo"}
    for k, v in L.items():
        if k not in skip: R[k] = v
    return R

# ------------------------------------------------------------------ v0.6 -> flat dict
def view(rec):
    if not isinstance(rec, dict) or "ldv:tier2Measurement" in rec or "foaf:primaryTopic" not in rec: return rec
    obs = rec.get("foaf:primaryTopic") or {}; f = obs.get("sosa:hasResult") or {}; samp = obs.get("sosa:hasFeatureOfInterest") or {}
    spec = samp.get("sosa:isSampleOf") or {}; link = rec.get("dcterms:relation") or {}; geom = samp.get("geo:hasGeometry") or {}
    t1 = {k: v for k, v in f.items() if k != "dcterms:type"}
    t1["ldv:dataStatus"] = str(_v(f.get("dcterms:type")) or "ldvc:raw").split(":")[-1].split("/")[-1]
    pt = {"ldv:index": _v(samp.get("dcterms:identifier"))}
    m = WKT.match(str(_v(geom.get("geo:asWKT")) or ""))
    if m:
        pt["ldv:x"], pt["ldv:y"], pt["ldv:z"] = float(m[2]), float(m[3]), float(m[4])
        if m[1]: pt["ldv:scanFrame"] = {"@id": m[1], "rdfs:label": geom.get("rdfs:label", m[1].rstrip("/").split("/")[-1])}
    if "ldv:scanFrame" in pt:
        for k in ("unitStatus", "definitionStatus"):
            v = meas(geom, k)
            if v is not None: pt["ldv:scanFrame"]["ldv:" + k] = v
    fa = obs.get("ldv:frequencyAxis") or {}
    fa1 = {"ldv:min": _v(fa.get("schema:minValue")), "ldv:max": _v(fa.get("schema:maxValue")), "ldv:step": _v(fa.get("ldv:step")), "ldv:binCount": _v(fa.get("ldv:binCount"))}
    if "qudt:hasUnit" in fa: fa1["qudt:hasUnit"] = fa["qudt:hasUnit"]
    sen = {k: v for k, v in (obs.get("sosa:madeBySensor") or {}).items() if k not in ("dqv:hasQualityMeasurement", "sosa:isHostedBy")}
    ms = meas(obs.get("sosa:madeBySensor"), "modelStatus")
    if ms is not None: sen["ldv:modelStatus"] = ms
    P0 = obs.get("sosa:usedProcedure") or {}; proc = {k: v for k, v in P0.items() if k not in ("dqv:hasQualityMeasurement", "dcterms:source", "dcterms:description")}
    if "dcterms:source" in P0: proc["ldv:reportedInLabForm"] = P0["dcterms:source"]
    if "dcterms:description" in P0: proc["ldv:indicatedByFile"] = P0["dcterms:description"]
    ps = meas(P0, "status")
    if ps is not None: proc["ldv:status"] = ps
    t2 = {"@id": obs.get("@id"), "@type": obs.get("@type"), "sosa:observedProperty": obs.get("sosa:observedProperty"), "sosa:hasResult": {"@id": f.get("@id")}, "sosa:hasFeatureOfInterest": {"@id": spec.get("@id")},
          "ldv:point": pt, "ldv:frequencyAxis": fa1, "sosa:madeBySensor": sen, "sosa:usedProcedure": proc}
    if obs.get("dcterms:temporal"): t2["dcterms:temporal"] = obs["dcterms:temporal"]
    host = (obs.get("sosa:madeBySensor") or {}).get("sosa:isHostedBy") or {}
    t3 = {"@id": obs.get("@id")}
    for k in ("prov:wasAssociatedWith", "prov:atLocation", "dcterms:references"):
        if obs.get(k): t3[k] = obs[k]
    if host.get("rdfs:label"): t3["ldv:testRig"] = host["rdfs:label"]
    env = [e for e in _list(obs.get("prov:used")) if "qudt:QuantityValue" in _types(e)]
    if env: t3["ldv:environment"] = env
    # binding
    ifc_doc = {}
    for el in _list(link.get("ls:hasToLinkElement")):
        d = el.get("ls:hasDocument")
        if isinstance(d, dict) and ("spdx:checksum" in d or "dcat:downloadURL" in d): ifc_doc = d; break
    ifc1 = {k: v for k, v in ifc_doc.items() if k not in ("dcterms:conformsTo",)}
    cf = ifc_doc.get("dcterms:conformsTo")
    if isinstance(cf, dict): ifc1["ldv:schema"] = cf.get("rdfs:label") or str(cf.get("@id", "")).rstrip("/").split("/")[-1]
    def el1(n):
        e = {"@id": n.get("@id")}
        if "rdfs:label" in n: e["rdfs:label"] = n["rdfs:label"]
        cls = [t for t in _types(n) if t.startswith("ifc:")]
        if cls: e["ldv:ifcClass"] = cls[0][4:]
        if "dcterms:identifier" in n: e["ldv:ifcGlobalId"] = _v(n["dcterms:identifier"])
        if "skos:notation" in n: e["ldv:wallCode"] = _v(n["skos:notation"])
        cs = n.get("spdx:checksum")
        if isinstance(cs, dict): e["ldv:elementFingerprint"] = _v(cs.get("spdx:checksumValue"))
        return e
    tgt = el1(spec)
    if spec.get("bot:hasSubElement"): tgt["bot:hasSubElement"] = [el1(s) for s in _list(spec["bot:hasSubElement"])]
    hp = spec.get("dcterms:hasPart")
    if hp is not None:
        items = hp.get("@list", []) if isinstance(hp, dict) else _list(hp); st = []
        for k, l in enumerate(items):
            if set(l) <= {"@id"}: st.append(l); continue
            th = _qv_m(l.get("schema:depth"))
            st.append({"@id": l.get("@id"), "rdfs:label": l.get("rdfs:label"), "ldv:order": k, "ldv:materialName": l.get("rdfs:label"), **({"ldv:thicknessM": th} if th is not None else {})})
        tgt["ldv:layerStack"] = {"@list": st}
    ps_ = spec.get("prov:hadPrimarySource")
    if isinstance(ps_, dict):
        w, h_, d_ = _qv_m(ps_.get("schema:width")), _qv_m(ps_.get("schema:height")), _qv_m(ps_.get("schema:depth"))
        tgt["ldv:reportedByLab"] = {"ldv:widthM": w, "ldv:heightM": h_, "ldv:thicknessMm": None if d_ is None else round(d_ * 1000, 6)}
    if spec.get("skos:note"): tgt["ldv:modelUnitNote"] = spec["skos:note"]
    t4 = {"@id": link.get("@id"), "@type": "ldv:Binding", "ldv:measurementRecord": {"@id": obs.get("@id")}, "ldv:ifcFile": ifc1, "ldv:target": tgt}
    for k in ("ldv:associationLevel", "ldv:registration"):
        if k in link: t4[k] = link[k]
    h = link.get("prov:wasInfluencedBy")
    if isinstance(h, dict):
        t4["ldv:registrationHypothesis"] = {"@id": h.get("@id"), "@type": "ldv:RegistrationHypothesis", "ldv:source": h.get("dcterms:source"), "ldv:mapping": h.get("ldv:transform"),
                                            "ldv:referenceFace": h.get("ldv:referenceFace"), "ldv:origin": h.get("dcterms:description"), "ldv:zAxis": h.get("skos:note"), "ldv:status": meas(h, "status")}
    act = link.get("prov:wasGeneratedBy") or {}
    if act.get("prov:endedAtTime") is not None: t4["ldv:verifiedAt"] = act["prov:endedAtTime"]
    plan = act.get("prov:used") or {}
    if plan.get("dcterms:description"): t4["ldv:fingerprintMethod"] = plan["dcterms:description"]
    bs = meas(link, "bindingStatus")
    if bs is not None: t4["ldv:bindingStatus"] = bs
    cp = {"@type": "ldv:CompletenessReport", "ldv:absent": _list(meas(rec, "absentFields", [])), "ldv:unresolved": _list(meas(rec, "unresolvedFields", []))}
    V = {"@context": rec.get("@context"), "@id": rec.get("@id"), "@type": rec.get("@type"), "dcterms:conformsTo": rec.get("dcterms:conformsTo"), "owl:versionInfo": rec.get("owl:versionInfo"),
         "ldv:tier1Integrity": t1, "ldv:tier2Measurement": t2, "ldv:tier3Lineage": t3, "ldv:tier4Binding": t4, "ldv:completeness": cp}
    skip = {"@context", "@id", "@type", "dcterms:conformsTo", "owl:versionInfo", "foaf:primaryTopic", "dcterms:relation", "dqv:hasQualityMeasurement"}
    for k, v in rec.items():
        if k not in skip: V[k] = v
    return V
