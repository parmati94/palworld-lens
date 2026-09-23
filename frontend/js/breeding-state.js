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
        breedOwner: '',             // player name whose pals count as "owned" ('' = everyone)
        breedOwnedOnly: false,      // parents mode: hide pairs we cannot breed right now
        breedExpanded: {},          // pair key -> candidates shown
        breedLimit: 50,             // parents mode: rows rendered (Show more adds 50)
        breedLoading: false,
        breedError: null,
        // Child -> Parents: the multi-step route from the owned pals to the
        // child (/api/breeding/route), fetched alongside the pairs so the
        // "can't breed this yet" state can say how far away it is.
        breedRoute: null,           // {status, exact, breeds, generations, min_generations, plans: [{breeds, generations, steps, hatch}]}
        breedRoutePlan: 0,          // which plan is showing
        breedRouteLoading: false,
        breedRouteOpen: false,      // the route modal is showing
        _breedRouteRequest: 0,
        _breedOwned: null,          // palsBySpecies cache, cleared when pals change
        _breedPassives: null,       // ownedPassives cache
        _breedCandidates: new Map(),
        _breedLayout: null,         // {plan, owned, layout} for breedRouteLayout()
        _breedRouteKey: '',         // breedRouteKey() the current breedRoute was planned for
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

        /** The pals the calculator may use: one player's, or everyone's. */
        breedPool() {
            return this.breedOwner ? this.pals.filter(p => p.owner_uid === this.breedOwner) : this.pals;
        },

        breedOwnerLabel() {
            return this.breedOwner || 'anyone';
        },

        breedOwned() {
            if (!this._breedOwned) this._breedOwned = palsBySpecies(this.breedPool());
            return this._breedOwned;
        },

        breedOwnedCount(id) {
            const slot = this.breedOwned()[id];
            return slot ? { Male: slot.Male.length, Female: slot.Female.length } : { Male: 0, Female: 0 };
        },

        breedPassiveOptions() {
            if (!this._breedPassives) this._breedPassives = ownedPassives(this.breedPool());
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
                    this.loadBreedingRoute();
                }
            } catch (err) {
                if (token === this._breedRequest) this.breedError = err.message || 'Breeding lookup failed';
            } finally {
                if (token === this._breedRequest) this.breedLoading = false;
            }
        },

        // ---- route: from owned pals to the child, in the fewest breeds ----------

        /** child | owner | owned species+genders: the only inputs the planner reads. */
        breedRouteKey() {
            const owned = this.breedOwned();
            const sig = Object.keys(owned).sort()
                .map(id => id + ':' + (owned[id].Male.length ? 'M' : '') + (owned[id].Female.length ? 'F' : ''))
                .join(',');
            return `${this.breedChild}|${this.breedOwner}|${sig}`;
        },

        /** Plan the route; skipped when nothing the planner reads has changed (pal refreshes are frequent). */
        async loadBreedingRoute() {
            if (this.breedMode !== 'parents' || !this.breedChild) { this.breedRoute = null; this._breedRouteKey = ''; return; }
            const key = this.breedRouteKey();
            if (this.breedRoute && key === this._breedRouteKey) return;
            this._breedRouteKey = key;
            const token = ++this._breedRouteRequest;
            this.breedRoute = null;
            this.breedRoutePlan = 0;
            this.breedRouteLoading = true;
            try {
                const data = await api.getBreedingRoute(this.breedChild, this.breedOwner);
                if (token === this._breedRouteRequest) this.breedRoute = data;
            } catch (err) {
                if (token === this._breedRouteRequest) this.breedRoute = { status: 'error', plans: [], error: err.message };
            } finally {
                if (token === this._breedRouteRequest) this.breedRouteLoading = false;
            }
        },

        breedShowRoute() {
            this.breedRouteOpen = true;
            if (!this.breedRoute && !this.breedRouteLoading) this.loadBreedingRoute();
        },

        breedRoutePlans() {
            return (this.breedRoute && this.breedRoute.plans) || [];
        },

        breedCurrentPlan() {
            return this.breedRoutePlans()[this.breedRoutePlan] || null;
        },

        breedRouteStepPlan(delta) {
            const n = this.breedRoutePlans().length;
            if (!n) return;
            this.breedRoutePlan = (this.breedRoutePlan + delta + n) % n;
        },

        /**
         * The current plan drawn as a flow, left to right: what you own on the
         * left, each pair merging into its child one column to the right,
         * the goal at the far right. Columns are generations. Every leaf
         * (an owned pal, or a bred pal already drawn once) takes one row;
         * a bred pal sits between its two inputs. Returns absolutely
         * positioned nodes plus connector edges for one SVG behind them.
         */
        breedRouteLayout() {
            const plan = this.breedCurrentPlan();
            const empty = { nodes: [], edges: [], w: 0, h: 0 };
            if (!plan || !plan.steps.length) return empty;
            // Every binding in the diagram reads this; lay out once per plan + owned set.
            const owned = this.breedOwned();
            const cached = this._breedLayout;
            if (cached && cached.plan === plan && cached.owned === owned) return cached.layout;
            const layout = this._layoutPlan(plan, owned);
            this._breedLayout = { plan, owned, layout };
            return layout;
        },

        _layoutPlan(plan, owned) {
            const COL = 176, ROW = 64, W = 150, H = 54;   // px
            const byChild = Object.fromEntries(plan.steps.map((s, i) => [s.child, { step: s, n: i + 1 }]));
            const hatch = plan.hatch || {};
            const nodes = [], edges = [];
            const drawn = new Set();
            let row = 0;
            const counts = (id) => {
                const slot = owned[id];
                return slot ? { Male: slot.Male.length, Female: slot.Female.length } : { Male: 0, Female: 0 };
            };
            const place = (species, need) => {
                const e = byChild[species];
                if (!e || drawn.has(species)) {
                    const node = {
                        id: nodes.length, species, name: this.breedSpecies(species).name,
                        kind: e ? 'ref' : 'owned', n: e ? e.n : 0, col: e ? e.step.depth : 0,
                        y: row * ROW, need, counts: e ? null : counts(species),
                    };
                    row++;
                    nodes.push(node);
                    return node;
                }
                drawn.add(species);
                const a = place(e.step.parent_a, e.step.need_a);
                const b = place(e.step.parent_b, e.step.need_b);
                const node = {
                    id: nodes.length, species, name: this.breedSpecies(species).name,
                    kind: species === this.breedChild ? 'goal' : 'bred', n: e.n, step: e.step, col: e.step.depth,
                    y: (a.y + b.y) / 2, need, hatch: hatch[species] || [],
                    unique: e.step.unique, now: e.step.from_a === 'owned' && e.step.from_b === 'owned',
                };
                nodes.push(node);
                edges.push([a, node], [b, node]);
                return node;
            };
            place(this.breedChild, null);
            let maxCol = 0;
            for (const nd of nodes) { nd.x = nd.col * COL; nd.w = W; nd.h = H; maxCol = Math.max(maxCol, nd.col); }
            const paths = edges.map(([f, t]) => {
                const x1 = f.x + W, y1 = f.y + H / 2, x2 = t.x, y2 = t.y + H / 2;
                const mx = (x1 + x2) / 2;
                return { d: `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`, now: t.now };
            });
            return { nodes, edges: paths, w: (maxCol + 1) * COL - (COL - W), h: row * ROW - (ROW - H) };
        },

        /** The plan as plain sentences in breeding order. */
        breedRouteChecklist() {
            const plan = this.breedCurrentPlan();
            if (!plan) return [];
            const hatch = plan.hatch || {};
            return plan.steps.map((s, i) => ({
                n: i + 1, step: s,
                a: this.breedSpecies(s.parent_a).name, b: this.breedSpecies(s.parent_b).name,
                child: this.breedSpecies(s.child).name,
                hatch: this.breedHatchText(hatch[s.child] || []),
                goal: s.child === this.breedChild,
                now: s.from_a === 'owned' && s.from_b === 'owned',
            }));
        },

        /** "hatch a female" / "hatch one of each" for a bred species in the current plan. */
        breedHatchText(genders) {
            if (!genders || !genders.length) return '';
            if (genders.length === 2) return 'hatch one of each';
            return 'hatch a ' + genders[0].toLowerCase();
        },

        breedRouteShortcuts() {
            return (this.breedRoute && this.breedRoute.shortcuts) || [];
        },

        /** "catch a Warsect Terra for 8" -- the best shortcut, for the banner. */
        breedBestShortcut() {
            const c = this.breedRouteShortcuts()[0];
            if (!c) return '';
            const name = this.breedSpecies(c.species).name;
            if (c.kind === 'pair') return `catch a ${name} and a ${this.breedSpecies(c.partner).name} for one breed`;
            return c.breeds_after === 1 ? `catch a ${name} for one breed` : `catch a ${name} for ${c.breeds_after}`;
        },

        /** Shortcut row -> the map, lit for that species. */
        breedShortcutOnMap(species) {
            this.breedRouteOpen = false;
            this.findOnMap(species, this.breedSpecies(species).name,
                           { label: 'Back to the breeding route', tool: 'breeding', route: true });
        },

        /** Short human line for the route button / banner. */
        breedRouteSummary() {
            const r = this.breedRoute;
            if (this.breedRouteLoading || !r) return '';
            const who = this.breedOwner || 'anyone';
            if (r.status === 'route') {
                const cut = this.breedBestShortcut();
                return `${r.breeds} breeds over ${r.generations} generations from what ${who} owns${cut ? ', or ' + cut : ''}`;
            }
            if (r.status === 'breedable') return `one breed from what ${who} owns`;
            if (r.status === 'owned') return `${who === 'anyone' ? 'someone' : who} already owns one`;
            if (r.status === 'unreachable') return `no route from what ${who} owns`;
            return '';
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
            this.goToTool('breeding');
        },

        /** Pal modal: show every pair that produces this species. */
        breedHowTo(speciesId) {
            this.breedMode = 'parents';
            this.breedChild = speciesId || '';
            this.goToTool('breeding');
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
