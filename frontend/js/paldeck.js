/**
 * Paldeck helpers: filtering and sorting the species list the API returns
 * (/api/paldeck via backend/common/paldeck.py) and reading one player's
 * capture-bonus progress against it. Pure functions, no Alpine, so
 * `node --test` covers them.
 *
 * Every species row carries `spawn` ({how, min_level, max_level, night,
 * alpha, groups} or null when nothing spawns it) and a server-wide `owned`
 * count. A player's progress is {bonus: {id: n <= cap}, caught: {id: n}}.
 */

export const BONUS_CAP = 5;

/** The "how do I get one" filter, in the order the picker lists it. */
export const SPAWN_HOW = [
    { value: 'catchable', label: 'Catchable', tip: 'Spawns in the field, as a herd or an alpha' },
    { value: 'wild', label: 'Wild herds', tip: 'Ordinary field spawns' },
    { value: 'alpha', label: 'Alpha only', tip: 'Only as a field boss' },
    { value: 'dungeon', label: 'Dungeons only', tip: 'Only inside instanced rooms' },
    { value: 'none', label: 'No wild spawn', tip: 'Breeding, raids, oil rigs, events' },
];

export const DECK_SORTS = [
    { value: 'number', label: 'Paldeck order' },
    { value: 'name', label: 'Name' },
    { value: 'level', label: 'Spawn level' },
    { value: 'owned', label: 'Most owned' },
    { value: 'missing', label: 'Fewest caught' },
];

/** "Wild · Lv 12–20", "Alpha · Lv 60", "Dungeons · Lv 20–25", "No wild spawn". */
export function spawnLabel(spawn) {
    if (!spawn) return 'No wild spawn';
    const lo = spawn.min_level, hi = spawn.max_level;
    const lv = lo == null ? '' : hi != null && hi !== lo ? `Lv ${lo}–${hi}` : `Lv ${lo}`;
    const how = spawn.how === 'wild' ? 'Wild' : spawn.how === 'alpha' ? 'Alpha' : 'Dungeons';
    return lv ? `${how} · ${lv}` : how;
}

/** The hover behind the spawn chip. */
export function spawnTip(spawn) {
    if (!spawn) return 'Nothing spawns it in the wild: breeding, raids, oil rigs or events';
    const parts = [];
    if (spawn.how === 'wild') parts.push(`Spawns in ${spawn.groups} field zone${spawn.groups === 1 ? '' : 's'}`);
    else if (spawn.how === 'alpha') parts.push('Only spawns as a field boss');
    else parts.push('Only spawns inside dungeons');
    if (spawn.night) parts.push('at night only');
    if (spawn.alpha && spawn.how === 'wild') parts.push('also roams as an alpha');
    return parts.join(', ');
}

/** Bonus catches paid for a species (0 when the player never caught one). */
export function bonusOf(progress, id) {
    return (progress && progress.bonus && progress.bonus[id]) || 0;
}

export function caughtOf(progress, id) {
    return (progress && progress.caught && progress.caught[id]) || 0;
}

/** The pips under a card: [{full}] x cap. */
export function bonusPips(n, cap = BONUS_CAP) {
    return Array.from({ length: cap }, (_, i) => ({ full: i < n }));
}

export function deckMatches(row, query) {
    const q = (query || '').trim().toLowerCase();
    if (!q) return true;
    return row.name.toLowerCase().includes(q) || row.id.toLowerCase().includes(q) || String(row.number).toLowerCase() === q.replace(/^#/, '');
}

function howMatches(row, how) {
    const s = row.spawn;
    switch (how) {
        case '': return true;
        case 'catchable': return !!s && (s.how === 'wild' || s.how === 'alpha');
        case 'none': return !s;
        default: return !!s && s.how === how;
    }
}

/**
 * The rows to draw. `missingOnly` needs a player's progress and keeps the
 * species with bonus catches still to earn (and, when `wildOnly`, only the
 * ones you can go and catch, which is what the fast-EXP list is for).
 */
export function filterDeck(rows, { query = '', element = '', work = '', how = '', drop = '', skill = '', progress = null, missingOnly = false, cap = BONUS_CAP } = {}) {
    return (rows || []).filter(r =>
        deckMatches(r, query)
        && (!element || (r.element_types || []).includes(element))
        && (!work || (r.work_suitability || {})[work] > 0)
        && (!drop || (r.drops || []).includes(drop))
        && (!skill || (r.learns || []).includes(skill))
        && howMatches(r, how)
        && (!missingOnly || !progress || bonusOf(progress, r.id) < cap));
}

/** Sort a copy. `number` keeps the API's deck order. */
export function sortDeck(rows, sort, progress = null, cap = BONUS_CAP) {
    const out = [...(rows || [])];
    const level = r => (r.spawn && r.spawn.min_level != null ? r.spawn.min_level : Infinity);
    const byName = (a, b) => a.name.localeCompare(b.name);
    switch (sort) {
        case 'name': out.sort(byName); break;
        case 'level': out.sort((a, b) => level(a) - level(b) || byName(a, b)); break;
        case 'owned': out.sort((a, b) => (b.owned || 0) - (a.owned || 0) || byName(a, b)); break;
        case 'missing':
            out.sort((a, b) => bonusOf(progress, a.id) - bonusOf(progress, b.id) || level(a) - level(b) || byName(a, b));
            break;
        default: break;
    }
    return out;
}

/**
 * The strip above a player's deck: what the next catch pays, catches to
 * the next level, species maxed. Figures come from the API (already at the
 * server's EXP rate); this only shapes them. `index` is the shared discovery
 * chain (catches, areas, bosses, relics ... all advance it), `catches` the
 * bonus catches alone.
 */
export function bonusSummary(progress, totalSpecies, cap = BONUS_CAP) {
    if (!progress) return null;
    const done = progress.species_done || 0;
    return {
        done,
        total: totalSpecies,
        left: progress.bonus_left != null ? progress.bonus_left : Math.max(totalSpecies * cap - (progress.bonus_index || 0), 0),
        index: progress.chain_index || progress.bonus_index || 0,
        catches: progress.bonus_index || 0,
        nextExp: progress.next_bonus_exp || 0,
        toLevel: progress.catches_to_next_level,
        expToLevel: progress.exp_to_next_level,
        level: progress.level,
    };
}

/** The status screen's EXP bar for a player: {pct, label, tip} or null at the cap / without the table. */
export function expBar(player) {
    const p = player && player.exp_progress;
    if (!p || !p.span) return null;
    const pct = Math.max(0, Math.min(100, (p.into / p.span) * 100));
    return {
        pct,
        label: `${p.to_next.toLocaleString()} to Lv ${(player.level || 0) + 1}`,
        tip: `${p.into.toLocaleString()} / ${p.span.toLocaleString()} EXP into level ${player.level} (${(player.exp || 0).toLocaleString()} total)`,
    };
}
