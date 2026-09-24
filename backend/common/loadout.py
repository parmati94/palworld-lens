"""What a player's gear and food do to their stats.

The status screen shows each stat after enhancements (Health 1900 >> 3550, "Equipment
Enhancements +1,650") and the save gives everything needed to reproduce it:

  DT_ItemDataTable_Common   armour HPValue / PhysicalDefenseValue / ShieldValue and up to four
                            PassiveSkillName* per item (the equip passives: +200 kg, ...)
  DT_StatusEffectFood       a dish's buff: EffectType1/2 + EffectValue1/2 (percent) for EffectTime s
  DT_PalPlayerParameter     the player's base row (Hp 500, Defense 100, ...), the same at every level
  Level.sav                 the character's FoodWithStatusEffect + its timer, ShieldHP, UnusedStatusPoint

Verified on a live player 2026-09-24: HP 1900 + 350 (helm) + 1300 (body) = 3550; Defense 100 + 150 +
400 = 650; Weight 1650 + 200 (MaxInventoryWeight_up_Equip_3) = 1850; Work speed 1450 * 1.30 (Pizza)
= 1885; Shield 1045 (Shield_04). Percent effects apply to the base value.

build_loadout_tables turns the pak dumps into data/json/loadout.json (scripts/datagen/
generate_loadout.py); enhance_stats applies it to a player.
"""
from typing import Dict, Iterable, List, Optional

MIN_GEAR = 300          # armour + accessories with a stat or passive (503 on 1.0)
MIN_FOOD = 20           # dishes with a buff (20 on 1.0)

STATS = ('hp', 'stamina', 'attack', 'defense', 'work_speed', 'weight')
NONE = 'None'

# passive-skill effect type -> (stat, flat or percent of base); only ToSelf effects count for the player
PASSIVE_EFFECTS = {
    'MaxHP': ('hp', 'pct'),
    'ShotAttack': ('attack', 'pct'),
    'Defense': ('defense', 'pct'),
    'CraftSpeed': ('work_speed', 'pct'),
    'MaxInventoryWeight': ('weight', 'flat'),
}
# food effect type -> (stat, percent of base); the rest (HungerResist, SANResist, ...) are not stats
FOOD_EFFECTS = {
    'WorkSpeed': ('work_speed', 'pct'),
    'Attack': ('attack', 'pct'),
    'Defense': ('defense', 'pct'),
}
PLAYER_BASE_FIELDS = {'Hp': 'hp', 'Stamina': 'stamina', 'ShotAttack': 'attack', 'Defense': 'defense',
                      'CraftSpeed': 'work_speed'}


def _num(v) -> float:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


def build_loadout_tables(item_rows: Dict[str, Dict], food_rows: Dict[str, Dict],
                         player_rows: Dict[str, Dict]) -> Dict[str, Dict]:
    """{gear: {item id: {hp, defense, shield, passives}}, food: {item id: {seconds, effects: [{type, value}]}},
    player_base: {stat: value}} from the three table dumps. Only items that change a stat are kept."""
    gear: Dict[str, Dict] = {}
    for item_id, r in (item_rows or {}).items():
        if not isinstance(r, dict):
            continue
        passives = [str(r.get(k)) for k in ('PassiveSkillName', 'PassiveSkillName2', 'PassiveSkillName3', 'PassiveSkillName4')
                    if r.get(k) not in (None, '', NONE)]
        hp, defense, shield = _num(r.get('HPValue')), _num(r.get('PhysicalDefenseValue')), _num(r.get('ShieldValue'))
        if not (hp or defense or shield or passives):
            continue
        entry: Dict = {}
        if hp:
            entry['hp'] = int(hp)
        if defense:
            entry['defense'] = int(defense)
        if shield:
            entry['shield'] = int(shield)
        if passives:
            entry['passives'] = passives
        gear[str(item_id)] = entry

    food: Dict[str, Dict] = {}
    for item_id, r in (food_rows or {}).items():
        if not isinstance(r, dict):
            continue
        effects = []
        for i in ('1', '2'):
            t = str(r.get(f'EffectType{i}') or NONE).split('::')[-1]
            if t and t != NONE:
                effects.append({'type': t, 'value': _num(r.get(f'EffectValue{i}'))})
        if effects:
            food[str(item_id)] = {'seconds': int(_num(r.get('EffectTime'))), 'effects': effects}

    base_row = (player_rows or {}).get('1') or next(iter((player_rows or {}).values()), {}) or {}
    player_base = {stat: int(_num(base_row.get(field))) for field, stat in PLAYER_BASE_FIELDS.items() if field in base_row}
    return {'gear': gear, 'food': food, 'player_base': player_base}


def enhance_stats(base: Dict[str, int], gear_ids: Iterable[str], food_id: Optional[str], tables: Dict[str, Dict],
                  passive_skills: Dict[str, Dict]) -> Dict[str, Dict[str, int]]:
    """{stat: {base, gear, food, total}} for the six status-screen stats.

    `base` is the value from level and stat points (what the screen shows as the left number);
    gear adds the armour values and the equip passives' ToSelf effects; food adds the active
    dish's percent buff. Percent effects apply to the base, the way the game does it.
    """
    out = {s: {'base': int(base.get(s) or 0), 'gear': 0.0, 'food': 0.0} for s in STATS}

    def apply(stat: str, kind: str, value: float, bucket: str) -> None:
        if stat not in out:
            return
        out[stat][bucket] += value if kind == 'flat' else out[stat]['base'] * value / 100.0

    gear_table = (tables or {}).get('gear') or {}
    for gid in gear_ids or []:
        row = gear_table.get(gid) or {}
        apply('hp', 'flat', _num(row.get('hp')), 'gear')
        apply('defense', 'flat', _num(row.get('defense')), 'gear')
        for pid in row.get('passives') or []:
            for e in ((passive_skills or {}).get(pid) or {}).get('effects') or []:
                if str(e.get('target') or 'ToSelf') != 'ToSelf':
                    continue
                stat_kind = PASSIVE_EFFECTS.get(str(e.get('type') or ''))
                if stat_kind:
                    apply(stat_kind[0], stat_kind[1], _num(e.get('value')), 'gear')

    dish = ((tables or {}).get('food') or {}).get(food_id or '') or {}
    for e in dish.get('effects') or []:
        stat_kind = FOOD_EFFECTS.get(str(e.get('type') or ''))
        if stat_kind:
            apply(stat_kind[0], stat_kind[1], _num(e.get('value')), 'food')

    result: Dict[str, Dict[str, int]] = {}
    for s, v in out.items():
        gear_v, food_v = int(round(v['gear'])), int(round(v['food']))
        result[s] = {'base': v['base'], 'gear': gear_v, 'food': food_v, 'total': v['base'] + gear_v + food_v}
    return result


def shield_max(gear_ids: Iterable[str], tables: Dict[str, Dict]) -> int:
    """The shield's capacity: the ShieldValue of whatever shield is worn (summed, should one wear two)."""
    gear_table = (tables or {}).get('gear') or {}
    return int(sum(_num((gear_table.get(g) or {}).get('shield')) for g in gear_ids or []))


def food_effects(food_id: Optional[str], tables: Dict[str, Dict]) -> List[Dict]:
    """The active dish's effects as [{type, value}], stat or not (HungerResist rides along)."""
    return list((((tables or {}).get('food') or {}).get(food_id or '') or {}).get('effects') or [])
