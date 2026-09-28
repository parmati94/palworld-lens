"""The Paldeck: every species the game lists, with what this server knows about each.

Two views over the same species table (data/json/pals.json):

  * the deck itself -- one row per Paldeck entry (288 on 1.0: the numbered species plus
    their "B" subspecies, which share the base's number), with the reference data the
    UI shows on a card: elements, work levels, partner skill name, where it spawns;
  * a player's capture-bonus progress -- their RecordData maps (backend/common/
    exp_tables.py explains the chain) resolved onto deck ids, plus what the next bonus
    catch pays and how many catches would level them up.

The deck is a species list, never an instance list: owned pals only appear as a count
per species (and, in the detail view, as the pals themselves). Pure functions over the
DataLoader tables and the parsed players / pals; the router wires them up.
"""
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Set

from backend.common import pal_icons
from backend.common.exp_tables import BONUS_CAP, bonus_exp_at, catches_to_next_level, exp_to_next_level
from backend.common.spawns import is_variant_id

CATCH_KINDS = {'field', 'field_boss'}                      # out in the world: go and catch one
DUNGEON_KINDS = {'dungeon', 'dungeon_boss', 'prison_boss'}  # instanced rooms
DETAIL_OWNED_LIMIT = 60
DROP_SLOTS = 10            # ItemId1..10 per DT_PalDropItem row
MIN_DROP_SPECIES = 600     # 894 character ids on 1.0 (bosses and NPCs included)
MIN_LEARN_SPECIES = 500    # 712 on 1.0


# ---------------------------------------------------------------------------
# The pak tables behind the species modal (data/json/paldeck.json)
# ---------------------------------------------------------------------------

def build_paldeck_tables(drop_rows: Dict[str, Dict], waza_rows: Dict[str, Dict]) -> Dict:
    """{drops: {character id: [{level, items: [{item, rate, min, max}]}]}, learn: {pal id: [{skill, level}]}}.

    DT_PalDropItem has one row per character and level threshold: Level 0 is what it always
    drops, a Level 70 / 80 row is the *whole* table once the pal is that level (base items plus
    awakening materials and relics). A BOSS_ row is the alpha's own table; its rate-0 entries are
    the base drops switched off, so they are dropped here. DT_WazaMasterLevel lists the active
    skills a species learns by level, ids the same "EPalWazaID::X" form as active_skills.json.
    """
    drops: Dict[str, List[Dict]] = defaultdict(list)
    for row in drop_rows.values():
        cid = row.get('CharacterID')
        if not cid:
            continue
        items = []
        for i in range(1, DROP_SLOTS + 1):
            item = row.get(f'ItemId{i}')
            rate = float(row.get(f'Rate{i}') or 0)
            if not item or item == 'None' or rate <= 0:
                continue
            items.append({'item': item, 'rate': rate, 'min': int(row.get(f'min{i}') or 0), 'max': int(row.get(f'Max{i}') or 0)})
        if items:
            drops[cid].append({'level': int(row.get('Level') or 0), 'items': items})
    for rows in drops.values():
        rows.sort(key=lambda r: r['level'])

    learn: Dict[str, List[Dict]] = defaultdict(list)
    for row in waza_rows.values():
        pal, skill = row.get('PalId'), row.get('WazaID')
        if pal and skill:
            learn[pal].append({'skill': skill, 'level': int(row.get('Level') or 0)})
    for rows in learn.values():
        rows.sort(key=lambda r: (r['level'], r['skill']))
    return {'drops': dict(drops), 'learn': dict(learn)}


def drops_for(tables: Dict, sid: str) -> Dict[str, List]:
    """{base: [items], high: [{level, items}], alpha: [items]} for a species: the Level 0 row, any
    higher-level rows reduced to what they add, and the BOSS_ form's own table."""
    table = (tables or {}).get('drops') or {}
    rows = table.get(sid) or []
    base = next((r['items'] for r in rows if r['level'] == 0), [])
    seen = {(i['item']) for i in base}
    high = []
    for r in rows:
        if r['level'] == 0:
            continue
        extra = [i for i in r['items'] if i['item'] not in seen]
        if extra:
            high.append({'level': r['level'], 'items': extra})
            seen.update(i['item'] for i in extra)
    boss = table.get('BOSS_' + sid) or []      # the pak spells the alpha rows BOSS_<id>
    alpha = next((r['items'] for r in boss if r['level'] == 0), [])
    return {'base': base, 'high': high, 'alpha': alpha}


