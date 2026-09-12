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

/** Element-themed gradient for the pal modal header (dual-element pals blend both). */
export function elementGradient(gameData, ids) {
    if (!ids || ids.length === 0) return 'linear-gradient(135deg, #3b82f6, #8b5cf6, #3b82f6)';
    const c1 = elementInfo(gameData, ids[0]).color;
    const c2 = ids.length > 1 ? elementInfo(gameData, ids[1]).color : c1;
    return `linear-gradient(135deg, ${shadeHex(c1, -25)}, ${c1}, ${shadeHex(c2, 10)}, ${shadeHex(c1, -25)})`;
}

export const WORK_LEVEL_COLORS = {
    1: '#9ca3af',  // gray-400
    2: '#22c55e',  // green-500
    3: '#3b82f6',  // blue-500
    4: '#8b5cf6',  // violet-500
    5: '#f59e0b',  // amber-500
};

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
            color: WORK_LEVEL_COLORS[level] || '#9ca3af',
        });
    }
    return out;
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
    if (v >= 50) return 'bg-green-500';
    if (v >= 25) return 'bg-amber-500';
    return 'bg-red-500';
}
export function needTextClass(pct) {
    const v = Number(pct) || 0;
    if (v >= 50) return 'text-green-400';
    if (v >= 25) return 'text-amber-400';
    return 'text-red-400';
}

/** Tinted chip classes for a 0–100 need value (icon + percentage pills). */
export function needChipClass(pct) {
    const v = Number(pct) || 0;
    if (v >= 50) return 'bg-green-500/15 text-green-300 border-green-500/30';
    if (v >= 25) return 'bg-amber-500/15 text-amber-300 border-amber-500/30';
    return 'bg-red-500/15 text-red-300 border-red-500/30';
}
