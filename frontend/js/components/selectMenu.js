/**
 * Small styled dropdown (label + chevron, list with highlight) for a short
 * list of options. Same look as the pals-tab filters, but reusable:
 *
 *   <div x-data="selectMenu({ options: () => availableOwners.map(o => ({ value: o, label: o })), placeholder: 'Everyone' })"
 *        x-modelable="value" x-model="breedOwner">
 *       {{> select-menu }}
 *   </div>
 *
 * `options` is a function so it can read live app state; an empty value
 * selects the placeholder entry.
 */
export function selectMenu(opts = {}) {
    return {
        value: '',
        open: false,
        placeholder: opts.placeholder || 'All',
        options: opts.options || (() => []),

        get list() {
            return [{ value: '', label: this.placeholder }, ...this.options()];
        },

        get label() {
            const hit = this.list.find(o => o.value === this.value);
            return hit ? hit.label : this.value;
        },

        pick(v) {
            this.value = v;
            this.open = false;
        },
    };
}
