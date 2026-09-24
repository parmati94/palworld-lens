"""Gear and food enhancements on the status screen, against the numbers a live player showed."""
from backend.common.loadout import build_loadout_tables, enhance_stats, food_effects, shield_max

ITEM_ROWS = {
    "StealHelmet": {"HPValue": 350, "PhysicalDefenseValue": 150, "ShieldValue": 0, "PassiveSkillName": "None"},
    "PlasticArmorWeight": {"HPValue": 1300, "PhysicalDefenseValue": 400, "ShieldValue": 0,
                           "PassiveSkillName": "TemperatureResist_Cold1", "PassiveSkillName2": "TemperatureResist_Heat1",
                           "PassiveSkillName3": "MaxInventoryWeight_up_Equip_3", "PassiveSkillName4": "None"},
    "Shield_04": {"HPValue": 0, "PhysicalDefenseValue": 0, "ShieldValue": 1045},
    "Accessory_Otomo": {"PassiveSkillName": "Attack_ACC_up1_Otomo_Only_Equip"},
    "Wood": {"HPValue": 0, "PhysicalDefenseValue": 0, "ShieldValue": 0, "PassiveSkillName": "None"},
}
FOOD_ROWS = {
    "Pizza": {"EffectTime": 600, "EffectType1": "EPalFoodStatusEffectType::WorkSpeed", "EffectValue1": 30,
              "EffectType2": "EPalFoodStatusEffectType::HungerResist", "EffectValue2": 25},
    "JamBun": {"EffectTime": 0, "EffectType1": "EPalFoodStatusEffectType::None", "EffectValue1": 0,
               "EffectType2": "EPalFoodStatusEffectType::None", "EffectValue2": 0},
}
PLAYER_ROWS = {"1": {"Stamina": 100, "Hp": 500, "MeleeAttack": 100, "ShotAttack": 100, "Defense": 100, "CraftSpeed": 100},
               "2": {"Stamina": 100, "Hp": 500, "MeleeAttack": 100, "ShotAttack": 100, "Defense": 100, "CraftSpeed": 100}}
PASSIVES = {
    "MaxInventoryWeight_up_Equip_3": {"effects": [{"type": "MaxInventoryWeight", "value": 200.0, "target": "ToSelf"}]},
    "TemperatureResist_Cold1": {"effects": [{"type": "TemperatureResist_Cold", "value": 1.0, "target": "ToSelf"}]},
    "TemperatureResist_Heat1": {"effects": [{"type": "TemperatureResist_Heat", "value": 1.0, "target": "ToSelf"}]},
    "Attack_ACC_up1_Otomo_Only_Equip": {"effects": [{"type": "ShotAttack", "value": 4.0, "target": "ToOtomo"}]},
}


def test_loadout_tables_keep_only_what_changes_a_stat():
    doc = build_loadout_tables(ITEM_ROWS, FOOD_ROWS, PLAYER_ROWS)
    assert doc["gear"] == {
        "StealHelmet": {"hp": 350, "defense": 150},
        "PlasticArmorWeight": {"hp": 1300, "defense": 400,
                               "passives": ["TemperatureResist_Cold1", "TemperatureResist_Heat1", "MaxInventoryWeight_up_Equip_3"]},
        "Shield_04": {"shield": 1045},
        "Accessory_Otomo": {"passives": ["Attack_ACC_up1_Otomo_Only_Equip"]},
    }
    assert doc["food"] == {"Pizza": {"seconds": 600, "effects": [{"type": "WorkSpeed", "value": 30.0}, {"type": "HungerResist", "value": 25.0}]}}
    assert doc["player_base"] == {"hp": 500, "stamina": 100, "attack": 100, "defense": 100, "work_speed": 100}


def test_envys_status_screen():
    # Level 63 with 14/10/11/13/13 points: base 1900 / 490 / 132 / 100 / 1450 / 1650. The screen showed
    # 3550 / 490 / 132 / 650 / 1885 / 1850 with a helm, weight armour, a Hyper Shield and a Pizza running.
    tables = build_loadout_tables(ITEM_ROWS, FOOD_ROWS, PLAYER_ROWS)
    base = {"hp": 1900, "stamina": 490, "attack": 132, "defense": 100, "work_speed": 1450, "weight": 1650}
    s = enhance_stats(base, ["StealHelmet", "PlasticArmorWeight", "Shield_04", "Accessory_Otomo"], "Pizza", tables, PASSIVES)
    assert s["hp"] == {"base": 1900, "gear": 1650, "food": 0, "total": 3550}
    assert s["defense"] == {"base": 100, "gear": 550, "food": 0, "total": 650}
    assert s["weight"] == {"base": 1650, "gear": 200, "food": 0, "total": 1850}
    assert s["work_speed"] == {"base": 1450, "gear": 0, "food": 435, "total": 1885}
    assert s["stamina"]["total"] == 490 and s["attack"]["total"] == 132      # the ToOtomo passive does not touch the player
    assert shield_max(["StealHelmet", "Shield_04"], tables) == 1045
    assert food_effects("Pizza", tables) == [{"type": "WorkSpeed", "value": 30.0}, {"type": "HungerResist", "value": 25.0}]


def test_no_tables_means_no_enhancements():
    s = enhance_stats({"hp": 500}, ["StealHelmet"], "Pizza", {}, {})
    assert s["hp"] == {"base": 500, "gear": 0, "food": 0, "total": 500}
    assert s["weight"] == {"base": 0, "gear": 0, "food": 0, "total": 0}
    assert shield_max(["Shield_04"], {}) == 0 and food_effects(None, {}) == []
