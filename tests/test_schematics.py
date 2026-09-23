"""Schematics draw the thing they unlock, not the game's one generic blueprint icon."""
import json
from pathlib import Path

from backend.common.schematics import MIN_SCHEMATICS, blueprint_ids, build_schematics, rarity_name, resolve
from backend.parser.builders.base_containers import _items

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'json'

ITEMS = {
    'Blueprint_Musket_4': {'type_a': 'Blueprint', 'rarity': 3, 'icon': 't_itemicon_material_blueprint',
                           'localized_name': 'Musket Schematic 3'},
    'Blueprint_WallTorch02': {'type_a': 'Blueprint', 'rarity': 0, 'icon': 't_itemicon_blueprint_building'},
    'Blueprint_Retired': {'type_a': 'Blueprint', 'rarity': 99},
    'Musket_4': {'type_a': 'Weapon', 'rarity': 3, 'icon': 't_itemicon_weapon_musket', 'localized_name': 'Musket'},
    'Wood': {'type_a': 'Material', 'rarity': 0, 'icon': 't_itemicon_material_wood', 'localized_name': 'Wood'},
}
BUILDINGS = {'WallTorch02': {'icon': 't_icon_buildobject_walltorch02', 'localized_name': 'Majestic Wall Torch'}}
RECIPES = [
    {'Product_Id': 'Musket_4', 'UnlockItemID': 'Blueprint_Musket_4'},
    {'Product_Id': 'Wood', 'UnlockItemID': 'None'},                    # tech-unlocked, no schematic
    {'Product_Id': 'Ghost', 'UnlockItemID': 'Blueprint_Retired'},      # product items.json does not know
]
BUILD_OBJECTS = [
    {'MapObjectId': 'WallTorch02', 'BlueprintItemID': 'Blueprint_WallTorch02'},
    {'MapObjectId': 'Workbench', 'BlueprintItemID': 'None'},
]


def test_build_schematics_links_blueprints_to_items_and_buildings():
    table, unmatched = build_schematics(RECIPES, BUILD_OBJECTS, ITEMS, BUILDINGS)
    assert table == {
        'Blueprint_Musket_4': {'product': 'Musket_4', 'kind': 'item'},
        'Blueprint_WallTorch02': {'product': 'WallTorch02', 'kind': 'building'},
    }
    assert unmatched == ['Blueprint_Retired']
    assert blueprint_ids(ITEMS) == ['Blueprint_Musket_4', 'Blueprint_Retired', 'Blueprint_WallTorch02']


def test_resolve_takes_the_products_icon_and_the_schematics_rarity():
    table, _ = build_schematics(RECIPES, BUILD_OBJECTS, ITEMS, BUILDINGS)
    musket = resolve(table['Blueprint_Musket_4'], 'Blueprint_Musket_4', ITEMS, BUILDINGS)
    assert musket == {'product_id': 'Musket_4', 'product_name': 'Musket', 'kind': 'item',
                      'icon': 't_itemicon_weapon_musket', 'rarity': 3, 'rarity_name': 'Epic'}
    torch = resolve(table['Blueprint_WallTorch02'], 'Blueprint_WallTorch02', ITEMS, BUILDINGS)
    assert torch['kind'] == 'building' and torch['icon'] == 't_icon_buildobject_walltorch02'
    assert torch['product_name'] == 'Majestic Wall Torch' and torch['rarity_name'] == 'Common'
    assert rarity_name(99) is None and rarity_name(None) is None and rarity_name(4) == 'Legendary'


class _Data:
    """The loader surface _items() uses, over the fixtures above."""
    def __init__(self):
        self.table, _ = build_schematics(RECIPES, BUILD_OBJECTS, ITEMS, BUILDINGS)

    def item(self, item_id):
        return ITEMS.get(item_id) or {}

    def schematic(self, item_id):
        e = self.table.get(item_id)
        return resolve(e, item_id, ITEMS, BUILDINGS) if e else None


def test_container_slots_draw_the_product_for_a_schematic():
    index = {'c1': [{'static_id': 'Blueprint_Musket_4', 'count': 2}, {'static_id': 'Wood', 'count': 40}]}
    musket, wood = _items('c1', index, _Data())
    assert musket.item_name == 'Musket Schematic 3' and musket.count == 2
    assert musket.icon == 't_itemicon_material_blueprint', 'the slot keeps the blueprint paper'
    assert musket.schematic.icon == 't_itemicon_weapon_musket', 'the UI draws the product over it'
    assert musket.schematic.product_name == 'Musket' and musket.schematic.rarity_name == 'Epic'
    assert wood.icon == 't_itemicon_material_wood' and wood.schematic is None


def test_shipped_schematics_cover_the_blueprints_and_every_product_has_an_icon():
    """data/json/schematics.json (generate_schematics.py) is optional, but when shipped it is complete."""
    p = DATA / 'schematics.json'
    if not p.exists():
        import pytest
        pytest.skip('schematics.json not generated')
    items = json.loads((DATA / 'items.json').read_text(encoding='utf-8'))
    buildings = json.loads((DATA / 'buildings.json').read_text(encoding='utf-8'))
    table = json.loads(p.read_text(encoding='utf-8'))['schematics']
    known = set(blueprint_ids(items))
    assert len(table) >= MIN_SCHEMATICS
    assert set(table) <= known
    assert len(known - set(table)) <= 5, sorted(known - set(table))   # retired ids only
    img = ROOT / 'frontend' / 'public' / 'img'
    for bp, e in table.items():
        row = (buildings if e['kind'] == 'building' else items)[e['product']]
        assert (img / f"{row['icon']}.webp").exists(), f'{bp} -> {e["product"]} has no icon on disk'
    assert table['Blueprint_Accessory_HeatColdResist_1_2'] == {'product': 'Accessory_HeatColdResist_1', 'kind': 'item'}
    assert table['Blueprint_WallTorch02'] == {'product': 'WallTorch02', 'kind': 'building'}
