"""Turns the logo into the application icon.

    .venv/bin/python make_icon.py logo.png

Produces `app/resources/Cicerone.icns` (macOS) and, if needed, `Cicerone.ico`
(Windows). It is run by hand when the logo changes: the result is committed, so
whoever builds the package does not have to repeat this step.

Two touch-ups that look cosmetic and are not:

- **the uniform border is cropped away.** Image generators hand back the icon
  centred inside a rectangle of background. Left as it is, the Dock would show
  a square of colour around the icon;
- **the corners are rounded into transparency.** macOS does not clip the icon
  itself: a square icon stays square, and it shows among the others.

This needs Pillow, which is a dependency of this script and not of the
application: do not add it to requirements.txt, or it would end up inside the
package for nothing.
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

DESTINATION = Path("app/resources")
# The sizes macOS expects inside an .iconset.
SIZES = [
    (16, "icon_16x16.png"), (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"), (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"), (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"), (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"), (1024, "icon_512x512@2x.png"),
]
# Apple rounds the corners at about a fifth of the side.
RADIUS = 0.225


def crop_border(image: Image.Image, tolerance: int = 12) -> Image.Image:
    """Removes the frame of uniform colour around the drawing."""
    graphic = image.convert("RGB")
    reference = graphic.getpixel((0, 0))

    def same(pixel) -> bool:
        return all(abs(a - b) <= tolerance for a, b in zip(pixel, reference))

    width, height = graphic.size
    top, bottom, left, right = 0, height - 1, 0, width - 1
    while top < bottom and all(same(graphic.getpixel((x, top))) for x in range(width)):
        top += 1
    while bottom > top and all(same(graphic.getpixel((x, bottom))) for x in range(width)):
        bottom -= 1
    while left < right and all(same(graphic.getpixel((left, y))) for y in range(top, bottom + 1)):
        left += 1
    while right > left and all(same(graphic.getpixel((right, y))) for y in range(top, bottom + 1)):
        right -= 1

    if (right - left) < 16 or (bottom - top) < 16:
        return image             # no recognisable border: leave it as it is
    return image.crop((left, top, right + 1, bottom + 1))


def squared(image: Image.Image) -> Image.Image:
    """Makes the image square, centring it without distorting it."""
    width, height = image.size
    if width == height:
        return image
    side = max(width, height)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(image, ((side - width) // 2, (side - height) // 2))
    return canvas


def rounded(image: Image.Image) -> Image.Image:
    """Makes everything outside the rounded corners transparent."""
    image = image.convert("RGBA")
    side = image.size[0]
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, side - 1, side - 1), radius=int(side * RADIUS), fill=255
    )
    clipped = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    clipped.paste(image, (0, 0), mask)
    return clipped


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    source = Path(sys.argv[1])
    if not source.exists():
        print(f"cannot find {source}")
        return 1

    image = rounded(squared(crop_border(Image.open(source))))
    image = image.resize((1024, 1024), Image.LANCZOS)
    DESTINATION.mkdir(parents=True, exist_ok=True)

    folder = DESTINATION / "Cicerone.iconset"
    folder.mkdir(exist_ok=True)
    for size, name in SIZES:
        image.resize((size, size), Image.LANCZOS).save(folder / name)

    icns = DESTINATION / "Cicerone.icns"
    outcome = subprocess.run(
        ["iconutil", "-c", "icns", str(folder), "-o", str(icns)],
        capture_output=True, text=True,
    )
    if outcome.returncode != 0:
        print("iconutil did not manage:", outcome.stderr.strip())
        return 1
    for leftover in folder.iterdir():
        leftover.unlink()
    folder.rmdir()

    ico = DESTINATION / "Cicerone.ico"
    image.save(ico, sizes=[(s, s) for s in (16, 32, 48, 64, 128, 256)])

    print(f"done: {icns} ({icns.stat().st_size // 1024} KB)")
    print(f"done: {ico} ({ico.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
