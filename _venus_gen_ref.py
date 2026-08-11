import json, time, urllib.request, urllib.error

BASE = "http://127.0.0.1:8189"

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

FRAMING = (", a single isolated object, ONE object only, the complete whole object centered "
           "with a small margin of empty background around it, full object visible, not "
           "cropped, not cut off, side three-quarter view from slightly above, volumetric "
           "form with clear depth, soft even neutral studio lighting with visible form "
           "shadows, detailed physically based render, matte finish, isolated on a plain "
           "neutral grey studio backdrop, no sky, no clouds, no environment")

NEG = ("grid, tiled, tiling, pattern, repeated, repeating, multiple objects, many objects, "
       "two objects, several, collection, set, array, rows, columns, collage, montage, "
       "contact sheet, sprite sheet, thumbnails, duplicated, busy texture, clutter, text, "
       "watermark, signature, harsh shadows, dark background, cropped, cut off, blueprint, "
       "schematic, technical drawing, orthographic, side elevation, line art, annotations, "
       "callouts, dimension lines, flat lighting, sky, clouds, landscape, horizon, "
       "environment, background scenery, colored fog, colored ambient light, pink sky, "
       "magenta lighting, tinted lighting, spherical balloon, hot air balloon, round balloon, "
       "submarine, torpedo, rocket, single fused hull, one solid body, display stand, plinth, "
       "pedestal, museum model, mounted on a base, tripod legs, landing gear")
# DO NOT add rope/cable/rigging negatives here. Measured A/B: they do NOT help decimation
# (the stall is non-manifold edges, not rope), and they DESTROY the envelope-over-gondola
# gap - the visible rigging lines are what tell the shape model there are two separate
# bodies. Rope is scaffolding for the GENERATOR; it is sub-voxel and disappears in the
# remesh anyway, so it costs nothing in the finished asset.

SUBJECTS = {
    "kdm_vanguard": (
        "a steampunk airship with two clearly separate parts: above, a huge elongated "
        "cigar-shaped gas balloon of pale cream fabric stretched over a rib frame; hanging "
        "well below it on tall visible metal struts with open air between them, a separate "
        "ornate brass boat-hull gondola carrying gold onion domes, railed promenade decks and "
        "a large spoked paddle-wheel on its side"),
    "arm_env": (
        "a huge armored airship gas balloon on its own, an elongated hull of riveted "
        "overlapping metal plates tapering to a sharp point at the front, a long spear-like ram "
        "spike projecting forward from the nose, jagged angular fin-blades jutting from the "
        "tail, nothing hanging underneath it, the bare balloon alone"),
    "arm_gondola": (
        "an armored airship crew gondola on its own, a long narrow riveted metal car with a row "
        "of small square windows down its side, a cluster of wide funnel-shaped engine bells at "
        "its stern, heavy suspension lugs along its roof, the car alone with nothing above it"),
}

BASE_SEED = 11
N = 6

def build(name, subject, seed):
    P = {}
    P["1"] = node("CheckpointLoaderSimple", ckpt_name="sd_xl_base_1.0.safetensors")
    P["2"] = node("CLIPTextEncode", text=subject + FRAMING, clip=["1", 1])
    P["3"] = node("CLIPTextEncode", text=NEG, clip=["1", 1])
    P["4"] = node("EmptyLatentImage", width=1216, height=832, batch_size=1)
    P["5"] = node("KSampler", model=["1", 0], positive=["2", 0], negative=["3", 0],
                  latent_image=["4", 0], seed=seed, steps=20, cfg=7.0,
                  sampler_name="dpmpp_2m", scheduler="karras", denoise=1.0)
    P["6"] = node("VAEDecode", samples=["5", 0], vae=["1", 2])
    P["7"] = node("SaveImage", images=["6", 0], filename_prefix=f"VEN8_{name}_s{seed}")
    return P

queued = []
for name, subject in SUBJECTS.items():
    for i in range(N):
        seed = BASE_SEED + i
        try:
            pid = post("/prompt", {"prompt": build(name, subject, seed), "client_id": "sweep"})["prompt_id"]
            queued.append((name, seed, pid))
            print(f"queued {name} seed {seed}", flush=True)
        except urllib.error.HTTPError as e:
            print(f"VALIDATION FAILED {name} s{seed}: {e.read().decode()[:900]}", flush=True)
            raise SystemExit(1)

print(f"--- {len(queued)} queued, waiting ---", flush=True)
done = 0
t0 = time.time()
while done < len(queued) and time.time() - t0 < 1800:
    done = 0
    for name, seed, pid in queued:
        h = get("/history/" + pid)
        if pid in h:
            done += 1
    time.sleep(5)

for name, seed, pid in queued:
    h = get("/history/" + pid)
    e = h.get(pid, {})
    outs = e.get("outputs", {}).get("7", {}).get("images", [])
    st = e.get("status", {}).get("status_str")
    print(f"{name} s{seed}: {st} -> {[o['filename'] for o in outs]}", flush=True)
