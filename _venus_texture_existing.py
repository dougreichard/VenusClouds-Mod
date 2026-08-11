"""Texture an ALREADY-DECIMATED mesh.

The correct order, learned the hard way:
  shape -> export dense -> decimate in Blender -> LOAD BACK -> texture
Trellis2SimplifyMesh shreds thin struts; and decimating AFTER texturing tears the mesh at
its UV seams. Decimating the bare geometry first avoids both.

Usage: texture_only.py <glb_path> <reference_image_basename> <out_prefix>
"""
import json, sys, time, urllib.request, urllib.error

BASE = "http://127.0.0.1:8189"
TEXTURE_SIZE = 2048

glb_path, img, prefix = sys.argv[1], sys.argv[2], sys.argv[3]

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

P = {}
P["1"] = node("Trellis2LoadModel", modelname="microsoft/TRELLIS.2-4B", backend="sdpa",
              device="cuda", low_vram=True, keep_models_loaded=True,
              conv_backend="flex_gemm", sparse_backend="xformers", use_reconviagen=False)
P["2"] = node("Trellis2LoadImageWithTransparency", image=img)
P["3"] = node("Trellis2PreProcessImage", image=["2",0], remove_background=True, max_size=1024)
P["4"] = node("Trellis2LoadMesh", glb_path=glb_path)
P["5"] = node("Trellis2MeshTexturing", pipeline=["1",0], image=["3",0], trimesh=["4",0],
              texture_size=TEXTURE_SIZE, resolution=1024)
P["6"] = node("Trellis2ExportMesh", trimesh=["5",0], filename_prefix=prefix, file_format="glb")

t0 = time.time()
try:
    pid = post("/prompt", {"prompt": P, "client_id": "texonly"})["prompt_id"]
except urllib.error.HTTPError as e:
    print("VALIDATION FAILED:", e.read().decode()[:1500]); raise SystemExit(1)
print("queued", pid, flush=True)
while time.time() - t0 < 3600:
    h = get("/history/" + pid)
    if pid in h:
        st = h[pid]["status"]
        errs = [m for m in st.get("messages", []) if m[0] == "execution_error"]
        if errs:
            em = errs[0][1]
            print(f"ERROR in {em.get('node_type')}: {em.get('exception_message','')[:400]}")
        else:
            print(f"{st.get('status_str')} in {time.time()-t0:.0f}s")
        break
    time.sleep(5)
