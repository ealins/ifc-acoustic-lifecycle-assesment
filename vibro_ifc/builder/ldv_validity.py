"""ldv_validity.py - one place that decides whether the three layers agree.  No Blender, no network; numpy only.
(ifcopenshell is optional: without it an IFC whose file hash changed is reported 'unverified', never 'valid'.)

LAYERS
  data       the TXT exports (+ the spectra cache that the viewer draws from them)
  semantics  the sidecar records (+ the view config derived from them)
  ifc        the IFC file and the elements the sidecar is bound to

A point is VALID only when all three agree for it:
  data       TXT exists, SHA-256 equals the record's checksum, header (index, x, y, z) equals the record and the view,
             and the spectra cache was built from exactly this file
  semantics  record exists, was not edited since the build (manifest), agrees with the view config
  ifc        file hash equals the record's, OR the file changed but every bound element still has the same fingerprint

Every function only READS files.
"""
import os, re, json, glob, hashlib
import numpy as np
try: from .sidecar import view as _view          # record layout (v0.5 tiers or v0.6 standard terms) -> flat fields
except ImportError: from sidecar import view as _view

HEADER = re.compile(r"Point Index:\t(\d+)\t\[x = ([-\d.eE+]+)\ty = ([-\d.eE+]+)\tz = ([-\d.eE+]+)\]")
METHOD = ("sha256 of 'GlobalId|IFC class|material label|bbox min|bbox max' (world coordinates, metres, 3 decimals); "
          "material label = material name, or for a layer set 'set name[layer@thickness/...]'")
MANIFEST = "build_manifest.json"

# ----------------------------------------------------------------------------- hashing (cached by path, mtime, size)
_CACHE = {}
def sha256(path):
    st = os.stat(path); key = (path, st.st_mtime_ns, st.st_size)
    if key not in _CACHE:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
        _CACHE[key] = h.hexdigest()
    return _CACHE[key]

def sha256_bytes(b): return hashlib.sha256(b).hexdigest()

# ----------------------------------------------------------------------------- IFC fingerprint (the same code builds and checks)
def have_ifcopenshell():
    try:
        import ifcopenshell, ifcopenshell.geom, ifcopenshell.util.element  # noqa
        return True
    except Exception:
        return False

def fingerprint(gid, cls, mat, lo, hi):
    f = lambda a: ",".join(f"{round(float(v), 3) + 0.0:.3f}" for v in a)      # +0.0 removes negative zero
    return hashlib.sha256(f"{gid}|{cls}|{mat}|{f(lo)}|{f(hi)}".encode()).hexdigest()

def material_label(mat):
    if mat is None: return None
    if mat.is_a("IfcMaterialLayerSetUsage"): mat = mat.ForLayerSet
    if mat.is_a("IfcMaterialLayerSet"):
        return "%s[%s]" % (mat.LayerSetName, "/".join("%s@%s" % (l.Material.Name, l.LayerThickness) for l in mat.MaterialLayers))
    return getattr(mat, "Name", None)

def geom_settings():
    import ifcopenshell.geom
    s = ifcopenshell.geom.settings(); s.set(s.USE_WORLD_COORDS, True); return s

def element_info(ifc, gid, settings=None):
    """class, material label, bbox and fingerprint of one element.  Raises RuntimeError if the GlobalId does not exist."""
    import ifcopenshell.geom, ifcopenshell.util.element
    s = settings or geom_settings(); el = ifc.by_guid(gid)
    mat = ifcopenshell.util.element.get_material(el); label = material_label(mat)
    v = np.array(ifcopenshell.geom.create_shape(s, el).geometry.verts).reshape(-1, 3); lo, hi = v.min(0), v.max(0)
    return {"class": el.is_a(), "material": label, "lo": lo, "hi": hi, "fingerprint": fingerprint(gid, el.is_a(), label, lo, hi)}

_IFC_ELEMS = {}
def check_elements(ifc_path, wanted):
    """wanted: {gid: stored fingerprint}.  -> {gid: 'ok'|'CHANGED'|'MISSING'|'unchecked'}   (cached while the file is unchanged)"""
    if not have_ifcopenshell(): return {g: "unchecked" for g in wanted}
    import ifcopenshell
    st = os.stat(ifc_path); key = (ifc_path, st.st_mtime_ns, st.st_size)
    if key not in _IFC_ELEMS:
        _IFC_ELEMS.clear(); _IFC_ELEMS[key] = {"ifc": ifcopenshell.open(ifc_path), "fp": {}, "settings": geom_settings()}
    c = _IFC_ELEMS[key]; out = {}
    for gid, want in wanted.items():
        if gid not in c["fp"]:
            try: c["fp"][gid] = element_info(c["ifc"], gid, c["settings"])["fingerprint"]
            except RuntimeError: c["fp"][gid] = None          # GlobalId not in the file
            except Exception: c["fp"][gid] = "error"          # geometry could not be built
        got = c["fp"][gid]
        out[gid] = "MISSING" if got is None else ("unchecked" if got == "error" else ("ok" if got == want else "CHANGED"))
    return out

