"""Player details from Players/*.sav: the kit, party, tech and records joined onto the player card."""
from types import SimpleNamespace

from backend.parser.builders.players import _kit, _party
from backend.parser.extractors.players import extract_player_details, net_ticks_to_iso


def _prop(v):
    return {"value": v}


def _guid_prop(gid):
    return {"value": {"ID": {"value": gid}}}


def _map(pairs):
    return {"value": [{"key": k, "value": v} for k, v in pairs]}


def _save_data(with_ancient=True):
    """A Players/*.sav SaveData.value the way save-tools parses it (only what the extractor reads)."""
    rec = {
        "TowerBossDefeatFlag": _map([("BOSS_BATTLE_NAME_GrassBoss", True), ("BOSS_BATTLE_NAME_ForestBoss", True)]),
        "NormalBossDefeatFlag": _map([("Alpha_A", True), ("Alpha_B", True), ("Alpha_C", False)]),
        "PaldeckUnlockFlag": _map([("SheepBall", True), ("PinkCat", True), ("Carbunclo", True), ("Kitsunebi", True)]),
        "PalCaptureCount": _map([("SheepBall", 10), ("PinkCat", 5), ("Carbunclo", 1)]),
        "FastTravelPointUnlockFlag": _map([(f"FT_{i}", True) for i in range(14)]),
        "NormalDungeonClearCount": _prop(1),
        "FixedDungeonClearCount": _prop(3),
    }
    sd = {
        "InventoryInfo": {"value": {
            "CommonContainerId": _guid_prop("bag-1"),
            "EssentialContainerId": _guid_prop("key-1"),
            "WeaponLoadOutContainerId": _guid_prop("wpn-1"),
            "PlayerEquipArmorContainerId": _guid_prop("arm-1"),
            "FoodEquipContainerId": _guid_prop("food-1"),
            "LanternEquipData": _prop({"EquipLanternItemId": _prop("Lantern")}),   # some players carry this; not a container
        }},
        "TechnologyPoint": _prop(11),
        "UnlockedRecipeTechnologyNames": {"value": {"values": ["Workbench", "PalSphere", "Campfire"]}},
        "RecordData": {"value": rec},
        "LastOnlineDateTime": _prop(639257695071730000),
    }
    if with_ancient:
        sd["bossTechnologyPoint"] = _prop(10)
    return sd


def test_player_details_come_from_the_players_sav():
    d = extract_player_details(_save_data())
    assert d["containers"] == {"bag": "bag-1", "key_items": "key-1", "weapons": "wpn-1", "gear": "arm-1", "food": "food-1"}
    assert d["tech"] == {"unlocked": 3, "points": 11, "ancient_points": 10}
    assert d["records"] == {"towers": 2, "alphas": 2, "paldeck": 4, "caught": 16, "fast_travels": 14, "dungeons": 4}
    assert d["last_online"] == "2026-09-23T14:11:47.173000+00:00"


def test_a_player_without_ancient_points_or_records_still_extracts():
    sd = _save_data(with_ancient=False)
    del sd["RecordData"]
    d = extract_player_details(sd)
    assert d["tech"]["ancient_points"] == 0
    assert d["records"] == {"towers": 0, "alphas": 0, "paldeck": 0, "caught": 0, "fast_travels": 0, "dungeons": 0}


def test_net_ticks_convert_to_utc_iso_and_zero_means_never():
    assert net_ticks_to_iso(621355968000000000 + 10_000_000) == "1970-01-01T00:00:01+00:00"
    assert net_ticks_to_iso(0) is None
    assert net_ticks_to_iso(None) is None


class _Data:
    _items = {"CopperHelmet": {"localized_name": "Copper Helmet", "icon": "i_helm", "rarity": 0, "type_b": "ArmorHead", "weight": 10.0},
              "Salad": {"localized_name": "Salad", "icon": "i_salad", "rarity": 1, "type_b": "FoodDishVegetable", "weight": 0.5},
              "BowGun_4": {"localized_name": "Crossbow", "icon": "i_xbow", "rarity": 2, "type_b": "WeaponCrossbow", "weight": 13.0},
              "Money": {"localized_name": "Gold Coin", "icon": "i_gold", "rarity": 0, "type_b": "Money", "weight": 0.0},
              "KeySphere_01": {"localized_name": "Key", "icon": "i_key", "rarity": 0, "type_b": "Essential"}}

    def item(self, item_id):
        return self._items.get(item_id) or {}


def test_kit_resolves_each_container_in_the_item_index():
    index = {"arm-1": [{"static_id": "CopperHelmet", "count": 1}],
             "wpn-1": [{"static_id": "BowGun_4", "count": 1}],
             "food-1": [{"static_id": "Salad", "count": 75}],
             "bag-1": [{"static_id": "Money", "count": 23453, "slot": 0}, {"static_id": "Salad", "count": 3, "slot": 4}, {"static_id": "Unknown_Thing", "count": 2, "slot": 9}],
             "key-1": [{"static_id": "KeySphere_01", "count": 1}]}
    kit = _kit({"gear": "arm-1", "weapons": "wpn-1", "food": "food-1", "bag": "bag-1", "key_items": "key-1"}, index, _Data(),
               {"bag-1": 45, "wpn-1": 6, "food-1": 5})
    assert [(i.item_name, i.count, i.rarity, i.slot, i.weight) for i in kit["gear"]] == [("Copper Helmet", 1, 0, "ArmorHead", 10.0)]
    assert (kit["weapon_slots"], kit["food_slots"]) == (6, 5)
    assert [i.item_name for i in kit["weapons"]] == ["Crossbow"]
    assert [(i.item_name, i.count) for i in kit["food"]] == [("Salad", 75)]
    assert [(i.item_name, i.count, i.slot_index) for i in kit["bag"]] == [("Gold Coin", 23453, 0), ("Salad", 3, 4), ("Unknown_Thing", 2, 9)]   # unknown ids keep their id
    assert kit["gold"] == 23453 and kit["bag_slots"] == 45
    assert [i.item_name for i in kit["key_items"]] == ["Key"]
    assert kit["carried_weight"] == 10.0 + 13.0 + 75 * 0.5 + 3 * 0.5   # 62.0; unknown items and gold weigh nothing
    empty = _kit({"gear": None}, index, _Data())
    assert empty["gear"] == [] and empty["bag_slots"] == 0 and empty["weapon_slots"] == 0 and empty["gold"] == 0
    assert _kit({"gear": "arm-1"}, index, None)["gear"] == []


def _pal(iid, name, container, slot, level=30):
    return SimpleNamespace(instance_id=iid, name=name, nickname=None, species_id=name, level=level,
                           image_candidates=[name.lower()], container_id=container, slot_index=slot)


def test_party_is_the_pals_in_the_party_container_in_slot_order():
    pals = [_pal("p3", "Chillet", "party-1", 2), _pal("p1", "Lamball", "party-1", 0),
            _pal("boxed", "Foxparks", "box-1", 0), _pal("p2", "Cattiva", "party-1", 1), _pal("p4", "Kitsun", "party-1", None)]
    assert [p.name for p in _party("party-1", pals)] == ["Lamball", "Cattiva", "Chillet", "Kitsun"]
    assert _party(None, pals) == []
