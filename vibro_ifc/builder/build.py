"""build.py - generic, config-driven builder.   python tools/build.py [project.json] [--strict] [--validate]

Reads three things and writes everything derived from them:
  IFC   (project.json "ifc")                       -> target element(s), geometry, fingerprints, frame (Pset) if present
  TXT   (project.json "data": dir + glob)          -> one record per file, spectra cache
  TEMPLATE (project.json "template")               -> the human-authored facts (lab form, open items); edit THIS, not the records
Writes   metadata/points/point_NNNN.jsonld, metadata/scan_index.jsonld, view/spectra.json, view/view_config_<name>.json, build_manifest.json
Nothing in the inputs is modified.  A TXT that cannot be read is EXCLUDED and listed (never silently dropped).
Records are generated artefacts: build_manifest.json holds their hashes, so a later hand edit is detected as 'stale'."""
import os, sys, re, json, glob, copy, datetime
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ldv_validity as V
import sidecar as SC
import ifcopenshell, ifcopenshell.util.element

DEFAULT_COLOURS = {"Planks": [0.80, 0.62, 0.40], "Timber": [0.80, 0.62, 0.40], "CrossLaminated": [0.86, 0.74, 0.52], "RockWool": [0.96, 0.89, 0.42], "Plaster": [0.88, 0.88, 0.88], "Cement": [0.70, 0.70, 0.72]}
NCOL = 7                                                        # frequency, real X/Y/Z, imag X/Y/Z
now = lambda: datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()

def die(msg): print("ERROR:", msg); sys.exit(2)

# ------------------------------------------------------------------------------------------------ config
def load_project(path):
    path = os.path.abspath(path)
    if not os.path.isfile(path): die("project file not found: %s" % path)
    cfg = json.load(open(path, encoding="utf-8")); root = os.path.dirname(path)
    cfg.setdefault("target", {}); cfg.setdefault("frame", {}); cfg.setdefault("out", {}); cfg.setdefault("data", {})
    for k in ("ifc", "template"):
        if k not in cfg: die("project.json needs '%s'" % k)
    return cfg, root

# ------------------------------------------------------------------------------------------------ IFC side
def pick_target(ifc, tcfg):
    """-> (kind, target element or None, [part elements])  kind: 'single' | 'parts' | 'all_walls'"""
    cls = tcfg.get("class", "IfcWall"); mode = tcfg.get("mode", "auto"); walls = list(ifc.by_type(cls))
    if not walls: die("the IFC has no %s" % cls)
    kids = lambda w: [c for rel in (getattr(w, "IsDecomposedBy", None) or []) for c in rel.RelatedObjects if c.is_a(cls)]
    if tcfg.get("guid"):
        try: el = ifc.by_guid(tcfg["guid"])
        except RuntimeError: die("GlobalId %s is not in the IFC" % tcfg["guid"])
        return ("parts", el, kids(el)) if kids(el) else ("single", el, [])
    if mode == "all_walls": return "all_walls", None, walls
    if len(walls) == 1: return "single", walls[0], []
    asm = [w for w in walls if kids(w)]
    if len(asm) == 1: return "parts", asm[0], kids(asm[0])
    cands = "\n".join("   %s  %s" % (w.GlobalId, w.Name) for w in walls)
    print("NOTE: %d %s elements and no single assembly: using all of them as parts of one specimen (set target.guid to choose one):\n%s" % (len(walls), cls, cands))
    return "all_walls", None, walls

def bbox(ifc, el, settings):
    try: i = V.element_info(ifc, el.GlobalId, settings); return i
    except Exception: return None

