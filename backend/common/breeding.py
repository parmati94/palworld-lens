"""Breeding lookups: which pair of species produces which child, and back.

The game decides a child in two steps: `DT_PalCombiUnique` (a hand-made list of
special pairs, two of them gated on parent gender) takes precedence, otherwise
the child is the species whose `combi_rank` is nearest the parents' average,
with tie-break rules that are NOT a simple "closest rank" (a naive formula
disagrees with the game on ~45% of pairs). We therefore do not re-derive the
formula: palworld-save-pal ships the full precomputed pair table in
data/json/breeding.json and this module only indexes it.

Table keys are save-pal tribe ids, which mostly equal pals.json keys but not
always (`SheepBall` vs `Sheepball`), and the table lists a few unreleased
"Unidentified Pal" placeholders that pals.json does not have. Every key is
resolved through SpeciesIndex at build time so the API and UI only ever see
pals.json ids; unresolvable rows are dropped and reported once.

Pure python, no dependencies, so the datagen scripts and tests can import it.
"""

from __future__ import annotations

import heapq
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from backend.common.pal_ids import SpeciesIndex

Gender = Optional[str]          # 'Male' | 'Female' | None (no gate / unknown)
PairKey = Tuple[str, str]       # order-independent: sorted (a, b)


@dataclass(frozen=True)
class Combo:
    """One breeding outcome. Genders are only set for gender-gated unique combos."""
    parent_a: str
    parent_b: str
    child: str
    unique: bool = False
    parent_a_gender: Gender = None
    parent_b_gender: Gender = None

    def admits(self, gender_a: Gender, gender_b: Gender) -> bool:
        """True when the given parent genders satisfy this combo's gate (if any)."""
        # The gate is stated for (parent_a, parent_b); orient() first when the
        # caller's pair is the other way round. No gate, or an unknown gender, passes.
        ok_a = self.parent_a_gender is None or gender_a in (None, self.parent_a_gender)
        ok_b = self.parent_b_gender is None or gender_b in (None, self.parent_b_gender)
        return ok_a and ok_b

    def oriented(self, first: str) -> "Combo":
        """The same combo restated with `first` as parent_a (gate moves with it)."""
        if self.parent_a == first or self.parent_b != first:
            return self
        return Combo(self.parent_b, self.parent_a, self.child, self.unique,
                     self.parent_b_gender, self.parent_a_gender)


def _key(a: str, b: str) -> PairKey:
    return (a, b) if a <= b else (b, a)


def _gender(raw) -> Gender:
    if not raw:
        return None
    s = str(raw).strip().capitalize()
    return s if s in ('Male', 'Female') else None


