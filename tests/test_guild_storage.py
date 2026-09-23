"""1.0 Guild Chest: one shared container per guild, mirrored at every base a chest stands."""
from types import SimpleNamespace

from backend.parser.builders.base_containers import build_base_containers, build_guild_storage
from backend.parser.extractors.bases import BaseMeta
from backend.parser.extractors.guilds import get_guild_storage


class _Data:
    technologies = {"GuildChest": {"localized_name": "Guild Chest"}}
    buildings = {"GuildChest": {"icon": "t_icon_buildobject_guildchest"}, "ItemChest": {"icon": "chest"}}

    def item(self, static_id):
        return {"localized_name": static_id.title(), "icon": f"icon_{static_id}"}

    def schematic(self, static_id):
        return None


def _meta(base_id, guild, name):
    return BaseMeta(base_id=base_id, guild_id=guild, name=name, container_id="w" + base_id)


def _chest(base, map_object_id="GuildChest", concrete="PalMapObjectGuildChestModel", container_id=None, iid="x"):
    return {"concrete_type": concrete, "map_object_id": map_object_id, "base_camp_id": base,
            "instance_id": iid, "hp_current": 4000, "hp_max": 4000, "container_id": container_id}


META = {"b3": _meta("b3", "g1", "Base 3"), "b5": _meta("b5", "g1", "Base 5"), "b9": _meta("b9", "g2", "Base 1")}
ITEMS = {"shared-g1": [{"static_id": "Wood", "count": 9377}, {"static_id": "Stone", "count": 6280}],
         "own-1": [{"static_id": "Fiber", "count": 3}]}


def test_guild_chest_resolves_the_guilds_shared_container_at_each_base():
    storage = [_chest("b3", iid="a"), _chest("b5", iid="b"), _chest("b3", iid="c"),          # two chests at b3
               _chest("b5", "ItemChest", "PalMapObjectItemChestModel", "own-1", iid="d")]
    by_base = build_base_containers(META, [], storage, ITEMS, _Data(), guild_storage={"g1": "shared-g1", "g2": "shared-g2"})

    b3 = [c for c in by_base["b3"] if c.shared]
    assert len(b3) == 1, "one card per base even with two chests placed"
    card = b3[0]
    assert card.container_type == "guild" and card.guild_id == "g1" and card.container_id == "shared-g1"
    assert card.display_name == "Guild Chest" and card.building_icon == "t_icon_buildobject_guildchest"
    assert [(i.item_id, i.count) for i in card.items] == [("Wood", 9377), ("Stone", 6280)]
    assert [b.base_name for b in card.shared_at] == ["Base 3", "Base 5"]

    b5 = by_base["b5"]
    assert [c.container_type for c in b5] == ["guild", "storage"]
    assert b5[0].container_id == "shared-g1" and b5[1].container_id == "own-1" and not b5[1].shared
    assert "b9" not in by_base, "a guild with a container but no chest placed shows nothing"


def test_guild_storage_summary_is_one_entry_per_guild():
    storage = [_chest("b3", iid="a"), _chest("b5", iid="b"), _chest("b9", iid="c")]
    by_base = build_base_containers(META, [], storage, ITEMS, _Data(), guild_storage={"g1": "shared-g1"})
    summary = build_guild_storage(by_base)
    assert set(summary) == {"g1", "g2"}
    assert [b.base_id for b in summary["g1"].bases] == ["b3", "b5"]
    assert summary["g1"].container.total_item_count == 9377 + 6280
    assert summary["g2"].container.items == []       # g2 has no shared container id in this save


def test_get_guild_storage_reads_the_1_0_extra_block():
    world = {"GuildExtraSaveDataMap": {"value": [
        {"key": "g1", "value": {"GuildItemStorage": {"value": {"RawData": {"value": {"container_id": "c1"}}}}}},
        {"key": "g2", "value": {"Lab": {}}},                       # no storage block
        "junk",
    ]}}
    assert get_guild_storage(world) == {"g1": "c1"}
    assert get_guild_storage({}) == {}
