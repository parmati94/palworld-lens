#!/usr/bin/env python3
"""
Compose the landmark map markers: the game's own compass sprites, tinted the
way the in-game world map draws them.

The pak ships each compass icon as a white sprite and the game colours it at
draw time. We bake the tint so the marker and the map-panel toggle can use one
static file. Inputs are the pak-native sprites under frontend/public/img
(pulled with `pal-extract tex T_icon_compass_<name>`):

  t_icon_compass_fttower.webp      fast travel statue      -> _cyan     (~#60E8F0, sampled in game)
  t_icon_compass_ftunlockmap.webp  watchtower (1.0)        -> _cyan     (the game draws both alike)
  t_icon_compass_tower.webp        syndicate tower         -> _red
  t_icon_compass_dungeon.webp      dungeon portal          -> _violet

Output: 128px webp with a soft glow, like the shipped compass icons.

  python3 scripts/datagen/compose_map_icons.py
"""
from pathlib import Path
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
IMG = ROOT / 'frontend' / 'public' / 'img'

OUTPUT_PX = 128
S = OUTPUT_PX * 2          # render at 2x, downsample for clean edges

CYAN = (96, 232, 240)      # sampled from an in-game world-map screenshot
RED = (255, 118, 96)
VIOLET = (196, 150, 255)

# (source sprite, output suffix, tint, sprite width as a share of the canvas)
ICONS = [
    ('t_icon_compass_fttower', 'cyan', CYAN, 0.86),
    ('t_icon_compass_ftunlockmap', 'cyan', CYAN, 0.86),
    ('t_icon_compass_tower', 'red', RED, 0.80),
    ('t_icon_compass_dungeon', 'violet', VIOLET, 0.74),
]


def compose(src: Path, out: Path, tint, share: float) -> None:
    sprite = Image.open(src).convert('RGBA')
    bbox = sprite.getchannel('A').point(lambda v: 255 if v > 30 else 0).getbbox()
    sprite = sprite.crop(bbox)

    tw = round(S * share)
    th = round(tw * sprite.height / sprite.width)
    if th > tw:                                  # tall sprites: fit the height instead
        th, tw = tw, round(tw * sprite.width / sprite.height)
    sprite = sprite.resize((tw, th), Image.LANCZOS)

    # Keep the sprite's luminance as shading, multiply in the tint.
    lum = sprite.convert('L')
    tinted = Image.merge('RGBA', [lum.point(lambda v, c=c: v * c // 255) for c in tint] + [sprite.getchannel('A')])

    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    im.alpha_composite(tinted, ((S - tw) // 2, (S - th) // 2))

    # soft glow behind, like the shipped compass icons
    result = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    result.alpha_composite(im.filter(ImageFilter.GaussianBlur(5)))
    result.alpha_composite(im)
    result.resize((OUTPUT_PX, OUTPUT_PX), Image.LANCZOS).save(out, 'WEBP', quality=95, method=6)


def main():
    for name, suffix, tint, share in ICONS:
        src, out = IMG / f'{name}.webp', IMG / f'{name}_{suffix}.webp'
        compose(src, out, tint, share)
        print(f'wrote {out.relative_to(ROOT)} ({OUTPUT_PX}px) from {src.name}')


if __name__ == '__main__':
    main()
