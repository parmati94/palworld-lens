/**
 * Leaflet.js Map Component for Palworld Lens
 * Industry-standard approach for game map visualization
 */

/**
 * Convert Palworld save coordinates to Leaflet map coordinates
 * CORRECTED FORMULA based on community research
 */
function saveToMapCoords(saveX, saveY) {
    // ---------------------------------------------------------
    // 1. CONFIGURATION (Calibration v3)
    // ---------------------------------------------------------
    
    // SCALE: Controls zoom/spread. 
    // We are increasing this significantly to SHRINK the map.
    // This will pull the "High" Top Base DOWN and the "Low" Bottom Base UP.
    // OLD: 600 -> NEW: 650
    const scaleDivisor = 625; 

    // OFFSET X: Moves points East/West.
    // Your drawing showed HUGE red lines pointing Left. 
    // We are dropping this aggressively to shift the whole map West.
    // OLD: 385 -> NEW: 245
    const manualOffsetX = 275;

    // OFFSET Y: Moves points North/South.
    // We are decreasing this to move the center of the map DOWN (South).
    // This combines with the scale fix to ensure the Top Base drops enough.
    // OLD: 255 -> NEW: 230
    const manualOffsetY = 242;

    // ---------------------------------------------------------
    // 2. CALCULATION
    // ---------------------------------------------------------

    // Transform Save (Unreal Units) to Game Map (Meters)
    const gameX = (saveY - 158000) / scaleDivisor;
    const gameY = (saveX + 123888) / scaleDivisor;
    
    // Define Map Constants
    const mapSize = 1000;
    const worldMin = -1150;
    const worldMax = 1150;
    const worldRange = worldMax - worldMin; // 2300

    // 3. Normalize to 0-1000 Pixel Space
    const normalizedX = (((gameX + manualOffsetX) - worldMin) / worldRange) * mapSize;
    const normalizedY = (((gameY + manualOffsetY) - worldMin) / worldRange) * mapSize;

    // 4. Return [Lat, Lng] (Leaflet Y, Leaflet X)
    return [normalizedY, normalizedX];
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
        
        init() {
            console.log('🗺️ Map component init called');
            
            // Check if Leaflet is loaded
            if (typeof L === 'undefined') {
                console.error('❌ Leaflet library not loaded! Make sure Leaflet.js is included before map-leaflet.js');
                return;
            }
            
            console.log('✅ Leaflet library loaded');
            
            // Wait for DOM and ensure element exists
            this.$nextTick(() => {
                setTimeout(() => {
                    // Try x-ref first, then fallback to getElementById
                    const mapEl = this.$refs.leafletMap || document.getElementById('leafletMap');
                    
                    if (mapEl) {
                        console.log('✅ Map container found:', mapEl);
                        // Store reference for later use
                        this.mapElement = mapEl;
                        
                        // Wait a bit more to ensure parent data is loaded
                        setTimeout(() => {
                            this.initMap();
                        }, 200);
                    } else {
                        console.error('❌ Map container not found. Tried $refs.leafletMap and getElementById("leafletMap")');
                        console.log('Available refs:', this.$refs);
                    }
                }, 100);
            });
        },
        
        initMap() {
            console.log('🗺️ Initializing Leaflet map...');
            
            if (this.map) return;
            
            try {
                const mapWidth = 1000;
                const mapHeight = 1000;
                const bounds = [[0, 0], [mapHeight, mapWidth]];
                
                // OPTIMIZATION 1: preferCanvas: true
                // This forces Leaflet to render markers on a <canvas> layer 
                // instead of creating individual DOM elements for every marker.
                this.map = L.map(this.mapElement, {
                    crs: L.CRS.Simple,
                    minZoom: -1,
                    maxZoom: 3,
                    attributionControl: false,
                    maxBounds: bounds,
                    maxBoundsViscosity: 0.5,
                    preferCanvas: true, 
                    zoomSnap: 0.5,       // Smoother zooming
                    wheelDebounceTime: 150 // Reduces render calls during scroll
                });
                
                console.log('✅ Leaflet map object created');
                
                // OPTIMIZATION 2: Add className for GPU acceleration
                const imageOverlay = L.imageOverlay('/img/World_Map_4k.webp', bounds, {
                    className: 'gpu-accelerated',
                    interactive: false // Prevents the image itself from capturing clicks
                });
                
                imageOverlay.addTo(this.map);
                
                // ... rest of your existing loading logic ...
                
                setTimeout(() => {
                    const imgElement = imageOverlay.getElement();
                    if (imgElement) {
                        // Ensure image isn't dragged (ghosting effect)
                        imgElement.style.pointerEvents = 'none'; 
                        imgElement.addEventListener('load', () => console.log('✅ Map image loaded'));
                    }
                }, 50);
                
                this.map.fitBounds(bounds);
                setTimeout(() => {
                    this.map.setView([mapHeight / 2, mapWidth / 2], 0);
                }, 100);
                
                this.mapReady = true;
                
                setTimeout(() => {
                    this.loadBases();
                }, 800);
            } catch (error) {
                console.error('❌ Error initializing map:', error);
            }
        },
        
        loadBases() {
            // Clear existing markers
            this.markers.forEach(marker => marker.remove());
            this.markers = [];
            
            // Get bases from parent app - try multiple ways to access it
            let guilds = [];
            
            // Method 1: Try Alpine.$data on the body element
            const bodyData = Alpine.$data(document.body);
            if (bodyData && bodyData.guilds) {
                guilds = bodyData.guilds;
                console.log('✅ Got guilds from body Alpine data');
            }
            // Method 2: Try this.$root
            else if (this.$root && this.$root.guilds) {
                guilds = this.$root.guilds;
                console.log('✅ Got guilds from $root');
            }
            // Method 3: Try window reference
            else if (window.Alpine && window.Alpine.store) {
                console.log('⚠️ Trying Alpine store (may not exist)');
            }
            
            console.log('🗺️ Loading bases from', guilds.length, 'guilds');
            console.log('🗺️ Guild data sample:', guilds[0]);
            
            let baseCount = 0;
            for (const guild of guilds) {
                console.log('🗺️ Processing guild:', guild.guild_name, 'with', guild.base_locations?.length || 0, 'bases');
                
                if (guild.base_locations) {
                    for (const base of guild.base_locations) {
                        console.log('📍 Base data:', base);
                        
                        if (base.x !== undefined && base.y !== undefined) {
                            this.addBaseMarker(base, guild);
                            baseCount++;
                        } else {
                            console.warn('⚠️ Base missing coordinates:', base.base_name, base);
                        }
                    }
                }
            }
            
            console.log('✅ Added', baseCount, 'base markers to map');
            
            if (baseCount === 0) {
                console.warn('⚠️ No bases with coordinates found. Check that:');
                console.warn('  1. Save data is loaded');
                console.warn('  2. Guilds have base_locations array');
                console.warn('  3. Bases have x, y coordinates');
                console.warn('  4. Try clicking "Refresh Bases" button after data loads');
            }
        },
        
        addBaseMarker(base, guild) {
            // Convert save coordinates to map coordinates using the correct formula
            const coords = saveToMapCoords(base.x, base.y);
            
            console.log('📍 Plotting base:', base.base_name);
            console.log('   Game coords:', base.x, base.y);
            console.log('   Map coords:', coords);
            
            // Create custom icon
            const icon = L.divIcon({
                className: 'base-marker',
                html: `
                    <div class="relative">
                        <div class="w-8 h-8 bg-blue-500 rounded-full border-2 border-white shadow-lg flex items-center justify-center text-white">
                            🏠
                        </div>
                    </div>
                `,
                iconSize: [32, 32],
                iconAnchor: [16, 16],
                popupAnchor: [0, -16]
            });
            
            // Create marker
            const marker = L.marker(coords, { icon: icon }).addTo(this.map);
            
            // Add popup with base info (removed Z coordinate)
            const popupContent = `
                <div class="p-2">
                    <div class="font-bold text-blue-600">${base.base_name}</div>
                    <div class="text-sm text-gray-600">${guild.guild_name}</div>
                    <div class="text-xs text-gray-500 mt-1">
                        Game X: ${Math.round(base.x)}<br>
                        Game Y: ${Math.round(base.y)}<br>
                        Map: [${Math.round(coords[0])}, ${Math.round(coords[1])}]
                    </div>
                </div>
            `;
            
            marker.bindPopup(popupContent);
            this.markers.push(marker);
        },
        
        resetView() {
            if (this.map) {
                const bounds = [[0, 0], [1000, 1000]];
                this.map.fitBounds(bounds);
            }
        },
        
        // Call this when data is refreshed
        refresh() {
            console.log('🔄 Refreshing map data...');
            this.loadBases();
        },
        
        // Helper to get all bases with coordinates (for template usage)
        getAllBasesWithCoords() {
            const bases = [];
            
            // Try to get guilds from Alpine
            let guilds = [];
            const bodyData = Alpine.$data(document.body);
            if (bodyData && bodyData.guilds) {
                guilds = bodyData.guilds;
            } else if (this.$root && this.$root.guilds) {
                guilds = this.$root.guilds;
            }
            
            for (const guild of guilds) {
                if (guild.base_locations) {
                    for (const base of guild.base_locations) {
                        if (base.x !== undefined && base.y !== undefined) {
                            bases.push({
                                ...base,
                                guild_name: guild.guild_name,
                                guild_id: guild.guild_id
                            });
                        }
                    }
                }
            }
            
            return bases;
        }
    };
}
