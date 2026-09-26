"""Palworld save file parser - main orchestrator.

`SaveFileParser.load()` reads the save once and builds every API model into a
`Snapshot`. The routers serve that snapshot; nothing is rebuilt per request.
A reload builds a new snapshot and swaps it in atomically.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from backend.models.models import ActivityPayload, SaveInfo, PalInfo, PlayerInfo, GuildInfo, BaseContainerInfo, GuildStorageInfo
from backend.parser.loaders.gvas_handler import GvasHandler
from backend.parser.loaders.data_loader import DataLoader
from backend.parser.loaders.schema_loader import SchemaManager
from backend.parser.extractors.characters import get_character_data, split_players
from backend.parser.extractors.guilds import get_guild_data, get_base_data, get_guild_storage
from backend.parser.extractors.bases import get_base_metadata, get_base_assignments
from backend.parser.extractors.structures import get_food_bowls, get_storage_containers, index_item_containers, index_container_sizes
from backend.parser.extractors.relationships import build_player_mapping, build_pal_ownership
from backend.parser.builders.pals import build_pals
from backend.parser.builders.players import build_players
from backend.parser.builders.guilds import build_guilds
from backend.parser.builders.base_containers import build_base_containers, build_guild_storage
from backend.parser.builders.activity import build_activity
from backend.parser.extractors.activity import (get_activity_objects, get_guild_labs, get_real_time_ticks, index_ground_eggs,
                                                index_works)
from backend.common.base_names import BaseNameStore
from backend.common.config import config
from backend.common.logging_config import get_logger

logger = get_logger(__name__)

SchemaManager.preload_all()


@dataclass
class Snapshot:
    """Everything the API serves, built once per save load."""
    info: SaveInfo
    players: List[PlayerInfo] = field(default_factory=list)
    guilds: List[GuildInfo] = field(default_factory=list)
    pals: List[PalInfo] = field(default_factory=list)
    base_containers: Dict[str, List[BaseContainerInfo]] = field(default_factory=dict)
    guild_storage: Dict[str, GuildStorageInfo] = field(default_factory=dict)
    activity: ActivityPayload = field(default_factory=ActivityPayload)


EMPTY = Snapshot(info=SaveInfo(world_name="Not Loaded", loaded=False))


class SaveFileParser:
    """Loads a save and exposes the built snapshot."""

    def __init__(self):
        self.gvas = GvasHandler()
        self.data = DataLoader()
        self.base_names = BaseNameStore(config.APP_STATE_PATH)
        self.snapshot: Snapshot = EMPTY

    def load(self) -> bool:
        """Load the save files and build a fresh snapshot. False on failure (old snapshot kept)."""
        if not self.gvas.load():
            return False
        try:
            self.snapshot = self._build()
        except Exception as e:
            logger.error(f"Failed to build snapshot: {e}", exc_info=True)
            return False
        logger.info(f"Snapshot built: {len(self.snapshot.players)} players, {len(self.snapshot.guilds)} guilds, "
                    f"{len(self.snapshot.pals)} pals, {len(self.snapshot.base_containers)} bases with containers")
        return True

    def reload(self) -> bool:
        logger.info("🔄 Reloading save file...")
        return self.load()

    def _build(self) -> Snapshot:
        world = self.gvas.world_data
        started = datetime.now()

        # Walk each save collection exactly once
        char_data = get_character_data(world)
        player_data = split_players(char_data)
        guild_data = get_guild_data(world)
        base_meta = get_base_metadata(get_base_data(world), landmarks=self.data.map_objects,
                                      layers=self.data.map_layers, custom_names=self.base_names.load())
        item_index = index_item_containers(world)
        food_bowls = get_food_bowls(world)
        storage = get_storage_containers(world)

        player_uid_to_containers, player_names = build_player_mapping(
            player_data, guild_data, base_meta, self.gvas.players_dir)
        pal_to_owner = build_pal_ownership(world, player_uid_to_containers)
        base_assignments = get_base_assignments(char_data, base_meta)

        party_containers = {d["party_container_id"] for d in player_uid_to_containers.values() if d.get("party_container_id")}
        pals = build_pals(char_data, base_assignments, self.data, pal_to_owner, party_containers=party_containers)
        container_sizes = index_container_sizes(world)
        players = build_players(player_data, guild_data, player_uid_to_containers,
                                item_index=item_index, data=self.data, pals=pals, container_sizes=container_sizes)
        guilds = build_guilds(guild_data, base_meta, player_names)
        containers = build_base_containers(base_meta, food_bowls, storage, item_index, self.data,
                                           guild_storage=get_guild_storage(world), container_sizes=container_sizes)
        guild_storage = build_guild_storage(containers)
        activity = build_activity(get_activity_objects(world), index_works(world), get_guild_labs(world), base_meta,
                                  item_index, pals, self.data, get_real_time_ticks(world),
                                  container_sizes=container_sizes,
                                  ground_eggs=index_ground_eggs(world, item_index))

        info = self._save_info(player_count=len(player_data), pal_count=len(char_data) - len(player_data),
                               guild_count=len(guilds))
        logger.debug(f"snapshot build took {(datetime.now() - started).total_seconds():.2f}s")
        return Snapshot(info=info, players=players, guilds=guilds, pals=pals, base_containers=containers,
                        guild_storage=guild_storage, activity=activity)

    def _save_info(self, player_count: int, pal_count: int, guild_count: int) -> SaveInfo:
        level_path = self.gvas.level_sav_path
        file_size = level_meta_path = level_meta_size = None
        if level_path and level_path.exists():
            file_size = level_path.stat().st_size
            meta = level_path.parent / "LevelMeta.sav"
            if meta.exists():
                level_meta_path, level_meta_size = str(meta), meta.stat().st_size
        return SaveInfo(
            world_name=self.gvas.world_name or "My World",
            loaded=True,
            level_path=str(level_path) if level_path else None,
            level_meta_path=level_meta_path,
            player_count=player_count,
            guild_count=guild_count,
            pal_count=pal_count,
            last_updated=self.gvas.last_load_time.isoformat() if self.gvas.last_load_time else None,
            file_size=file_size,
            level_meta_size=level_meta_size,
        )

    # ------------------------------------------------------------------
    @property
    def loaded(self) -> bool:
        return self.gvas.loaded and self.snapshot.info.loaded

    @property
    def last_load_time(self) -> Optional[datetime]:
        return self.gvas.last_load_time

    def get_save_info(self) -> SaveInfo:
        return self.snapshot.info

    def get_players(self) -> List[PlayerInfo]:
        return self.snapshot.players

    def get_guilds(self) -> List[GuildInfo]:
        return self.snapshot.guilds

    def get_pals(self) -> List[PalInfo]:
        return self.snapshot.pals

    def get_base_containers(self) -> Dict[str, List[BaseContainerInfo]]:
        return self.snapshot.base_containers

    def get_guild_storage(self) -> Dict[str, GuildStorageInfo]:
        return self.snapshot.guild_storage

    def get_activity(self) -> ActivityPayload:
        return self.snapshot.activity

    def activity_payload(self) -> Dict:
        return self.snapshot.activity.model_dump()

    def rename_base(self, base_id: str, name: Optional[str]) -> Optional[str]:
        """Store a custom name (blank = back to "Base N") and patch the live snapshot.

        Cheaper than a rebuild, and the next reload derives the same names
        from the store anyway. Returns the stored name, or None when cleared.
        """
        alive = [b.base_id for g in self.snapshot.guilds for b in g.base_locations]
        stored = self.base_names.set(base_id, name, keep=alive)
        number = next((b.number for g in self.snapshot.guilds for b in g.base_locations if b.base_id == base_id), 0)
        shown = stored or f"Base {number}"
        for g in self.snapshot.guilds:
            for b in g.base_locations:
                if b.base_id == base_id:
                    b.base_name = shown
        for p in self.snapshot.pals:
            if p.base_id == base_id:
                p.base_name = shown
        for cards in self.snapshot.base_containers.values():
            for c in cards:
                if c.base_id == base_id:
                    c.base_name = shown
                for at in c.shared_at:
                    if at.base_id == base_id:
                        at.base_name = shown
        for gs in self.snapshot.guild_storage.values():
            for at in gs.bases:
                if at.base_id == base_id:
                    at.base_name = shown
        return stored

    def base_names_payload(self) -> Dict:
        return {"names": dict(self.base_names.names), "writable": self.base_names.writable}

    def base_containers_payload(self) -> Dict:
        """The /api/base-containers body, also embedded in the watch stream."""
        by_base = self.snapshot.base_containers
        return {
            "containers": {base_id: [c.model_dump() for c in cs] for base_id, cs in by_base.items()},
            "guild_storage": {gid: g.model_dump() for gid, g in self.snapshot.guild_storage.items()},
            "count": len(by_base),
        }


# Global parser instance
parser = SaveFileParser()
