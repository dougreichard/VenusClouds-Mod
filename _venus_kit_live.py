"""Push a kitbashed hull into a RUNNING Blender so it can be looked at and orbited.

    python _venus_kit_live.py <recipe>              # show what is already built
    python _venus_kit_live.py <recipe> --build      # rebuild it first, then show
    python _venus_kit_live.py <recipe> --watch      # rebuild + refresh on every recipe edit

The headless bake stays the authority on what ships - this only puts the result in front
of a pair of eyes. That was the missing half of the pipeline: it could BUILD hulls but
nobody could SEE them, which is how a palette got picked three times by averaging instead
of by looking (see the notes on _venus_kit_palette.py).

Talks to Blender Lab's MCP add-on over its TCP socket (127.0.0.1:9876). The add-on drives
its work queue off `bpy.app.timers`, which only fire in a real GUI event loop - so Blender
must be OPEN. Headless is not an option here; use _venus_kit_preview.py for that.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import venus_kit_recipes as KIT     # noqa: E402

HOST, PORT = "127.0.0.1", 9876
SHIPS = os.path.join(HERE, "media", "ships")
BAKE = os.path.join(HERE, "_venus_kit_bake.py")
RECIPES = os.path.join(HERE, "venus_kit_recipes.py")


def blender_exec(code, timeout=120):
    """Run `code` inside the running Blender and return its result dict.

    The add-on speaks JSON with NO length prefix - sending one makes it answer with a
    JSONDecodeError against its own parser. Messages are NUL-TERMINATED in both
    directions: its receive loop is `while b"\\0" not in buf`, so an un-terminated request
    just blocks until the 10s client timeout and comes back "Client timed out".
    """
    request = json.dumps({"type": "execute", "code": code, "strict_json": False}) + "\0"
    try:
        sock = socket.create_connection((HOST, PORT), timeout=10)
    except OSError as e:
        raise SystemExit(
            "No Blender listening on %s:%d (%s).\n"
            "Open Blender, then enable the MCP add-on's server "
            "(Edit > Preferences > Add-ons > MCP, or it auto-starts if configured)."
            % (HOST, PORT, e))
    try:
        sock.sendall(request.encode("utf-8"))
        sock.settimeout(timeout)
        buf = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
            text = buf.decode("utf-8", "replace").rstrip("\x00")
            try:
                return json.loads(text)
            except ValueError:
                continue        # partial message - keep reading
    finally:
        sock.close()
    raise SystemExit("Blender closed the connection before answering.")


def _load_code(mesh, diffuse):
    """Blender-side code: wipe the scene, import the hull, light it, frame it."""
    return '''
import bpy, math
from mathutils import Vector

MESH = r"%s"
DIFF = r"%s"

# read_factory_settings is blocked by the add-on sandbox (it would nuke user prefs);
# read_homefile with factory startup is the sanctioned equivalent.
bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)

# obj_import polls for a 3D-view context, which the add-on's timer callback does not
# have - so borrow one from the open window or the import fails "context is incorrect".
win = bpy.context.window_manager.windows[0]
area = next((a for a in win.screen.areas if a.type == "VIEW_3D"), None)
region = next((r for r in area.regions if r.type == "WINDOW"), None) if area else None
if area and region:
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
        bpy.ops.wm.obj_import(filepath=MESH)
else:
    with bpy.context.temp_override(window=win, screen=win.screen):
        bpy.ops.wm.obj_import(filepath=MESH)

objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]

mat = bpy.data.materials.new("atlas")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = bpy.data.images.load(DIFF)
tex.interpolation = "Closest"          # Synty atlases are flat colour blocks; no blur
mat.node_tree.links.new(bsdf.inputs["Base Color"], tex.outputs["Color"])
bsdf.inputs["Roughness"].default_value = 0.85
for o in objs:
    o.data.materials.clear()
    o.data.materials.append(mat)

mins = Vector((1e9,) * 3)
maxs = Vector((-1e9,) * 3)
for o in objs:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        for i in range(3):
            mins[i] = min(mins[i], w[i])
            maxs[i] = max(maxs[i], w[i])
center = (mins + maxs) / 2.0
size = maxs - mins
radius = max(size.length / 2.0, 0.001)

# Three-quarter view - the angle that shows a hull's length and its height at once.
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
d = radius * 2.9
cam.location = center + Vector((d * 0.72, -d * 0.80, d * 0.42))
cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()

key = bpy.data.objects.new("key", bpy.data.lights.new("key", type="SUN"))
key.data.energy = 4.0
key.rotation_euler = (math.radians(52), 0, math.radians(35))
bpy.context.scene.collection.objects.link(key)

world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.30, 0.28, 0.26, 1)
bpy.context.scene.world = world

# Pick the engine by ASSIGNING. Blender 5.2 lists only BLENDER_EEVEE in the `engine` enum
# even though CYCLES and WORKBENCH both assign fine, so a membership test silently demotes
# this to grey Workbench clay. EEVEE Next is BLENDER_EEVEE_NEXT on 4.x and plain
# BLENDER_EEVEE on 5.x - same engine, two names.
for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
    try:
        bpy.context.scene.render.engine = engine
        break
    except Exception:
        continue

# Solid+textured shading in the viewport, so the atlas is visible without a render.
for a in win.screen.areas:
    if a.type == "VIEW_3D":
        for space in a.spaces:
            if space.type == "VIEW_3D":
                space.shading.type = "MATERIAL"

result = {
    "objects": len(objs),
    "faces": sum(len(o.data.polygons) for o in objs),
    "bbox": [round(v, 2) for v in size],
    "engine": bpy.context.scene.render.engine,
}
''' % (mesh, diffuse)


def show(name, build=False, tex=1024):
    recipe = KIT.RECIPES.get(name)
    if recipe is None:
        raise SystemExit("no such recipe: %s (have %d)" % (name, len(KIT.RECIPES)))
    art = recipe.get("art", name)

    if build:
        cmd = [sys.executable, BAKE, name, "--out", SHIPS, "--tex", str(tex)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        for line in (proc.stdout or "").splitlines():
            print("  " + line)
        if proc.returncode != 0:
            print((proc.stderr or "")[-800:])
            return False

    mesh = os.path.join(SHIPS, art + ".obj")
    diffuse = os.path.join(SHIPS, art + "_diffuse.png")
    if not os.path.exists(mesh):
        raise SystemExit("not built yet: %s (run with --build)" % mesh)

    reply = blender_exec(_load_code(mesh.replace("\\", "/"), diffuse.replace("\\", "/")))
    if reply.get("status") != "ok":
        print("Blender refused the load:")
        print(reply.get("message") or json.dumps(reply)[:800])
        return False
    r = reply.get("result") or {}
    print("  live: %s  %s objects, %s faces, bbox %s, %s"
          % (art, r.get("objects"), r.get("faces"), r.get("bbox"), r.get("engine")))
    return True


def main():
    ap = argparse.ArgumentParser(description="Show a kitbashed hull in the running Blender.")
    ap.add_argument("name", help="recipe name")
    ap.add_argument("--build", action="store_true", help="rebuild the hull before showing it")
    ap.add_argument("--tex", type=int, default=1024, help="baked map size when building")
    ap.add_argument("--watch", action="store_true",
                    help="rebuild and refresh every time venus_kit_recipes.py changes")
    a = ap.parse_args()

    if not a.watch:
        return 0 if show(a.name, build=a.build, tex=a.tex) else 1

    # The iterate loop: edit a recipe, save, and the live scene catches up on its own.
    print("watching %s - Ctrl+C to stop" % os.path.basename(RECIPES))
    show(a.name, build=True, tex=a.tex)
    stamp = os.path.getmtime(RECIPES)
    try:
        while True:
            time.sleep(1.0)
            now = os.path.getmtime(RECIPES)
            if now != stamp:
                stamp = now
                print("recipes changed - rebuilding %s" % a.name)
                show(a.name, build=True, tex=a.tex)
    except KeyboardInterrupt:
        print("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
