"""Join the save's activity records with the game data and the pal list into Activity cards.

Inputs come from extractors/activity.py (buildings, works, guild labs, the
world clock), extractors/structures.index_item_containers (what sits in each
building), the built PalInfo list (names and icons for assigned pals) and the
DataLoader (item and building names, data/json/activity.json).
"""
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from backend.common.activity import IDLE_UNIT, expedition_state, fraction, lab_summary
from backend.common.logging_config import get_logger
from backend.common import pal_icons
from backend.models.models import (ActivityJob, ActivityPal, ActivityPayload, BaseActivity, CropInfo, EggInfo,
                                   ExpeditionInfo, GuildActivity, ItemRef, LabInfo, LabResearch)
from backend.parser.extractors.bases import BaseMeta
from backend.parser.loaders.data_loader import DataLoader
from backend.parser.utils.mappers import map_building_name

logger = get_logger(__name__)

STATUS_ORDER = {"ready": 0, "working": 1, "unstaffed": 2, "no_materials": 3, "idle": 4}


def _item(data: DataLoader, item_id: str, count: int = 0) -> ItemRef:
    row = data.item(item_id)
    rarity = row.get("rarity")
    return ItemRef(item_id=item_id, item_name=row.get("localized_name") or item_id, icon=row.get("icon"),
                   rarity=rarity if isinstance(rarity, int) and 0 <= rarity <= 4 else None, count=count)


def _pal(p) -> ActivityPal:
    return ActivityPal(instance_id=p.instance_id, name=getattr(p, "nickname", None) or p.name,
                       species_id=getattr(p, "species_id", None), image_candidates=list(p.image_candidates),
                       level=int(getattr(p, "level", 0) or 0))


def _pals(ids: Iterable[str], by_id: Dict[str, object]) -> List[ActivityPal]:
    return [_pal(by_id[i]) for i in ids if i in by_id]


def _contents(container_id: Optional[str], item_index: Dict[str, List[Dict]], data: DataLoader) -> List[ItemRef]:
    return [_item(data, e["static_id"], e["count"]) for e in item_index.get(container_id or "", [])]


def _job(obj: Dict, data: DataLoader, meta: BaseMeta) -> ActivityJob:
    building_type = obj.get("map_object_id") or ""
    hp_max = obj.get("hp_max")
    return ActivityJob(
        instance_id=obj.get("instance_id") or "",
        kind=obj["kind"],
        building_type=building_type,
        display_name=map_building_name(building_type, data),
        building_icon=(data.buildings.get(building_type) or {}).get("icon"),
        base_id=meta.base_id,
        status="idle",
        is_damaged=bool(hp_max) and hp_max > 0 and (obj.get("hp_current") or 0) < hp_max,
    )


