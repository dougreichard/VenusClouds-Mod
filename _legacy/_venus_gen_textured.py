"""Full chain: image -> shape -> decimate to the fleet's poly budget -> texture -> export.
Mirrors example_workflows/MeshWithTexturing.json.
Usage: finish.py <input_image_basename> [<more> ...]"""
import json, sys, time, urllib.request, urllib.error

BASE = "http://127.0.0.1:8189"
# Trellis2SimplifyMesh (Cumesh) DESTROYS this geometry at low targets - the thin struts and
# rigging that make it read as an airship collapse into slivers. Keep the in-chain simplify
# mild, texture at that density, and do the real decimation in Blender afterwards
# (COLLAPSE, two passes) where the form survives.
TARGET_FACES = 200000
TEXTURE_SIZE = 2048      # matches VEN_*_diffuse.png

def post(p, d):
    r = urllib.request.Request(BASE+p, data=json.dumps(d).encode(),
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=180).read())

def get(p):
    return json.loads(urllib.request.urlopen(BASE+p, timeout=180).read())

OI = get("/object_info")

def defaults(cls):
    o = {}
    for n, s in OI[cls]["input"].get("required", {}).items():
        t = s[0]
        m = s[1] if len(s) > 1 and isinstance(s[1], dict) else {}
        if isinstance(t, list):
            o[n] = m.get("default", t[0] if t else None)
        elif t in ("INT", "FLOAT", "STRING", "BOOLEAN"):
            o[n] = m.get("default", 0 if t in ("INT", "FLOAT") else ("" if t == "STRING" else False))
    return o

def node(cls, **w):
    i = defaults(cls); i.update(w)
    return {"class_type": cls, "inputs": i}

def build(img, prefix):
    P = {}
    P["1"]  = node("Trellis2LoadModel", modelname="microsoft/TRELLIS.2-4B", backend="sdpa",
                   device="cuda", low_vram=True, keep_models_loaded=True,
                   conv_backend="flex_gemm", sparse_backend="xformers", use_reconviagen=False)
    P["2"]  = node("Trellis2LoadImageWithTransparency", image=img)
    P["3"]  = node("Trellis2PreProcessImage", image=["2",0], remove_background=True, max_size=1024)
    P["4"]  = node("Trellis2ImageCondGenerator", pipeline=["1",0], image=["3",0])
    P["5"]  = node("Trellis2SparseGenerator", pipeline=["4",2], image_cond=["4",0])
    P["6"]  = node("Trellis2ShapeGenerator", pipeline=["5",2], image_cond=["4",0],
                   coords=["5",0], resolution=512)
    P["6b"] = node("Trellis2ShapeCascadeGenerator", pipeline=["6",2], image_cond=["4",0],
                   shape_slat=["6",0], from_resolution=["6",1],
                   sparse_structure_resolution=["5",1], to_resolution=1024)
    P["7"]  = node("Trellis2DecodeLatents", pipeline=["6b",2], shape_slat=["6b",0],
                   resolution=["6b",1])
    # MINIMAL texture chain: exactly the shape chain that is known to work, plus texturing.
    # FillHolesWithCuMesh / SimplifyMesh / FillHolesNicelyWithMeshlib are all omitted - one of
    # them shreds the thin struts and rigging into slivers.
    P["9"]  = node("Trellis2ReconstructMeshWithQuad", mesh=["7",0])
    P["13"] = node("Trellis2MeshWithVoxelToTrimesh", mesh=["9",0])
    P["14"] = node("Trellis2MeshTexturing", pipeline=["7",2], image=["3",0], trimesh=["13",0],
                   texture_size=TEXTURE_SIZE, resolution=1024)
    P["15"] = node("Trellis2ExportMesh", trimesh=["14",0], filename_prefix=prefix,
                   file_format="glb")
    return P

for arg in sys.argv[1:]:
    prefix = "VenusTexMin_" + arg.replace("pick_", "").replace("part_", "")
    t0 = time.time()
    try:
        pid = post("/prompt", {"prompt": build(arg + ".png", prefix), "client_id": "finish"})["prompt_id"]
    except urllib.error.HTTPError as e:
        print(f"[{arg}] VALIDATION FAILED: {e.read().decode()[:1200]}", flush=True); continue
    print(f"[{arg}] queued {pid}", flush=True)
    while time.time() - t0 < 3600:
        h = get("/history/" + pid)
        if pid in h:
            st = h[pid]["status"]
            errs = [m for m in st.get("messages", []) if m[0] == "execution_error"]
            if errs:
                em = errs[0][1]
                print(f"[{arg}] ERROR in {em.get('node_type')}: {em.get('exception_message','')[:400]}", flush=True)
            else:
                print(f"[{arg}] {st.get('status_str')} in {time.time()-t0:.0f}s", flush=True)
            break
        time.sleep(5)
