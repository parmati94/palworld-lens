"""backend/common/paldeck.py -- the species deck and a player's capture bonus progress."""
from types import SimpleNamespace

from backend.common.breeding import BreedingIndex
from backend.common.exp_tables import build_exp_tables
from backend.common.pal_ids import SpeciesIndex
from backend.common.paldeck import (build_paldeck_tables, deck_aliases, deck_ids, deck_numbers, drops_for, filter_options, learnset_for,
                                    owned_by_species, player_progress, resolve_counts, spawn_summary, species_detail, species_rows)

PALS = {
    "SheepBall": {"is_pal": True, "pal_deck_index": 1, "localized_name": "Lamball", "description": "Fluffy.",
                  "element_types": ["Neutral"], "work_suitability": {"Handcraft": 1, "Transport": 1, "EmitFlame": 0},
                  "rarity": 1, "size": "XS", "male_probability": 50, "best_work_suitability": "Handcraft"},
    "Kitsunebi": {"is_pal": True, "pal_deck_index": 5, "localized_name": "Foxparks", "element_types": ["Fire"],
                  "work_suitability": {"EmitFlame": 1}, "rarity": 1},
    "Kitsunebi_Ice": {"is_pal": True, "pal_deck_index": 5, "localized_name": "Foxcicle", "element_types": ["Ice"],
                      "work_suitability": {"Cool": 1}, "rarity": 2, "nocturnal": True, "deck_suffix": "B"},
    "PlantSlime": {"is_pal": True, "pal_deck_index": 12, "localized_name": "Gumoss", "element_types": ["Grass"]},
    "PlantSlime_Flower": {"is_pal": True, "pal_deck_index": 12, "localized_name": "Gumoss", "element_types": ["Grass"],
                          "deck_entry_of": "PlantSlime"},                                  # the flower Gumoss: entry 12, not 12B
    "IceHorse": {"is_pal": True, "pal_deck_index": 200, "localized_name": "Frostallion", "element_types": ["Ice"],
                 "work_suitability": {"Cool": 4}, "rarity": 20},
    "BOSS_IceHorse": {"is_pal": True, "pal_deck_index": 200, "is_boss": True},          # boss form: not a deck row
    "Quest_Farmer03_SheepBall": {"is_pal": True, "pal_deck_index": 1},                  # scripted copy: not a deck row
    "GYM_ElecPanda": {"is_pal": True, "pal_deck_index": 0, "is_tower_boss": True},
    "YakushimaMonster001": {"is_pal": True, "pal_deck_index": 0},                       # no number: not in the deck
}
SPAWNS = {
    "herd_a": {"kind": "field", "points": {"MainMap": [[0, 0], [1, 1]]},
               "pals": {"SheepBall": {"share": 0.8, "level": [1, 3]}, "Kitsunebi": {"share": 0.2, "level": [2, 4], "time": "night"}}},
    "herd_b": {"kind": "field", "points": {"MainMap": [[5, 5]]},
               "pals": {"Kitsunebi": {"share": 1.0, "level": [3, 6], "time": "night"}}},
    "alpha": {"kind": "field_boss", "points": {"MainMap": [[9, 9]]},
              "pals": {"IceHorse": {"share": 1.0, "level": [50, 50], "boss": True}}},
    "room": {"kind": "dungeon", "points": {"MainMap": [[7, 7]]},
             "pals": {"Kitsunebi_Ice": {"share": 1.0, "level": [20, 25]}}},
    "flowers": {"kind": "field", "points": {"MainMap": [[2, 2]]},
                "pals": {"PlantSlime_Flower": {"share": 1.0, "level": [2, 4]}}},
}
BREEDING = {"pal_info": {k: {"combi_rank": 100 + i, "ignore_combi": k == "IceHorse"} for i, k in enumerate(("SheepBall", "Kitsunebi", "Kitsunebi_Ice", "IceHorse"))},
            "unique_combos": [{"parent_a": "Kitsunebi", "parent_b": "IceHorse", "child": "Kitsunebi_Ice"}],
            "child_to_parents_formula": {"SheepBall": [{"parent_a": "SheepBall", "parent_b": "SheepBall"}],
                                         "IceHorse": [{"parent_a": "IceHorse", "parent_b": "IceHorse"}]},
            "child_to_parents_unique": {"Kitsunebi_Ice": [{"parent_a": "Kitsunebi", "parent_b": "IceHorse"}]}}