def build_activity(objects: List[Dict], works: Dict[str, Dict], labs: Dict[str, Dict], base_meta: Dict[str, BaseMeta],
                   item_index: Dict[str, List[Dict]], pals: List, data: DataLoader,
                   now_ticks: Optional[int]) -> ActivityPayload:
    by_pal = {p.instance_id: p for p in pals}
    tables = data.activity
    bases: Dict[str, List[ActivityJob]] = defaultdict(list)
    guilds: Dict[str, GuildActivity] = {}
    lab_objects: Dict[str, Dict] = {}   # guild -> the lab building (first one)

    for obj in objects:
        meta = base_meta.get(obj.get("base_camp_id") or "")
        if not meta:
            continue
        job = _job(obj, data, meta)
        work = works.get(obj.get("work_id") or "") or {}
        job.assigned = _pals(work.get("assigned") or [], by_pal)
        contents = _contents(obj.get("container_id"), item_index, data)
        kind = job.kind

        if kind == "machine":
            rid = obj.get("recipe_id")
            job.recipe_id = rid
            job.order_remaining = int(obj.get("order_remaining") or 0)
            job.craftable_now = int(obj.get("craftable_now") or 0)
            unit, done = work.get("unit"), work.get("done")
            if rid:
                product_id = tables["recipe_products"].get(rid, rid)
                job.product = _item(data, product_id)
                job.outputs = [c for c in contents if c.item_id == product_id]
                job.inputs = [c for c in contents if c.item_id != product_id]
                if unit is not None and unit > 0:
                    job.unit_work, job.unit_done, job.progress = unit, done, fraction(done, unit)
                if job.order_remaining <= 0:
                    job.status = "ready"
                elif job.assigned:
                    job.status = "working"
                elif job.craftable_now <= 0 and not job.inputs:
                    job.status = "no_materials"
                else:
                    job.status = "unstaffed"
            else:
                job.outputs = contents
                job.status = "idle"

        elif kind == "station":
            pid = obj.get("product_item_id")
            if pid:
                job.product = _item(data, pid)
            job.outputs = contents
            unit, done = work.get("unit"), work.get("done")
            if unit is not None and unit > 0 and unit != IDLE_UNIT:
                job.unit_work, job.unit_done, job.progress = unit, done, fraction(done, unit)
            job.status = "working" if job.assigned else "idle"

        elif kind == "crop":
            cid = obj.get("crop_id") or ""
            growth = fraction(obj.get("crop_progress"), obj.get("crop_required"))
            row = data.item(cid)
            job.crop = CropInfo(crop_id=cid, name=row.get("localized_name") or cid, icon=row.get("icon"),
                                growth=growth, watered=fraction(obj.get("crop_watered"), 1.0),
                                required_s=obj.get("crop_required"), progress_s=obj.get("crop_progress"))
            job.product = _item(data, cid) if row else None
            job.progress = growth
            watered = obj.get("crop_watered") or 0
            if growth is not None and growth >= 1.0:
                job.status = "ready"
            elif job.assigned or (growth or 0) > 0 or watered > 0:
                job.status = "working"
            else:
                job.status = "idle"          # a bare plot: nothing planted or watered, nobody on it

        elif kind == "incubator":
            eggs = [c for c in contents if c.item_id.startswith("PalEgg")]
            hatched = obj.get("hatched_character_id")
            job.egg = EggInfo(egg=eggs[0] if eggs else None,
                              hatched_species_id=hatched,
                              hatched_name=(obj.get("hatched_nickname") or (data.pal_name(hatched) if hatched else None)),
                              hatched_image_candidates=pal_icons.icon_candidates(hatched) if hatched else [])
            unit, done = work.get("unit"), work.get("done")
            if unit is not None and unit > 0:
                job.unit_work, job.unit_done, job.progress = unit, done, fraction(done, unit)
            if hatched:
                job.status = "ready"
            elif eggs:
                job.status = "ready" if (job.progress or 0) >= 1.0 else "working"
            else:
                job.status = "idle"
            job.outputs = eggs

        elif kind in ("ranch", "breeding", "generator"):
            job.outputs = contents
            if kind == "generator":
                job.stored_energy = obj.get("stored_energy")
            job.status = "working" if job.assigned else "idle"

        elif kind == "expedition":
            mid = obj.get("mission_id")
            row = tables["expeditions"].get(mid or "") or {}
            st = expedition_state(mid, obj.get("mission_start_ticks"), now_ticks, row.get("seconds"))
            job.expedition = ExpeditionInfo(mission_id=mid, name=row.get("name") or mid, difficulty=row.get("difficulty"),
                                            seconds=row.get("seconds"), state=st["state"],
                                            seconds_left=st["seconds_left"], elapsed=st["elapsed"],
                                            pals=_pals(obj.get("mission_pals") or [], by_pal), haul=contents)
            job.status = {"idle": "idle", "out": "working", "back": "ready"}[st["state"]]
            if st["state"] == "idle" and contents:
                job.status = "ready"         # nobody out, but the last haul is still in the station
            if meta.guild_id:
                guilds.setdefault(meta.guild_id, GuildActivity(guild_id=meta.guild_id)).expeditions.append(job)
            continue      # lives on the guild, not in the base's job list

        elif kind == "lab":
            if meta.guild_id and meta.guild_id not in lab_objects:
                lab_objects[meta.guild_id] = {"obj": obj, "job": job}
            continue

        bases[meta.base_id].append(job)

    # Labs: one per guild, research from the guild block, workers from the lab building's work record
    for guild_id, lab in labs.items():
        summary = lab_summary(tables["lab"], lab.get("current"), lab.get("progress") or {})
        placed = lab_objects.get(guild_id)
        if not placed and not lab.get("progress"):
            continue
        info = LabInfo(guild_id=guild_id,
                       base_id=placed["job"].base_id if placed else None,
                       current=LabResearch(**summary["current"]) if summary["current"] else None,
                       completed=summary["completed"], parked=[LabResearch(**p) for p in summary["parked"]],
                       known=summary["known"], assigned=placed["job"].assigned if placed else [])
        guilds.setdefault(guild_id, GuildActivity(guild_id=guild_id)).lab = info

    out: Dict[str, BaseActivity] = {}
    for base_id, jobs in bases.items():
        jobs.sort(key=lambda j: (STATUS_ORDER.get(j.status, 9), j.display_name.lower(), j.instance_id))
        out[base_id] = BaseActivity(
            base_id=base_id, jobs=jobs,
            working=sum(j.status == "working" for j in jobs),
            ready=sum(j.status == "ready" for j in jobs),
            stuck=sum(j.status in ("unstaffed", "no_materials") for j in jobs),
            idle=sum(j.status == "idle" for j in jobs),
        )
    for g in guilds.values():
        g.expeditions.sort(key=lambda j: (STATUS_ORDER.get(j.status, 9), j.instance_id))
    logger.info(f"Built activity for {len(out)} bases, {len(guilds)} guilds")
    return ActivityPayload(bases=out, guilds=guilds, as_of_ticks=now_ticks)
