"""Cut single-ship reference images out of the concept schematic sheets.

WHY THIS BEATS A TEXT PROMPT. The shape stage (`gen_prop_mesh_cuda.py --image`) will take
ANY image, so a crop of the real concept art goes straight into Hunyuan and skips SDXL
entirely. The first pass proved the cost of not doing this: three subjects came back in
three unrelated palettes, and the citadel lost its brass completely, because nothing tied
the generated references to the actual art.

WHY THE SIDE VIEW. Hunyuan reproduces SILHOUETTE, and for a ship the side view is the one
that carries it - length, envelope-over-gondola stacking, fin placement. A 3/4 "prop" view
is what the pipeline generates by default and it is why the first Valiant came out squat.

ONE view, not several: the installed Hunyuan3D-2.1 has multi-view for PAINT only
(`hy3dpaint/utils/multiview_utils.py`); the shape pipeline takes a single `--image`.

Crops are declared as fractions of the sheet, not pixels, so they survive a re-render of
the concept art at another size. `--grid` writes a coordinate overlay to read new ones off.
"""
import argparse
import os

from PIL import Image, ImageDraw

ART = r"E:/a/venus_clouds"

SHEETS = {
    "kingdom_naval": "Gemini_Generated_Image_5adcyc5adcyc5adc.png",
    "kingdom_platform": "Gemini_Generated_Image_gd1l7fgd1l7fgd1l.png",
    "fleet_component": "Gemini_Generated_Image_mxs9xzmxs9xzmxs9.png",
    "fleet_component2": "Gemini_Generated_Image_n6hrtun6hrtun6hr.png",
    "pirate_platform": "Gemini_Generated_Image_ogu7joogu7joogu7.png",
    "pirate_capital": "Gemini_Generated_Image_t81ul2t81ul2t81u.png",
    "battle": "venus_clouds.png",
    "battle_raiders": "Gemini_Generated_Image_6xx4g06xx4g06xx4.png",
}

# name -> (sheet, left, top, right, bottom) as FRACTIONS of the sheet.
# Read off the `--grid` overlay. Kept tight: the sheets are covered in leader lines and
# annotation text, and anything inside the crop is something Hunyuan will try to model.
CROPS = {
    # --- Kingdom ---
    "venus_kdm_vanguard_side":  ("fleet_component", 0.235, 0.350, 0.500, 0.585),
    "venus_kdm_valiant_side":   ("fleet_component", 0.275, 0.635, 0.495, 0.785),
    "venus_kdm_outpost_side":   ("fleet_component", 0.325, 0.130, 0.485, 0.280),
    # --- Armada (the MACHINED pirates, from the schematic sheets) ---
    "venus_pir_bloodhawk_side": ("fleet_component", 0.520, 0.365, 0.755, 0.595),
    "venus_pir_blacksails_side": ("fleet_component", 0.518, 0.665, 0.685, 0.775),
    "venus_pir_hub_side":       ("fleet_component", 0.830, 0.150, 0.975, 0.285),
}


def grid_overlay(sheet_key, out, step=0.05):
    """Write a copy of a sheet with a labeled fractional grid, to read crop rects off."""
    im = Image.open(os.path.join(ART, SHEETS[sheet_key])).convert("RGB")
    d = ImageDraw.Draw(im)
    W, H = im.size
    for i in range(1, int(1 / step)):
        x, y = int(W * i * step), int(H * i * step)
        major = (i % 2 == 0)
        d.line([(x, 0), (x, H)], fill=(255, 0, 0) if major else (255, 160, 160), width=2 if major else 1)
        d.line([(0, y), (W, y)], fill=(0, 90, 255) if major else (150, 190, 255), width=2 if major else 1)
        if major:
            d.text((x + 3, 3), "%.1f" % (i * step), fill=(255, 0, 0))
            d.text((3, y + 3), "%.1f" % (i * step), fill=(0, 90, 255))
    im.save(out)
    return im.size


def cut(name, out_dir, pad=0.01, square=True, bg=(245, 240, 228)):
    """Cut one crop. Padded, and squared by EXPANDING onto the sheet where possible so the
    ship is not distorted - Hunyuan wants a centered object, not a stretched one."""
    sheet, l, t, r, b = CROPS[name]
    im = Image.open(os.path.join(ART, SHEETS[sheet])).convert("RGB")
    W, H = im.size
    l, t, r, b = l - pad, t - pad, r + pad, b + pad
    box = [int(W * l), int(H * t), int(W * r), int(H * b)]
    box = [max(0, box[0]), max(0, box[1]), min(W, box[2]), min(H, box[3])]
    crop = im.crop(box)
    if square:
        w, h = crop.size
        s = max(w, h)
        canvas = Image.new("RGB", (s, s), bg)
        canvas.paste(crop, ((s - w) // 2, (s - h) // 2))
        crop = canvas
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, name + ".png")
    crop.save(dst)
    return dst, crop.size


def contact_sheet(paths, out, cols=4, cell=256):
    """All crops in one image, so a whole set can be judged at once rather than one by one."""
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGB")
        im.thumbnail((cell - 8, cell - 20))
        x, y = (i % cols) * cell, (i // cols) * cell
        sheet.paste(im, (x + 4, y + 16))
        d.text((x + 5, y + 3), os.path.splitext(os.path.basename(p))[0][:34], fill=(255, 220, 120))
    sheet.save(out)
    return out


def main():
    ap = argparse.ArgumentParser(description="Cut single-ship refs from the concept sheets.")
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--grid", default=None, help="sheet key: write a coordinate overlay")
    ap.add_argument("--out", default=os.path.join(here, "_refs"))
    ap.add_argument("--all", action="store_true", help="cut every declared crop")
    a = ap.parse_args()

    if a.grid:
        os.makedirs(a.out, exist_ok=True)
        dst = os.path.join(a.out, "_grid_" + a.grid + ".png")
        print(dst, grid_overlay(a.grid, dst))
        return

    if a.all:
        made = []
        for name in CROPS:
            dst, size = cut(name, a.out)
            print("  %-28s %s" % (name, size))
            made.append(dst)
        if made:
            print("contact sheet:", contact_sheet(made, os.path.join(a.out, "_contact.png")))


if __name__ == "__main__":
    main()
