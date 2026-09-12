export function palModal() {
    return {
        showPalModal: false,
        selectedPal: null,

        openPalModal(pal) {
            this.selectedPal = pal;
            this.showPalModal = true;
        },

        closePalModal() {
            this.showPalModal = false;
            // Clear after the leave transition, unless the modal was reopened meanwhile.
            setTimeout(() => {
                if (!this.showPalModal) this.selectedPal = null;
            }, 200);
        },

        // Element icon + header gradient come from utils.js via the app scope.

        init() {
            this.$watch('showPalModal', value => {
                if (value) {
                    document.body.style.overflow = 'hidden';
                } else {
                    document.body.style.overflow = '';
                }
            });

            // Listen for custom event
            window.addEventListener('open-pal-modal', (e) => {
                this.openPalModal(e.detail);
            });
        }
    };
}
