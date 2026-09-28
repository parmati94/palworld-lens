/**
 * Filter chips: one search box, an "Add filter" menu, and a chip per filter that is set.
 * The bar is one line when nothing is asked and grows only with what is.
 *
 *   <div x-data="filterChips({ defs: () => deckFilterDefs() })">{{> filter-chips search="deckSearch" }}</div>
 *
 * `defs` returns [{key, label, get, set, options, icon?, always?}]: `get`/`set` read and
 * write the page's own state (so the URL hash and everything else keep working), `options`
 * returns [{value, label, icon?, hint?}] and may be long -- the picker searches it.
 * `always: true` pins a chip that cannot be removed (a sort order). Pickers open in one
 * panel under the bar, whichever chip or menu entry asked for it.
 */
export const PICKER_SEARCH_FROM = 12;  // options at or above this get a search box
export const PICKER_LIMIT = 80;        // rows drawn at once; the search narrows the rest

export function filterChips(opts = {}) {
    return {
        open: null,          // def key whose picker is open, '+' for the add menu, or null
        query: '',

        defs() { return (opts.defs ? opts.defs() : []) || []; },
        get active() { return this.defs().filter(d => !d.always && d.get()); },
        get inactive() { return this.defs().filter(d => !d.always && !d.get()); },
        get pinned() { return this.defs().filter(d => d.always); },
        get openDef() { return this.open && this.open !== '+' ? this.defs().find(d => d.key === this.open) || null : null; },

        /** The chip text for a def: the option's label, else the raw value. */
        label(d) {
            const v = d.get();
            const o = d.options().find(o => o.value === v);
            return o ? o.label : v;
        },
        icon(d) {
            const o = d.options().find(o => o.value === d.get());
            return o && o.icon ? o.icon : '';
        },
        searchable(d) { return d.options().length >= PICKER_SEARCH_FROM; },

        list(d) {
            const q = this.query.trim().toLowerCase();
            const all = d.options();
            const rows = q ? all.filter(o => o.label.toLowerCase().includes(q) || String(o.value).toLowerCase().includes(q)) : all;
            return rows.slice(0, PICKER_LIMIT);
        },
        more(d) { return Math.max(this.list(d).length < d.options().length && !this.query ? d.options().length - PICKER_LIMIT : 0, 0); },

        toggle(key) {
            this.open = this.open === key ? null : key;
            this.query = '';
            if (this.openDef && this.searchable(this.openDef)) {
                this.$nextTick(() => { const q = this.$el.querySelector('[data-picker-query]'); if (q) q.focus(); });
            }
        },
        pick(d, value) {
            d.set(value);
            this.open = null;
            this.query = '';
        },
        remove(d) {
            d.set('');
            if (this.open === d.key) this.open = null;
        },
        clearAll() {
            this.defs().forEach(d => { if (!d.always) d.set(''); });
            this.open = null;
        },
    };
}