def learnset_for(tables: Dict, sid: str) -> List[Dict]:
    return list(((tables or {}).get('learn') or {}).get(sid) or [])


# ---------------------------------------------------------------------------
# The deck
# ---------------------------------------------------------------------------

def is_deck_species(sid: str, row: Dict) -> bool:
    """A Paldeck entry: a pal with a deck number that is not a boss form, disabled, or a scripted copy."""
    if not isinstance(row, dict) or not row.get('is_pal') or row.get('disabled'):
        return False
    if not int(row.get('pal_deck_index') or 0) > 0:
        return False
    if row.get('is_boss') or row.get('is_tower_boss') or row.get('is_raid_boss'):
        return False
    return not is_variant_id(sid)


def deck_numbers(pals: Dict[str, Dict]) -> Dict[str, str]:
    """{species id: "200" | "200B"}: subspecies share the base's number and take a letter, like the game."""
    by_index: Dict[int, List[str]] = defaultdict(list)
    for sid, row in pals.items():
        if is_deck_species(sid, row):
            by_index[int(row['pal_deck_index'])].append(sid)
    out: Dict[str, str] = {}
    for index, ids in by_index.items():
        # the base form is the id without a variant suffix (shortest wins when both carry one)
        ids.sort(key=lambda s: (s.count('_'), len(s), s))
        for i, sid in enumerate(ids):
            out[sid] = str(index) if i == 0 else f'{index}{chr(ord("A") + i)}'
    return out


def deck_ids(pals: Dict[str, Dict]) -> List[str]:
    """Deck species in Paldeck order (number, then base before its subspecies)."""
    numbers = deck_numbers(pals)
    return sorted(numbers, key=lambda s: (int(pals[s]['pal_deck_index']), numbers[s]))


def spawn_summary(groups: Dict[str, Dict]) -> Dict[str, Dict]:
    """{species id: {how, min_level, max_level, night, alpha, groups}} from the spawner groups.

    `how` is the shortest honest answer to "can I go catch one": `wild` (a field herd),
    `alpha` (only as a field boss), `dungeon` (only inside instanced rooms). Species in
    no group at all are absent -- breeding-only, raids, oil rigs, events.
    """
    out: Dict[str, Dict] = {}
    for g in groups.values():
        kind = g.get('kind')
        for sid, e in (g.get('pals') or {}).items():
            lo, hi = (e.get('level') or [0, 0])[:2]
            s = out.setdefault(sid, {'wild': False, 'alpha': False, 'dungeon': False,
                                     'min_level': None, 'max_level': None, 'night': True, 'groups': 0})
            s['groups'] += 1
            if kind in CATCH_KINDS:
                if e.get('boss'):
                    s['alpha'] = True
                else:
                    s['wild'] = True
            elif kind in DUNGEON_KINDS:
                s['dungeon'] = True
            if not e.get('time'):
                s['night'] = False
            s['min_level'] = int(lo) if s['min_level'] is None else min(s['min_level'], int(lo))
            s['max_level'] = int(hi) if s['max_level'] is None else max(s['max_level'], int(hi))
    for s in out.values():
        s['how'] = 'wild' if s['wild'] else 'alpha' if s['alpha'] else 'dungeon'
        for k in ('wild', 'dungeon'):
            s.pop(k)
    return out


def owned_by_species(pals: Iterable) -> Dict[str, Dict]:
    """{species id: {count, owners}} over the server's pals."""
    out: Dict[str, Dict] = {}
    for p in pals:
        sid = getattr(p, 'species_id', None)
        if not sid:
            continue
        s = out.setdefault(sid, {'count': 0, 'owners': set()})
        s['count'] += 1
        if getattr(p, 'owner_uid', None):
            s['owners'].add(p.owner_uid)
    return out