class BreedingIndex:
    """Indexes breeding.json against pals.json ids.

    species        -- sorted breedable species ids (pals.json keys)
    ignore_combi   -- species that only breed with themselves (legendaries etc.)
    unresolved     -- table ids that matched nothing in pals.json (dropped)
    """

    def __init__(self, table: Dict, species: SpeciesIndex):
        self._resolve = species.resolve
        self.unresolved: Set[str] = set()
        self.species: List[str] = []
        self.ignore_combi: Set[str] = set()
        self._by_pair: Dict[PairKey, List[Combo]] = {}   # unique combos, then formula
        self._by_child: Dict[str, List[Combo]] = {}

        info = table.get('pal_info') or {}
        for raw, row in info.items():
            sid = self._id(raw)
            if sid is None:
                continue
            self.species.append(sid)
            if (row or {}).get('ignore_combi'):
                self.ignore_combi.add(sid)
        self.species = sorted(set(self.species))
        self._known: Set[str] = set(self.species)
        known = self._known

        unique_pairs: Set[PairKey] = set()
        for row in table.get('unique_combos') or []:
            a, b, c = self._id(row.get('parent_a')), self._id(row.get('parent_b')), self._id(row.get('child'))
            if not (a and b and c) or not {a, b, c} <= known:
                continue
            # The table lists X + X = X for ignore_combi species as "unique";
            # that is just the same-species rule, not a special combo.
            special = not (a == b == c)
            combo = Combo(a, b, c, special, _gender(row.get('parent_a_gender')), _gender(row.get('parent_b_gender')))
            unique_pairs.add(_key(a, b))
            self._add(combo)

        # Formula pairs that a unique combo overrides never apply in-game
        # (DT_PalCombiUnique wins), so they are not indexed at all.
        for raw_child, pairs in (table.get('child_to_parents_formula') or {}).items():
            c = self._id(raw_child)
            if c is None or c not in known:
                continue
            for row in pairs or []:
                a, b = self._id(row.get('parent_a')), self._id(row.get('parent_b'))
                if not (a and b) or not {a, b} <= known or _key(a, b) in unique_pairs:
                    continue
                self._add(Combo(a, b, c))

        for combos in self._by_child.values():
            combos.sort(key=lambda x: (not x.unique, x.parent_a, x.parent_b))

    # ------------------------------------------------------------------
    def _id(self, raw) -> Optional[str]:
        if not raw:
            return None
        sid = self._resolve(str(raw))
        if sid is None:
            self.unresolved.add(str(raw))
        return sid

    def _add(self, combo: Combo) -> None:
        self._by_pair.setdefault(_key(combo.parent_a, combo.parent_b), []).append(combo)
        self._by_child.setdefault(combo.child, []).append(combo)

    # ------------------------------------------------------------------
    # Queries. Every species argument is resolved, so raw character ids
    # (BOSS_Foo, Foo_Oilrig) are accepted.
    # ------------------------------------------------------------------
    def is_breedable(self, species_id: str) -> bool:
        return self.resolve(species_id) is not None

    def resolve(self, species_id: str) -> Optional[str]:
        """The table's id for a raw species / character id, or None if it is not breedable."""
        sid = self._resolve(species_id) if species_id else None
        return sid if sid is not None and sid in self._known else None

    def child_of(self, parent_a: str, parent_b: str,
                 gender_a: Gender = None, gender_b: Gender = None) -> List[Combo]:
        """Outcomes for a pair, oriented as (parent_a, parent_b).

        Usually one. The gender-gated pairs return both children when no
        genders are given, and the one that applies when they are.
        """
        a, b = self._resolve(parent_a), self._resolve(parent_b)
        if a is None or b is None:
            return []
        out = []
        for combo in self._by_pair.get(_key(a, b), []):
            oriented = combo.oriented(a)
            if oriented.admits(_gender(gender_a), _gender(gender_b)):
                out.append(oriented)
        return out

    def parents_of(self, child: str) -> List[Combo]:
        """Every pair that produces `child`, unique combos first."""
        c = self._resolve(child)
        return list(self._by_child.get(c, [])) if c else []

    def partners_for(self, parent_a: str, child: str) -> List[Combo]:
        """Pairs producing `child` that include `parent_a`, oriented with it first."""
        a = self._resolve(parent_a)
        if a is None:
            return []
        return [combo.oriented(a) for combo in self.parents_of(child)
                if a in (combo.parent_a, combo.parent_b)]

    def pair_count(self) -> int:
        return sum(len(v) for v in self._by_pair.values())

    def pairs_including(self, species_id: str) -> List[Tuple[str, "Combo"]]:
        """Every (other parent, combo) with `species_id` as a parent; combo oriented with it first."""
        sid = self._resolve(species_id) if species_id else None
        if sid is None:
            return []
        if not hasattr(self, '_adj'):
            adj: Dict[str, List[Tuple[str, Combo]]] = {}
            for (a, b), combos in self._by_pair.items():
                for combo in combos:
                    adj.setdefault(a, []).append((b, combo.oriented(a)))
                    if a != b:
                        adj.setdefault(b, []).append((a, combo.oriented(b)))
            self._adj = adj
        return self._adj.get(sid, [])


