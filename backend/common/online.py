"""Who is on the server right now, from the game's REST API.

The save never says who is online (LastOnlineDateTime is the last LOGIN), but the
server's REST API `/v1/api/players` lists the players connected at this moment, keyed
by `playerId` -- the Players/<id>.sav filename, which the parser exposes as
PlayerInfo.player_uid. One short-lived cache serves every caller (each SSE client
rebuilds its payload on a reload, and /api/players is called on top), so a reload
costs the game server one request however many tabs are open. Any failure means
"unknown", never a stall: the reload path must not wait on the game server.
"""
import asyncio
import time
from typing import Iterable, List, Optional, Set

import httpx

from backend.common.config import config
from backend.common.logging_config import get_logger

logger = get_logger(__name__)

TIMEOUT = 2.0        # seconds; the game server is on the LAN or not answering
CACHE_TTL = 10.0     # seconds; autosaves are ~30 s apart, tabs reload together

_cache: dict = {"at": 0.0, "ids": None}
_lock = asyncio.Lock()


def presence_key(player_id) -> str:
    """The REST `playerId` (upper hex, no dashes) and our `player_uid` (lower, dashed) as one key."""
    return str(player_id or "").replace("-", "").lower()


def ids_from_listing(listing) -> Set[str]:
    """The keys of the players in a REST `/v1/api/players` response body."""
    rows = listing.get("players") if isinstance(listing, dict) else listing
    return {presence_key(r.get("playerId")) for r in (rows or []) if isinstance(r, dict) and r.get("playerId")}


def configured() -> bool:
    return bool(config.RCON_HOST and config.RCON_PASSWORD)


async def fetch_online_ids() -> Optional[Set[str]]:
    """Keys of the players online now; None when not configured or the server did not answer."""
    if not configured():
        return None
    async with _lock:
        now = time.monotonic()
        if _cache["ids"] is not None and now - _cache["at"] < CACHE_TTL:
            return _cache["ids"]
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                r = await client.get(f"http://{config.RCON_HOST}:{config.RCON_PORT}/v1/api/players",
                                     auth=("admin", config.RCON_PASSWORD))
            if r.status_code != 200:
                logger.warning(f"online check: HTTP {r.status_code} from the game server")
                return None
            ids = ids_from_listing(r.json())
        except Exception as e:      # timeout, refused, bad JSON: unknown, not an error for the reload
            logger.warning(f"online check: {type(e).__name__}: {e}")
            return None
        _cache.update(at=now, ids=ids)
        return ids


def stamp_online(players: Iterable, online_ids: Optional[Set[str]]) -> List:
    """Copies of the player models with `online` set: True/False against the listing, None when unknown."""
    out = []
    for p in players:
        online = None if online_ids is None else presence_key(getattr(p, "player_uid", None)) in online_ids
        out.append(p.model_copy(update={"online": online}) if hasattr(p, "model_copy") else p)
    return out


async def with_online(players: Iterable) -> List:
    return stamp_online(players, await fetch_online_ids())