def species_rows(data, pals: Iterable) -> List[Dict]:
    """One row per deck entry, in deck order."""
    numbers = deck_numbers(data.pals)
    spawns = spawn_summary(data.spawns)
    owned = owned_by_species(pals)
    rows = []
    for sid in deck_ids(data.pals):
        row = data.pals[sid]
        ps = data.partner_skills.get(sid) or {}
        own = owned.get(sid) or {'count': 0, 'owners': set()}
        rows.append({
            'id': sid,
            'name': data.pal_name(sid),
            'number': numbers[sid],
            'image_candidates': pal_icons.icon_candidates(sid),
            'element_types': row.get('element_types') or [],
            'rarity': row.get('rarity'),
            'size': row.get('size'),
            'work_suitability': {k: v for k, v in (row.get('work_suitability') or {}).items() if v},
            'best_work': row.get('best_work_suitability'),
            'partner_skill': ps.get('name'),
            'nocturnal': bool(row.get('nocturnal')),
            'male_probability': row.get('male_probability', 50),
            'breedable': data.breeding.is_breedable(sid),
            'spawn': spawns.get(sid),
            'owned': own['count'],
            'owners': len(own['owners']),
        })
    return rows


# ---------------------------------------------------------------------------
# A player's progress
# ---------------------------------------------------------------------------

def resolve_counts(raw: Dict[str, int], species, deck: Set[str], cap: Optional[int] = None) -> Dict[str, int]:
    """A save map {character id: n} onto deck ids (summed when two ids resolve to one species)."""
    out: Dict[str, int] = defaultdict(int)
    for cid, n in (raw or {}).items():
        sid = species.resolve(cid)
        if sid in deck and n:
            out[sid] += int(n)
    if cap is not None:
        return {k: min(v, cap) for k, v in out.items()}
    return dict(out)


def player_name(p) -> str:
    return getattr(p, 'nickname', None) or getattr(p, 'player_name', None) or ''


def player_progress(players: Iterable, species, deck: Set[str], exp_table: Dict, rate: Optional[float]) -> List[Dict]:
    """Each player's place in the capture bonus chain, level-first."""
    out = []
    r = rate or 1.0
    for p in players:
        rec = getattr(p, 'records', None)
        if rec is None:
            continue
        bonus = resolve_counts(rec.capture_bonus, species, deck, cap=BONUS_CAP)
        caught = resolve_counts(rec.capture_counts, species, deck)
        index = int(rec.bonus_index or 0)
        needed = exp_to_next_level(exp_table, p.level, p.exp)
        out.append({
            'name': player_name(p),
            'level': p.level,
            'bonus_index': index,
            'next_bonus_exp': int(round(bonus_exp_at(exp_table, index) * r)),
            'exp_to_next_level': needed,
            'catches_to_next_level': catches_to_next_level(exp_table, index, needed, r),
            'species_done': sum(1 for v in bonus.values() if v >= BONUS_CAP),
            'species_started': len(bonus),
            'bonus_left': sum(BONUS_CAP - min(bonus.get(sid, 0), BONUS_CAP) for sid in deck),
            'bonus': bonus,
            'caught': caught,
        })
    out.sort(key=lambda x: -x['level'])
    return out


# ---------------------------------------------------------------------------
# One species, in full
# ---------------------------------------------------------------------------

