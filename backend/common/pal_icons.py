"""Pal character_id -> icon file candidates.

The app never uses the `icon` field save-pal ships for pals (it is a placeholder,
`t_commonhuman_icon_normal`, for most 1.0 additions). Instead the icon file is
derived from the pal's character_id: `t_<stem>_icon_normal.webp`. This module is
the single definition of that derivation, shared by:

  * backend/models/models.py   -- PalInfo.image_id / image_candidates (API)
  * scripts/datagen/generate_icons.py -- which textures to pull from the pak
  * scripts/datagen/validate.py       -- which pals must have an icon on disk

Keep them in step by editing only this file. Pure python, no dependencies, so
the datagen scripts can import it without the backend's requirements.

Candidates are ordered most-specific first. Variant ids (PREDATOR_, GYM_, RAID_,
SUMMON_, POLICE_ prefixes; _Oilrig, _Tower, _Quest, _Otomo, _Avatar, _2 ...
suffixes) usually have no icon of their own, so after the exact id we fall back
by dropping trailing tokens until we reach a base species that does. GYM_ ids
keep their prefix first because gym bosses DO ship dedicated icons.
"""

from __future__ import annotations

# Prefixes that never appear in texture names. BOSS_ is stripped up front (it is
# by far the most common and was the original rule); the rest are fallbacks.
_BOSS = ('boss_',)
_VARIANT_PREFIXES = ('predator_', 'gym_', 'raid_', 'summon_', 'police_')


def _strip_boss(stem: str) -> str:
    for p in _BOSS:
        if stem.startswith(p):
            return stem[len(p):]
    return stem


def image_id(character_id: str) -> str:
    """The primary icon stem (lowercase, no `t_`/`_icon_normal`)."""
    return icon_candidates(character_id)[0]


def icon_candidates(character_id: str) -> list[str]:
    """Ordered, de-duplicated icon stems to try for this pal."""
    stem = (character_id or '').strip().lower()
    if not stem:
        return ['unknown']
    stem = _strip_boss(stem)

    # Quest variants use the base pal's image: Quest_Farmer03_PinkCat -> pinkcat
    if stem.startswith('quest_'):
        parts = stem.split('_')
        if len(parts) > 2:
            stem = parts[-1]

    roots = [stem]
    for p in _VARIANT_PREFIXES:
        if stem.startswith(p):
            roots.append(stem[len(p):])
            break

    out: list[str] = []
    for root in roots:
        parts = root.split('_')
        while parts:
            cand = '_'.join(parts)
            if cand and cand not in out and cand + '_' not in _VARIANT_PREFIXES:
                out.append(cand)
            parts.pop()
    return out