def read_frame(fcfg, elements, T_lo, T_hi):
    """-> M (4x4 scan->IFC), hypothesis dict.  Source: Pset_AcousticCoordinateSystem on the IFC, else project.json matrix, else a stated default."""
    ps = {}
    for el in elements:
        ps = ifcopenshell.util.element.get_psets(el).get("Pset_AcousticCoordinateSystem", {})
        if ps: ident = ifcopenshell.util.element.get_psets(el).get("Pset_AcousticWallIdentity", {}); break
    src = fcfg.get("source", "auto"); M = np.zeros((4, 4)); M[3, 3] = 1
    if src in ("auto", "pset") and ps.get("AcousticToIFCMapping"):
        mp = dict(re.findall(r"IFC_([XYZ])=Acoustic_([XYZ])", ps["AcousticToIFCMapping"]))
        if set(mp) != {"X", "Y", "Z"}: die("cannot read AcousticToIFCMapping: %s" % ps["AcousticToIFCMapping"])
        into = "into the wall" in str(ps.get("AcousticZAxis", "")).lower()
        for i, a in enumerate("XYZ"):
            j = "XYZ".index(mp[a]); M[i, j] = 1.0
            if a == "Y" and mp[a] == "Z": M[i, j] = 1.0 if into else -1.0
        hyp = {"source": "IFC Pset_AcousticCoordinateSystem (%s)" % ps.get("CoordinateSystemName", "?"), "mapping": ps["AcousticToIFCMapping"],
               "referenceFace": ident.get("ReferenceFace", fcfg.get("face_name", "?")), "origin": ps.get("OriginDefinition", "?"), "zAxis": ps.get("AcousticZAxis", "?"),
               "status": "declared by model; not confirmed by lab", "kind": "PSET"}
    elif src in ("auto", "explicit") and fcfg.get("matrix"):
        A = np.array(fcfg["matrix"], float)
        if A.shape not in ((3, 3), (3, 4)): die("frame.matrix must be 3x3 or 3x4")
        M[:3, :A.shape[1]] = A
        hyp = {"source": "project.json frame.matrix", "mapping": json.dumps(fcfg["matrix"]), "referenceFace": fcfg.get("face_name", "?"), "origin": fcfg.get("origin", "as given by the matrix"),
               "zAxis": fcfg.get("zAxis", "as given by the matrix"), "status": "declared in project.json; not confirmed by lab", "kind": "EXPLICIT"}
    else:
        M[0, 0] = 1; M[1, 2] = 1; M[2, 1] = 1
        hyp = {"source": "builder default (no Pset and no frame.matrix given)", "mapping": "IFC_X=Acoustic_X; IFC_Y=Acoustic_Z; IFC_Z=Acoustic_Y", "referenceFace": fcfg.get("face_name", "?"),
               "origin": "IFC origin", "zAxis": "scan depth -> IFC y (assumed)", "status": "ASSUMED default; nobody declared it", "kind": "DEFAULT"}
        print("WARNING: no frame declared -> using the default axis swap (scan y -> IFC z, scan z -> IFC y). Declare it in the IFC Pset or project.json.")
    sgn = float(M[1, np.argmax(abs(M[1, :3]))]) if abs(M[1, :3]).sum() else 1.0
    return M, hyp, (T_lo[1] if sgn >= 0 else T_hi[1]), int(sgn)

# ------------------------------------------------------------------------------------------------ TXT side
def read_txt(path):
    """-> (index, x, y, z, rows array (n x 7), first data line number)   raises ValueError with a reason"""
    raw = open(path, "rb").read().decode("latin-1"); L = raw.splitlines(); m = V.HEADER.search("\n".join(L[:6]))
    if not m: raise ValueError("no 'Point Index ... [x = .. y = .. z = ..]' header line")
    n0 = next((k for k, l in enumerate(L) if len(l.split("\t")) >= NCOL and re.fullmatch(r"[-+\d.eE]+", l.split("\t")[0].strip() or "x")), None)
    if n0 is None: raise ValueError("no numeric data rows found")
    try: a = np.array([[float(c) for c in l.split("\t")] for l in L[n0:] if l.strip()])
    except ValueError as e: raise ValueError("non-numeric cell in the data rows (%s)" % e)
    if a.ndim != 2 or a.shape[1] != NCOL: raise ValueError("expected %d columns, found %s" % (NCOL, a.shape[1:] or "ragged rows"))
    if not np.isfinite(a).all(): raise ValueError("NaN/inf in the data")
    return int(m[1]), float(m[2]), float(m[3]), float(m[4]), a, n0

