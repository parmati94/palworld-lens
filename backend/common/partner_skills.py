"""Partner skills: the game's per-species skill text, rendered per level.

A partner skill has one description template per species (the text the game
shows when a pal is first activated) with placeholders for the numbers that
grow as the pal is condensed, plus inline markup that references other text
tables. The pak spreads this over six tables:

  DT_SkillNameText_Common         PARTNERSKILL_<id>          the skill's name
  DT_PalFirstActivatedInfoText    PAL_FIRST_SPAWN_DESC_<id>  the template
  DT_PartnerSkillParameter        <id>                       which passive-skill
                                                             ids apply at each of
                                                             the five levels
  DT_PassiveSkill_Main            <passive id>               EffectValue1..4
  DT_PartnerSkillAppendText       <kind>_Rank_<n>            "(Damage Up: S)"
  DT_UI_Common_Text_Common        element / status names the markup points at

Placeholders resolve per level (0-based index into the per-level lists):

  {Passive<i>_EffectValue<j>}       PassiveSkills[lv].SkillAndParametersArray[i-1]
                                    -> DT_PassiveSkill_Main[key].EffectValue<j>
  {ReferencePassive<i>_EffectValue1} TextReferencePassiveSkills[lv].PassiveSkillIds[i-1]
  {ActiveSkillMainValueByRank}      ActiveSkill.ActiveSkill_MainValueByRank[lv]
  {ActiveSkillOverWriteEffectTime}  ActiveSkill.ActiveSkill_OverWriteEffectTimeByRank[lv]
  {ReferenceMsgId_<kind>}           DT_PartnerSkillAppendText[<kind>_Rank_<lv+1>]

Markup is resolved to words, never stripped blind: <uiCommon id=|K|/> is a UI
string, <characterName id=|K|/> a pal, <itemName id=|K|/> an item,
<mapObjectName id=|K|/> a building, <activeSkillName id=|K|/> an active skill.
<img id=|ElemIcon_X|/> is dropped (the element name always follows it), and
bare style tags (<Status_Up>...</>) keep their text.

The level shown for an owned pal is its save `Rank` (1-5): condensing raises
both. Pure python; the datagen script and the tests import this.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

LEVELS = 5
# A shipped table with fewer real species than this is a partial extraction.
MIN_PARTNER_SKILL_SPECIES = 250

_ATTR_TAG = re.compile(r'<(\w+)\s+([^>]*?)/>')
_ATTR = re.compile(r'(\w+)=\|([^|]*)\|')
_STYLE_TAG = re.compile(r'</?[A-Za-z0-9_]*>')
_PLACEHOLDER = re.compile(r'\{([A-Za-z0-9_]+)\}')
_PASSIVE = re.compile(r'^(Reference)?Passive(\d)_EffectValue(\d)$')
_TEXT = 'LocalizedString'

Lookup = Callable[[str], Optional[str]]


def text_of(row: Any) -> str:
    """The English string of a text-table row as the extractor dumps it."""
    if isinstance(row, dict):
        td = row.get('TextData')
        if isinstance(td, dict):
            return str(td.get(_TEXT) or td.get('SourceString') or '')
        return str(row.get(_TEXT) or '')
    return str(row or '')


def format_number(v: Any) -> str:
    """40.0 -> '40', 1.1 -> '1.1', 0.15 -> '0.15'."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f == int(f):
        return str(int(f))
    return ('%.4f' % f).rstrip('0').rstrip('.')


def strip_markup(s: str, lookups: Optional[Dict[str, Lookup]] = None) -> str:
    """Resolve attribute tags via `lookups` (tag name -> id resolver) and drop style tags."""
    lookups = lookups or {}

    def sub(m: re.Match) -> str:
        tag, attrs = m.group(1), dict(_ATTR.findall(m.group(2)))
        if tag == 'img':
            return ''
        key = attrs.get('id', '')
        fn = lookups.get(tag)
        hit = fn(key) if fn else None
        return hit if hit else key

    s = _ATTR_TAG.sub(sub, s)
    s = _STYLE_TAG.sub('', s)
    return s


def clean_text(s: str) -> str:
    """Paragraphs separated by one blank line; the game's hard wraps inside a
    paragraph become spaces so the text can wrap to whatever width shows it."""
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    paragraphs = []
    for block in re.split(r'\n[ \t]*\n', s):
        lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in block.split('\n')]
        text = ' '.join(ln for ln in lines if ln)
        if text:
            paragraphs.append(text)
    return '\n\n'.join(paragraphs)