EXP = build_exp_tables({str(i): {"BonusExp": 10 * (i + 1)} for i in range(20)},
                       {"1": {"TotalEXP": 0}, "2": {"TotalEXP": 50}, "3": {"TotalEXP": 200}})


def _drop_row(cid, level, *items):
    row = {"CharacterID": cid, "Level": level}
    for i in range(1, 11):
        item = items[i - 1] if i <= len(items) else ("None", 0.0, 0, 0)
        row[f"ItemId{i}"], row[f"Rate{i}"], row[f"min{i}"], row[f"Max{i}"] = item
    return row


DROP_ROWS = {
    "IceHorse000": _drop_row("IceHorse", 0, ("IceOrgan", 100.0, 10, 10), ("Diamond", 100.0, 1, 1)),
    "IceHorse080": _drop_row("IceHorse", 80, ("Relic", 100.0, 30, 50), ("IceOrgan", 100.0, 10, 10), ("Diamond", 100.0, 1, 1)),
    "BOSS_IceHorse000": _drop_row("BOSS_IceHorse", 0, ("PalCrystal_Ex", 100.0, 6, 8), ("IceOrgan", 0.0, 10, 10), ("Blueprint_X", 3.0, 1, 1)),
    "SheepBall000": _drop_row("SheepBall", 0, ("Wool", 100.0, 1, 3)),
}
WAZA_ROWS = {
    "IceHorse007": {"PalId": "IceHorse", "WazaID": "EPalWazaID::IceMissile", "Level": 7},
    "IceHorse001": {"PalId": "IceHorse", "WazaID": "EPalWazaID::AirCanon", "Level": 1},
    "BOSS_IceHorse001": {"PalId": "BOSS_IceHorse", "WazaID": "EPalWazaID::AirCanon", "Level": 1},
}
PALDECK_TABLES = build_paldeck_tables(DROP_ROWS, WAZA_ROWS)
ITEMS = {"IceOrgan": {"localized_name": "Ice Organ", "icon": "i_ice", "rarity": 0},
         "Diamond": {"localized_name": "Diamond", "icon": "i_dia", "rarity": 3}}
ACTIVE = {"EPalWazaID::IceMissile": {"localized_name": "Ice Missile", "element": "Ice", "power": 30, "cool_time": 3.0},
          "EPalWazaID::AirCanon": {"localized_name": "Air Cannon", "element": "Normal", "power": 25, "cool_time": 2.0}}


# IceHorse has a wild alpha spawn, so its obtain row must lose; Kitsunebi_Ice keeps its dungeon.
OBTAIN = {"species": {"IceHorse": {"how": "raid"}, "SheepBall": {"how": "meteor", "min_level": 13, "max_level": 51,
                                                                  "alpha": True, "regions": {"Grass": [13, 15]}}}}


class _Data:
    def __init__(self):
        self.pals = PALS
        self.spawns = SPAWNS
        self.partner_skills = {"IceHorse": {"name": "Ice Steed", "levels": []}}
        self.species = SpeciesIndex(PALS.keys())
        self.breeding = BreedingIndex(BREEDING, self.species)
        self.exp = EXP
        self.paldeck_tables = PALDECK_TABLES
        self.active_skills = ACTIVE
        self.obtain = OBTAIN

    def pal_name(self, sid):
        return (self.pals.get(sid) or {}).get("localized_name") or sid

    def item(self, item_id):
        return ITEMS.get(item_id) or {}


def _pal(iid, sid, level, owner="Envy", nickname=None, **kw):
    return SimpleNamespace(instance_id=iid, species_id=sid, name=sid, nickname=nickname, owner_uid=owner, level=level,
                           base_name=None, in_party=False, is_alpha=False, is_lucky=False, **kw)


def _player(name, level, exp, counts, bonus, index, chain=None):
    return SimpleNamespace(nickname=name, player_name=name, level=level, exp=exp,
                           records=SimpleNamespace(capture_counts=counts, capture_bonus=bonus, bonus_index=index,
                                                   chain_index=index if chain is None else chain))


def test_deck_numbers_give_subspecies_the_base_number_with_a_letter():
    assert deck_numbers(PALS) == {"SheepBall": "1", "Kitsunebi": "5", "Kitsunebi_Ice": "5B", "PlantSlime": "12", "IceHorse": "200"}
    assert deck_ids(PALS) == ["SheepBall", "Kitsunebi", "Kitsunebi_Ice", "PlantSlime", "IceHorse"]


