#!/usr/bin/env python3
"""
Compose the fast-travel map marker: the game's compass eagle, tinted the
cyan the in-game world map uses.

The pak ships the eagle as a white sprite (T_icon_compass_FTtower) and the
game colours it at draw time -- the world map shows it plain, no diamond, in
a light cyan (~#60E8F0). We bake that tint so the marker and the map-panel
toggle can use one static file.

Input : frontend/public/img/t_icon_compass_fttower.webp (pak-native 100px, white)
Output: frontend/public/img/t_icon_compass_fttower_cyan.webp (128px, tinted)

  python3 scripts/datagen/compose_fast_travel_icon.py
"""
from pathlib import Path
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
IMG = ROOT / 'frontend' / 'public' / 'img'
SRC = IMG / 't_icon_compass_fttower.webp'
OUT = IMG / 't_icon_compass_fttower_cyan.webp'

OUTPUT_PX = 128
S = OUTPUT_PX * 2          # render at 2x, downsample for clean edges
EAGLE_WIDTH = 220          # ~86% of canvas; the sprite has no padding to speak of
TINT = (96, 232, 240)      # sampled from an in-game world-map screenshot


def main():
    wings = Image.open(SRC).convert('RGBA')
    bbox = wings.getchannel('A').point(lambda v: 255 if v > 30 else 0).getbbox()
    wings = wings.crop(bbox)

    tw = EAGLE_WIDTH
    th = round(tw * wings.height / wings.width)
    wings = wings.resize((tw, th), Image.LANCZOS)

    # Keep the sprite's luminance as shading, multiply in the tint.
    lum = wings.convert('L')
    tinted = Image.merge('RGBA', [lum.point(lambda v, c=c: v * c // 255) for c in TINT] + [wings.getchannel('A')])

    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    im.alpha_composite(tinted, ((S - tw) // 2, (S - th) // 2))

    # soft glow behind, like the shipped compass icons
    out = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    out.alpha_composite(im.filter(ImageFilter.GaussianBlur(5)))
    out.alpha_composite(im)
    out.resize((OUTPUT_PX, OUTPUT_PX), Image.LANCZOS).save(OUT, 'WEBP', quality=95, method=6)
    print(f'wrote {OUT.relative_to(ROOT)} ({OUTPUT_PX}px) from {SRC.name}')


if __name__ == '__main__':
    main()
