/**
 * Per-viewer preferences in localStorage. These are things you set once and
 * expect to stick (table page size, sort, map layers, base sub-tab), never
 * server state or anything that already lives in the URL hash.
 *
 * localStorage can be blocked, full, or wiped, so every access is guarded and
 * the app must work identically with nothing stored.
 */
const KEY = 'palworld-lens:prefs';

export function loadPrefs() {
    try {
        const raw = window.localStorage.getItem(KEY);
        const parsed = raw ? JSON.parse(raw) : null;
        return parsed && typeof parsed === 'object' ? parsed : {};
    } catch {
        return {};
    }
}

export function savePref(key, value) {
    try {
        const prefs = loadPrefs();
        if (value === undefined || value === null) delete prefs[key];
        else prefs[key] = value;
        window.localStorage.setItem(KEY, JSON.stringify(prefs));
    } catch {
        // Storage unavailable: preference just won't persist.
    }
}

/** Read one pref, falling back when it's missing or the wrong type/value. */
export function pref(prefs, key, fallback, allowed = null) {
    const v = prefs[key];
    if (v === undefined || v === null) return fallback;
    if (typeof v !== typeof fallback) return fallback;
    if (allowed && !allowed.includes(v)) return fallback;
    return v;
}
