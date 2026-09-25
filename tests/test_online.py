"""Online status: the REST player listing joined onto the parsed players by the Players/<id>.sav id."""
from types import SimpleNamespace

from backend.common.online import ids_from_listing, presence_key, stamp_online


class _Player(SimpleNamespace):
    def model_copy(self, update):
        return _Player(**{**vars(self), **update})


LISTING = {"players": [
    {"name": "Tism Princess", "playerId": "0C8E09B3000000000000000000000000", "userId": "steam_1"},
    {"name": "franky", "playerId": "F5E88537000000000000000000000000", "userId": "steam_2"},
    {"name": "ghost"},   # no id: ignored
]}


def test_presence_key_matches_rest_id_to_save_uid():
    assert presence_key("0C8E09B3000000000000000000000000") == presence_key("0c8e09b3-0000-0000-0000-000000000000")
    assert presence_key(None) == ""


def test_ids_from_listing_reads_the_players_array_or_a_bare_list():
    assert ids_from_listing(LISTING) == {"0c8e09b3000000000000000000000000", "f5e88537000000000000000000000000"}
    assert ids_from_listing(LISTING["players"]) == ids_from_listing(LISTING)
    assert ids_from_listing({}) == set()


def test_stamp_online_sets_true_false_or_unknown():
    players = [_Player(player_uid="0c8e09b3-0000-0000-0000-000000000000", online=None),
               _Player(player_uid="18169ce0-0000-0000-0000-000000000000", online=None),
               _Player(player_uid=None, online=None)]
    on = stamp_online(players, ids_from_listing(LISTING))
    assert [p.online for p in on] == [True, False, False]
    assert [p.online for p in stamp_online(players, None)] == [None, None, None]     # server did not answer
    assert players[0].online is None                                                  # the cached models are untouched
