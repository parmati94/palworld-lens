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
            setTimeout(() => {
                this.selectedPal = null;
            }, 200);
        },

        getPalHeaderGradient(elementTypes) {
            if (!elementTypes || elementTypes.length === 0) {
                return 'linear-gradient(135deg, #1f2937 0%, #374151 100%)';
            }
            
            const elementColors = {
                'Neutral': '#64748b',
                'Dark': '#1e1b4b',
                'Dragon': '#7c3aed',
                'Fire': '#dc2626',
                'Grass': '#16a34a',
                'Ground': '#92400e',
                'Electric': '#eab308',
                'Water': '#0ea5e9',
                'Ice': '#06b6d4',
                'Leaf': '#22c55e'
            };
            
            if (elementTypes.length === 1) {
                const color = elementColors[elementTypes[0]] || '#1f2937';
                return `linear-gradient(135deg, ${color} 0%, ${color}dd 100%)`;
            }
            
            const color1 = elementColors[elementTypes[0]] || '#1f2937';
            const color2 = elementColors[elementTypes[1]] || '#374151';
            return `linear-gradient(135deg, ${color1} 0%, ${color2} 100%)`;
        },

        getElementIcon(element) {
            const iconMap = {
                'Neutral': 'element_normal.webp',
                'Dark': 'element_dark.webp',
                'Dragon': 'element_dragon.webp',
                'Fire': 'element_fire.webp',
                'Grass': 'element_grass.webp',
                'Ground': 'element_ground.webp',
                'Electric': 'element_electric.webp',
                'Water': 'element_water.webp',
                'Ice': 'element_ice.webp',
                'Leaf': 'element_leaf.webp'
            };
            return iconMap[element] || 'element_normal.webp';
        },

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
