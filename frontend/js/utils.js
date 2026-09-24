/**
 * Utility functions for Palworld Lens
 */
import mapLayersJson from '../../data/json/map_layers.json' with { type: 'json' };

/**
 * Format a date string to localized format
 */
export function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString();
}

/**
 * Format bytes to human-readable file size
 */
export function formatFileSize(bytes) {
    if (!bytes) return 'N/A';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 B';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 10) / 10 + ' ' + sizes[i];
}

// ---------------------------------------------------------------------------
// Element / work-type reference data. The API sends ids (Leaf, EmitFlame, ...);
// names, icons and colours come from /api/game-data (data/json/elements.json and
// l10n/work_suitability.json + backend/common/constants.py). Nothing here
// hardcodes an element or a work type.
// ---------------------------------------------------------------------------
const FALLBACK_ELEMENT = { color: '#6b7280', icon: 'neutral', icon_white: 'neutral_white' };

export function elementInfo(gameData, id) {
    const e = gameData && gameData.elements && gameData.elements[id];
    return e || { ...FALLBACK_ELEMENT, name: id || 'Unknown' };
}

/** Lighten (pct > 0) or darken (pct < 0) a #rrggbb colour by a percentage. */
export function shadeHex(hex, pct) {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
    if (!m) return hex;
    const n = parseInt(m[1], 16);
    const ch = (v) => Math.max(0, Math.min(255, Math.round(v + (pct >= 0 ? (255 - v) : v) * pct / 100)));
    const r = ch(n >> 16), g = ch((n >> 8) & 255), b = ch(n & 255);
    return '#' + ((r << 16) | (g << 8) | b).toString(16).padStart(6, '0');
}

/** `#rrggbb` + alpha (0..1) -> `#rrggbbaa`, for inline element tints. */
export function hexAlpha(hex, alpha) {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
    if (!m) return hex;
    return '#' + m[1] + Math.round(Math.max(0, Math.min(1, alpha)) * 255).toString(16).padStart(2, '0');
}

/**
 * Pal modal header backdrop: the dark card surface with the element colour(s)
 * glowing through from the corners. Dual-element pals get one glow each.
 */
export function elementBackdrop(gameData, ids) {
    const base = '#111827';
    if (!ids || ids.length === 0) {
        return `radial-gradient(50rem 22rem at 12% -10%, rgb(var(--accent-500) / 0.3), transparent 60%), ${base}`;
    }
    const c1 = elementInfo(gameData, ids[0]).color;
    const c2 = ids.length > 1 ? elementInfo(gameData, ids[1]).color : c1;
    return `radial-gradient(50rem 22rem at 12% -10%, ${hexAlpha(c1, 0.45)}, transparent 60%), `
         + `radial-gradient(40rem 18rem at 100% 120%, ${hexAlpha(c2, 0.3)}, transparent 60%), ${base}`;
}

/**
 * Work suitability runs 1..10 since 1.0 (pals are born with up to 7-8; 9 and 10
 * come from condensing, Applied Technique books and base auras). Levels get
 * hotter as they climb; 9 and 10 borrow the legendary passive treatment via
 * `workLevelBadgeClass` and have no flat colour.
 */
export const WORK_LEVEL_COLORS = {
    1: '#9ca3af',  // gray-400
    2: '#22c55e',  // green-500
    3: '#3b82f6',  // blue-500
    4: '#8b5cf6',  // violet-500
    5: '#f59e0b',  // amber-500
    6: '#f97316',  // orange-500
    7: '#ef4444',  // red-500
    8: '#f43f5e',  // rose-500
};

/** Extra class for the modal badge: the legendary gradient at 9, gold-ringed at 10. */
export function workLevelBadgeClass(level) {
    if (level >= 10) return 'work-badge-max';
    if (level >= 9) return 'work-badge-legendary';
    return '';
}

/** [{type, name, level, icon, color}] for every work type a pal has at level > 0. */
export function workSuitabilityDisplay(gameData, pal) {
    const types = (gameData && gameData.work_types) || {};
    const out = [];
    for (const [type, level] of Object.entries((pal && pal.work_suitability) || {})) {
        if (!(level > 0)) continue;
        const ref = types[type] || {};
        out.push({
            type,
            name: ref.name || type,
            level,
            icon: ref.icon || 'unknown',
            color: WORK_LEVEL_COLORS[Math.min(level, 8)] || '#9ca3af',
            badge: workLevelBadgeClass(level),
        });
    }
    return out;
}

/** "Kelp Farm · Kelpsea Hill" / "Base 3 · Kelpsea Hill" / "Base 3" -- name plus where it is. */
export function baseLabel(base) {
    if (!base) return '';
    const name = base.base_name || '';
    const place = base.place || base.base_place || '';
    return place && place !== name ? `${name} · ${place}` : name;
}

export const PARTNER_SKILL_LEVELS = 5;

/**
 * A pal's partner skill at its condensing level: {name, level, description, levels}
 * from gameData.partner_skills (data/json/partner_skills.json), or null when the
 * species has none. The level is the save's Rank (1-5; absent = 1).
 */
export function partnerSkillFor(gameData, pal) {
    const table = (gameData && gameData.partner_skills) || {};
    const entry = pal && pal.species_id ? table[pal.species_id] : null;
    if (!entry || !entry.levels || !entry.levels.length) return null;
    const level = Math.max(1, Math.min(PARTNER_SKILL_LEVELS, parseInt(pal.rank, 10) || 1));
    const levels = entry.levels;
    return {
        name: entry.name,
        level,
        current: levels[Math.min(level, levels.length) - 1],   // {text, mount, bonus}
        levels,
        // The text only changes between levels when it carries numbers (fixed-text skills repeat)
        grows: new Set(levels.map(l => JSON.stringify(l))).size > 1,
    };
}