# ----------------------------------------------------------------------
# Route planning: how to get from the pals you own to a species you don't.
# ----------------------------------------------------------------------
Owned = Dict[str, Set[str]]     # species id -> genders owned ({'Male', 'Female'})
GENDERS = ('Male', 'Female')


@dataclass(frozen=True)
class Step:
    """One breed in a plan: `combo` (oriented) produces `child`.

    `from_a` / `from_b`: 'owned' or 'bred' (an earlier step's child).
    `need_a` / `need_b`: the gender that parent has to be in this step, or
    None when either works. A bred parent hatches in a random gender, so
    "need_b = Female" means "hatch until you get a female".
    """
    child: str
    combo: Combo
    from_a: str
    from_b: str
    depth: int                      # generations from owned pals (1 = both parents owned)
    need_a: Gender = None
    need_b: Gender = None


@dataclass
class Plan:
    steps: List[Step]               # dependency order: every parent is owned or an earlier step; target last

    @property
    def breeds(self) -> int:
        return len(self.steps)

    @property
    def generations(self) -> int:
        return max((s.depth for s in self.steps), default=0)

    def hatch(self) -> Dict[str, Set[str]]:
        """Bred species -> genders the plan needs it in (both = hatch one of each)."""
        out: Dict[str, Set[str]] = {s.child: set() for s in self.steps}
        for s in self.steps:
            for parent, src, need in ((s.combo.parent_a, s.from_a, s.need_a), (s.combo.parent_b, s.from_b, s.need_b)):
                if src == 'bred' and need:
                    out[parent].add(need)
        return out


@dataclass
class Route:
    target: str
    status: str                     # 'owned' | 'breedable' | 'route' | 'unreachable'
    plans: List[Plan]               # fewest breeds first; [] unless status is breedable/route
    exact: bool = True              # False: search timed out, plans[0] is the heuristic tree
    min_generations: int = 0        # lower bound on breeds (a plan can't be shorter than its depth)

    @property
    def plan(self) -> Optional[Plan]:
        return self.plans[0] if self.plans else None

    @property
    def steps(self) -> List[Step]:
        return self.plan.steps if self.plan else []

    @property
    def breeds(self) -> int:
        return self.plan.breeds if self.plan else 0

    @property
    def generations(self) -> int:
        return self.plan.generations if self.plan else 0


def _genders_available(species: str, owned: Owned, bred: Set[str]) -> Set[str]:
    if species in bred:
        return set(GENDERS)
    return set(owned.get(species) or ())


def _arrangements(combo: Combo, owned: Owned, bred: Set[str]) -> List[Tuple[str, str]]:
    """(gender_a, gender_b) pairs this combo can be bred with from what is owned / bred."""
    ga = _genders_available(combo.parent_a, owned, bred)
    gb = _genders_available(combo.parent_b, owned, bred)
    return [(a, b) for a in ga for b in gb if a != b and combo.admits(a, b)]


def pair_feasible(combo: Combo, owned: Owned, bred: Set[str]) -> bool:
    """Can this (oriented) pair be bred from what is owned plus what earlier steps produce?

    Needs one male and one female that satisfy the combo's gender gate. A
    same-species pair needs both genders of it, so owning only males of X
    never yields X + X.
    """
    return bool(_arrangements(combo, owned, bred))


def _needs(combo: Combo, owned: Owned, bred: Set[str]) -> Tuple[Gender, Gender]:
    """Forced gender per parent (None = either), from the arrangements left."""
    arr = _arrangements(combo, owned, bred)
    if not arr:
        return None, None
    a_set, b_set = {a for a, _ in arr}, {b for _, b in arr}
    return (next(iter(a_set)) if len(a_set) == 1 else None,
            next(iter(b_set)) if len(b_set) == 1 else None)


