export function containerModal() {
    return {
        showContainerModal: false,
        selectedContainer: null,

        openContainerModal(container) {
            this.selectedContainer = container;
            this.showContainerModal = true;
        },

        closeContainerModal() {
            this.showContainerModal = false;
            setTimeout(() => {
                this.selectedContainer = null;
            }, 200);
        },

        init() {
            // Listen for the custom event
            this.$watch('showContainerModal', value => {
                if (value) {
                    document.body.style.overflow = 'hidden';
                } else {
                    document.body.style.overflow = '';
                }
            });
        }
    };
}
