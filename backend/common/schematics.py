"""Schematics: which item or building each blueprint unlocks.

The game draws every schematic with the same folded-blueprint icon; the thing
it unlocks lives one table away. Two pak tables link them:

  DT_ItemRecipeDataTable   recipe rows: Product_Id + UnlockItemID (the blueprint
                           that unlocks the recipe, 'None' for tech-unlocked ones)
  DT_BuildObjectDataTable  buildings: MapObjectId + BlueprintItemID

`build_schematics` turns those into {blueprint_id: {product, kind}} for
data/json/schematics.json (generate_schematics.py); the DataLoader resolves the
product's icon, name and the schematic's own rarity at runtime so the UI can
draw the product over the blueprint paper, the way the game's item widget does
(WBP_PalInGameMenuItemIcon: Image_Main = the item's icon, Image_Main_BP = the
product at 0.8 scale on top). Pure python, no dependencies.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

NONE = 'None'
BLUEPRINT_TYPE = 'Blueprint'
# A patch that drops below this is a partial extraction, not a smaller game.
MIN_SCHEMATICS = 500

# items.json `rarity` 0-4, the game's tiers in order. 99 marks a few
# unobtainable dev items; anything off the end is rendered as no tier.
RARITY_NAMES = ('Common', 'Uncommon', 'Rare', 'Epic', 'Legendary')


def rarity_name(rarity: Optional[int]) -> Optional[str]:
    if rarity is None or not 0 <= int(rarity) < len(RARITY_NAMES):
        return None
    return RARITY_NAMES[int(rarity)]


def blueprint_ids(items: Dict[str, Dict]) -> List[str]:
    """Every schematic item id in items.json (type_a == Blueprint)."""
    return sorted(k for k, v in items.items() if isinstance(v, dict) and v.get('type_a') == BLUEPRINT_TYPE)


def build_schematics(recipes: Iterable[Dict], build_objects: Iterable[Dict],
                     items: Dict[str, Dict], buildings: Dict[str, Dict]) -> Tuple[Dict[str, Dict], List[str]]:
    """{blueprint_id: {'product': id, 'kind': 'item'|'building'}}, plus the blueprints nothing unlocks.

    Item recipes win over buildings when both name the same blueprint (they
    never do today). Only blueprints items.json knows are kept, and only
    products items.json / buildings.json can draw.
    """
    known = set(blueprint_ids(items))
    out: Dict[str, Dict] = {}
    for r in recipes:
        bp, product = r.get('UnlockItemID') or NONE, r.get('Product_Id') or NONE
        if bp == NONE or bp not in known or product == NONE or product not in items:
            continue
        out.setdefault(bp, {'product': product, 'kind': 'item'})
    for b in build_objects:
        bp, product = b.get('BlueprintItemID') or NONE, b.get('MapObjectId') or NONE
        if bp == NONE or bp not in known or product == NONE or product not in buildings:
            continue
        out.setdefault(bp, {'product': product, 'kind': 'building'})
    unmatched = sorted(known - set(out))
    return dict(sorted(out.items())), unmatched


def resolve(schematic: Dict, blueprint_id: str, items: Dict[str, Dict], buildings: Dict[str, Dict]) -> Dict:
    """One schematics.json entry -> what the API sends: product id/name/kind, icon, rarity."""
    product, kind = schematic['product'], schematic['kind']
    row = (buildings if kind == 'building' else items).get(product) or {}
    rarity = (items.get(blueprint_id) or {}).get('rarity')
    return {
        'product_id': product,
        'product_name': row.get('localized_name') or product,
        'kind': kind,
        'icon': row.get('icon'),
        'rarity': rarity if rarity_name(rarity) else None,
        'rarity_name': rarity_name(rarity),
    }