def test_the_pak_suffix_places_a_subspecies_even_when_its_id_sorts_first():
    pals = {"Zed_Fire": {"is_pal": True, "pal_deck_index": 9},                       # would be the base by id shape...
            "Zed": {"is_pal": True, "pal_deck_index": 9, "deck_suffix": "B"}}         # ...but the pak says B
    assert deck_numbers(pals) == {"Zed_Fire": "9", "Zed": "9B"}
    no_pak = {"Zed_Fire": {"is_pal": True, "pal_deck_index": 9}, "Zed": {"is_pal": True, "pal_deck_index": 9}}
    assert deck_numbers(no_pak) == {"Zed": "9", "Zed_Fire": "9B"}                     # the old shape rule as fallback


def test_a_form_that_shares_an_entry_is_no_row_and_counts_for_its_entry():
    assert deck_aliases(PALS) == {"PlantSlime_Flower": "PlantSlime"}
    deck = set(deck_ids(PALS))
    raw = {"PlantSlime": 3, "PlantSlime_Flower": 2, "BOSS_PlantSlime_Flower": 1}
    assert resolve_counts(raw, SpeciesIndex(PALS.keys()), deck) == {"PlantSlime": 3}                     # without the aliases it is lost
    assert resolve_counts(raw, SpeciesIndex(PALS.keys()), deck, aliases=deck_aliases(PALS)) == {"PlantSlime": 6}
    owned = owned_by_species([_pal("a", "PlantSlime", 3), _pal("b", "PlantSlime_Flower", 4, owner="Ricky")], deck_aliases(PALS))
    assert owned["PlantSlime"]["count"] == 2 and owned["PlantSlime"]["owners"] == {"Envy", "Ricky"} and "PlantSlime_Flower" not in owned
    rows = species_rows(_Data(), [_pal("b", "PlantSlime_Flower", 4)])
    gum = next(r for r in rows if r["id"] == "PlantSlime")
    assert gum["owned"] == 1 and not any(r["id"] == "PlantSlime_Flower" for r in rows)
    detail = species_detail(_Data(), "PlantSlime", [], [_player("Envy", 2, 120, {"PlantSlime_Flower": 2}, {"PlantSlime_Flower": 2}, 2)])
    assert [g["name"] for g in detail["spawn_groups"]] == ["flowers"]                  # the flower spawner shows on Gumoss's card
    assert detail["caught_by"] == [{"name": "Envy", "caught": 2, "bonus": 2}]
    assert species_detail(_Data(), "PlantSlime_Flower", [], []) is None


def test_spawn_summary_says_how_you_get_one():
    s = spawn_summary(SPAWNS)
    assert s["SheepBall"] == {"how": "wild", "alpha": False, "min_level": 1, "max_level": 3, "night": False, "groups": 1}
    assert s["Kitsunebi"]["how"] == "wild" and s["Kitsunebi"]["night"] is True and s["Kitsunebi"]["max_level"] == 6
    assert s["IceHorse"]["how"] == "alpha" and s["IceHorse"]["alpha"] is True
    assert s["Kitsunebi_Ice"]["how"] == "dungeon"


def test_species_rows_are_the_deck_in_order_with_server_counts():
    pals = [_pal("a", "SheepBall", 3), _pal("b", "SheepBall", 7, owner="Ricky"), _pal("c", "IceHorse", 50), _pal("d", "SheepBall", 1)]
    rows = species_rows(_Data(), pals)
    assert [r["number"] for r in rows] == ["1", "5", "5B", "12", "200"]
    lam = rows[0]
    assert lam["name"] == "Lamball" and lam["owned"] == 3 and lam["owners"] == 2
    assert lam["work_suitability"] == {"Handcraft": 1, "Transport": 1}     # zero levels dropped
    assert lam["best_work"] == "Handcraft" and lam["breedable"] is True and lam["spawn"]["how"] == "wild"
    frost = rows[4]
    assert frost["partner_skill"] == "Ice Steed" and frost["owned"] == 1 and frost["spawn"]["how"] == "alpha"
    assert rows[2]["spawn"]["how"] == "dungeon" and rows[2]["owned"] == 0 and rows[2]["nocturnal"] is True


