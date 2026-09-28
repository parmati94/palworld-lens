/**
 * Paldeck tab state and actions, mixed into the app scope (app.js spreads
 * `paldeckState()` into its data object) so the tab, the species modal, the
 * player modal's "Open in Paldeck" and the URL hash all see one set of fields.
 * Derived values are methods, not getters: an object spread copies a getter's
 * value once, so a `get deckRows()` here would freeze as [] at startup.
 *
 * The deck is a species list (every entry the game numbers), never the owned
 * pals; the only owned data on a card is a server-wide count. Picking a player
 * overlays their capture-bonus progress (pips per card, the summary strip,
 * the "missing" filter). Data: /api/paldeck once per tab visit, refreshed
 * when the save reloads (the owned counts and the players' chains move).
 */
import { api } from './services/api.js';
import { BONUS_CAP, DECK_SORTS, SPAWN_HOW, bonusOf, bonusSummary, caughtOf, filterDeck, sortDeck } from './paldeck.js';

export const DECK_SORT_IDS = DECK_SORTS.map(s => s.value);
export const DECK_HOW_IDS = SPAWN_HOW.map(s => s.value);

export function paldeckState() {
    return {
        paldeck: null,              // last /api/paldeck payload: {species, players, bonus_cap, exp_rate, has_exp_table}
        paldeckLoading: false,
        paldeckError: null,
        paldeckStale: false,        // the save reloaded since the deck was fetched
        deckSearch: '',
        deckElement: '',
        deckWork: '',
        deckHow: '',                // '' | catchable | wild | alpha | dungeon | none
        deckPlayer: '',             // player name whose progress overlays the deck ('' = nobody)
        deckMissing: false,         // with a player: only species with bonus catches left
        deckSort: 'number',
        deckLimit: 120,             // cards rendered (Show more adds 120)
        _paldeckRequest: 0,

        // ---- data ---------------------------------------------------------

        async ensurePaldeck(force = false) {
            if (this.paldeckLoading) return;
            if (this.paldeck && !force && !this.paldeckStale) return;
            this.paldeckLoading = true;
            const req = ++this._paldeckRequest;
            try {
                const data = await api.getPaldeck();
                if (req !== this._paldeckRequest) return;
                this.paldeck = data;
                this.paldeckStale = false;
                this.paldeckError = null;
                // a remembered player who is no longer on the save drops back to Everyone
                if (this.deckPlayer && !(data.players || []).some(p => p.name === this.deckPlayer)) this.deckPlayer = '';
            } catch (err) {
                if (req === this._paldeckRequest) this.paldeckError = err.message || 'Failed to load the Paldeck';
            } finally {
                if (req === this._paldeckRequest) this.paldeckLoading = false;
            }
        },

        /** Called when the save reloads: refetch if the tab is showing, else mark it stale. */
        paldeckInvalidate() {
            if (!this.paldeck) return;
            this.paldeckStale = true;
            if (this.currentTab === 'paldeck') this.ensurePaldeck(true);
        },

        deckSpecies() { return (this.paldeck && this.paldeck.species) || []; },
        deckPlayers() { return (this.paldeck && this.paldeck.players) || []; },
        deckCap() { return (this.paldeck && this.paldeck.bonus_cap) || BONUS_CAP; },
        deckSorts: DECK_SORTS,
        deckHows: SPAWN_HOW,

        /** The picked player's progress row, or null. */
        deckProgress() {
            return this.deckPlayer ? this.deckPlayers().find(p => p.name === this.deckPlayer) || null : null;
        },

        deckSummary() {
            return bonusSummary(this.deckProgress(), this.deckSpecies().length, this.deckCap());
        },

        /** Every element / work type any deck species has, for the filter menus. */
        deckElements() {
            const keys = new Set();
            this.deckSpecies().forEach(s => (s.element_types || []).forEach(e => keys.add(e)));
            return [...keys].map(key => ({ value: key, label: this.elementName(key) })).sort((a, b) => a.label.localeCompare(b.label));
        },
        deckWorkTypes() {
            const keys = new Set();
            this.deckSpecies().forEach(s => Object.keys(s.work_suitability || {}).forEach(w => keys.add(w)));
            return [...keys].map(key => ({ value: key, label: this.workTypeName(key) })).sort((a, b) => a.label.localeCompare(b.label));
        },

        deckRows() {
            const rows = filterDeck(this.deckSpecies(), {
                query: this.deckSearch, element: this.deckElement, work: this.deckWork, how: this.deckHow,
                progress: this.deckProgress(), missingOnly: this.deckMissing && !!this.deckProgress(), cap: this.deckCap(),
            });
            return sortDeck(rows, this.deckSort, this.deckProgress(), this.deckCap());
        },
        deckRowsShown() { return this.deckRows().slice(0, this.deckLimit); },

        deckFilterCount() {
            return [this.deckElement, this.deckWork, this.deckHow].filter(Boolean).length;
        },

        /** Species the picked player still earns bonus EXP from, before the other filters. */
        deckMissingCount() {
            const p = this.deckProgress();
            if (!p) return 0;
            return filterDeck(this.deckSpecies(), { progress: p, missingOnly: true, cap: this.deckCap() }).length;
        },

        deckClearFilters() {
            this.deckSearch = '';
            this.deckElement = '';
            this.deckWork = '';
            this.deckHow = '';
            this.deckMissing = false;
            this.deckLimit = 120;
        },

        deckBonus(id) { return bonusOf(this.deckProgress(), id); },
        deckCaught(id) { return caughtOf(this.deckProgress(), id); },
        deckPipsTip(id) {
            const p = this.deckProgress();
            if (!p) return '';
            const b = this.deckBonus(id), c = this.deckCaught(id);
            if (b >= this.deckCap()) return `${p.name} has all ${this.deckCap()} bonus catches (${c} caught)`;
            return `${p.name}: ${b} of ${this.deckCap()} bonus catches, ${this.deckCap() - b} to go`;
        },

        // ---- navigation ---------------------------------------------------

        /** The Paldeck tab overlaid with one player's progress, missing species first. */
        openPaldeckFor(playerName, missing = true) {
            this.deckPlayer = playerName || '';
            this.deckMissing = !!(missing && playerName);
            if (this.deckMissing) { this.deckSort = 'missing'; this.deckHow = 'catchable'; }
            this.currentTab = 'paldeck';
            this.jumpToTop();
        },

        /** Open the species modal for a deck id (from any tab: pal modal, map, breeding). */
        openSpecies(id) {
            if (!id) return;
            const row = this.deckSpecies().find(s => s.id === id) || null;
            window.dispatchEvent(new CustomEvent('open-species-modal', { detail: { id, row } }));
        },

        /** The Pals tab filtered to this species' pals. */
        viewPalsOfSpecies(name) {
            this.clearFilters();
            this.palSearch = name || '';
            this.currentTab = 'pals';
            this.jumpToTop();
        },

        /** Open an owned pal from the species modal (the full record lives in the app's pal list). */
        openOwnedPal(instanceId) {
            const pal = (this.pals || []).find(p => p.instance_id === instanceId);
            if (pal) window.dispatchEvent(new CustomEvent('open-pal-modal', { detail: pal }));
        },
    };
}
