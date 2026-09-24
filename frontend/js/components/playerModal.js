/** The player modal: the game's inventory screen for one player (inventory / party / status pills). */
export function playerModal() {
    return {
        showPlayerModal: false,
        selectedPlayer: null,
        playerTab: 'inventory',

        openPlayerModal(player, tab = 'inventory') {
            this.selectedPlayer = player;
            this.playerTab = tab;
            this.showPlayerModal = true;
        },

        closePlayerModal() {
            this.showPlayerModal = false;
            setTimeout(() => {
                if (!this.showPlayerModal) this.selectedPlayer = null;
            }, 200);
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