# ----------------------------------------------------------------------------- reading the records
def _v(x):
    return x.get("@value") if isinstance(x, dict) and "@value" in x else x

def _loc(node):
    d = (node or {}).get("dcat:downloadURL") or {}
    return d.get("@id") if isinstance(d, dict) else d

def _sum(node): return _v(((node or {}).get("spdx:checksum") or {}).get("spdx:checksumValue"))

def bound_elements(rec):
    """{gid: stored fingerprint} of everything the binding names: the target and/or its sub-elements"""
    t = ((_view(rec or {})).get("ldv:tier4Binding") or {}).get("ldv:target") or {}; out = {}
    for e in [t] + list(t.get("bot:hasSubElement", [])):
        if isinstance(e, dict) and "ldv:ifcGlobalId" in e and "ldv:elementFingerprint" in e:
            out[_v(e["ldv:ifcGlobalId"])] = _v(e["ldv:elementFingerprint"])
    return out

def read_header(path):
    try:
        with open(path, "rb") as f: head = f.read(2048).decode("latin-1")
    except OSError: return None
    m = HEADER.search(head)
    return None if not m else (int(m[1]), float(m[2]), float(m[3]), float(m[4]))

def load_manifest(root):
    p = os.path.join(root, MANIFEST) if root else None
    if p and os.path.isfile(p):
        try: return json.load(open(p, encoding="utf-8"))
        except ValueError: return {"_broken": True}
    return None