def levels(a):
    H = {c: a[:, i] + 1j * a[:, i + 3] for c, i in (("X", 1), ("Y", 2), ("Z", 3))}
    H["NORM"] = np.sqrt(sum(abs(h) ** 2 for h in H.values())); return {c: 20 * np.log10(np.maximum(abs(h), 1e-30)) for c, h in H.items()}

def sub(o, tag):
    if isinstance(o, dict): return {k: sub(v, tag) for k, v in o.items()}
    if isinstance(o, list): return [sub(v, tag) for v in o]
    return o.replace("{point}", tag) if isinstance(o, str) else o

# ------------------------------------------------------------------------------------------------ main
def main(argv):
    strict = "--strict" in argv; args = [a for a in argv if not a.startswith("--")]
    cfg, ROOT = load_project(args[0] if args else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "project.json"))
    P = lambda *a: os.path.join(ROOT, *a); rel = lambda p: os.path.relpath(p, ROOT).replace("\\", "/")
    out_md = cfg["out"].get("metadata", "metadata"); out_view = cfg["out"].get("view", "view"); vname = cfg["out"].get("view_name", "view")
    ddir = cfg["data"].get("dir", "data"); dglob = cfg["data"].get("glob", "*.txt"); FREQ = float(cfg["data"].get("default_freq_hz", 1000)); COMP = cfg["data"].get("default_channel", "Z")
    COL = dict(DEFAULT_COLOURS, **cfg.get("colours", {}))
    # ---------------- IFC
    IFC_REL = cfg["ifc"]; IFC = P(IFC_REL)
    if not os.path.isfile(IFC): die("IFC not found: %s" % IFC)
    ifc = ifcopenshell.open(IFC); S = V.geom_settings(); kind, tgt, parts = pick_target(ifc, cfg["target"])
    elems = ([tgt] if tgt is not None else []) + parts; info = {}
    for e in elems:
        i = bbox(ifc, e, S)
        if i is not None: info[e.GlobalId] = i
    if not info: die("no element of the target has geometry")
    lo = np.min([i["lo"] for i in info.values()], 0) + 0.0; hi = np.max([i["hi"] for i in info.values()], 0) + 0.0; L, T, H = (hi - lo).tolist()
    ifc_stamp = (re.search(r"FILE_NAME\('[^']*','([^']*)'", open(IFC, encoding="latin-1").read()) or [None, ""])[1]
    print("IFC %s: %s target, bbox %s .. %s" % (ifc.schema_identifier, kind, lo.round(4), hi.round(4)))
    # layer stack: only for a single element with a material layer set
    stack = []; unit_note = None
    if kind == "single":
        mat = ifcopenshell.util.element.get_material(tgt)
        if mat is not None and (mat.is_a("IfcMaterialLayerSetUsage") or mat.is_a("IfcMaterialLayerSet")):
            lset = mat.ForLayerSet if mat.is_a("IfcMaterialLayerSetUsage") else mat; y = 0.0
            for k, l in enumerate(lset.MaterialLayers):
                th = float(l.LayerThickness); nm = l.Material.Name if l.Material else "layer%d" % k
                stack.append({"@id": "ex:layer/%s/%d" % (tgt.GlobalId, k), "@type": "ldv:MaterialLayer", "rdfs:label": nm, "ldv:order": k, "ldv:offsetM": round(y, 6) + 0.0, "ldv:thicknessM": th, "ldv:materialName": nm}); y += th
            mm = any(u.is_a("IfcSIUnit") and u.UnitType == "LENGTHUNIT" and u.Prefix == "MILLI" for u in ifc.by_type("IfcUnitAssignment")[0].Units)
            if mm and abs(y - T) < 1e-6:
                unit_note = ("MaterialLayer.LayerThickness values sum to %.3f and the geometry is %.3f m, so they are written in METRES, but the file declares millimetre as length unit: "
                             "a strict IFC reader would read %.3f mm. Treated here as metres." % (y, T, y)); print("WARNING:", unit_note)
    M, HYP, face_y, nsign = read_frame(cfg["frame"], elems, lo, hi); det = float(np.linalg.det(M[:3, :3]))
    # ---------------- template
    tmpl = SC.view(json.load(open(P(cfg["template"]), encoding="utf-8")))          # template may be v0.5 or v0.6; the builder works on the flat fields
    ctx_base = dict(tmpl["@context"]); ctx_base.update({k: v for k, v in SC.NEW_CTX.items() if k not in ctx_base})
    b0 = tmpl["ldv:tier4Binding"]; lab = (b0.get("ldv:target") or {}).get("ldv:reportedByLab")
    ifc_node = {"@id": "ex:ifcfile/" + os.path.splitext(os.path.basename(IFC))[0].replace(" ", "_"), "@type": "prov:Entity", "dcterms:title": os.path.basename(IFC), "ldv:schema": ifc.schema_identifier,
                "dcterms:modified": {"@value": ifc_stamp, "@type": "xsd:dateTime"}, "spdx:checksum": {"@type": "spdx:Checksum", "spdx:algorithm": {"@id": "spdx:checksumAlgorithm_sha256"}, "spdx:checksumValue": V.sha256(IFC)},
                "dcat:downloadURL": {"@id": IFC_REL}}
    def nice(e):                                      # parts often carry generic names ('Part:324797'); the material name says more
        i = info.get(e.GlobalId); generic = not e.Name or re.match(r"^(Part|Wall|Basic Wall)\W*:?\s*\d*$", e.Name)
        return (i["material"] if (kind != "single" and i and i["material"] and generic) else e.Name) or e.GlobalId
    def el_node(e, order=None):
        i = info.get(e.GlobalId); n = {"@id": "ex:ifc/" + e.GlobalId, "@type": "bot:Element", "ldv:ifcClass": e.is_a(), "ldv:ifcGlobalId": e.GlobalId, "rdfs:label": nice(e)}
        if e.Tag: n["ldv:wallCode"] = e.Tag
        if i is not None:
            n["ldv:elementFingerprint"] = i["fingerprint"]
            if e is not tgt: n["ldv:offsetM"] = round(float(i["lo"][1] - lo[1]), 6) + 0.0; n["ldv:thicknessM"] = round(float(i["hi"][1] - i["lo"][1]), 6) + 0.0
        return n
    if kind == "single":
        target = el_node(tgt); target["ldv:layerStack"] = {"@list": stack}
    elif kind == "parts":
        target = el_node(tgt); target["bot:hasSubElement"] = [el_node(p) for p in sorted(parts, key=lambda p: (info[p.GlobalId]["lo"][1] if p.GlobalId in info else 0))]
    else:
        target = {"@id": "ex:specimen/" + re.sub(r"\W+", "", cfg.get("name", "specimen")), "@type": "bot:Element", "rdfs:label": cfg.get("name", "specimen"),
                  "bot:hasSubElement": [el_node(p) for p in sorted(parts, key=lambda p: (info[p.GlobalId]["lo"][1] if p.GlobalId in info else 0))]}
    if lab: target["ldv:reportedByLab"] = lab
    if unit_note: target["ldv:modelUnitNote"] = unit_note
    binding_t = {"ldv:associationLevel": "component", "ldv:registration": "not established", "ldv:ifcFile": ifc_node, "ldv:target": target,
                 "ldv:registrationHypothesis": {"@id": "ex:registration-hypothesis/" + HYP["kind"], "@type": "ldv:RegistrationHypothesis", "ldv:source": HYP["source"], "ldv:mapping": HYP["mapping"],
                                                "ldv:referenceFace": HYP["referenceFace"], "ldv:origin": HYP["origin"], "ldv:zAxis": HYP["zAxis"], "ldv:status": HYP["status"]},
                 "ldv:fingerprintMethod": V.METHOD, "ldv:bindingStatus": "valid", "ldv:verifiedAt": {"@value": now(), "@type": "xsd:dateTime"}}
    # ---------------- data files
    files = sorted(glob.glob(P(ddir, dglob))); data = {}; excluded = {}
    if not files: die("no data files match %s" % P(ddir, dglob))
    for f in files:
        try: idx, x, y, z, a, n0 = read_txt(f)
        except ValueError as e: excluded[rel(f)] = str(e); continue
        if idx in data: excluded[rel(f)] = "point index %d already read from %s" % (idx, rel(data[idx]["path"])); continue
        data[idx] = {"path": f, "x": x, "y": y, "z": z, "a": a, "n0": n0, "sha": V.sha256(f), "size": os.path.getsize(f)}
    if not data: die("none of the %d files could be read: %s" % (len(files), excluded))
    ref = next(iter(data.values()))["a"][:, 0]; axis = lambda f_: (float(f_[0]), float(f_[-1]), float(np.round(np.median(np.diff(f_)), 9)), int(len(f_)))
    ax0 = axis(ref)
    for idx in list(data):
        d = data[idx]; f_ = d["a"][:, 0]
        if axis(f_) != ax0 or not np.allclose(np.diff(f_), ax0[2]): excluded[rel(d["path"])] = "frequency axis %s differs from the first file's %s (the view needs one common axis)" % (axis(f_), ax0); del data[idx]
    if excluded:
        print("EXCLUDED %d file(s):" % len(excluded)); [print("   %s: %s" % kv) for kv in excluded.items()]
        if strict: die("--strict: excluded files present")
    order = sorted(data)
    # ---------------- records
    md = P(out_md, "points"); os.makedirs(md, exist_ok=True)
    for old in glob.glob(os.path.join(md, "point_*.jsonld")): os.remove(old)                      # a removed TXT must not leave a record behind
    os.makedirs(P(out_view), exist_ok=True)
    rec_hash, obs, fls, recs, pts, SP = {}, [], [], [], [], {}
    for idx in order:
        d = data[idx]; tag = "point-%04d" % idx; rec = sub(copy.deepcopy(tmpl), tag); rec["@context"] = ctx_base
        t1 = rec["ldv:tier1Integrity"]; t1["dcterms:title"] = os.path.basename(d["path"]); t1["dcat:downloadURL"] = {"@id": rel(d["path"])}
        t1["spdx:checksum"]["spdx:checksumValue"] = d["sha"]; t1["dcat:byteSize"]["@value"] = d["size"]
        dia = t1.get("csvw:dialect", {}); hdr = int(dia.get("csvw:headerRowCount", 2)); dia["csvw:skipRows"] = d["n0"] - hdr
        t2 = rec["ldv:tier2Measurement"]; pt = t2["ldv:point"]; pt["ldv:index"] = idx; pt["ldv:x"], pt["ldv:y"], pt["ldv:z"] = d["x"], d["y"], d["z"]
        fa = t2["ldv:frequencyAxis"]; fa["ldv:min"], fa["ldv:max"], fa["ldv:step"], fa["ldv:binCount"] = ax0
        b = rec["ldv:tier4Binding"]; b.update(copy.deepcopy(binding_t)); b["@id"] = "ex:binding/CLT10-4-3_" + tag if "{point}" not in b0.get("@id", "") and "CLT" in b0.get("@id", "") else b0.get("@id", "ex:binding/" + tag).replace("{point}", tag)
        b["@type"] = "ls:DirectedLink"; b["ldv:measurementRecord"] = {"@id": b0["ldv:measurementRecord"]["@id"].replace("{point}", tag)}
        cp = rec["ldv:completeness"]; cp["ldv:absent"] = [x for x in cp["ldv:absent"] if x != "ifcElementFingerprint"]
        out = "%s/points/point_%04d.jsonld" % (out_md, idx); json.dump(SC.to_v06(rec), open(P(out), "w", encoding="utf-8"), indent=2, ensure_ascii=False)       # profile v0.6
        rec_hash[out] = V.sha256(P(out)); recs.append({"@id": out}); obs.append({"@id": t2["@id"]}); fls.append({"@id": t1["@id"]})
        SP[idx] = levels(d["a"]); col = {"X": 1, "Y": 2, "Z": 3}.get(COMP, 3); i0 = int(np.argmin(abs(d["a"][:, 0] - FREQ)))
        pts.append({"index": idx, "scan": [d["x"], d["y"], d["z"]], "file": rel(d["path"]), "level_db": float(SP[idx][COMP][i0] if COMP in SP[idx] else SP[idx]["NORM"][i0]), "observation": t2["@id"]})
    index = {"@context": ctx_base, "@id": "ex:scan/" + re.sub(r"\W+", "", cfg.get("name", "scan")), "@type": ["dcat:Dataset", "sosa:ObservationCollection"], "dcterms:title": cfg.get("name", "scan") + ": points supplied",
             "dcterms:description": "Index of the %d point records built from %s. Treating these files as one dataset is an assumption to confirm." % (len(recs), ddir),
             "sosa:hasMember": obs, "dcterms:hasPart": fls, "rdfs:seeAlso": recs}
    json.dump(index, open(P(out_md, "scan_index.jsonld"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    # ---------------- spectra cache + view config
    f_ = data[order[0]]["a"][:, 0]; chans = ("X", "Y", "Z", "NORM")
    spectra = {"reference": "dB re 1 m/s/N (H1 velocity per force, as exported)", "freq0": float(f_[0]), "step": ax0[2], "count": ax0[3], "channels": list(chans), "points": order,
               "db": {c: [np.round(SP[i][c], 2).tolist() for i in order] for c in chans}}
    sp_path = P(out_view, "spectra.json"); json.dump(spectra, open(sp_path, "w"), separators=(",", ":"))
    pts.sort(key=lambda p: p["index"]); Sx = np.array([p["scan"] for p in pts]); X = (M @ np.c_[Sx, np.ones(len(Sx))].T).T[:, :3]
    ins = (X[:, 0] >= lo[0] - 1e-9) & (X[:, 0] <= hi[0] + 1e-9) & (X[:, 2] >= lo[2] - 1e-9) & (X[:, 2] <= hi[2] + 1e-9)
    ycol = lambda nm: next((c for k, c in sorted(COL.items(), key=lambda kv: -len(kv[0])) if k.lower() in nm.lower()), [0.8, 0.8, 0.8])   # longest keyword wins
    qd = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 2, 6, 4), (1, 5, 7, 3), (0, 4, 5, 1), (2, 3, 7, 6)]; fcs = [[a, b, c] for a, b, c, d in qd] + [[a, c, d] for a, b, c, d in qd]
    def box(x0, x1, y0, y1, z0, z1): return [[x, y, z] for y in (y0, y1) for z in (z0, z1) for x in (x0, x1)]
    layers = []
    if stack:
        for k, st in enumerate(stack):
            y0, y1 = lo[1] + st["ldv:offsetM"], lo[1] + st["ldv:offsetM"] + st["ldv:thicknessM"]
            layers.append({"name": st["rdfs:label"], "guid": tgt.GlobalId, "layer_index": k, "ifc_class": tgt.is_a(), "material": st["rdfs:label"], "y_min": round(float(y0), 4), "y_max": round(float(y1), 4), "fingerprint_ok": True,
                           "color": ycol(st["rdfs:label"]), "verts": box(lo[0], hi[0], y0, y1, lo[2], hi[2]), "faces": fcs, "derived": "slab from the IfcMaterialLayerSet; the IFC has no separate element for this layer"})
    else:
        for p_ in sorted(parts or [tgt], key=lambda p: info[p.GlobalId]["lo"][1] if p.GlobalId in info else 0):
            i = info.get(p_.GlobalId)
            if i is None: continue
            layers.append({"name": nice(p_), "guid": p_.GlobalId, "ifc_class": p_.is_a(), "material": i["material"] or p_.Name, "y_min": round(float(i["lo"][1]), 4), "y_max": round(float(i["hi"][1]), 4), "fingerprint_ok": True,
                           "color": ycol((p_.Name or "") + " " + str(i["material"])), "verts": box(*(float(i["lo"][0]), float(i["hi"][0]), float(i["lo"][1]), float(i["hi"][1]), float(i["lo"][2]), float(i["hi"][2]))), "faces": fcs})
    face_name = HYP["referenceFace"] if HYP["referenceFace"] != "?" else cfg["frame"].get("face_name", "face")
    vcfg = {"hypothesis": {"hyp": HYP["kind"], "origin": HYP["origin"], "face_y": float(face_y), "face_name": face_name, "normal_sign": nsign, "UNCONFIRMED": True,
                           "note": "Frame source: %s. %s. NOT confirmed by the lab; which face was scanned is also unconfirmed. Used only to draw the scene." % (HYP["source"], HYP["status"])},
            "package_root": "..", "wall": {"min": lo.tolist(), "max": hi.tolist(), "length": L, "thickness": T, "height": H}, "layers": layers,
            "provenance": {"point_records": len(pts), "ifc_file": IFC_REL, "ifc_hash_matches_record": True, "all_layer_fingerprints_ok": True, "binding_status_in_records": ["valid"], "association_level": ["component"],
                           "registration": ["not established"], "layers_are_derived": bool(stack), "built_at": now()},
            "transform_scan_to_ifc": M.tolist(), "determinant": det,
            "markers": {"scan_origin": (M @ [0, 0, 0, 1])[:3].tolist(), "scanned_centroid": X.mean(0).tolist(), "wall_face_centre": [(lo[0] + hi[0]) / 2, float(face_y), (lo[2] + hi[2]) / 2]},
            "colour": {"label": "level of the %s component at %g Hz (dB re 1 m/s/N)" % (COMP, FREQ), "min": min(p["level_db"] for p in pts), "max": max(p["level_db"] for p in pts)},
            "spectra": "spectra.json", "slider": {"default_hz": FREQ, "default_channel": COMP}, "spot_radius_m": 0.015, "spot_radius_note": "exaggerated for display; the real laser spot is about 1 mm",
            "points": [dict(p, ifc=x.tolist(), display=[float(x[0]), float(face_y) - 0.001 * nsign, float(x[2])], inside_face=bool(k)) for p, x, k in zip(pts, X, ins)]}
    if unit_note: vcfg["provenance"]["model_unit_note"] = unit_note
    vpath = P(out_view, "view_config_%s.json" % vname); json.dump(vcfg, open(vpath, "w"), separators=(",", ":"))
    # ---------------- manifest
    man = {"manifestVersion": 1, "builtAt": now(), "builder": "ldv_toolkit/tools/build.py", "project": {"file": "project.json", "sha256": V.sha256(P("project.json")) if os.path.isfile(P("project.json")) else None, "data_dir": ddir, "data_glob": dglob},
           "inputs": {"ifc": {"path": IFC_REL, "sha256": V.sha256(IFC), "target": kind, "elements": {g: i["fingerprint"] for g, i in info.items()}},
                      "template": {"path": cfg["template"], "sha256": V.sha256(P(cfg["template"]))}},
           "data": {rel(data[i]["path"]): {"sha256": data[i]["sha"], "point": i, "bytes": data[i]["size"]} for i in order}, "excluded": excluded,
           "records": rec_hash,
           "derived": {rel(vpath): {"sha256": V.sha256(vpath)}, rel(sp_path): {"sha256": V.sha256(sp_path), "point_sha256": {str(i): data[i]["sha"] for i in order}}},
           "frame": {"source": HYP["source"], "status": HYP["status"]}}
    json.dump(man, open(P(V.MANIFEST), "w", encoding="utf-8"), indent=2)
    print("built %d records, spectra (%d bins, %g-%g Hz), view config '%s'; %d of %d points inside the face; manifest %s" % (len(order), ax0[3], ax0[0], ax0[1], rel(vpath), int(ins.sum()), len(pts), V.MANIFEST))
    if "--validate" in argv:
        try:
            import validate as VAL
            bad = 0
            for r in recs:
                shp = next((x for x in (P(out_md, "shapes_v0.6.ttl"), os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "metadata", "shapes_v0.6.ttl")) if os.path.isfile(x)), None)
                if shp is None: print("SHACL skipped: shapes_v0.6.ttl not found"); break
                ok, rows = VAL.run(P(r["@id"]), shp, quiet=True); bad += sum(1 for s in rows if s[0] == "Violation")
            print("SHACL: %d Violation results over %d records (open items such as licence / persistent identifier are expected)" % (bad, len(recs)))
        except ImportError as e: print("SHACL skipped:", e)
    return man

if __name__ == "__main__":
    main(sys.argv[1:])