def test_resolve_counts_folds_boss_and_case_onto_deck_ids_and_caps():
    deck = set(deck_ids(PALS))
    raw = {"SheepBall": 4, "BOSS_SheepBall": 3, "kitsunebi": 2, "GYM_ElecPanda": 9, "Nope": 1, "Kitsunebi_Ice": 0}
    assert resolve_counts(raw, SpeciesIndex(PALS.keys()), deck) == {"SheepBall": 7, "Kitsunebi": 2}
    assert resolve_counts(raw, SpeciesIndex(PALS.keys()), deck, cap=5) == {"SheepBall": 5, "Kitsunebi": 2}


def test_player_progress_reads_the_chain_and_the_ladder():
    players = [
        _player("Envy", 2, 120, {"SheepBall": 9, "Kitsunebi": 2}, {"SheepBall": 5, "Kitsunebi": 2}, 7),
        _player("bagel", 1, 0, {}, {}, 0),
        SimpleNamespace(nickname="ghost", player_name="ghost", level=1, exp=0, records=None),   # no Players/*.sav
    ]
    deck = set(deck_ids(PALS))
    got = player_progress(players, SpeciesIndex(PALS.keys()), deck, EXP, rate=None)
    assert [p["name"] for p in got] == ["Envy", "bagel"]
    envy = got[0]
    assert envy["bonus_index"] == 7 and envy["chain_index"] == 7 and envy["next_bonus_exp"] == 80   # row 7 pays 80
    assert envy["exp_to_next_level"] == 80                                     # level 3 at 200 total
    assert envy["catches_to_next_level"] == 1                                  # 80 covers it
    assert envy["species_done"] == 1 and envy["species_started"] == 2
    assert envy["bonus_left"] == 0 + 3 + 5 + 5 + 5                             # 5 deck species, 25 slots
    assert envy["bonus"] == {"SheepBall": 5, "Kitsunebi": 2} and envy["caught"]["SheepBall"] == 9
    # the server's ExpRate scales what a catch pays, so fewer catches are needed
    doubled = player_progress(players[:1], SpeciesIndex(PALS.keys()), deck, EXP, rate=2.0)[0]
    assert doubled["next_bonus_exp"] == 160 and doubled["catches_to_next_level"] == 1
    assert got[1]["bonus_left"] == 25 and got[1]["catches_to_next_level"] == 3   # 10 + 20 + 30 >= 50
    # the table is read at the shared discovery chain, which runs ahead of the capture counter
    ahead = player_progress([_player("Envy", 2, 120, {}, {"SheepBall": 2}, 2, chain=9)], SpeciesIndex(PALS.keys()), deck, EXP, rate=None)[0]
    assert ahead["bonus_index"] == 2 and ahead["chain_index"] == 9 and ahead["next_bonus_exp"] == 100


def test_species_detail_joins_spawns_breeding_owned_and_catchers():
    data = _Data()
    pals = [_pal("a", "Kitsunebi", 12, nickname="Sparky"), _pal("b", "Kitsunebi", 30, owner="Ricky"), _pal("c", "SheepBall", 1)]
    players = [_player("Envy", 2, 120, {"Kitsunebi": 2, "BOSS_Kitsunebi": 1}, {"Kitsunebi": 3}, 7),
               _player("bagel", 1, 0, {"SheepBall": 1}, {"SheepBall": 1}, 1)]
    d = species_detail(data, "Kitsunebi", pals, players)
    assert d["number"] == "5" and d["name"] == "Foxparks" and d["spawn"]["how"] == "wild"
    assert [g["name"] for g in d["spawn_groups"]] == ["herd_a", "herd_b"]
    assert d["spawn_groups"][0] == {"name": "herd_a", "kind": "field", "level": [2, 4], "share": 0.2, "boss": False,
                                    "night": True, "layers": ["MainMap"], "points": 2}
    assert [o["name"] for o in d["owned"]] == ["Kitsunebi", "Sparky"] and d["owned_total"] == 2
    assert d["caught_by"] == [{"name": "Envy", "caught": 3, "bonus": 3}]
    ice = species_detail(data, "Kitsunebi_Ice", pals, players)
    assert ice["breeding"]["unique"] == [{"parent_a": "Kitsunebi", "parent_b": "IceHorse",
                                          "parent_a_name": "Foxparks", "parent_b_name": "Frostallion"}]
    frost = species_detail(data, "IceHorse", pals, players)
    assert frost["breeding"]["self_only"] is True and frost["breeding"]["pairs"] == 1
    assert species_detail(data, "BOSS_IceHorse", pals, players) is None
    assert species_detail(data, "Nope", pals, players) is None


