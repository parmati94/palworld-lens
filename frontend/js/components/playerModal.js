/** The player modal: the game's inventory screen for one player (inventory / party / status pills). */
export function playerModal() {
    return {
        showPlayerModal: false,
        selectedPlayer: null,
        playerTab: 'inventory',
        bagTab: 'bag',          // the bag panel's own sub-tabs: bag | key items

        openPlayerModal(player, tab = 'inventory') {
            this.selectedPlayer = player;
            this.playerTab = tab;
            this.bagTab = 'bag';
            this.showPlayerModal = true;
        },

        closePlayerModal() {
            this.showPlayerModal = false;
            setTimeout(() => {
                if (!this.showPlayerModal) this.selectedPlayer = null;
            }, 200);
        },

        /** Which pill is lit: on phones the inventory screen is paged (bag / gear / status), on desktop it is
         *  one pill, so 'inventory' lights Bag on a phone and any of the three pages lights Inventory on desktop. */
        playerTabIs(id) {
            const pages = ['inventory', 'bag', 'gear', 'status'];
            if (id === 'inventory') return pages.includes(this.playerTab);
            if (id === 'bag') return this.playerTab === 'bag' || this.playerTab === 'inventory';
            return this.playerTab === id;
        },

        /** The full PalInfo for a party entry (the app's pal list is passed in from the template,
         *  since a component's `this` does not see the app scope), so the party pane can show HP and elements. */
        partyPal(ref, pals) {
            return (pals || []).find(p => p.instance_id === ref.instance_id) || null;
        },

        init() {
            this.$watch('showPlayerModal', value => {
                document.body.style.overflow = value ? 'hidden' : '';
            });
            window.addEventListener('open-player-modal', (e) => {
                const d = e.detail || {};
                this.openPlayerModal(d.player || d, d.tab);
            });
        }
    };
}
