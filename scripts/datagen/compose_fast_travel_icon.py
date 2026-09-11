#!/usr/bin/env python3
"""
Compose the fast-travel map marker: the game's compass eagle inside a diamond.

The pak has no baked version of this. The compass ships only the wings
(T_icon_compass_FTtower) and the world map uses a plain glyph
(T_worldmap_icon_fasttravel). Older game builds DID ship the wings inside a
diamond -- that's the 64px icon palworld.gg still serves -- and it's the
marker people recognise, so we draw the same thing at 128px in the style of
the _camp / _tower compass diamonds that do ship baked.

Input : frontend/public/img/t_icon_compass_fttower.webp (pak-native 100px wings)
Output: frontend/public/img/t_icon_compass_fttower_diamond.webp (128px)

  python3 scripts/datagen/compose_fast_travel_icon.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
IMG = ROOT / 'frontend' / 'public' / 'img'
SRC = IMG / 't_icon_compass_fttower.webp'
OUT = IMG / 't_icon_compass_fttower_diamond.webp'

S = 256          # render at 2x, downsample for clean edges
OUTPUT_PX = 128

# Layout mirrors the baked icon older builds shipped (and palworld.gg serves):
# a single-stroke diamond OUTLINE (no fill) centred on the canvas, with the
# eagle drawn over it -- body covering the diamond's centre, wings spanning
# ~75% of the canvas so they overhang the diamond on both sides.
DIAMOND_INSET = 52         # diamond spans S-2*inset = 152px of 256 (~60%)
DIAMOND_CY = 132           # a touch below centre so the top point clears the head
STROKE = 9
EAGLE_WIDTH = 196          # ~77% of canvas
EAGLE_CY = 122             # eagle centred just above the diamond centre


def diamond(d, inset, width, cy, fill=None):
    c = S / 2
    r = c - inset
    pts = [(c, cy - r), (c + r, cy), (c, cy + r), (c - r, cy)]
    if fill:
        d.polygon(pts, fill=fill)
    d.line(pts + [pts[0]], fill=(255, 255, 255, 255), width=width, joint='curve')


def main():
    wings = Image.open(SRC).convert('RGBA')
    # crop to the sprite's opaque bounds so the eagle, not its padding, is sized
    bbox = wings.getchannel('A').point(lambda v: 255 if v > 30 else 0).getbbox()
    wings = wings.crop(bbox)

    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    diamond(d, DIAMOND_INSET, STROKE, DIAMOND_CY)         # outline only, like the original

    tw = EAGLE_WIDTH
    th = round(tw * wings.height / wings.width)
    eagle = wings.resize((tw, th), Image.LANCZOS)
    im.alpha_composite(eagle, ((S - tw) // 2, EAGLE_CY - th // 2))

    # soft glow behind, like the shipped compass icons
    out = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    out.alpha_composite(im.filter(ImageFilter.GaussianBlur(5)))
    out.alpha_composite(im)
    out.resize((OUTPUT_PX, OUTPUT_PX), Image.LANCZOS).save(OUT, 'WEBP', quality=95, method=6)
    print(f'wrote {OUT.relative_to(ROOT)} ({OUTPUT_PX}px) from {SRC.name} {wings.size} wings')


if __name__ == '__main__':
    main()
