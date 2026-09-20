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
 * selects the placeholder entry. Pass `required: true` for a picker with no
 * "all" entry (the value is always one of the options).
 */
export function selectMenu(opts = {}) {
    return {
        value: '',
        open: false,
        placeholder: opts.placeholder || 'All',
        required: !!opts.required,
        options: opts.options || (() => []),

        get list() {
            const all = this.options();
            return this.required ? all : [{ value: '', label: this.placeholder }, ...all];
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