def _at(seq: Any, lv: int) -> Any:
    """Item `lv` of a per-level list, clamped (two species ship a single level)."""
    if not isinstance(seq, list) or not seq:
        return None
    return seq[min(lv, len(seq) - 1)]


def _passive_key(entry: Any) -> Optional[str]:
    """SkillAndParametersArray[i] / PassiveSkillIds[i] -> passive id."""
    if not isinstance(entry, dict):
        return None
    name = entry.get('SkillName', entry)
    if isinstance(name, dict):
        return name.get('Key')
    return name if isinstance(name, str) else None


class Resolver:
    """Placeholder values for one species at one level."""

    def __init__(self, param: Dict[str, Any], passives_main: Dict[str, Dict], appends: Dict[str, str]):
        self.param = param or {}
        self.main = passives_main
        self.appends = appends
        self.missing: List[str] = []

    def _effect(self, key: Optional[str], j: int) -> Optional[str]:
        row = self.main.get(key or '')
        if not row:
            return None
        return format_number(row.get(f'EffectValue{j}', 0))

    def value(self, name: str, lv: int) -> Optional[str]:
        m = _PASSIVE.match(name)
        if m:
            ref, i, j = bool(m.group(1)), int(m.group(2)) - 1, int(m.group(3))
            if ref:
                level = _at(self.param.get('TextReferencePassiveSkills'), lv) or {}
                key = _passive_key(_at(level.get('PassiveSkillIds'), i))
            else:
                level = _at(self.param.get('PassiveSkills'), lv) or {}
                key = _passive_key(_at(level.get('SkillAndParametersArray'), i))
            return self._effect(key, j)
        active = self.param.get('ActiveSkill') or {}
        if name == 'ActiveSkillMainValueByRank':
            v = _at(active.get('ActiveSkill_MainValueByRank'), lv)
            return None if v is None else format_number(v)
        if name == 'ActiveSkillOverWriteEffectTime':
            v = _at(active.get('ActiveSkill_OverWriteEffectTimeByRank'), lv)
            return None if v is None else format_number(v)
        if name.startswith('ReferenceMsgId_'):
            # "(Ride Speed Up: 10%)" -- blank at level 1; its own paragraph otherwise.
            kind = name[len('ReferenceMsgId_'):]
            text = (self.appends.get(f'{kind}_Rank_{lv + 1}') or '').strip()
            return f'\n\n{text}' if text else ''
        return None

    def render(self, template: str, lv: int, lookups: Dict[str, Lookup]) -> str:
        def sub(m: re.Match) -> str:
            v = self.value(m.group(1), lv)
            if v is None:
                self.missing.append(m.group(1))
                return m.group(0)
            return v
        s = _PLACEHOLDER.sub(sub, template)
        return clean_text(strip_markup(s, lookups))


def build_partner_skills(names: Dict[str, str], templates: Dict[str, str], params: Dict[str, Dict],
                         passives_main: Dict[str, Dict], appends: Dict[str, str],
                         lookups: Dict[str, Lookup], resolve_species: Callable[[str], Optional[str]],
                         ) -> Dict[str, Any]:
    """{species key: {name, levels: [5 rendered descriptions]}} plus a report.

    `names`/`templates`/`appends` are already plain strings keyed by pak id
    (PARTNERSKILL_ / PAL_FIRST_SPAWN_DESC_ prefixes removed). `resolve_species`
    maps a pak id to the pals.json key (None = not a shipped species).
    """
    out: Dict[str, Dict] = {}
    report = {'unresolved': [], 'no_name': [], 'unfilled': {}, 'leftover_markup': []}
    names_lower = {k.lower(): v for k, v in names.items()}   # WindChimes vs Windchimes
    for pak_id, template in templates.items():
        sid = resolve_species(pak_id)
        if sid is None:
            report['unresolved'].append(pak_id)
            continue
        if sid in out:
            continue
        name = names.get(pak_id) or names_lower.get(pak_id.lower()) or ''
        if not name:
            report['no_name'].append(pak_id)
        r = Resolver(params.get(pak_id) or params.get(sid) or {}, passives_main, appends)
        levels = [r.render(template, lv, lookups) for lv in range(LEVELS)]
        if r.missing:
            report['unfilled'][pak_id] = sorted(set(r.missing))
        if any('<' in s for s in levels):
            report['leftover_markup'].append(pak_id)
        out[sid] = {'name': name or pak_id, 'levels': levels}
    return {'species': dict(sorted(out.items())), 'report': report}


def clamp_level(rank: Any) -> int:
    try:
        return max(1, min(LEVELS, int(rank or 1)))
    except (TypeError, ValueError):
        return 1