def test_paldeck_tables_drop_rate_zero_entries_and_sort_by_level():
    t = PALDECK_TABLES
    assert [r["level"] for r in t["drops"]["IceHorse"]] == [0, 80]
    assert [i["item"] for i in t["drops"]["BOSS_IceHorse"][0]["items"]] == ["PalCrystal_Ex", "Blueprint_X"]   # rate 0 dropped
    assert t["learn"]["IceHorse"] == [{"skill": "EPalWazaID::AirCanon", "level": 1}, {"skill": "EPalWazaID::IceMissile", "level": 7}]


def test_drops_for_splits_base_high_level_extras_and_the_alpha_table():
    d = drops_for(PALDECK_TABLES, "IceHorse")
    assert [i["item"] for i in d["base"]] == ["IceOrgan", "Diamond"]
    assert d["high"] == [{"level": 80, "items": [{"item": "Relic", "rate": 100.0, "min": 30, "max": 50}]}]   # only what the row adds
    assert [i["item"] for i in d["alpha"]] == ["PalCrystal_Ex", "Blueprint_X"]
    assert drops_for(PALDECK_TABLES, "SheepBall") == {"base": [{"item": "Wool", "rate": 100.0, "min": 1, "max": 3}], "high": [], "alpha": []}
    assert drops_for(PALDECK_TABLES, "Nope") == {"base": [], "high": [], "alpha": []}
    assert drops_for({}, "IceHorse") == {"base": [], "high": [], "alpha": []}
    assert learnset_for(PALDECK_TABLES, "Nope") == [] and learnset_for({}, "IceHorse") == []


def test_species_detail_names_drops_and_learned_skills():
    d = species_detail(_Data(), "IceHorse", [], [])
    assert [(i["item_name"], i["rarity"], i["min"], i["max"]) for i in d["drops"]["base"]] == [("Ice Organ", 0, 10, 10), ("Diamond", 3, 1, 1)]
    assert d["drops"]["high"][0]["items"][0]["item_name"] == "Relic"      # unknown item keeps its id
    assert [i["item_id"] for i in d["drops"]["alpha"]] == ["PalCrystal_Ex", "Blueprint_X"]
    assert [(l["level"], l["name"], l["element"], l["power"]) for l in d["learnset"]] == [(1, "Air Cannon", "Normal", 25), (7, "Ice Missile", "Ice", 30)]
    assert species_detail(_Data(), "SheepBall", [], [])["learnset"] == []


def test_species_rows_carry_drop_and_skill_ids_and_filter_options_name_them():
    rows = species_rows(_Data(), [])
    frost = next(r for r in rows if r["id"] == "IceHorse")
    assert frost["drops"] == ["IceOrgan", "Diamond", "Relic", "PalCrystal_Ex", "Blueprint_X"]
    assert frost["learns"] == ["EPalWazaID::AirCanon", "EPalWazaID::IceMissile"]
    assert next(r for r in rows if r["id"] == "Kitsunebi")["drops"] == []
    f = filter_options(_Data(), rows)
    assert [(i["name"], i["count"]) for i in f["items"]][:3] == [("Blueprint_X", 1), ("Diamond", 1), ("Ice Organ", 1)]
    assert next(i for i in f["items"] if i["id"] == "Wool")["count"] == 1
    assert [(k["name"], k["element"], k["count"]) for k in f["skills"]] == [("Air Cannon", "Normal", 1), ("Ice Missile", "Ice", 1)]


def test_species_rows_fall_back_to_obtain_when_nothing_spawns_one():
    data = _Data()
    data.spawns = {k: v for k, v in SPAWNS.items() if "SheepBall" not in (v.get("pals") or {})}
    rows = {r["id"]: r for r in species_rows(data, [])}
    assert rows["SheepBall"]["spawn"]["how"] == "meteor" and rows["SheepBall"]["spawn"]["regions"] == {"Grass": [13, 15]}
    assert rows["IceHorse"]["spawn"]["how"] == "alpha"          # the spawner wins over the obtain row
    detail = species_detail(data, "SheepBall", [], [])
    assert detail["spawn"]["how"] == "meteor" and detail["spawn_groups"] == []