def _reach(index: BreedingIndex, owned: Owned) -> Tuple[Dict[str, int], Set[str]]:
    """Min generations to every reachable species (owned = 0), and the bred set.

    A bred parent can be hatched in either gender, so once a species is
    reachable it is fully usable; feasibility only ever hinges on owned genders.
    """
    gen: Dict[str, int] = {s: 0 for s, g in owned.items() if g and index.is_breedable(s)}
    frontier = set(gen)
    r = 0
    while frontier:
        r += 1
        bred = {s for s, g in gen.items() if g > 0}
        new: Dict[str, int] = {}
        for s in frontier:
            for other, combo in index.pairs_including(s):
                if other not in gen or combo.child in gen or combo.child in new:
                    continue
                if pair_feasible(combo, owned, bred):
                    new[combo.child] = r
        gen.update(new)
        frontier = set(new)
    return gen, {s for s, g in gen.items() if g > 0}


def _descendants(sp: str, chosen: Dict[str, Combo]) -> Set[str]:
    """Species in `chosen` whose derivation (transitively) uses `sp`."""
    out: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for x, c in chosen.items():
            if x not in out and (sp in (c.parent_a, c.parent_b) or out & {c.parent_a, c.parent_b}):
                out.add(x)
                changed = True
    return out


def _compact(index: BreedingIndex, owned: Owned, target: str, chosen: Dict[str, Combo]) -> Dict[str, Combo]:
    """Shrink a plan by re-deriving species from what the plan already breeds.

    A hyperpath tree derives each branch on its own; often an intermediate
    on one branch could be made from something the other branch already has.
    For every bred species try each of its pairs whose parents are owned or
    already in the plan (and not downstream of it, which would cycle), then
    drop whatever nothing references any more. Repeats until nothing changes.
    """
    chosen = dict(chosen)

    def gc() -> None:
        keep: Set[str] = set()
        stack = [target]
        while stack:
            x = stack.pop()
            if x in keep or x not in chosen:
                continue
            keep.add(x)
            stack.extend((chosen[x].parent_a, chosen[x].parent_b))
        for x in list(chosen):
            if x not in keep:
                del chosen[x]

    changed = True
    while changed:
        changed = False
        for sp in sorted(chosen):
            if sp not in chosen:
                continue
            banned = _descendants(sp, chosen) | {sp, target}
            usable = {x for x in chosen if x not in banned} | {x for x in owned if owned[x]}
            current = chosen[sp]
            cur_new = sum(1 for p in (current.parent_a, current.parent_b) if p not in owned or not owned[p])
            for c in index.parents_of(sp):
                if c.parent_a in usable and c.parent_b in usable and pair_feasible(c, owned, set(chosen)):
                    before = len(chosen)
                    chosen[sp] = c
                    gc()
                    if len(chosen) < before:
                        changed = True
                        break
                    chosen[sp] = current
                    gc()
    return chosen


