/**
 * Species modal: one Paldeck entry in full. Opens from the deck grid, the pal
 * modal's Paldeck button, or anywhere with a species id
 * (`open-species-modal` {id, row?}). Shows the deck row at once and fills in
 * the detail (/api/paldeck/<id>: description, spawn groups, breeding, the
 * pals of it on this server) when it arrives; one cache per page load.
 */
import { api } from '../services/api.js';

const cache = new Map();

export function speciesModal() {
    return {
        showSpeciesModal: false,
        species: null,      // the deck row ({id, name, number, ...}) or a stub {id, name}
        detail: null,       // /api/paldeck/<id>
        detailFailed: false,
        _request: 0,

        async openSpeciesModal({ id, row = null }) {
            if (!id) return;
            this.species = row || cache.get(id) || { id, name: id, number: '', element_types: [], image_candidates: [id.toLowerCase()] };
            this.detail = cache.get(id) || null;
            this.detailFailed = false;
            this.showSpeciesModal = true;
            if (this.detail) return;
            const req = ++this._request;
            try {
                const d = await api.getSpecies(id);
                cache.set(id, d);
                if (req === this._request) { this.detail = d; this.species = d; }
            } catch (err) {
                if (req === this._request) this.detailFailed = true;
            }
        },

        closeSpeciesModal() {
            this.showSpeciesModal = false;
            setTimeout(() => {
                if (!this.showSpeciesModal) { this.species = null; this.detail = null; }
            }, 200);
        },

        /** What the header can show before the detail arrives. */
        get sp() { return this.detail || this.species; },

        /** The partner skill ladder from the game tables (same source as the pal modal). */
        get speciesPartner() {
            const table = (this.gameData && this.gameData.partner_skills) || {};
            const entry = this.sp && table[this.sp.id];
            return entry && entry.levels && entry.levels.length ? entry : null;
        },

        init() {
            this.$watch('showSpeciesModal', v => { document.body.style.overflow = v ? 'hidden' : ''; });
            window.addEventListener('open-species-modal', e => this.openSpeciesModal(e.detail || {}));
        },
    };
}
