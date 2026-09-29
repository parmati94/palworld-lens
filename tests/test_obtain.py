"""backend/common/obtain.py -- how you get the species nothing spawns in the wild."""
from backend.common.obtain import (HAND_ROWS, SPECIES_OVERRIDES, build_obtain, obtain_hows, obtain_levels,
                                   obtain_spawn)

MONSTER = {
    "SheepBall": {"IsPal": True, "IsRaidBoss": False},
    "NightLady": {"IsPal": True, "IsRaidBoss": False},
    "RAID_NightLady": {"IsPal": True, "IsRaidBoss": True},
    "RAID_NightLady_2": {"IsPal": True, "IsRaidBoss": True},
    "RAID_YakushimaBoss002_Hand_Left_2": {"IsPal": True, "IsRaidBoss": True},   # a multi-part collab boss
    "RAID_Fake": {"IsPal": True, "IsRaidBoss": False},                          # RAID_ name, not flagged
}
SUPPLY = {
    "DT_SupplyIncident_Pal": {"MONSTER0": {"CharacterID": {"Key": "DarkAlien"}, "Level": 22}},
    "DT_SupplyIncident_Pal_Grass01": {"MONSTER0": {"CharacterID": {"Key": "DarkAlien"}, "Level": 15},
                                      "MONSTER0_0": {"CharacterID": {"Key": "DarkAlien"}, "Level": 13}},
    "DT_SupplyIncident_Pal_DarkIsland_03": {"MONSTER0": {"CharacterID": {"Key": "BOSS_DarkAlien"}, "Level": 51},
                                            "NPC": {"CharacterID": {"Key": "None"}, "Level": 50}},
    "DT_SupplyIncident_Pal_Snow02": {"MONSTER0": {"CharacterID": {"Key": "BOSS_WhiteAlienDragon"}, "Level": 40},
                                     "MONSTER1": {"CharacterID": {"Key": "NightLady"}, "Level": 40}},
}
HAND = {"Mothman": {"how": "world_tree", "min_level": 78, "max_level": 78, "alpha": True, "place": "Shinespore Root"},
        "WorldTreeDragon": {"how": "none"}}
KNOWN = ["SheepBall", "NightLady", "DarkAlien", "WhiteAlienDragon", "Mothman", "WorldTreeDragon"]


def test_build_reads_raids_meteors_and_hand_rows():
    doc = build_obtain(MONSTER, SUPPLY, hand=HAND, known=KNOWN)
    s = doc["species"]
    assert s["NightLady"] == {"how": "raid", "alpha": False}       # a raid egg outranks the meteor sighting
    assert s["DarkAlien"]["how"] == "meteor" and s["DarkAlien"]["alpha"] is True
    assert (s["DarkAlien"]["min_level"], s["DarkAlien"]["max_level"]) == (13, 51)
    assert list(s["DarkAlien"]["regions"]) == ["Grass", "Any", "DarkIsland"]    # by level
    assert s["DarkAlien"]["regions"]["Grass"] == [13, 15]
    assert s["WhiteAlienDragon"] == {"how": "meteor", "alpha": True, "min_level": 40, "max_level": 40, "regions": {"Snow": [40, 40]}}
    assert s["Mothman"]["place"] == "Shinespore Root" and s["WorldTreeDragon"] == {"how": "none"}
    assert "YakushimaBoss002" not in s and "Fake" not in s and "SheepBall" not in s


def test_build_keeps_unknown_species_when_not_filtered():
    s = build_obtain(MONSTER, {}, hand={})["species"]
    assert set(s) == {"NightLady", "YakushimaBoss002"}       # the hand and head rows fold onto one species


def test_obtain_spawn_is_shaped_like_a_spawner_summary():
    doc = build_obtain(MONSTER, SUPPLY, hand=HAND, known=KNOWN)
    sp = obtain_spawn(doc, "DarkAlien")
    assert sp["how"] == "meteor" and sp["min_level"] == 13 and sp["night"] is False and sp["groups"] == 0
    assert sp["regions"]["Grass"] == [13, 15]
    assert obtain_spawn(doc, "Mothman")["place"] == "Shinespore Root"
    assert obtain_spawn(doc, "NightLady")["min_level"] is None
    assert obtain_spawn(doc, "SheepBall") is None and obtain_spawn({}, "SheepBall") is None


def test_levels_and_hows_cover_only_the_kinds_you_catch_at_a_level():
    doc = build_obtain(MONSTER, SUPPLY, hand=HAND, known=KNOWN)
    assert obtain_levels(doc) == {"DarkAlien": 13, "WhiteAlienDragon": 40, "Mothman": 78}
    assert obtain_hows(doc) == {"DarkAlien": "meteor", "WhiteAlienDragon": "meteor", "Mothman": "world_tree"}
    assert obtain_levels({}) == {}


def test_hand_rows_and_overrides_name_the_known_exceptions():
    assert HAND_ROWS["KingWhale"]["how"] == "story" and SPECIES_OVERRIDES["KingWhale"] == {"disabled": False}
    assert HAND_ROWS["WorldTreeDragon"] == {"how": "none"}
    assert {HAND_ROWS[s]["how"] for s in ("Mothman", "FlowerPrince")} == {"world_tree"}