def _heuristic(index: BreedingIndex, owned: Owned, target: str, bred_all: Set[str],
               limit: int = 5) -> List[Dict[str, Combo]]:
    """Shortest-hyperpath trees (Knuth): cost = 1 + cost(a) + cost(b), owned = 0.

    Overcounts shared intermediates, so every candidate final pair's tree is
    compacted (_compact) and re-costed by distinct species. Used when the
    exact search runs out of time. Returns up to `limit` plans, smallest first.
    """
    inf = float('inf')
    cost: Dict[str, float] = {s: 0 for s in owned if owned[s] and index.is_breedable(s)}
    via: Dict[str, Combo] = {}
    settled: Set[str] = set()
    heap = [(0, s) for s in cost]
    heapq.heapify(heap)
    while heap:
        c, s = heapq.heappop(heap)
        if s in settled or c > cost.get(s, inf):
            continue
        settled.add(s)
        for other, combo in index.pairs_including(s):
            if other not in settled or not pair_feasible(combo, owned, bred_all):
                continue
            child = combo.child
            if owned.get(child):
                continue
            nc = 1 + cost[s] + cost[other]
            if nc < cost.get(child, inf):
                cost[child] = nc
                via[child] = combo
                heapq.heappush(heap, (nc, child))
    if target not in via:
        return []

    def tree(final: Combo) -> Dict[str, Combo]:
        chosen: Dict[str, Combo] = {target: final}
        stack = [final.parent_a, final.parent_b]
        while stack:
            sp = stack.pop()
            if sp in chosen or sp not in via:
                continue
            chosen[sp] = via[sp]
            stack.extend((via[sp].parent_a, via[sp].parent_b))
        return chosen

    trees = []
    for combo in index.parents_of(target):
        if target in (combo.parent_a, combo.parent_b):
            continue
        if combo.parent_a in cost and combo.parent_b in cost and pair_feasible(combo, owned, bred_all):
            trees.append(tree(combo))
    trees.sort(key=len)
    out = [_compact(index, owned, target, t) for t in trees[:max(limit * 3, 12)]]
    out.sort(key=len)
    return out[:limit]


def _to_plan(chosen: Dict[str, Combo], owned: Owned, target: str) -> Plan:
    """Order a species -> combo map so parents come first; fill sources, depth and gender needs."""
    bred_all = set(chosen)
    order: List[str] = []
    seen: Set[str] = set()

    def visit(sp: str) -> None:
        if sp in seen or sp not in chosen:
            return
        seen.add(sp)
        visit(chosen[sp].parent_a)
        visit(chosen[sp].parent_b)
        order.append(sp)

    visit(target)
    depth: Dict[str, int] = {}
    steps: List[Step] = []
    for sp in order:
        c = chosen[sp]
        fa = 'bred' if c.parent_a in chosen else 'owned'
        fb = 'bred' if c.parent_b in chosen else 'owned'
        d = 1 + max(depth.get(c.parent_a, 0), depth.get(c.parent_b, 0))
        depth[sp] = d
        na, nb = _needs(c, owned, bred_all)
        steps.append(Step(sp, c, fa, fb, d, na, nb))
    return Plan(steps)


class _Timeout(Exception):
    pass


