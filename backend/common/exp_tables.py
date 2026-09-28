"""The game's experience tables: the capture bonus chain and the level ladder.

Catching a species pays bonus EXP for its first five catches (1.0; it was ten before).
The save keeps the bookkeeping per player in RecordData:

  PalCaptureCount            catches per species id, uncapped
  PalCaptureBonusCount       catches per species that counted, capped at BONUS_CAP
  PalCaptureBonusExpTableIndex  how many bonus catches so far, all species together

and the pak pays the *next* bonus from DT_PalCaptureBonusExpTable, one climbing table
(22 EXP at row 1, 7,384 at 697, 294,653 at the end). The row is NOT the capture counter
alone: it is the sum of every `*Bonus*TableIndex` counter in RecordData -- captures, areas
found, bosses beaten, relics, notes, item pickups, fast travel points, NPCs -- one shared
discovery chain (extractors/players.bonus_chain). Verified 2026-09-28: a Lifmunk catch
paid 25,476 = row 1388 = 702 + 217 + 270 + 35 + 5 + 28 + 131 exactly. The capture counter
still equals the sum of the per-species bonus counts (checked on six players). DT_PalExpTable gives the player
level ladder (TotalEXP = cumulative EXP to reach that level; Envy lv 72 with 22.5M sits
between rows 72 and 73).

build_exp_tables turns the two pak dumps into data/json/exp.json (scripts/datagen/
generate_exp.py); the helpers below read it. Bonus values are at the server's default
EXP rate; the caller scales by ExpRate when it knows it.
"""
from typing import Dict, List, Optional

BONUS_CAP = 5             # bonus catches per species in 1.0
MIN_BONUS_ROWS = 1000     # the 1.0 table has 4999 rows
MIN_LEVELS = 60           # 100 rows on 1.0


def build_exp_tables(bonus_rows: Dict[str, Dict], level_rows: Dict[str, Dict]) -> Dict:
    """{capture_bonus: [exp per running index, from 0], levels: {level: {total, next}}}."""
    bonus: List[int] = []
    for key in sorted(bonus_rows, key=lambda k: int(k)):
        bonus.append(int((bonus_rows[key] or {}).get('BonusExp') or 0))
    levels: Dict[str, Dict[str, int]] = {}
    for key, row in level_rows.items():
        row = row or {}
        levels[str(int(key))] = {'total': int(row.get('TotalEXP') or 0), 'next': int(row.get('NextEXP') or 0)}
    return {'capture_bonus': bonus, 'levels': levels}


def bonus_exp_at(table: Dict, index: int) -> int:
    """EXP the next bonus catch pays for a player at running `index` (past the end: the last row)."""
    chain = (table or {}).get('capture_bonus') or []
    if not chain:
        return 0
    return int(chain[min(max(int(index or 0), 0), len(chain) - 1)])


def exp_to_next_level(table: Dict, level: int, exp: int) -> Optional[int]:
    """EXP still needed for `level + 1`, or None past the table (the level cap)."""
    levels = (table or {}).get('levels') or {}
    row = levels.get(str(int(level or 0) + 1))
    if not row:
        return None
    return max(int(row['total']) - int(exp or 0), 0)


def level_progress(table: Dict, level: int, exp: int) -> Optional[Dict[str, int]]:
    """The status screen's EXP bar: {into, span, to_next} for this level, or None at the cap / no table."""
    levels = (table or {}).get('levels') or {}
    here, nxt = levels.get(str(int(level or 0))), levels.get(str(int(level or 0) + 1))
    if not here or not nxt:
        return None
    span = int(nxt['total']) - int(here['total'])
    into = min(max(int(exp or 0) - int(here['total']), 0), span)
    return {'into': into, 'span': span, 'to_next': span - into}


def catches_to_next_level(table: Dict, index: int, needed: Optional[int], rate: float = 1.0) -> Optional[int]:
    """How many bonus catches from `index` cover `needed` EXP at the server's rate; None at the cap."""
    if needed is None:
        return None
    if needed <= 0:
        return 0
    chain = (table or {}).get('capture_bonus') or []
    if not chain:
        return None
    total, n, i = 0.0, 0, max(int(index or 0), 0)
    while total < needed:
        total += chain[min(i, len(chain) - 1)] * (rate or 1.0)
        n += 1
        i += 1
        if n > 100000:   # a rate of 0 or a broken table must not spin forever
            return None
    return n