def species_detail(data, sid: str, pals: Iterable, players: Iterable) -> Optional[Dict]:
    """Everything the species modal shows, or None for an id that is not a deck entry."""
    numbers = deck_numbers(data.pals)
    if sid not in numbers:
        return None
    row = data.pals[sid]
    l10n = row  # localized_name / description are merged into the species row by the loader
    groups = []
    for name, g in data.spawns.items():
        e = (g.get('pals') or {}).get(sid)
        if not e:
            continue
        pts = g.get('points') or {}
        groups.append({
            'name': name,
            'kind': g.get('kind'),
            'level': e.get('level') or [0, 0],
            'share': e.get('share'),
            'boss': bool(e.get('boss')),
            'night': e.get('time') == 'night',
            'layers': sorted(pts.keys()),
            'points': sum(len(v) for v in pts.values()),
        })
    groups.sort(key=lambda g: (g['kind'] not in CATCH_KINDS, g['boss'], g['level'][0]))

    owned = []
    for p in pals:
        if getattr(p, 'species_id', None) != sid:
            continue
        owned.append({
            'instance_id': p.instance_id,
            'name': p.nickname or p.name,
            'level': p.level,
            'owner': getattr(p, 'owner_uid', None),
            'base_name': getattr(p, 'base_name', None),
            'in_party': bool(getattr(p, 'in_party', False)),
            'is_alpha': bool(getattr(p, 'is_alpha', False)),
            'is_lucky': bool(getattr(p, 'is_lucky', False)),
        })
    owned.sort(key=lambda o: -o['level'])

    pairs = list(data.breeding.parents_of(sid)) if data.breeding.is_breedable(sid) else []
    unique = [{'parent_a': c.parent_a, 'parent_b': c.parent_b,
               'parent_a_name': data.pal_name(c.parent_a), 'parent_b_name': data.pal_name(c.parent_b)}
              for c in pairs if c.unique]

    def item_tile(entry: Dict) -> Dict:
        row = data.item(entry['item']) if hasattr(data, 'item') else {}
        rarity = row.get('rarity')
        return {'item_id': entry['item'], 'item_name': row.get('localized_name') or entry['item'], 'icon': row.get('icon'),
                'rarity': rarity if isinstance(rarity, int) and 0 <= rarity <= 4 else None,
                'rate': entry['rate'], 'min': entry['min'], 'max': entry['max']}

    tables = getattr(data, 'paldeck_tables', None) or {}
    d = drops_for(tables, sid)
    drops = {'base': [item_tile(i) for i in d['base']],
             'high': [{'level': h['level'], 'items': [item_tile(i) for i in h['items']]} for h in d['high']],
             'alpha': [item_tile(i) for i in d['alpha']]}
    learnset = []
    for e in learnset_for(tables, sid):
        skill = (getattr(data, 'active_skills', None) or {}).get(e['skill']) or {}
        learnset.append({'level': e['level'], 'skill_id': e['skill'],
                         'name': skill.get('localized_name') or e['skill'].split('::')[-1],
                         'element': skill.get('element'), 'power': skill.get('power'), 'cool_time': skill.get('cool_time'),
                         'description': skill.get('description') or ''})

    deck = set(numbers)
    caught_by = []
    for p in players:
        rec = getattr(p, 'records', None)
        if rec is None:
            continue
        n = resolve_counts(rec.capture_counts, data.species, deck).get(sid, 0)
        b = resolve_counts(rec.capture_bonus, data.species, deck, cap=BONUS_CAP).get(sid, 0)
        if n or b:
            caught_by.append({'name': player_name(p), 'caught': n, 'bonus': b})
    caught_by.sort(key=lambda c: (-c['bonus'], -c['caught']))

    return {
        'id': sid,
        'name': data.pal_name(sid),
        'number': numbers[sid],
        'description': l10n.get('description') or '',
        'image_candidates': pal_icons.icon_candidates(sid),
        'element_types': row.get('element_types') or [],
        'rarity': row.get('rarity'),
        'size': row.get('size'),
        'scaling': row.get('scaling') or {},
        'work_suitability': {k: v for k, v in (row.get('work_suitability') or {}).items() if v},
        'best_work': row.get('best_work_suitability'),
        'nocturnal': bool(row.get('nocturnal')),
        'male_probability': row.get('male_probability', 50),
        'price': row.get('price'),
        'food_amount': row.get('food_amount'),
        'spawn': spawn_summary(data.spawns).get(sid),
        'spawn_groups': groups,
        'breedable': bool(pairs),
        'breeding': {
            'pairs': len(pairs),
            'unique': unique,
            'self_only': bool(pairs) and all(c.parent_a == sid and c.parent_b == sid for c in pairs),
        },
        'drops': drops,
        'learnset': learnset,
        'owned': owned[:DETAIL_OWNED_LIMIT],
        'owned_total': len(owned),
        'caught_by': caught_by,
    }