class _ExactSearch:
    """Iterative deepening on the number of distinct species bred.

    Backwards from the target: pick a pair for it, then for every parent that
    is not owned, and so on; a parent already in the plan is reused unless
    that would make a cycle. `lower` (the generations bound) is the first k
    tried; the first plan found proves the minimum, then `alt_budget` more
    seconds go on collecting alternatives at that k.
    """

    def __init__(self, index: BreedingIndex, owned: Owned, target: str,
                 gen: Dict[str, int], bred_all: Set[str], max_plans: int):
        self.index, self.owned, self.target = index, owned, target
        self.gen, self.bred_all, self.max_plans = gen, bred_all, max_plans
        self.found: List[Dict[str, Combo]] = []
        self.deadline = 0.0
        self._cands: Dict[str, List[Combo]] = {}

    def run(self, lower: int, time_budget: float, alt_budget: float) -> Tuple[List[Dict[str, Combo]], bool]:
        """(plans, exact). exact is False only when no plan was found in time."""
        start = time.monotonic()
        self.deadline = start + time_budget
        self.alt_budget = alt_budget
        try:
            for k in range(max(1, lower), 64):
                if self._dfs(frozenset([self.target]), {}, k) or self.found:
                    break
        except _Timeout:
            pass
        return self.found, bool(self.found)

    # Pairs worth trying for a species: both parents reachable, genders workable, not the target.
    def _pairs(self, sp: str) -> List[Combo]:
        if sp not in self._cands:
            self._cands[sp] = [c for c in self.index.parents_of(sp)
                               if c.parent_a in self.gen and c.parent_b in self.gen
                               and self.target not in (c.parent_a, c.parent_b)
                               and pair_feasible(c, self.owned, self.bred_all)]
        return self._cands[sp]

    def _is_owned(self, sp: str) -> bool:
        return bool(self.owned.get(sp)) and sp in self.gen

    @staticmethod
    def _ancestors(sp: str, chosen: Dict[str, Combo]) -> Set[str]:
        out: Set[str] = set()
        stack = [sp]
        while stack:
            c = chosen.get(stack.pop())
            if not c:
                continue
            for p in (c.parent_a, c.parent_b):
                if p not in out:
                    out.add(p)
                    stack.append(p)
        return out

    def _dfs(self, need: frozenset, chosen: Dict[str, Combo], k: int) -> bool:
        """True = stop (enough plans). `need` = species still to derive; `chosen` = species -> pair."""
        if time.monotonic() > self.deadline:
            raise _Timeout()
        if not need:
            self.found.append(dict(chosen))
            if len(self.found) == 1:   # minimum proven; alternatives are optional
                self.deadline = min(self.deadline, time.monotonic() + self.alt_budget)
            return len(self.found) >= self.max_plans
        sp = min(need)
        rest = need - {sp}
        for c in self._pairs(sp):
            new: Set[str] = set()
            cyclic = False
            for p in (c.parent_a, c.parent_b):
                if self._is_owned(p):
                    continue
                if p == sp or (p in chosen and sp in self._ancestors(p, chosen)):
                    cyclic = True
                    break
                if p not in chosen and p not in rest:
                    new.add(p)
            if cyclic or len(chosen) + 1 + len(rest | new) > k:
                continue
            chosen[sp] = c
            stop = self._dfs(rest | new, chosen, k)
            del chosen[sp]
            if stop:
                return True
        return False


def plan_route(index: BreedingIndex, owned: Owned, target: str,
               max_plans: int = 5, time_budget: float = 1.0, alt_budget: float = 0.3) -> Route:
    """Fewest breeds from `owned` to `target`, with alternatives.

    Exact when _ExactSearch finishes inside `time_budget` (each intermediate
    bred once and reused; the generations sweep gives the lower bound). If
    no plan turns up in time -- tiny owned sets can need 50+ breeds -- the
    compacted Knuth hyperpath trees stand in and `exact` is False.
    """
    tid = index.resolve(target)
    if tid is None:
        return Route(target, 'unreachable', [])
    if owned.get(tid):
        return Route(tid, 'owned', [])

    gen, bred_all = _reach(index, owned)
    if tid not in gen:
        return Route(tid, 'unreachable', [])
    lower = gen[tid]

    found, exact = _ExactSearch(index, owned, tid, gen, bred_all, max_plans).run(lower, time_budget, alt_budget)
    if not found:
        found = _heuristic(index, owned, tid, bred_all, max_plans)
        if not found:
            return Route(tid, 'unreachable', [], exact, lower)

    plans = [_to_plan(c, owned, tid) for c in found]
    plans.sort(key=lambda p: (p.breeds, p.generations))
    status = 'breedable' if plans[0].breeds == 1 else 'route'
    return Route(tid, status, plans, exact, lower)


# ----------------------------------------------------------------------
# Shortcuts: what to CATCH instead of breeding all the way up.
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Shortcut:
    """Catch `species` (and, for a pair, `partner` too) and the route shrinks to `breeds_after`.

    kind 'intermediate': it is bred somewhere in the plan; catching it drops
    that whole subtree. kind 'partner': it makes the target in one breed
    with `partner`, which is already owned. kind 'pair': catch both it and
    `partner` and breed once. `need` / `partner_need` are the genders to
    catch (None = either); `level` / `partner_level` the lowest wild level.
    """
    species: str
    kind: str
    breeds_after: int
    saves: int
    catches: int
    need: Gender = None
    level: Optional[int] = None
    partner: Optional[str] = None
    partner_need: Gender = None
    partner_level: Optional[int] = None
    unique: bool = False


