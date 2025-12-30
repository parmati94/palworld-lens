/**
 * Convert Palworld save coordinates to Leaflet map coordinates
 * SYSTEM: 0-256 Virtual World (Standard Leaflet Scale)
 * [0,0] is Top-Left. [-256, 256] is Bottom-Right.
 */
function saveToMapCoords(saveX, saveY) {
    const scaleDivisor = 625; 
    const manualOffsetX = 275;
    const manualOffsetY = 242;

    const gameX = (saveY - 158000) / scaleDivisor;
    const gameY = (saveX + 123888) / scaleDivisor;
    
    // Virtual World Bounds (Game Units)
    const worldMin = -1150;
    const worldMax = 1150;
    const worldRange = worldMax - worldMin; 

    // 1. Normalize to 0.0 -> 1.0
    const normX = ((gameX + manualOffsetX) - worldMin) / worldRange;
    const normY = ((gameY + manualOffsetY) - worldMin) / worldRange;

    // 2. Scale to Leaflet 256 Unit System
    const leafletX = normX * 256;
    
    // 3. Invert Y Axis for Mapping
    // Tiles go Down (0 -> 1). Game coords go Up.
    const leafletY = (1 - normY) * 256; 

    // Return [Lat, Lng]
    // In Leaflet CRS.Simple, Y goes UP (Positive). We use NEGATIVE Y to match image coordinates.
    return [-leafletY, leafletX];
}

/**
 * Alpine.js + Leaflet Map Component
 */
function leafletMapComponent() {
    return {
        map: null,
        mapElement: null,
        markers: [],
        mapReady: false,
        resizeObserver: null,
        
        init() {
            if (typeof L === 'undefined') return;

            this.$nextTick(() => {
                setTimeout(() => {
                    const mapEl = this.$refs.leafletMap || document.getElementById('leafletMap');
                    if (mapEl) {
                        this.mapElement = mapEl;
                        this.initMap();
                        
                        // Resize Observer to fix the "Partial Load" layout bug
                        this.resizeObserver = new ResizeObserver(() => {
                            if (this.map) {
                                setTimeout(() => {
                                    this.map.invalidateSize();
                                }, 10);
                            }
                        });
                        this.resizeObserver.observe(this.mapElement);
                    }
                }, 100);
            });
        },
        
        initMap() {
            if (this.map) return;
            
            try {
                // Define the world boundaries:
                // Top-Left: [0, 0]
                // Bottom-Right: [-256, 256]
                const bounds = [[0, 0], [-256, 256]];
                
                this.map = L.map(this.mapElement, {
                    crs: L.CRS.Simple,
                    minZoom: 0,
                    maxZoom: 5,
                    
                    // --- PERFORMANCE OPTIMIZATIONS ---
                    zoomSnap: 1,      
                    zoomDelta: 1,      
                    wheelPxPerZoomLevel: 120,
                    
                    attributionControl: false,
                    maxBounds: [[20, -20], [-276, 276]], 
                    maxBoundsViscosity: 0.8
                });

                // TILE LAYER
                L.tileLayer('/img/tiles/{z}/{x}/{y}.png', {
                    minZoom: 0,
                    maxZoom: 5,
                    tileSize: 256,
                    bounds: bounds,
                    noWrap: true,
                    tms: false, 
                    
                    updateWhenIdle: false, 
                    keepBuffer: 10,       
                    updateWhenZooming: false,
                    
                    errorTileUrl: 'https://placehold.co/256x256/333/666?text=Missing'
                }).addTo(this.map);

                // --- DYNAMIC START ZOOM ---
                const containerWidth = this.mapElement.clientWidth || 1000;
                const fillZoom = Math.log2(containerWidth / 256);
                const initialZoom = Math.max(2, Math.min(5, Math.ceil(fillZoom)));

                // Center view
                this.map.setView([-128, 128], initialZoom);
                
                this.mapReady = true;
                
                // Initial load attempt
                setTimeout(() => {
                    this.map.invalidateSize();
                    this.loadBases();
                }, 200);
                
            } catch (error) {
                console.error('Map error:', error);
            }
        },

        loadBases(retries = 0) {
            // 1. Clear old markers
            this.markers.forEach(marker => marker.remove());
            this.markers = [];
            
            // 2. Try to get data
            const bodyData = Alpine.$data(document.body);
            let guilds = bodyData && bodyData.guilds ? bodyData.guilds : (this.$root && this.$root.guilds ? this.$root.guilds : []);
            
            // 3. Retry Logic
            if ((!guilds || guilds.length === 0) && retries < 10) {
                console.log(`⏳ Map waiting for data... (Attempt ${retries + 1}/10)`);
                setTimeout(() => this.loadBases(retries + 1), 500);
                return;
            }
            
            console.log(`📍 Loading markers for ${guilds.length} guilds...`);

            for (const guild of guilds) {
                if (guild.base_locations) {
                    for (const base of guild.base_locations) {
                        if (base.x !== undefined && base.y !== undefined) {
                            this.addBaseMarker(base, guild);
                        }
                    }
                }
            }
        },

        addBaseMarker(base, guild) {
            const coords = saveToMapCoords(base.x, base.y);
            
            const icon = L.divIcon({
                className: 'base-marker',
                html: `
                    <div class="relative group">
                        <div class="w-6 h-6 bg-blue-500 rounded-full border-2 border-white shadow-lg flex items-center justify-center text-white transition-transform transform group-hover:scale-110 cursor-pointer">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>
                        </div>
                        <div class="absolute -bottom-8 left-1/2 transform -translate-x-1/2 bg-gray-900/90 text-white text-xs px-2 py-1 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none border border-gray-600 z-[1000] shadow-lg">
                            ${base.base_name}
                        </div>
                    </div>
                `,
                iconSize: [24, 24],
                iconAnchor: [12, 12]
            });
            
            const marker = L.marker(coords, { icon: icon }).addTo(this.map);
            
            marker.on('click', () => {
                window.dispatchEvent(new CustomEvent('navigate-to-base', { 
                    detail: { guildId: guild.guild_id, baseId: base.base_id } 
                }));
            });
            
            this.markers.push(marker);
        },

        resetView() {
            if (this.map) {
                // Re-calculate the best fit zoom on reset
                const containerWidth = this.mapElement.clientWidth;
                const fillZoom = Math.log2(containerWidth / 256);
                const resetZoom = Math.max(2, Math.min(5, Math.ceil(fillZoom)));
                
                this.map.setView([-128, 128], resetZoom);
                this.map.invalidateSize();
            }
        },

        refresh() { this.loadBases(); },

        getAllBasesWithCoords() {
            const bases = [];
            const bodyData = Alpine.$data(document.body);
            let guilds = bodyData && bodyData.guilds ? bodyData.guilds : (this.$root && this.$root.guilds ? this.$root.guilds : []);
            for (const guild of guilds) {
                if (guild.base_locations) {
                    for (const base of guild.base_locations) {
                        if (base.x !== undefined && base.y !== undefined) bases.push(base);
                    }
                }
            }
            return bases;
        }
    };
}