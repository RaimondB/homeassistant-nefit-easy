"""Build home-assistant/brands-compatible PNGs from the SVG sources.

Brands rules enforced here:
  * icon.png  == 256x256, icon@2x.png  == 512x512 (square)
  * logo.png  longest side == 256, logo@2x.png longest side == 512
  * all PNGs trimmed of transparent border, transparent background

SVGs are the single source of truth; this only rasterizes (rsvg-convert)
and crops/resizes (Pillow). Run: ``python assets/build_brands.py``.
"""

from __future__ import annotations

import os
import subprocess

from PIL import Image

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "brands")
ALPHA_FLOOR = 12  # ignore faint glow halo when trimming


def _rasterize(svg: str, px: int) -> Image.Image:
    png = subprocess.run(  # noqa: S603, S607  # local build tool, fixed argv
        ["rsvg-convert", "-w", str(px), "-h", str(px), svg],
        check=True,
        capture_output=True,
    ).stdout
    tmp = os.path.join(OUT, "_tmp.png")
    with open(tmp, "wb") as fh:
        fh.write(png)
    img = Image.open(tmp).convert("RGBA")
    os.remove(tmp)
    return img


def _trim(img: Image.Image) -> Image.Image:
    alpha = img.getchannel("A").point(lambda a: 255 if a > ALPHA_FLOOR else 0)
    bbox = alpha.getbbox()
    return img.crop(bbox) if bbox else img


def _square(img: Image.Image) -> Image.Image:
    w, h = img.size
    s = max(w, h)
    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    canvas.paste(img, ((s - w) // 2, (s - h) // 2), img)
    return canvas


def build_icon() -> None:
    # Render big, trim the halo, force a centred square, resize exactly.
    base = _square(_trim(_rasterize(os.path.join(HERE, "icon.svg"), 1024)))
    for name, px in (("icon.png", 256), ("icon@2x.png", 512)):
        base.resize((px, px), Image.LANCZOS).save(os.path.join(OUT, name))


def build_logo() -> None:
    # rsvg keeps the SVG aspect when only width is given.
    raw = subprocess.run(  # noqa: S603, S607  # local build tool, fixed argv
        ["rsvg-convert", "-w", "1960", os.path.join(HERE, "logo.svg")],
        check=True,
        capture_output=True,
    ).stdout
    tmp = os.path.join(OUT, "_logo.png")
    with open(tmp, "wb") as fh:
        fh.write(raw)
    img = _trim(Image.open(tmp).convert("RGBA"))
    os.remove(tmp)
    for name, longest in (("logo.png", 256), ("logo@2x.png", 512)):
        w, h = img.size
        scale = longest / max(w, h)
        img.resize(
            (max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS
        ).save(os.path.join(OUT, name))


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    build_icon()
    build_logo()
    for f in sorted(os.listdir(OUT)):
        if f.endswith(".png"):
            with Image.open(os.path.join(OUT, f)) as im:
                print(f"{f}: {im.size[0]}x{im.size[1]} {im.mode}")


if __name__ == "__main__":
    main()
