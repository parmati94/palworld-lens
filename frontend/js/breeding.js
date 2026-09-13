/**
 * Breeding calculator helpers: match the pair table the API returns against
 * the pals this save actually contains.
 *
 * The backend answers "A + B -> C" and "which pairs make C" from
 * data/json/breeding.json (backend/common/breeding.py). Everything about
 * OUR pals -- who owns a male A and a female B, which two carry the passives
 * we want -- happens here, from the pal list the app already holds. Pure
 * functions, no Alpine, so `node --test` covers them.
 */

const GENDERS = ['Male', 'Female'];

/** {species_id: {Male: [pal], Female: [pal]}} for every pal with a known gender. */
export function palsBySpecies(pals) {
    const out = {};
    for (const pal of pals || []) {
        if (!pal.species_id || !GENDERS.includes(pal.gender)) continue;
        const slot = out[pal.species_id] || (out[pal.species_id] = { Male: [], Female: [] });
        slot[pal.gender].push(pal);
    }
    return out;
}

/** Skill ids a pal carries (passive_skills come as [{skill_id, name, rank}]). */
export function passiveIds(pal) {
    return ((pal && pal.passive_skills) || []).map(s => s.skill_id || s.name).filter(Boolean);
}

/**
 * The (male, female) assignments a pair allows. A gender-gated combo pins
 * both; otherwise either parent may be the male. Same-species pairs need
 * one of each.
 */
export function arrangements(pair) {
    if (pair.parent_a_gender || pair.parent_b_gender) {
        return [{ a: pair.parent_a_gender || 'Male', b: pair.parent_b_gender || 'Female' }];
    }
    if (pair.parent_a === pair.parent_b) return [{ a: 'Male', b: 'Female' }];
    return [{ a: 'Male', b: 'Female' }, { a: 'Female', b: 'Male' }];
}

/**
 * How many of each parent we own, per gender, and whether some owned male +
 * owned female satisfies the pair.
 */
export function pairOwned(pair, bySpecies) {
    const empty = { Male: [], Female: [] };
    const a = bySpecies[pair.parent_a] || empty;
    const b = bySpecies[pair.parent_b] || empty;
    const counts = {
        a: { Male: a.Male.length, Female: a.Female.length },
        b: { Male: b.Male.length, Female: b.Female.length },
    };
    const feasible = arrangements(pair).some(x => a[x.a].length > 0 && b[x.b].length > 0);
    return { counts, feasible, ownsA: a.Male.length + a.Female.length > 0, ownsB: b.Male.length + b.Female.length > 0 };
}

/**
 * Best owned (a, b) couples for a pair, scored by how many `targetIds`
 * (passive skill ids) the two parents carry between them, then by how many
 * good passives they bring overall, then by level. Same-species pairs never
 * pair a pal with itself.
 */
export function bestCandidates(pair, bySpecies, targetIds = [], limit = 6) {
    const empty = { Male: [], Female: [] };
    const a = bySpecies[pair.parent_a] || empty;
    const b = bySpecies[pair.parent_b] || empty;
    const targets = new Set(targetIds);
    const CAP = 40;   // per side; enough for the best couples, bounded work

    const rank = (pal) => {
        const ids = passiveIds(pal);
        const hit = ids.filter(id => targets.has(id)).length;
        const good = (pal.passive_skills || []).filter(s => (s.rank || 0) > 0).length;
        return { pal, ids, hit, good };
    };
    const top = (list) => list.map(rank)
        .sort((x, y) => y.hit - x.hit || y.good - x.good || (y.pal.level || 0) - (x.pal.level || 0))
        .slice(0, CAP);

    const out = [];
    for (const x of arrangements(pair)) {
        for (const pa of top(a[x.a])) {
            for (const pb of top(b[x.b])) {
                if (pa.pal.instance_id === pb.pal.instance_id) continue;
                const union = new Set([...pa.ids, ...pb.ids]);
                const matched = [...targets].filter(id => union.has(id));
                out.push({
                    a: pa.pal, b: pb.pal, matched,
                    score: matched.length,
                    good: pa.good + pb.good,
                    level: (pa.pal.level || 0) + (pb.pal.level || 0),
                });
            }
        }
    }
    out.sort((x, y) => y.score - x.score || y.good - x.good || y.level - x.level);
    // For symmetric pairs the same couple appears once per arrangement direction
    // only when species differ, so no de-dup is needed; same-species couples
    // (m, f) are unique by construction.
    return out.slice(0, limit);
}

/** Every distinct passive our pals carry: [{id, name, rank}] sorted by name. */
export function ownedPassives(pals) {
    const seen = new Map();
    for (const pal of pals || []) {
        for (const s of pal.passive_skills || []) {
            const id = s.skill_id || s.name;
            if (id && !seen.has(id)) seen.set(id, { id, name: s.name || id, rank: s.rank ?? 0 });
        }
    }
    return [...seen.values()].sort((x, y) => (y.rank - x.rank) || x.name.localeCompare(y.name));
}

/** Sort key for pair rows: pairs we can breed now first, then special combos, then by name. */
export function comparePairRows(x, y) {
    if (x.owned.feasible !== y.owned.feasible) return x.owned.feasible ? -1 : 1;
    if ((x.best?.score || 0) !== (y.best?.score || 0)) return (y.best?.score || 0) - (x.best?.score || 0);
    const xPartial = x.owned.ownsA || x.owned.ownsB, yPartial = y.owned.ownsA || y.owned.ownsB;
    if (xPartial !== yPartial) return xPartial ? -1 : 1;
    if (x.pair.unique !== y.pair.unique) return x.pair.unique ? -1 : 1;
    return (x.nameA + x.nameB).localeCompare(y.nameA + y.nameB);
}
