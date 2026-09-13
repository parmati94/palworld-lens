/**
 * Breeding tab state and actions, mixed into the app scope (app.js spreads
 * `breedingState()` into its data object) so the tab, the pal modal and the
 * URL hash all see one set of fields.
 *
 * Species lookups come from /api/breeding/* (data/json/breeding.json via
 * backend/common/breeding.py). Matching against owned pals is breeding.js.
 */
import { api } from './services/api.js';
import { palsBySpecies, pairOwned, bestCandidates, ownedPassives, comparePairRows } from './breeding.js';

export const BREED_MODES = ['parents', 'child'];

export function breedingState() {
    return {
        breedingSpecies: [],        // [{id, name, image_candidates, element_types, male_probability, ignore_combi}]
        breedingById: {},
        breedingSpeciesLoading: false,
        breedMode: 'parents',       // 'parents': ? + ? -> child (default)   'child': A + B -> ?
        breedA: '',
        breedB: '',
        breedChild: '',
        breedResults: [],           // /child results for (breedA, breedB)
        breedPairs: [],             // /parents pairs for breedChild
        breedTargets: [],           // passive skill ids the child should end up with
        breedOwnedOnly: false,      // parents mode: hide pairs we cannot breed right now
        breedExpanded: {},          // pair key -> candidates shown
        breedLimit: 50,             // parents mode: rows rendered (Show more adds 50)
        breedLoading: false,
        breedError: null,
        _breedOwned: null,          // palsBySpecies cache, cleared when pals change
        _breedPassives: null,       // ownedPassives cache
        _breedCandidates: new Map(),
        _breedRequest: 0,

        // ---- data ---------------------------------------------------------

        async ensureBreedingSpecies() {
            if (this.breedingSpecies.length || this.breedingSpeciesLoading) return;
            this.breedingSpeciesLoading = true;
            try {
                const data = await api.getBreedingSpecies();
                this.breedingSpecies = data.species || [];
                this.breedingById = Object.fromEntries(this.breedingSpecies.map(s => [s.id, s]));
            } catch (err) {
                this.breedError = err.message || 'Failed to load breeding data';
            } finally {
                this.breedingSpeciesLoading = false;
            }
        },

        /** Species row for an id; a stub for ids we have not loaded (renders as the raw id). */
        breedSpecies(id) {
            return this.breedingById[id] || { id, name: id || '', image_candidates: ['unknown'], element_types: [], male_probability: 50 };
        },

        isBreedable(id) {
            return !!(id && this.breedingById[id]);
        },

        breedInvalidateOwned() {
            this._breedOwned = null;
            this._breedPassives = null;
            this._breedCandidates = new Map();
        },

        breedOwned() {
            if (!this._breedOwned) this._breedOwned = palsBySpecies(this.pals);
            return this._breedOwned;
        },

        breedOwnedCount(id) {
            const slot = this.breedOwned()[id];
            return slot ? { Male: slot.Male.length, Female: slot.Female.length } : { Male: 0, Female: 0 };
        },

        breedPassiveOptions() {
            if (!this._breedPassives) this._breedPassives = ownedPassives(this.pals);
            return this._breedPassives;
        },

        breedPassiveName(id) {
            const p = this.breedPassiveOptions().find(x => x.id === id);
            return p ? p.name : id;
        },

        breedPassiveRank(id) {
            const p = this.breedPassiveOptions().find(x => x.id === id);
            return p ? p.rank : 0;
        },

        breedFilteredPassiveOptions(query = '') {
            const q = (query || '').trim().toLowerCase();
            return this.breedPassiveOptions().filter(p => !this.breedTargets.includes(p.id) && (!q || p.name.toLowerCase().includes(q)));
        },

        breedToggleTarget(id) {
            if (this.breedTargets.includes(id)) this.breedTargets = this.breedTargets.filter(x => x !== id);
            else this.breedTargets = [...this.breedTargets, id];
            this._breedCandidates = new Map();
        },

        // ---- queries ------------------------------------------------------

        async runBreeding() {
            const token = ++this._breedRequest;
            this.breedError = null;
            try {
                if (this.breedMode === 'child') {
                    this.breedPairs = [];
                    if (!this.breedA || !this.breedB) { this.breedResults = []; return; }
                    this.breedLoading = true;
                    const data = await api.getBreedingChild(this.breedA, this.breedB);
                    if (token !== this._breedRequest) return;
                    this.breedResults = data.results || [];
                } else {
                    this.breedResults = [];
                    if (!this.breedChild) { this.breedPairs = []; return; }
                    this.breedLoading = true;
                    const data = await api.getBreedingParents(this.breedChild);
                    if (token !== this._breedRequest) return;
                    this.breedPairs = data.pairs || [];
                    this.breedExpanded = {};
                    this.breedLimit = 50;
                }
            } catch (err) {
                if (token === this._breedRequest) this.breedError = err.message || 'Breeding lookup failed';
            } finally {
                if (token === this._breedRequest) this.breedLoading = false;
            }
        },

        breedPairKey(pair) {
            return `${pair.parent_a}|${pair.parent_b}|${pair.child}|${pair.parent_a_gender || ''}|${pair.parent_b_gender || ''}`;
        },

        /** One row per pair: names, ownership and (when targets are set) the best couple. */
        breedRow(pair) {
            const owned = pairOwned(pair, this.breedOwned());
            const key = this.breedPairKey(pair);
            const row = {
                key, pair, owned,
                nameA: this.breedSpecies(pair.parent_a).name,
                nameB: this.breedSpecies(pair.parent_b).name,
                best: null,
            };
            if (owned.feasible && this.breedTargets.length) row.best = this.breedCandidates(row)[0] || null;
            return row;
        },

        /** Parents mode rows, breedable-now first; honours the owned-only toggle. */
        breedRows() {
            let rows = this.breedPairs.map(p => this.breedRow(p));
            if (this.breedOwnedOnly) rows = rows.filter(r => r.owned.feasible);
            return rows.sort(comparePairRows);
        },

        breedVisibleRows() {
            return this.breedRows().slice(0, this.breedLimit);
        },

        breedFeasibleCount() {
            return this.breedPairs.reduce((n, p) => n + (pairOwned(p, this.breedOwned()).feasible ? 1 : 0), 0);
        },

        /** Child mode: the A + B outcome(s) as rows (two for a gender-gated pair). */
        breedChildRows() {
            return this.breedResults.map(p => ({ ...this.breedRow(p), expanded: true }));
        },

        /** Best owned couples for a row, cached per pair + target set. */
        breedCandidates(row) {
            const key = row.key + '#' + this.breedTargets.join(',');
            if (!this._breedCandidates.has(key)) {
                this._breedCandidates.set(key, bestCandidates(row.pair, this.breedOwned(), this.breedTargets));
            }
            return this._breedCandidates.get(key);
        },

        breedToggleRow(key) {
            this.breedExpanded = { ...this.breedExpanded, [key]: !this.breedExpanded[key] };
        },

        breedIsExpanded(row) {
            return row.expanded || !!this.breedExpanded[row.key];
        },

        /** Male % for a species as the game rolls it. */
        breedMaleOdds(id) {
            const p = this.breedSpecies(id).male_probability;
            return p === undefined || p === null ? 50 : p;
        },

        // ---- entry points from other tabs -----------------------------------

        /** Pal modal: use this pal's species as parent A. */
        breedFrom(speciesId) {
            this.breedMode = 'child';
            this.breedA = speciesId || '';
            this.breedB = '';
            this.currentTab = 'breeding';
            window.scrollTo({ top: 0, behavior: 'smooth' });
        },

        /** Pal modal: show every pair that produces this species. */
        breedHowTo(speciesId) {
            this.breedMode = 'parents';
            this.breedChild = speciesId || '';
            this.currentTab = 'breeding';
            window.scrollTo({ top: 0, behavior: 'smooth' });
        },

        breedSwap() {
            [this.breedA, this.breedB] = [this.breedB, this.breedA];
        },

        /** Open the pal modal for a candidate. */
        breedOpenPal(pal) {
            window.dispatchEvent(new CustomEvent('open-pal-modal', { detail: pal }));
        },
    };
}
