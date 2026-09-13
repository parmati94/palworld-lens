/**
 * Searchable species dropdown for the breeding tab.
 *
 *   <div x-data="speciesPicker({ placeholder: 'Parent A' })" x-modelable="value" x-model="breedA">
 *       {{> species-picker }}
 *   </div>
 *
 * Reads the species list and owned counts from the app scope
 * (breedingSpecies / breedOwnedCount, see breeding-state.js).
 */
export function speciesPicker(opts = {}) {
    return {
        value: '',
        open: false,
        query: '',
        ownedOnly: false,
        placeholder: opts.placeholder || 'Choose a pal',

        get list() {
            const q = this.query.trim().toLowerCase();
            let list = this.breedingSpecies || [];
            if (this.ownedOnly) {
                list = list.filter(s => { const c = this.breedOwnedCount(s.id); return c.Male + c.Female > 0; });
            }
            if (q) list = list.filter(s => s.name.toLowerCase().includes(q) || s.id.toLowerCase().includes(q));
            return list;
        },

        get selected() {
            // null until the species list has loaded, so no placeholder icon is requested
            return (this.value && this.breedingById[this.value]) || null;
        },

        toggle() {
            this.open = !this.open;
            if (this.open) this.$nextTick(() => this.$refs.query && this.$refs.query.focus());
        },

        pick(id) {
            this.value = id;
            this.open = false;
            this.query = '';
        },

        clear() {
            this.value = '';
            this.query = '';
        },

        ownedLabel(id) {
            const c = this.breedOwnedCount(id);
            return c.Male + c.Female ? `♂${c.Male} ♀${c.Female}` : '';
        },
    };
}
