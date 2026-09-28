"""backend/common/paldeck.py -- the species deck and a player's capture bonus progress."""
from types import SimpleNamespace

from backend.common.breeding import BreedingIndex
from backend.common.exp_tables import build_exp_tables
from backend.common.pal_ids import SpeciesIndex
from backend.common.paldeck import (deck_ids, deck_numbers, player_progress, resolve_counts, spawn_summary,
                                    species_detail, species_rows)

PALS = {
    "SheepBall": {"is_pal": True, "pal_deck_index": 1, "localized_name": "Lamball", "description": "Fluffy.",
                  "element_types": ["Neutral"], "work_suitability": {"Handcraft": 1, "Transport": 1, "EmitFlame": 0},
                  "rarity": 1, "size": "XS", "male_probability": 50, "best_work_suitability": "Handcraft"},
    "Kitsunebi": {"is_pal": True, "pal_deck_index": 5, "localized_name": "Foxparks", "element_types": ["Fire"],
                  "work_suitability": {"EmitFlame": 1}, "rarity": 1},
    "Kitsunebi_Ice": {"is_pal": True, "pal_deck_index": 5, "localized_name": "Foxcicle", "element_types": ["Ice"],
                      "work_suitability": {"Cool": 1}, "rarity": 2, "nocturnal": True},
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
}
BREEDING = {"pal_info": {k: {"combi_rank": 100 + i, "ignore_combi": k == "IceHorse"} for i, k in enumerate(("SheepBall", "Kitsunebi", "Kitsunebi_Ice", "IceHorse"))},
            "unique_combos": [{"parent_a": "Kitsunebi", "parent_b": "IceHorse", "child": "Kitsunebi_Ice"}],
            "child_to_parents_formula": {"SheepBall": [{"parent_a": "SheepBall", "parent_b": "SheepBall"}],
                                         "IceHorse": [{"parent_a": "IceHorse", "parent_b": "IceHorse"}]},
            "child_to_parents_unique": {"Kitsunebi_Ice": [{"parent_a": "Kitsunebi", "parent_b": "IceHorse"}]}}
EXP = build_exp_tables({str(i): {"BonusExp": 10 * (i + 1)} for i in range(20)},
                       {"1": {"TotalEXP": 0}, "2": {"TotalEXP": 50}, "3": {"TotalEXP": 200}})


class _Data:
    def __init__(self):
        self.pals = PALS
        self.spawns = SPAWNS
        self.partner_skills = {"IceHorse": {"name": "Ice Steed", "levels": []}}
        self.species = SpeciesIndex(PALS.keys())
        self.breeding = BreedingIndex(BREEDING, self.species)
        self.exp = EXP

    def pal_name(self, sid):
        return (self.pals.get(sid) or {}).get("localized_name") or sid


def _pal(iid, sid, level, owner="Envy", nickname=None, **kw):
    return SimpleNamespace(instance_id=iid, species_id=sid, name=sid, nickname=nickname, owner_uid=owner, level=level,
                           base_name=None, in_party=False, is_alpha=False, is_lucky=False, **kw)


def _player(name, level, exp, counts, bonus, index):
    return SimpleNamespace(nickname=name, player_name=name, level=level, exp=exp,
                           records=SimpleNamespace(capture_counts=counts, capture_bonus=bonus, bonus_index=index))


def test_deck_numbers_give_subspecies_the_base_number_with_a_letter():
    assert deck_numbers(PALS) == {"SheepBall": "1", "Kitsunebi": "5", "Kitsunebi_Ice": "5B", "IceHorse": "200"}
    assert deck_ids(PALS) == ["SheepBall", "Kitsunebi", "Kitsunebi_Ice", "IceHorse"]


def test_spawn_summary_says_how_you_get_one():
    s = spawn_summary(SPAWNS)
    assert s["SheepBall"] == {"how": "wild", "alpha": False, "min_level": 1, "max_level": 3, "night": False, "groups": 1}
    assert s["Kitsunebi"]["how"] == "wild" and s["Kitsunebi"]["night"] is True and s["Kitsunebi"]["max_level"] == 6
    assert s["IceHorse"]["how"] == "alpha" and s["IceHorse"]["alpha"] is True
    assert s["Kitsunebi_Ice"]["how"] == "dungeon"


def test_species_rows_are_the_deck_in_order_with_server_counts():
    pals = [_pal("a", "SheepBall", 3), _pal("b", "SheepBall", 7, owner="Ricky"), _pal("c", "IceHorse", 50), _pal("d", "SheepBall", 1)]
    rows = species_rows(_Data(), pals)
    assert [r["number"] for r in rows] == ["1", "5", "5B", "200"]
    lam = rows[0]
    assert lam["name"] == "Lamball" and lam["owned"] == 3 and lam["owners"] == 2
    assert lam["work_suitability"] == {"Handcraft": 1, "Transport": 1}     # zero levels dropped
    assert lam["best_work"] == "Handcraft" and lam["breedable"] is True and lam["spawn"]["how"] == "wild"
    frost = rows[3]
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
    assert envy["bonus_index"] == 7 and envy["next_bonus_exp"] == 80         # row 7 pays 80
    assert envy["exp_to_next_level"] == 80                                     # level 3 at 200 total
    assert envy["catches_to_next_level"] == 1                                  # 80 covers it
    assert envy["species_done"] == 1 and envy["species_started"] == 2
    assert envy["bonus_left"] == 0 + 3 + 5 + 5                                 # 4 deck species, 20 slots
    assert envy["bonus"] == {"SheepBall": 5, "Kitsunebi": 2} and envy["caught"]["SheepBall"] == 9
    # the server's ExpRate scales what a catch pays, so fewer catches are needed
    doubled = player_progress(players[:1], SpeciesIndex(PALS.keys()), deck, EXP, rate=2.0)[0]
    assert doubled["next_bonus_exp"] == 160 and doubled["catches_to_next_level"] == 1
    assert got[1]["bonus_left"] == 20 and got[1]["catches_to_next_level"] == 3   # 10 + 20 + 30 >= 50


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