def _plan_size_if_owned(chosen: Dict[str, Combo], target: str, caught: str) -> int:
    """Breeds left in a plan once `caught` no longer has to be bred (unreferenced steps drop out)."""
    keep: Set[str] = set()
    stack = [target]
    while stack:
        x = stack.pop()
        if x in keep or x == caught or x not in chosen:
            continue
        keep.add(x)
        stack.extend((chosen[x].parent_a, chosen[x].parent_b))
    return len(keep)


def shortcuts(index: BreedingIndex, owned: Owned, route: Route, catchable: Dict[str, int],
              limit: int = 5, max_pairs: int = 2) -> List[Shortcut]:
    """Catchable species that cut the route down; fewest breeds left, then fewest catches, then lowest level.

    Three sources, one entry per species keeping the best: intermediates of
    the best plan (savings = the subtree that disappears, exact); wild
    partners that finish the target in one breed with an owned pal; and
    pairs where both parents are wild, ranked by the harder of the two to
    find (capped at `max_pairs` so single catches stay visible). A caught
    pal is whichever gender you go for, so it counts as either gender for
    feasibility, and `need` says which one to catch.
    """
    if route.status != 'route' or not route.plan:
        return []
    plan = route.plan
    target = route.target
    chosen = {s.child: s.combo for s in plan.steps}
    hatch = plan.hatch()
    best: Dict[str, Shortcut] = {}

    def offer(sc: Shortcut) -> None:
        cur = best.get(sc.species)
        if cur is None or (sc.breeds_after, sc.catches) < (cur.breeds_after, cur.catches):
            best[sc.species] = sc

    for step in plan.steps:
        sp = step.child
        if sp == target or sp not in catchable:
            continue
        after = _plan_size_if_owned(chosen, target, sp)
        genders = hatch.get(sp) or set()
        need = next(iter(genders)) if len(genders) == 1 else None
        offer(Shortcut(sp, 'intermediate', after, plan.breeds - after, 1, need, catchable[sp]))

    for mine, genders in owned.items():
        if not genders or not index.is_breedable(mine):
            continue
        for combo in index.partners_for(mine, target):
            other = combo.parent_b
            if other in (target, mine) or other not in catchable or owned.get(other):
                continue
            if not pair_feasible(combo, owned, {other}):
                continue
            _, need_other = _needs(combo, owned, {other})
            offer(Shortcut(other, 'partner', 1, plan.breeds - 1, 1, need_other, catchable[other], mine, None, None, combo.unique))

    pairs: List[Shortcut] = []
    for combo in index.parents_of(target):
        a, b = combo.parent_a, combo.parent_b
        if target in (a, b) or a not in catchable or b not in catchable or owned.get(a) or owned.get(b):
            continue
        if not pair_feasible(combo, owned, {a, b}):
            continue
        need_a, need_b = _needs(combo, owned, {a, b})
        if catchable[a] > catchable[b]:   # lead with the easier one
            a, b, need_a, need_b = b, a, need_b, need_a
        pairs.append(Shortcut(a, 'pair', 1, plan.breeds - 1, 2, need_a, catchable[a], b, need_b, catchable[b], combo.unique))
    pairs.sort(key=lambda sc: (max(sc.level, sc.partner_level), sc.level, sc.species))
    used: Set[str] = set(best)
    taken = 0
    for sc in pairs:   # different pals in each suggestion, not the same partner twice
        if taken >= max_pairs:
            break
        if sc.species in used or sc.partner in used:
            continue
        best[sc.species] = sc
        used.update((sc.species, sc.partner))
        taken += 1

    ranked = sorted(best.values(), key=lambda sc: (sc.breeds_after, sc.catches, sc.level if sc.level is not None else 999, sc.species))
    return [sc for sc in ranked if sc.saves > 0][:limit]
