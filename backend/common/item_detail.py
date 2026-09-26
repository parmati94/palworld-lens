"""One item, described: what the item popup shows when a slot is clicked.

Everything comes from tables the loader already holds (items.json + its l10n row, loadout.json for
gear stats, passive_skills.json for the equip passives' names) -- nothing is read from the save.
"""
import re
from typing import Any, Dict, Optional

from backend.common.loadout import food_effects_line
from backend.common.schematics import RARITY_NAMES

# items.json type_a, worded the way the game's inventory tabs do
CATEGORY_NAMES = {
    'Weapon': 'Weapon', 'SpecialWeapon': 'Weapon', 'Armor': 'Armor', 'Accessory': 'Accessory', 'Glider': 'Glider',
    'SphereModule': 'Sphere Module', 'Material': 'Material', 'Consume': 'Consumable', 'Food': 'Food', 'Ammo': 'Ammo',
    'Blueprint': 'Schematic', 'Essential': 'Key Item', 'MonsterEquipWeapon': 'Pal Gear',
}
# type_b refinements worth a word
SUBTYPE_NAMES = {
    'ArmorHead': 'Head', 'ArmorBody': 'Body', 'Shield': 'Shield', 'Essential_PalGear': 'Pal Gear', 'Essential_BossReward': 'Boss Reward',
    'ConsumeWazaMachine': 'Skill Fruit', 'MaterialPalEgg': 'Egg', 'ConsumeBullet': 'Ammo', 'FoodDishMeat': 'Dish',
    'FoodDishVegetable': 'Dish', 'FoodDishFish': 'Dish', 'MaterialOre': 'Ore', 'MaterialIngot': 'Ingot',
    'SPWeaponCaptureBall': 'Pal Sphere', 'ConsumePalAwakening': 'Pal Soul', 'ConsumeGainStatusPoints': 'Elixir',
    'ConsumePalWorkSuitabilityUp': 'Work Book', 'ConsumePassiveSkillChange': 'Passive Skill', 'Drug': 'Medicine',
    'ConsumeFishingBait': 'Bait', 'WeaponMelee': 'Melee', 'WeaponBow': 'Bow', 'WeaponCrossbow': 'Crossbow',
    'WeaponHandgun': 'Handgun', 'WeaponAssaultRifle': 'Assault Rifle', 'WeaponShotgun': 'Shotgun',
    'WeaponRocketLauncher': 'Rocket Launcher', 'WeaponGatlingGun': 'Gatling Gun', 'WeaponThrowObject': 'Thrown',
}


# The upstream item text names the workbench by its id with the underscores swapped for spaces
# ("Can be crafted at Factory Hard 04.", "Can be produced in a WeaponFactory Dirty 03.") where the
# game shows its name ("Advanced Workshop"). Swap the name back in wherever such an id appears.
_PLACEHOLDERS = {'COMMON_STATUS_RANGE_Attack': 'Attack', 'COMMON_STATUS_RANGE_Defense': 'Defense'}
_building_names_cache: Dict[int, Any] = {}


def _spaced_building_ids(buildings: Dict[str, Dict]):
    """(regex, {spaced id: name}) for every building id with an underscore, longest first; cached per table."""
    hit = _building_names_cache.get(id(buildings))
    if hit:
        return hit
    names = {k.replace('_', ' '): (v or {}).get('localized_name') for k, v in buildings.items() if '_' in k and (v or {}).get('localized_name')}
    rx = re.compile(r'\b(' + '|'.join(re.escape(k) for k in sorted(names, key=len, reverse=True)) + r')\b') if names else None
    _building_names_cache[id(buildings)] = (rx, names)
    return rx, names


def clean_description(text, buildings: Dict[str, Dict]) -> Optional[str]:
    t = str(text or '').strip()
    if not t:
        return None
    for raw, word in _PLACEHOLDERS.items():
        t = t.replace(raw, word)
    rx, names = _spaced_building_ids(buildings)
    if rx:
        t = rx.sub(lambda m: names[m.group(1)], t)
    return t


def _plain(text) -> Optional[str]:
    """A passive's description, unless it is the raw effect id ('TemperatureResist_Cold +2.0')."""
    t = str(text or '').strip()
    return t if t and '_' not in t else None


def category_label(row: Dict) -> Optional[str]:
    a, b = str(row.get('type_a') or ''), str(row.get('type_b') or '')
    main = CATEGORY_NAMES.get(a) or (a if a and a != 'None' else None)
    sub = SUBTYPE_NAMES.get(b)
    if main and sub and sub != main:
        return f'{main} · {sub}'
    return main or sub


def describe_item(item_id: str, data: Any) -> Optional[Dict]:
    """The popup's payload for an item id, or None when the tables do not know it."""
    row = data.item(item_id)
    if not row:
        return None
    # the save spells ids inconsistently; the loadout and schematic tables are keyed on the canonical one
    item_id = getattr(data, '_items_lower', {}).get(item_id.lower(), item_id) if item_id not in data.items else item_id
    rarity = row.get('rarity')
    rarity = rarity if isinstance(rarity, int) and 0 <= rarity <= 4 else None
    loadout = getattr(data, 'loadout', None) or {}
    gear = (loadout.get('gear') or {}).get(item_id) or {}
    passives = getattr(data, 'passive_skills', None) or {}

    out: Dict[str, Any] = {
        'item_id': item_id,
        'name': row.get('localized_name') or item_id,
        'description': clean_description(row.get('description'), getattr(data, 'buildings', None) or {}),
        'icon': row.get('icon'),
        'rarity': rarity,
        'rarity_name': RARITY_NAMES[rarity] if rarity is not None else None,
        'category': category_label(row),
        'weight': row.get('weight') if isinstance(row.get('weight'), (int, float)) else None,
        'max_stack': row.get('max_stack_count') if isinstance(row.get('max_stack_count'), int) else None,
        'price': row.get('price') if isinstance(row.get('price'), (int, float)) and row.get('price') else None,
        'schematic': data.schematic(item_id),
        'gear': {k: int(v) for k, v in gear.items() if k in ('hp', 'defense', 'shield') and isinstance(v, (int, float)) and v},
        'passives': [
            {'id': pid, 'name': (passives.get(pid) or {}).get('localized_name') or pid,
             'description': _plain((passives.get(pid) or {}).get('description'))}
            for pid in gear.get('passives') or []
        ],
        'food': food_effects_line(item_id, loadout) or None,
    }
    return out