const MOUNT_LABELS = { ground: 'Mount', flying: 'Flying mount', water: 'Water mount' };
export function mountLabel(kind) { return MOUNT_LABELS[kind] || ''; }

const HTML_ESCAPE = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
const PARTNER_TAG = /<(up|kw|mu)>|<el ([A-Za-z]+)>|<\/(up|kw|mu|el)>/g;

/**
 * Partner skill text -> HTML. The generator leaves only four tags in the text
 * (<up> a growing number, <kw> a keyword, <el X> an element name, <mu> a muted
 * aside); everything else is escaped here, so nothing from the data file runs.
 */
export function partnerSkillHtml(gameData, text) {
    let out = '', pos = 0;
    const esc = s => s.replace(/[&<>"]/g, c => HTML_ESCAPE[c]);
    for (const m of (text || '').matchAll(PARTNER_TAG)) {
        out += esc(text.slice(pos, m.index));
        pos = m.index + m[0].length;
        if (m[3]) out += '</span>';
        else if (m[2]) out += `<span class="font-medium" style="color:${elementInfo(gameData, m[2]).color}">`;
        else if (m[1] === 'up') out += '<span class="text-amber-200 font-semibold tabular-nums">';
        else if (m[1] === 'kw') out += '<span class="text-gray-50 font-medium">';
        else out += '<span class="text-gray-500">';
    }
    out += esc((text || '').slice(pos));
    return out.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');
}

// ---------------------------------------------------------------------------
// Items. A schematic slot keeps the game's blueprint icon and carries a
// `schematic` block (backend/common/schematics.py) whose `icon` is the product
// the UI layers on top, the way the game's item widget does.
// ---------------------------------------------------------------------------
// The game frames each inventory slot in its rarity colour. Ring classes for the icon tile;
// tiers outside 0-4 (or missing) get the plain Common frame.
export const RARITY_RING_CLASSES = {
    0: 'ring-gray-600/70',
    1: 'ring-green-500/70',
    2: 'ring-blue-500/80',
    3: 'ring-purple-500/80',
    4: 'ring-amber-400/90',
};

export function rarityRingClass(rarity) {
    return RARITY_RING_CLASSES[rarity] ?? RARITY_RING_CLASSES[0];
}

/** Case-insensitive match on the item's name, id, or (for a schematic) the product it unlocks. */
export function itemMatches(item, query) {
    const q = (query || '').trim().toLowerCase();
    if (!q) return true;
    const hay = [item.item_name, item.item_id, item.schematic && item.schematic.product_name];
    return hay.some(s => s && String(s).toLowerCase().includes(q));
}

/**
 * Containers that hold something matching `query`, each with `items` cut down to the matches.
 * A blank query returns the list untouched, so callers can bind to it unconditionally.
 */
export function searchContainers(containers, query) {
    const q = (query || '').trim();
    if (!q) return containers || [];
    return (containers || [])
        .map(c => ({ ...c, items: (c.items || []).filter(i => itemMatches(i, q)) }))
        .filter(c => c.items.length > 0);
}

/** Sum of item counts across a container list (after searchContainers, the matching total). */
export function sumItemCounts(containers) {
    return (containers || []).reduce((n, c) => n + (c.items || []).reduce((m, i) => m + (i.count || 0), 0), 0);
}

/**
 * Where else on the server `query` turns up: one row per other base, biggest total first.
 * `containersByBase` is the API's {base_id: [container]} map.
 *
 * A shared guild chest stands at several bases with one container_id, so it is counted once
 * and gets its own row (label = the chest's name, click lands on the first base it stands
 * at); one already on screen at the current base is skipped. Different guilds name their
 * bases the same way ("Base 2") and every guild's chest is "Guild Chest", so pass
 * `ownerOf(baseId)` and rows whose label clashes are marked `ambiguous` with the owner attached.
 * `onlyBases` (a Set of base ids) limits the sweep, e.g. to the guild's own bases: "where did
 * I put it" is a question about your chests, not the neighbours'.
 */
export function searchElsewhere(containersByBase, currentBaseId, query, { skipTypes = ['food_bowl'], ownerOf = null, onlyBases = null } = {}) {
    const q = (query || '').trim();
    if (!q || !containersByBase) return [];
    const seen = new Set((containersByBase[currentBaseId] || []).map(c => c.container_id));
    const perBase = new Map();
    const rows = [];
    for (const [baseId, containers] of Object.entries(containersByBase)) {
        if (baseId === currentBaseId || (onlyBases && !onlyBases.has(baseId))) continue;
        for (const c of searchContainers(containers.filter(c => !skipTypes.includes(c.container_type)), q)) {
            if (seen.has(c.container_id)) continue;
            seen.add(c.container_id);
            const count = sumItemCounts([c]);
            if (c.shared) {
                const at = (c.shared_at && c.shared_at.length ? c.shared_at : [{ base_id: baseId, base_name: c.base_name }]);
                rows.push({ base_id: at[0].base_id, base_name: at[0].base_name || baseId, label: c.display_name || 'Guild chest',
                            shared: true, at: at.map(b => b.base_name), chests: 1, count, owner: ownerOf ? ownerOf(at[0].base_id) : '' });
                continue;
            }
            let row = perBase.get(baseId);
            if (!row) {
                row = { base_id: baseId, base_name: c.base_name || baseId, label: c.base_name || baseId, shared: false,
                        chests: 0, count: 0, owner: ownerOf ? ownerOf(baseId) : '' };
                perBase.set(baseId, row);
                rows.push(row);
            }
            row.chests += 1;
            row.count += count;
        }
    }
    // Two guilds' "Base 2", or two guilds' "Guild Chest": the label alone will not do.
    const labels = new Map();
    for (const r of rows) labels.set(r.label, (labels.get(r.label) || 0) + 1);
    for (const r of rows) r.ambiguous = (labels.get(r.label) || 0) > 1;
    return rows.sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

// ---------------------------------------------------------------------------
// Base activity (/api/activity). Status names come from the backend
// (backend/parser/builders/activity.py); the words and colours live here.
// ---------------------------------------------------------------------------
export const ACTIVITY_STATUS = {
    ready:        { label: 'Ready',            chip: 'bg-amber-500/15 text-amber-200 border-amber-500/40',   bar: 'bg-amber-400' },
    working:      { label: 'Working',          chip: 'bg-emerald-500/15 text-emerald-200 border-emerald-500/40', bar: 'bg-emerald-400' },
    unstaffed:    { label: 'Nobody on it',     chip: 'bg-orange-500/15 text-orange-200 border-orange-500/40', bar: 'bg-orange-400' },
    no_materials: { label: 'Out of materials', chip: 'bg-red-500/15 text-red-200 border-red-500/40',         bar: 'bg-red-400' },
    full:         { label: 'Full',             chip: 'bg-red-500/15 text-red-200 border-red-500/40',         bar: 'bg-red-400' },
    empty:        { label: 'No power',         chip: 'bg-red-500/15 text-red-200 border-red-500/40',         bar: 'bg-red-400' },
    idle:         { label: 'Idle',             chip: 'bg-gray-700/60 text-gray-400 border-gray-600/60',      bar: 'bg-gray-500' },
};

export function activityStatus(status) {
    return ACTIVITY_STATUS[status] || ACTIVITY_STATUS.idle;
}

/** Job cards in three groups: what wants a look, what is running, what sits idle. Empty groups are dropped. */
export function activityGroups(jobs) {
    const groups = [
        { id: 'attention', label: 'Needs a look', jobs: [] },
        { id: 'working', label: 'Working', jobs: [] },
        { id: 'idle', label: 'Idle', jobs: [] },
    ];
    for (const j of jobs || []) {
        const g = j.status === 'working' ? groups[1] : j.status === 'idle' ? groups[2] : groups[0];
        g.jobs.push(j);
    }
    // same-shaped cards side by side: machines, then sites, power, plots, incubators, the rest
    for (const g of groups) {
        g.jobs.sort((a, b) => (kindRank(a.kind) - kindRank(b.kind)) || (a.display_name || '').localeCompare(b.display_name || '') || (a.instance_id || '').localeCompare(b.instance_id || ''));
    }
    return groups.filter(g => g.jobs.length);
}

const KIND_ORDER = ['machine', 'station', 'generator', 'crop', 'incubator', 'ranch', 'breeding', 'expedition', 'lab'];
function kindRank(kind) {
    const i = KIND_ORDER.indexOf(kind);
    return i < 0 ? KIND_ORDER.length : i;
}

/** Palworld's per-family colours for the Activity cards: the hero tile, the progress bar, the caption. */
export const ACTIVITY_KIND = {
    machine:    { label: 'Machine',    tile: 'bg-orange-500/15 ring-orange-400/40', bar: 'bg-orange-400', text: 'text-orange-300' },
    station:    { label: 'Station',    tile: 'bg-teal-500/15 ring-teal-400/40',     bar: 'bg-teal-400',   text: 'text-teal-300' },
    crop:       { label: 'Plot',       tile: 'bg-lime-500/15 ring-lime-400/40',     bar: 'bg-lime-400',   text: 'text-lime-300' },
    incubator:  { label: 'Incubator',  tile: 'bg-amber-500/15 ring-amber-400/40',   bar: 'bg-amber-400',  text: 'text-amber-300' },
    ranch:      { label: 'Ranch',      tile: 'bg-pink-500/15 ring-pink-400/40',     bar: 'bg-pink-400',   text: 'text-pink-300' },
    breeding:   { label: 'Breeding',   tile: 'bg-rose-500/15 ring-rose-400/40',     bar: 'bg-rose-400',   text: 'text-rose-300' },
    generator:  { label: 'Power',      tile: 'bg-sky-500/15 ring-sky-400/40',       bar: 'bg-sky-400',    text: 'text-sky-300' },
    expedition: { label: 'Expedition', tile: 'bg-violet-500/15 ring-violet-400/40', bar: 'bg-violet-400', text: 'text-violet-300' },
    lab:        { label: 'Research',   tile: 'bg-violet-500/15 ring-violet-400/40', bar: 'bg-violet-400', text: 'text-violet-300' },
};
const PLAIN_KIND = { label: '', tile: 'bg-gray-900/60 ring-gray-700/60', bar: 'bg-gray-400', text: 'text-gray-400' };

export function activityKind(kind) {
    return ACTIVITY_KIND[kind] || PLAIN_KIND;
}

/**
 * What a card leads with: the product (ingot, berry, egg, hatched pal) rather than the building.
 * { item, pal, title, caption } -- one of item / pal is set when there is a product to show;
 * otherwise the building's own icon is the tile and the title is the building.
 */
export function activityHero(job) {
    if (!job) return { item: null, pal: null, title: '', caption: '' };
    const building = job.display_name || '';
    if ((job.kind === 'machine' || job.kind === 'station') && job.product) {
        return { item: job.product, pal: null, title: job.product.item_name, caption: building };
    }
    if (job.kind === 'crop' && job.crop) {
        return { item: { item_id: job.crop.crop_id, item_name: job.crop.name, icon: job.crop.icon, rarity: null },
                 pal: null, title: job.crop.name, caption: building };
    }
    if (job.kind === 'incubator' && job.eggs && job.eggs.length === 1) {
        const e = job.eggs[0];
        if (e.hatched && e.species_id) {
            return { item: null, pal: { name: e.name || e.species_id, image_candidates: e.image_candidates || [] },
                     title: e.name || e.species_id, caption: building };
        }
        if (e.egg) return { item: e.egg, pal: null, title: e.egg.item_name, caption: building };
    }
    if (job.kind === 'expedition' && job.expedition && job.expedition.state !== 'idle') {
        return { item: null, pal: null, title: job.expedition.name || job.expedition.mission_id, caption: building };
    }
    return { item: null, pal: null, title: building, caption: '' };
}

/** The pals on a card: an expedition's crew, otherwise whoever is assigned to the building. */
/** A breeding farm's one line: eggs to pick up, else what the pair is doing. */
export function breedingLine(job, crewCount) {
    const eggs = job.held || 0;
    const noCake = crewCount && !(job.inputs || []).length;
    if (eggs) return `${eggs} egg${eggs === 1 ? '' : 's'} to collect${noCake ? ' · no cake' : ''}`;
    if (!crewCount) return 'nobody on it';
    return noCake ? 'no cake' : 'breeding';
}

export function activityCrew(job) {
    if (!job) return [];
    return job.expedition ? (job.expedition.pals || []) : (job.assigned || []);
}
export const CREW_INLINE_MAX = 3;   // more than this and the card shows a button that opens the crew modal (keeps the row to one line)

/** Title + subtitle for the crew modal: "Astral Frost Cavern" / "100 pals · Away, 58m left". */
export function crewModalDetail(job) {
    const pals = activityCrew(job);
    const e = job.expedition;
    const title = e ? (e.name || e.mission_id || job.display_name) : job.display_name;
    let state = '';
    if (e) state = e.state === 'out' ? `On expedition, ${formatDuration(e.seconds_left)} left` : e.state === 'back' ? 'Haul waiting' : 'Idle';
    return { title, subtitle: `${pals.length} pal${pals.length === 1 ? '' : 's'}${state ? ' · ' + state : ''}`, pals };
}

/** "2 hatched · 1 incubating" for an incubator's eggs; '' when empty. */
export function eggSummary(eggs) {
    const list = eggs || [];
    const hatched = list.filter(e => e.hatched).length;
    const incubating = list.length - hatched;
    const parts = [];
    if (hatched) parts.push(`${hatched} hatched`);
    if (incubating) parts.push(`${incubating} incubating`);
    return parts.join(' · ');
}

/** Title + subtitle + eggs for the egg modal (the crew modal, showing eggs). */
export function eggModalDetail(job) {
    const eggs = job.eggs || [];
    return { title: job.display_name, subtitle: `${eggs.length} egg${eggs.length === 1 ? '' : 's'} · ${eggSummary(eggs)}`, eggs };
}
export const EGGS_INLINE_MAX = 1;   // one egg draws on the card itself; more open the modal

/** A breeding farm's eggs on the ground, one tile per egg for the stacked button (capped). */
export function eggStack(job, max = 5) {
    const out = [];
    for (const item of job.outputs || []) {
        for (let i = 0; i < (item.count || 0) && out.length < max; i++) out.push({ ...item, key: `${item.item_id}-${i}` });
    }
    return out;
}

/** Title + subtitle + item rows for the modal behind that button: "Breeding Farm" / "15 eggs on the ground". */
export function farmEggsModalDetail(job) {
    const n = job.held || 0;
    return { title: job.display_name, subtitle: `${n} egg${n === 1 ? '' : 's'} on the ground`, items: job.outputs || [] };
}

// ---- pal stats ----

/** The hover behind a pal's Attack / Defense / Max HP tile, like the game's: "Base 1,006 · Trust +6 · Souls +36% · Passives +20%";
 *  '' when the pal has no breakdown. */
export function palStatTip(pal, stat) {
    const b = pal && pal.stat_breakdown && pal.stat_breakdown[stat];
    if (!b) return '';
    const parts = [`Base ${b.base.toLocaleString()}`];
    if (b.trust) parts.push(`Trust +${b.trust.toLocaleString()}`);
    if (b.souls_pct) parts.push(`Souls +${b.souls_pct}%`);
    if (b.passives_pct) parts.push(`Passives ${b.passives_pct > 0 ? '+' : ''}${b.passives_pct}%`);
    return parts.join(' · ');
}

/** True when anything beyond level, talents and stars lifts the stat (the game's little arrow). */
export function palStatEnhanced(pal, stat) {
    const b = pal && pal.stat_breakdown && pal.stat_breakdown[stat];
    return !!b && (b.trust !== 0 || b.souls_pct !== 0 || b.passives_pct !== 0);
}

// ---- player card + modal ----

/** The gear container's fixed slots (1.0, nine slots; verified on five players): 0 head, 1 body,
 *  2/3/6/7 accessories (a 2x2 in the game), 4 shield, 5 glider, 8 sphere module. */
export const GEAR_SLOT_ROWS = [
    { label: 'Head', slots: [0] },
    { label: 'Body', slots: [1] },
    { label: 'Shield', slots: [4] },
    { label: 'Glider', slots: [5] },
    { label: 'Sphere Module', short: 'Module', slots: [8] },
];
export const ACCESSORY_SLOTS = [2, 3, 6, 7];
const GEAR_SLOTS_BY_TYPE = { ArmorHead: [0], ArmorBody: [1], Accessory: ACCESSORY_SLOTS, Shield: [4], Glider: [5], SphereModule: [8] };
const EQUIP_TYPES = new Set(['ArmorHead', 'ArmorBody', 'Accessory', 'Shield', 'Glider', 'SphereModule']);

/** {slot index: item} for the gear container. An item without a slot index goes to the first free
 *  slot of its type; anything left over lands on `other`. */
export function gearBySlot(player) {
    const at = {};
    const other = [];
    for (const item of (player && player.gear) || []) {
        let i = item.slot_index;
        if (!(Number.isInteger(i) && i >= 0 && i <= 8 && !at[i])) {
            i = (GEAR_SLOTS_BY_TYPE[item.slot] || []).find(s => !at[s]);
        }
        if (i === undefined) other.push(item); else at[i] = item;
    }
    return { at, other };
}

/** [{label, items: [item | null, ...]}] for the single-slot gear rows, plus an 'Other' row for gear
 *  that fits nowhere (a slot we don't know). */
export function gearRows(player) {
    const { at, other } = gearBySlot(player);
    const rows = GEAR_SLOT_ROWS.map(r => ({ label: r.label, short: r.short, items: r.slots.map(s => at[s] || null) }));
    if (other.length) rows.push({ label: 'Other', items: other });
    return rows;
}

/** The four accessory slots in the game's 2x2 order. */
export function accessorySlots(player) {
    const { at } = gearBySlot(player);
    return ACCESSORY_SLOTS.map(s => at[s] || null);
}

/** The weapon slots as the game lays them out: four down the left, the rest (two) on the right. */
export function weaponColumns(player) {
    const grid = slotGrid(player && player.weapons, Math.max(player && player.weapon_slots || 0, 4));
    return { left: grid.slice(0, 4), right: grid.slice(4) };
}

/** The stack's weight as the game prints it on the tile ("5.6"); '' when the item's weight is unknown. */
export function stackWeight(item) {
    if (!item || typeof item.weight !== 'number') return '';
    return (item.weight * (item.count || 1)).toFixed(1);
}

/** Equipment shows no count; everything else does, the way the game's tiles do. */
export function showCount(item) {
    return !!item && !EQUIP_TYPES.has(item.slot) && (item.count || 0) >= 1;
}

const RARITY_BAR_CLASSES = { 0: 'bg-gray-500/60', 1: 'bg-green-400/80', 2: 'bg-blue-400/90', 3: 'bg-purple-400/90', 4: 'bg-amber-300' };
export function rarityBarClass(rarity) {
    return RARITY_BAR_CLASSES[rarity] ?? RARITY_BAR_CLASSES[0];
}

/** A container as the game draws it: every one of n slots, empty ones included, each item where it
 *  sits (slot_index). An item without a slot index, past the end, or on a taken slot takes the next
 *  free one; an item is never dropped, so the grid grows past n if it has to. */
export function slotGrid(items, n) {
    const list = items || [];
    const size = Math.max(n || 0, list.length);
    const grid = new Array(size).fill(null);
    const later = [];
    for (const item of list) {
        const i = item.slot_index;
        if (Number.isInteger(i) && i >= 0 && i < size && grid[i] === null) grid[i] = item;
        else later.push(item);
    }
    for (const item of later) grid[grid.indexOf(null)] = item;
    return grid;
}

/** The bag grid. */
export function bagGrid(player) {
    return slotGrid(player && player.bag, player && player.bag_slots);
}

/** Carried weight against the player's max (with gear, when the breakdown is there): {carried, max, pct, over}. */
export function weightLine(player) {
    const carried = Number(player && player.carried_weight) || 0;
    const s = player && player.stats && player.stats.weight;
    const max = Number(s ? s.total : player && player.calculated_weight) || 0;
    const pct = max ? Math.min(100, Math.round(carried / max * 100)) : 0;
    return { carried, max, pct, over: max > 0 && carried > max };
}

/** The game's status page: [{key, label, value, base, gear, food, enhanced, points, ancient}] (`ancient` = the
 *  save's GotExStatusPointList: extra points from elixirs, DT_GainStatusPointsItem).
 *  `value` is the enhanced total when the player carries a stats breakdown, else the base value.
 *  Capture power is points only. */
export function statusRows(player) {
    const p = player || {};
    const st = p.stats || {};
    const row = (key, label, baseValue, points, ancient) => {
        const s = st[key];
        const base = s ? s.base : baseValue;
        const gear = s ? s.gear : 0, food = s ? s.food : 0;
        const value = s ? s.total : baseValue;
        return { key, label, value, base, gear, food, enhanced: (gear || 0) + (food || 0) !== 0, points: points || 0, ancient: ancient || 0 };
    };
    return [
        row('hp', 'Health', p.calculated_max_hp, p.stat_points_hp, p.ex_stat_points_hp),
        row('stamina', 'Stamina', p.calculated_stamina, p.stat_points_stamina, p.ex_stat_points_stamina),
        row('attack', 'Attack', p.calculated_attack, p.stat_points_attack, p.ex_stat_points_attack),
        row('defense', 'Defense', st.defense ? undefined : null, 0, 0),
        row('work_speed', 'Work speed', p.calculated_work_speed, p.stat_points_work_speed, p.ex_stat_points_work_speed),
        row('weight', 'Weight', p.calculated_weight, p.stat_points_weight, p.ex_stat_points_weight),
        { key: 'capture', label: 'Capture power', value: null, base: null, gear: 0, food: 0, enhanced: false, points: p.stat_points_capture || 0, ancient: 0 },
    ].filter(r => r.value != null || r.points || r.key === 'capture');
}

/** The hover text behind a status row: "Base 1,900 · Gear +1,650 · Food +435 (Pizza) · 14 pts spent · 29 from elixirs". */
export function statusTip(row, player) {
    if (!row || row.value == null) return '';
    const parts = [`Base ${row.base.toLocaleString()}`];
    if (row.gear) parts.push(`Gear ${row.gear > 0 ? '+' : ''}${row.gear.toLocaleString()}`);
    if (row.food) {
        const dish = player && player.food_buff && player.food_buff.item_name;
        parts.push(`Food ${row.food > 0 ? '+' : ''}${row.food.toLocaleString()}${dish ? ` (${dish})` : ''}`);
    }
    if (row.points) parts.push(`${row.points} pts spent`);
    if (row.ancient) parts.push(`${row.ancient} from elixirs`);
    return parts.join(' · ');
}

/** The small figure beside a status row: the stat points spent on it ("14 pts"); elixir points show on hover. */
export function statusPoints(row) {
    return row && row.points ? `${row.points} pts` : '';
}


/** The records strip on a player card: [{label, value, tip}], tech first. Empty when the save had none. */
export function playerRecordCells(player) {
    const r = player && player.records;
    const t = player && player.tech;
    if (!r && !t) return [];
    const cells = [];
    if (t) {
        const spend = [t.points ? `${t.points} tech pts` : '', t.ancient_points ? `${t.ancient_points} ancient pts` : ''].filter(Boolean).join(', ');
        cells.push({ label: 'Tech', value: t.unlocked, tip: spend ? `${spend} to spend` : 'nothing to spend' });
    }
    if (r) cells.push(
        { label: 'Paldeck', value: r.paldeck, tip: `${r.caught.toLocaleString()} pals caught` },
        { label: 'Towers', value: r.towers, tip: 'tower bosses beaten' },
        { label: 'Alphas', value: r.alphas, tip: 'field bosses beaten' },
        { label: 'Dungeons', value: r.dungeons, tip: 'roaming and set dungeons cleared' },
        { label: 'Fast travel', value: r.fast_travels, tip: 'points unlocked' },
    );
    return cells;
}

/** "Too hot"/"too cold" cannot be told apart yet (the save's sign is unverified), so: comfortable or not. */
export function eggTemperature(egg) {
    const d = egg && egg.temp_diff;
    if (d == null || d === 0) return null;
    return { label: 'Wrong temperature', tip: `Off by ${Math.abs(d)} -- a heater or cooler next to it fixes this` };
}

/** Bar colour for how full a site is: fine, filling up (90%+), full. */
export function fillBarClass(fill, base) {
    if (fill == null) return base;
    if (fill >= 0.999) return 'bg-red-400';
    if (fill >= 0.9) return 'bg-amber-400';
    return base;
}

/** A stack count the way the game abbreviates it: 1,234 / 12.3K / 1.2M. */
export function formatCount(n) {
    if (n == null || !isFinite(n)) return '';
    const short = (v) => v.toFixed(1).replace(/\.0$/, '');
    if (n > 999999) return short(n / 1000000) + 'M';
    if (n > 9999) return short(n / 1000) + 'K';
    return n.toLocaleString();
}

/** "1h 12m", "12m", "45s" for a span in seconds; '' for nothing. */
export function formatDuration(seconds) {
    if (seconds == null || !isFinite(seconds)) return '';
    const s = Math.max(0, Math.round(seconds));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    if (h) return `${h}h ${m}m`;
    if (m) return `${m}m`;
    return `${sec}s`;
}

/** One line for a machine's order, the way the game counts it: "776 / 1,335 made"; "order done" once nothing is left. */
export function orderLine(job) {
    if (!job || !job.recipe_id) return '';
    if (!(job.order_total > 0)) return 'no order';
    if (job.order_left <= 0) return `${job.order_total.toLocaleString()} made · complete`;
    return `${(job.order_made || 0).toLocaleString()} / ${job.order_total.toLocaleString()} made`;
}

/** Tooltip for a container slot: what a schematic unlocks, nothing for plain items. */
export function itemTip(item) {
    if (item && item.note) return item.note;
    const s = item && item.schematic;
    if (!s) return (item && item.item_name) ? (item.count > 1 ? `${item.item_name} ×${formatCount(item.count)}` : item.item_name) : '';
    const tier = s.rarity_name ? ` (${s.rarity_name})` : '';
    return s.kind === 'building'
        ? `Schematic: lets you build ${s.product_name}${tier}`
        : `Schematic: unlocks the ${s.product_name} recipe${tier}`;
}

/**
 * Get rank icon filename for passive skills
 */
export function getRankIcon(rank) {
    if (rank < 0) {
        // Use negative rank icons: rank_-1.webp, rank_-2.webp, rank_-3.webp
        return `img/rank_${rank}.webp`;
    } else {
        // Use rank_1 through rank_4, ignore rank_0
        const iconRank = Math.max(1, Math.min(rank, 4));
        return `img/rank_${iconRank}.webp`;
    }
}

/**
 * Get rank color filter for passive skills
 */
export function getRankFilter(rank) {
    if (rank < 0) {
        // Negative ranks: red
        return 'brightness(0) saturate(100%) invert(27%) sepia(51%) saturate(2878%) hue-rotate(346deg) brightness(104%) contrast(97%)';
    } else if (rank === 1) {
        // Rank 1: grey
        return 'brightness(0) saturate(100%) invert(75%) sepia(0%) saturate(0%) hue-rotate(0deg) brightness(92%) contrast(88%)';
    } else if (rank === 2 || rank === 3) {
        // Rank 2-3: gold
        return 'brightness(0) saturate(100%) invert(77%) sepia(72%) saturate(441%) hue-rotate(360deg) brightness(102%) contrast(104%)';
    } else if (rank >= 4) {
        // Rank 4+: purple
        return 'brightness(0) saturate(100%) invert(32%) sepia(90%) saturate(2476%) hue-rotate(262deg) brightness(91%) contrast(101%)';
    }
    return 'none';
}

/**
 * Get passive skill background class based on rank
 */
export function getPassiveBackgroundClass(rank) {
    if (rank < 0) {
        // Negative: red gradient with downward stripes
        return 'passive-bg-negative';
    } else if (rank === 1) {
        // Rank 1: muted grey (default)
        return 'bg-gray-700/50 hover:bg-gray-700/60';
    } else if (rank === 2 || rank === 3) {
        // Rank 2-3: gold gradient with diagonal stripes
        return 'passive-bg-gold';
    } else if (rank >= 4) {
        // Rank 4: cyan-purple gradient with pattern
        return 'passive-bg-legendary';
    }
    return 'bg-gray-700/50 hover:bg-gray-700/60';
}

/**
 * Get passive skill text color based on rank
 */
export function getPassiveTextClass(rank) {
    if (rank >= 2 && rank <= 3) {
        // Gold background needs dark text
        return 'text-gray-900';
    }
    // All others use white text
    return 'text-gray-200';
}

/**
 * Get passive skill description color based on rank
 */
export function getPassiveDescriptionClass(rank) {
    if (rank >= 2 && rank <= 3) {
        // Gold background needs darker description
        return 'text-gray-700';
    }
    // All others use lighter description
    return 'text-gray-400';
}

/**
 * Convert Palworld save coordinates to Leaflet map coordinates
 * SYSTEM: 0-256 Virtual World (Standard Leaflet Scale)
 * [0,0] is Top-Left. [-256, 256] is Bottom-Right.
 */
/**
 * World rectangles each map texture covers, taken verbatim from the game's own
 * DT_WorldMapUIData (landScapeRealPositionMin / landScapeRealPositionMax).
 * Palworld 1.0 added the World Tree as a second map layer with its own texture
 * and its own bounds, so a coordinate alone doesn't say which map it's on.
 *
 * Every span is exactly square and matches the square 8192px texture, so each
 * projection is an exact linear map -- no hand-fitted constants. (The pre-1.0
 * code fitted scaleDivisor/manualOffset by eye against the old artwork, which
 * broke the moment 1.0 redrew it.)
 */
// Pal icons are derived from the character_id, not the data's `icon` field.
// The backend sends `image_candidates` (backend/common/pal_icons.py), most
// specific first; on <img> error walk to the next one, then the legacy
// `<stem>.webp` names, then unknown.webp. Stops for good after that.
export function palIconSrc(pal) {
    const c = (pal && pal.image_candidates && pal.image_candidates[0]) || (pal && pal.image_id) || 'unknown';
    return `/img/t_${c}_icon_normal.webp`;
}

export function palIconError(img, pal) {
    const cands = (pal && pal.image_candidates && pal.image_candidates.length)
        ? pal.image_candidates : [(pal && pal.image_id) || 'unknown'];
    const chain = [
        ...cands.map(c => `/img/t_${c}_icon_normal.webp`),
        ...cands.map(c => `/img/${c}.webp`),
        '/img/unknown.webp',
    ];
    const cur = img.getAttribute('src');
    const i = chain.indexOf(cur);
    const next = chain[i + 1];
    if (!next) { img.onerror = null; return; }
    if (next === '/img/unknown.webp') img.onerror = null;
    img.src = next;
}

// One entry per map texture, from data/json/map_layers.json (shared with
// scripts/slice_map.py, generate_map_objects.py, validate.py and the API).
export const MAP_LAYERS = Object.fromEntries(
    Object.entries(mapLayersJson)
        .filter(([name]) => !name.startsWith('_'))
        .map(([name, m]) => [name, {
            label: m.label, minX: m.x[0], maxX: m.x[1], minY: m.y[0], maxY: m.y[1], tiles: `/img/${m.tiles}`,
        }])
);
export const MAP_LAYER_ORDER = Object.keys(MAP_LAYERS);

/** Which map layer a world coordinate belongs to (MainMap wins on overlap). */
export function layerForCoords(saveX, saveY) {
    for (const name of MAP_LAYER_ORDER) {
        const m = MAP_LAYERS[name];
        if (saveX >= m.minX && saveX <= m.maxX && saveY >= m.minY && saveY <= m.maxY) return name;
    }
    return 'MainMap';
}

/**
 * Convert Palworld save coordinates to MapLibre [lng, lat] for a given layer.
 *
 * The tile pyramids are cut from a square image that fills the entire z0 Web
 * Mercator tile, so a normalised image position (u right, v down, both 0..1)
 * IS a Mercator fraction. Inverting the Mercator projection gives lng/lat:
 *   lng = u * 360 - 180
 *   lat = atan(sinh(pi * (1 - 2v)))
 */
export function saveToLngLat(saveX, saveY, layer = 'MainMap') {
    const m = MAP_LAYERS[layer] || MAP_LAYERS.MainMap;
    const u = (saveY - m.minY) / (m.maxY - m.minY);          // horizontal = world Y
    const v = 1 - ((saveX - m.minX) / (m.maxX - m.minX));    // vertical = world X, inverted
    const lng = u * 360 - 180;
    const lat = Math.atan(Math.sinh(Math.PI * (1 - 2 * v))) * 180 / Math.PI;
    return [lng, lat];
}

/**
 * A static map crop around a world position, for the player modal: the tiles of the layer's pyramid
 * (cut straight from the square map image, so tile (z, x, y) covers u in [x, x+1] / 2^z and v likewise)
 * placed so the position sits at the centre of a w x h box. {layer, tiles: [{src, left, top}], size}.
 */
export function miniMap(location, w = 288, h = 192, zoom = 4) {
    if (!location || !isFinite(location.x) || !isFinite(location.y)) return null;
    const layer = layerForCoords(location.x, location.y);
    const m = MAP_LAYERS[layer];
    const size = 256 * Math.pow(2, zoom);
    const u = (location.y - m.minY) / (m.maxY - m.minY);
    const v = 1 - (location.x - m.minX) / (m.maxX - m.minX);
    const px = Math.min(Math.max(u * size, w / 2), size - w / 2);   // keep the box inside the map
    const py = Math.min(Math.max(v * size, h / 2), size - h / 2);
    const offX = w / 2 - px, offY = h / 2 - py;
    const tiles = [];
    const n = Math.pow(2, zoom);
    for (let ty = Math.floor((py - h / 2) / 256); ty <= Math.floor((py + h / 2 - 1) / 256); ty++) {
        for (let tx = Math.floor((px - w / 2) / 256); tx <= Math.floor((px + w / 2 - 1) / 256); tx++) {
            if (tx < 0 || ty < 0 || tx >= n || ty >= n) continue;
            tiles.push({ src: `${m.tiles}/${zoom}/${tx}/${ty}.webp`, left: tx * 256 + offX, top: ty * 256 + offY });
        }
    }
    return { layer, label: m.label, tiles, size: 256, pin: { left: u * size + offX, top: v * size + offY } };
}

/**
 * Fetch with automatic retry logic
 */
export async function fetchWithRetry(url, options = {}, retries = 3, delay = 1000) {
    options = { ...options, credentials: 'same-origin' };
    
    for (let i = 0; i < retries; i++) {
        try {
            const response = await fetch(url, options);
            
            // If unauthorized, redirect to login immediately (don't retry)
            if (response.status === 401) {
                console.log('🔒 Got 401 Unauthorized, redirecting to login...');
                window.location.replace('/login.html');
                return new Promise(() => {});
            }
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response;
        } catch (err) {
            console.warn(`Fetch attempt ${i + 1}/${retries} failed for ${url}:`, err.message);
            
            // If this is the last retry, throw the error
            if (i === retries - 1) {
                throw err;
            }
            
            // Wait before retrying with exponential backoff
            const waitTime = delay * (i + 1);
            console.log(`Retrying in ${waitTime}ms...`);
            await new Promise(resolve => setTimeout(resolve, waitTime));
        }
    }
}

/**
 * Format uptime in seconds to Days, Hours, Minutes, Seconds
 */
export function formatUptime(seconds) {
    if (!seconds && seconds !== 0) return 'N/A';
    
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    const parts = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);
    if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);
    
    return parts.join(' ');
}

/**
 * Build a compact page list for pagination controls.
 * Returns numbers plus '…' gap markers, e.g. [1, '…', 4, 5, 6, '…', 12].
 */
export function buildPageList(total, current) {
    if (total <= 1) return [1];
    const wanted = new Set([1, total, current - 1, current, current + 1]);
    const pages = [...wanted].filter(p => p >= 1 && p <= total).sort((a, b) => a - b);
    const out = [];
    for (let i = 0; i < pages.length; i++) {
        if (i > 0 && pages[i] - pages[i - 1] > 1) out.push('…');
        out.push(pages[i]);
    }
    return out;
}

/**
 * Human relative time: "just now", "4m ago", "3h ago", "2d ago". `now` is passed
 * in (rather than read) so Alpine re-renders when the caller's clock ticks.
 */
export function formatRelativeTime(dateStr, now = Date.now()) {
    if (!dateStr) return 'N/A';
    const t = new Date(dateStr).getTime();
    if (Number.isNaN(t)) return 'N/A';
    const s = Math.max(0, Math.round((now - t) / 1000));
    if (s < 45) return 'just now';
    const m = Math.round(s / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.round(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.round(h / 24);
    if (d < 30) return `${d}d ago`;
    return new Date(dateStr).toLocaleDateString();
}

/**
 * Colour class for a 0–100 need bar (hunger, sanity, hp%). Green is fine,
 * amber is getting low, red needs attention.
 */
export function needBarClass(pct) {
    const v = Number(pct) || 0;
    if (v >= 50) return 'bg-ok-500';
    if (v >= 25) return 'bg-warn-500';
    return 'bg-danger-500';
}
export function needTextClass(pct) {
    const v = Number(pct) || 0;
    if (v >= 50) return 'text-ok-400';
    if (v >= 25) return 'text-warn-400';
    return 'text-danger-400';
}

/** Tinted chip classes for a 0–100 need value (icon + percentage pills). */
export function needChipClass(pct) {
    const v = Number(pct) || 0;
    if (v >= 50) return 'bg-ok-500/15 text-ok-300 border-ok-500/30';
    if (v >= 25) return 'bg-warn-500/15 text-warn-300 border-warn-500/30';
    return 'bg-danger-500/15 text-danger-300 border-danger-500/30';
}