# ----------------------------------------------------------------------------- the assessment
def assess(root, records, rec_paths, view_pts, view_path=None, spectra_path=None, use_ifc_elements=True):
    """root       package folder (contains data/)
       records    {point index: JSON-LD record}      rec_paths {point index: file the record was read from}
       view_pts   list of {'index', 'scan': [x,y,z], 'file'} from the view config
       -> dict with per-layer verdicts, per-point verdicts and a list of human-readable problems"""
    man = load_manifest(root); rel = lambda p: os.path.relpath(p, root).replace("\\", "/")
    problems = {"data": [], "semantics": [], "ifc": []}; notes = []
    pts = {}
    if root is None or not os.path.isdir(root):
        return {"overall": "INVALID", "headline": "no package folder found (the folder that contains data/)", "layers": {k: {"state": "unverified", "valid": 0, "total": 0} for k in problems},
                "points": {}, "problems": {"data": ["package folder not found"], "semantics": [], "ifc": []}, "notes": [], "binding": {}, "manifest": False, "untracked": [], "view_points_unrecorded": []}
    if man is None: notes.append("no %s: edits of the sidecar, view config or spectra cannot be detected" % MANIFEST)
    elif man.get("_broken"): notes.append("%s is not valid JSON" % MANIFEST); man = None
    mrec = (man or {}).get("records", {}); mder = (man or {}).get("derived", {}); mdata = (man or {}).get("data", {})
    # --- view config + spectra cache against the manifest
    view_ok = spectra_ok = None
    if man and view_path and os.path.isfile(view_path) and rel(view_path) in mder:
        view_ok = sha256(view_path) == mder[rel(view_path)]["sha256"]
        if not view_ok: problems["semantics"].append("view config was edited after the build (%s)" % rel(view_path))
    if man and spectra_path and os.path.isfile(spectra_path) and rel(spectra_path) in mder:
        spectra_ok = sha256(spectra_path) == mder[rel(spectra_path)]["sha256"]
        if not spectra_ok: problems["data"].append("spectra cache was edited after the build (%s)" % rel(spectra_path))
    cache_from = {}                                      # point index -> sha256 of the TXT the spectra were computed from
    if man and spectra_path and rel(spectra_path) in mder: cache_from = {int(k): v for k, v in mder[rel(spectra_path)].get("point_sha256", {}).items()}
    # --- IFC: once per distinct IFC file named by the records
    ifc_state = {}                                       # path -> dict
    def ifc_for(rec):
        b = _view(rec or {}).get("ldv:tier4Binding") or {}; node = b.get("ldv:ifcFile") or {}; loc = _loc(node)
        if loc is None: return {"file": "no locator", "elements": {}, "verdict": "unverified", "why": "record names no IFC file"}
        path = os.path.join(root, loc)
        if path in ifc_state and ifc_state[path]["_want"] == bound_elements(rec): return ifc_state[path]
        r = {"path": path, "_want": bound_elements(rec)}
        if not os.path.isfile(path):
            r.update(file="missing", elements={g: "MISSING" for g in r["_want"]}, verdict="stale", why="IFC file not found: %s" % loc)
        elif sha256(path) == _sum(node):
            r.update(file="ok", elements={g: "ok" for g in r["_want"]}, verdict="valid", why="")
        else:
            r["file"] = "CHANGED"
            if not (use_ifc_elements and r["_want"]):
                r.update(elements={g: "unchecked" for g in r["_want"]}, verdict="unverified", why="IFC file changed and no element fingerprints to compare")
            else:
                el = check_elements(path, r["_want"]); r["elements"] = el
                if any(s in ("CHANGED", "MISSING") for s in el.values()):
                    bad = [g for g, s in el.items() if s in ("CHANGED", "MISSING")]
                    r.update(verdict="stale", why="IFC element(s) %s: %s" % ("changed or missing", ", ".join(bad[:4]) + (" ..." if len(bad) > 4 else "")))
                elif any(s == "unchecked" for s in el.values()):
                    r.update(verdict="unverified", why="IFC file changed; element fingerprints could not be recomputed (ifcopenshell not available, e.g. enable Bonsai)")
                else:
                    r.update(verdict="valid", why="", note="IFC file changed, but every bound element has the same fingerprint")
        ifc_state[path] = r; return r
    # --- per point
    for p in view_pts:
        i = int(p["index"]); rec = records.get(i); why = {"data": [], "semantics": [], "ifc": []}; st = {"data": "valid", "semantics": "valid", "ifc": "valid"}
        # data
        t1 = _view(rec or {}).get("ldv:tier1Integrity") or {}; loc = _loc(t1) or p.get("file"); txt = os.path.join(root, loc) if loc else None
        file_state = "no locator"
        if txt is None: st["data"] = "stale"; why["data"].append("no data file named")
        elif not os.path.isfile(txt): st["data"] = "missing"; file_state = "missing"; why["data"].append("TXT file missing: %s" % loc)
        else:
            h = sha256(txt); file_state = "ok"
            if rec is not None and h != _sum(t1): st["data"] = "stale"; file_state = "CHANGED"; why["data"].append("TXT changed since the sidecar was written (hash differs)")
            hd = read_header(txt)
            if hd is None: st["data"] = "stale"; why["data"].append("TXT header not readable (no 'Point Index' line)")
            elif hd[0] != i or any(abs(a - b) > 1e-9 for a, b in zip(hd[1:], p["scan"])):
                st["data"] = "stale"; file_state = "CHANGED" if file_state == "ok" else file_state; why["data"].append("TXT header (index/x/y/z) differs from the view config")
            if i in cache_from and cache_from[i] != h and st["data"] == "valid":
                st["data"] = "stale"; why["data"].append("spectra cache was built from a different TXT; rebuild to refresh the view")
            if mdata and loc in mdata and mdata[loc]["sha256"] != h and st["data"] == "valid":
                st["data"] = "stale"; why["data"].append("TXT differs from the file registered at the last build")
        # semantics
        if rec is None: st["semantics"] = "missing"; why["semantics"].append("no sidecar record for this point")
        else:
            rp = rec_paths.get(i)
            if man and rp and os.path.isfile(rp) and rel(rp) in mrec and sha256(rp) != mrec[rel(rp)]:
                st["semantics"] = "stale"; why["semantics"].append("record edited after the build (%s)" % rel(rp))
            pt = (_view(rec).get("ldv:tier2Measurement") or {}).get("ldv:point") or {}
            try:
                if any((k not in pt) or abs(float(_v(pt[k])) - float(c)) > 1e-9 for k, c in (("ldv:x", p["scan"][0]), ("ldv:y", p["scan"][1]), ("ldv:z", p["scan"][2]))):
                    st["semantics"] = "stale"; why["semantics"].append("record x/y/z differ from the view config")
            except (KeyError, TypeError, ValueError): st["semantics"] = "stale"; why["semantics"].append("record has no usable x/y/z")
            if view_ok is False: st["semantics"] = "stale"; why["semantics"].append("view config edited after the build")
            if spectra_ok is False and st["data"] == "valid": st["data"] = "stale"; why["data"].append("spectra cache edited after the build")
        # ifc
        r = ifc_for(rec) if rec is not None else {"file": "no record", "elements": {}, "verdict": "unverified", "why": "no record, so no binding"}
        if rec is None: st["ifc"] = "unverified"          # nothing to bind: the missing record is already reported under semantics
        elif r["verdict"] != "valid": st["ifc"] = "stale" if r["verdict"] == "stale" else "unverified"; why["ifc"].append(r["why"])
        pts[i] = {"data": st["data"], "semantics": st["semantics"], "ifc": st["ifc"], "valid": all(v == "valid" for v in st.values()),
                  "checks": {"data file": file_state if file_state != "no locator" else "no locator", "IFC file": r["file"]}, "elements": r["elements"], "why": why}
        for k in problems:
            for w in why[k]:
                line = "point %d: %s" % (i, w)
                if line not in problems[k]: problems[k].append(line)
    # --- records without a view point, TXT files nobody knows about
    in_view = {int(p["index"]) for p in view_pts}; unrec = sorted(set(records) - in_view)
    if unrec: problems["semantics"].append("records not in the view config (rebuild the view): %s" % unrec[:12])
    known = {os.path.normpath(os.path.join(root, _loc((_view(r).get("ldv:tier1Integrity") or {})) or "")) for r in records.values()} | {os.path.normpath(os.path.join(root, p.get("file", ""))) for p in view_pts}
    pat = ((man or {}).get("project") or {}).get("data_glob", "*.txt"); ddir = ((man or {}).get("project") or {}).get("data_dir", "data")
    untracked = sorted(os.path.basename(f) for f in glob.glob(os.path.join(root, ddir, pat)) if os.path.normpath(f) not in known)
    if untracked: problems["data"].append("TXT files present but not in the sidecar (new measurements; rebuild): %s" % ", ".join(untracked[:6]) + (" ..." if len(untracked) > 6 else ""))
    # --- layer verdicts
    n = len(pts); layers = {}
    for k in ("data", "semantics", "ifc"):
        ok = sum(1 for v in pts.values() if v[k] == "valid")
        bad = [v[k] for v in pts.values() if v[k] not in ("valid", "unverified")]
        state = "valid" if (n and ok == n and not problems[k]) else ("stale" if (bad or problems[k]) else "unverified")
        layers[k] = {"valid": ok, "total": n, "state": state}
    # a layer-level problem that is not tied to one point (extra files, edited view) also makes the layer not fully valid
    nvalid = sum(1 for v in pts.values() if v["valid"])
    if n == 0: overall = "INVALID"
    elif nvalid == n and all(layers[k]["state"] == "valid" for k in layers): overall = "VALID"
    elif nvalid == 0: overall = "INVALID"
    else: overall = "PARTIAL"
    bind = {}
    for path, r in ifc_state.items(): bind[os.path.basename(path)] = {"file": r["file"], "verdict": r["verdict"], "elements": r["elements"], "why": r.get("why", ""), "note": r.get("note", "")}
    if overall == "VALID": head = "all %d points valid: data, sidecar and IFC agree" % n
    else:
        bits = ["%s %s" % (k, layers[k]["state"]) for k in layers if layers[k]["state"] != "valid"]
        head = "%s: %d of %d points valid  (%s)" % (overall, nvalid, n, "; ".join(bits) or "see problems")
    return {"overall": overall, "headline": head, "layers": layers, "points": pts, "problems": problems, "notes": notes, "binding": bind, "manifest": man is not None,
            "untracked": untracked, "view_points_unrecorded": unrec}

# ----------------------------------------------------------------------------- file watching
def watch_files(root, rec_paths, view_path, spectra_path, ifc_paths=()):
    """every file the verdict depends on (so a viewer can poll their mtimes cheaply)"""
    fs = set(rec_paths.values()) | {view_path, spectra_path} | set(ifc_paths)
    if root:
        fs.add(os.path.join(root, MANIFEST))
        for sub in ("data",):
            d = os.path.join(root, sub)
            if os.path.isdir(d): fs |= {os.path.join(d, f) for f in os.listdir(d)}
    return sorted(f for f in fs if f)

def signature(files):
    out = []
    for f in files:
        try: s = os.stat(f); out.append((f, s.st_mtime_ns, s.st_size))
        except OSError: out.append((f, 0, -1))
    return tuple(out)
