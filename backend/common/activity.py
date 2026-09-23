"""Base activity: what a base is doing right now, from the save's work and machine records.

Pure helpers shared by the datagen (generate_activity_tables.py builds
data/json/activity.json from the pak) and the builder
(backend/parser/builders/activity.py joins the save with that table).

What the save records, and how it is read here
----------------------------------------------
* Machines (PalMapObjectConvertItemModel: furnaces, benches, mills, kitchens,
  sphere lines) carry `current_recipe_id`, `remain_product_num` (what is left of
  the order) and `requested_product_num` (how many the inputs on hand can make).
* Every worked building has a work record (WorkSaveData) with the amount one
  unit needs and how far the current unit is, plus the pals assigned. The
  save-tools parser labels those two floats `current_work_amount` and
  `auto_work_self_amount_by_sec`; against real saves the first is the per-unit
  requirement (recipe WorkAmount / the machine's speed rate) and the second the
  progress on the unit in hand, so those are the names used here.
* Crops (FarmBlockV2) cycle through phases; `current_state` says which, and the
  assign table (DT_MapObjectAssignData_Common, rows FarmBlockV2_<crop>_<state>)
  names the work each needs: 5 planting (Seeding), 2 watering, 4 harvesting
  (Collection); 3 is the timed growing phase with no work row. Progress lives in
  a different field per phase: `crop_progress_rate_value` for planting and
  harvesting (= the work record's done / unit), `water_stack_rate_value` for
  watering, `state_machine.growup_progress_time / growup_required_time` for
  growing. Verified on a 58-plot save except growing, which no plot was in.
* Incubators hold the egg item in their container and, once hatched, the whole
  pal in `hatched_character_save_parameter` until someone picks it up.
* Expedition stations (CharacterTeamMissionModel) carry the mission id (upper
  case in the save, mixed case in the table), the pals sent (auto-assign sends
  about a hundred) and a start time in the world's real-time ticks
  (GameTimeSaveData.RealDateTimeTicks advances with wall time; verified live);
  the mission table says how long it takes. `state` 2 = out, 3 = home.
* Lab research lives on the guild (GuildExtraSaveDataMap.Lab): the research in
  progress and the work put into each one; the lab table says how much it needs.
* Generators (GenerateEnergyModel) carry `stored_energy_amount`; the capacity is
  not in any data table but on each generator's blueprint (MaxEnergyStorage),
  which the datagen dumps so the card can show a fill percentage.

Timers are only as fresh as the save: every figure is "as of" the save time.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

NONE = 'None'
TICKS_PER_SECOND = 10_000_000       # GameTimeSaveData.RealDateTimeTicks: 100 ns ticks
MIN_LAB_RESEARCH = 100
MIN_MISSIONS = 10
MIN_GENERATORS = 3                  # Power Generator, Large, Manual, Ancient, the battery
GENERATOR_TYPE_B = 'Infra_GeneratePower'
IDLE_UNIT = -1.0                    # a machine with no order keeps -1 in the per-unit slot
CROP_PHASES = {5: 'planting', 2: 'watering', 3: 'growing', 4: 'harvesting'}

# Concrete model class -> the kind of card the UI draws. Anything else at a base is furniture.
KINDS = {
    'PalMapObjectConvertItemModel': 'machine',
    'PalMapObjectProductItemModel': 'station',
    'PalMapObjectFarmBlockV2Model': 'crop',
    'PalMapObjectHatchingEggModel': 'incubator',
    'PalMapObjectMultiHatchingEggModel': 'incubator',
    'PalMapObjectMonsterFarmModel': 'ranch',
    'PalMapObjectBreedFarmModel': 'breeding',
    'PalMapObjectGenerateEnergyModel': 'generator',
    'PalMapObjectCharacterTeamMissionModel': 'expedition',
    'PalMapObjectLabModel': 'lab',
}


def _text(rows: Dict[str, Dict], key: str) -> Optional[str]:
    td = (rows.get(key) or {}).get('TextData') or {}
    return td.get('LocalizedString') or td.get('SourceString') or None


def _enum(v: Any) -> str:
    return str(v or '').split('::')[-1]


def _find_number(obj: Any, key: str) -> Optional[float]:
    """First numeric `key` anywhere in a dumped blueprint (its properties sit in a nested export list)."""
    if isinstance(obj, dict):
        if key in obj and isinstance(obj[key], (int, float)):
            return float(obj[key])
        for v in obj.values():
            found = _find_number(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_number(v, key)
            if found is not None:
                return found
    return None


def energy_from_blueprint(blueprint: Any) -> Optional[Dict[str, Optional[float]]]:
    """{capacity, rate} from a generator blueprint dump; None when it has no MaxEnergyStorage."""
    capacity = _find_number(blueprint, 'MaxEnergyStorage')
    if not capacity:
        return None
    return {'capacity': capacity, 'rate': _find_number(blueprint, 'GenerateEnergyRateByWorker')}


def generator_ids(build_rows: Dict[str, Dict]) -> List[str]:
    """Build-object rows that generate or bank power (TypeB Infra_GeneratePower)."""
    return sorted(k for k, r in build_rows.items() if _enum(r.get('TypeB')) == GENERATOR_TYPE_B)


def build_activity_tables(lab_rows: Dict[str, Dict], lab_text: Dict[str, Dict],
                          mission_rows: Dict[str, Dict], mission_text: Dict[str, Dict],
                          recipe_rows: Dict[str, Dict],
                          generator_blueprints: Optional[Dict[str, Any]] = None) -> Dict[str, Dict]:
    """The tables data/json/activity.json ships, from the raw pak dumps.

    generator_blueprints: build-object id -> the dumped blueprint (obj) for each power building.
    """
    lab = {}
    for rid, r in lab_rows.items():
        lab[rid] = {
            'name': _text(lab_text, r.get('TextId') or '') or rid,
            'work': float(r.get('RequiredWorkAmount') or 0),
            'category': _enum(r.get('LabCategoryWorkSuitability')) or None,
            'requires': None if (r.get('RequiredResearchId') or NONE) == NONE else r['RequiredResearchId'],
        }
    expeditions = {}
    for mid, r in mission_rows.items():
        expeditions[mid] = {
            'name': _text(mission_text, r.get('TitleTextId') or '') or mid,
            'seconds': int(r.get('RequiredSeconds') or 0),
            'difficulty': _enum(r.get('Difficulty')) or None,
        }
    recipe_products = {rid: r['Product_Id'] for rid, r in recipe_rows.items()
                       if r.get('Product_Id') and r['Product_Id'] != NONE and r['Product_Id'] != rid}
    generators = {}
    for oid, bp in (generator_blueprints or {}).items():
        energy = energy_from_blueprint(bp)
        if energy:
            generators[oid] = energy
    return {'lab': dict(sorted(lab.items())), 'expeditions': dict(sorted(expeditions.items())),
            'recipe_products': dict(sorted(recipe_products.items())), 'generators': dict(sorted(generators.items()))}


def fraction(done: Optional[float], total: Optional[float]) -> Optional[float]:
    """done/total clamped to 0..1; None when there is no total to measure against."""
    if total is None or done is None or total <= 0:
        return None
    return max(0.0, min(1.0, float(done) / float(total)))


def _unit(v: Optional[float]) -> Optional[float]:
    return None if v is None else max(0.0, min(1.0, float(v)))


def crop_phase(state: Optional[int], work_rate: Optional[float], watered: Optional[float],
               grow_progress: Optional[float], grow_required: Optional[float],
               unit: Optional[float] = None, done: Optional[float] = None) -> Dict[str, Any]:
    """{phase, progress} for a plot: which step of plant -> water -> grow -> harvest it is on, and how far."""
    phase = CROP_PHASES.get(state) if state is not None else None
    if phase == 'watering':
        progress = _unit(watered)
    elif phase == 'growing':
        progress = fraction(grow_progress, grow_required)
    elif phase in ('planting', 'harvesting'):
        progress = _unit(work_rate) if work_rate is not None else fraction(done, unit)
    else:
        progress = None
    return {'phase': phase, 'progress': progress}


def ticks_to_seconds(ticks: Optional[int]) -> Optional[float]:
    return None if ticks is None else float(ticks) / TICKS_PER_SECOND


def expedition_state(mission_id: Optional[str], start_ticks: Optional[int], now_ticks: Optional[int],
                     seconds: Optional[int]) -> Dict[str, Any]:
    """'idle' (nothing sent), 'out' (still away, with seconds_left), or 'back' (time is up, haul waiting)."""
    if not mission_id or mission_id == NONE:
        return {'state': 'idle', 'seconds_left': None, 'elapsed': None}
    if start_ticks is None or now_ticks is None or not seconds:
        return {'state': 'out', 'seconds_left': None, 'elapsed': None}
    elapsed = max(0.0, (now_ticks - start_ticks) / TICKS_PER_SECOND)
    left = seconds - elapsed
    return {'state': 'out' if left > 0 else 'back', 'seconds_left': max(0.0, left), 'elapsed': elapsed}


def lab_summary(lab_table: Dict[str, Dict], current_id: Optional[str], progress: Dict[str, float]) -> Dict[str, Any]:
    """The research in hand (with progress), how many are done, and the ones started but parked."""
    def entry(rid: str) -> Dict[str, Any]:
        row = lab_table.get(rid) or {}
        work = float(row.get('work') or 0)
        done = float(progress.get(rid) or 0)
        return {'research_id': rid, 'name': row.get('name') or rid, 'category': row.get('category'),
                'work': work, 'done': done, 'progress': fraction(done, work),
                'complete': bool(work) and done >= work}
    entries = {rid: entry(rid) for rid in progress}
    current = entry(current_id) if current_id and current_id != NONE else None
    completed = sorted((e for e in entries.values() if e['complete']), key=lambda e: e['name'])
    parked = sorted((e for rid, e in entries.items() if not e['complete'] and e['done'] > 0
                     and rid != (current_id or '')), key=lambda e: -(e['progress'] or 0))
    return {'current': current, 'completed': len(completed), 'parked': parked,
            'known': len(lab_table)}
