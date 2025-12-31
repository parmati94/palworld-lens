/**
 * Alpine.js + Leaflet Map Component
 * Note: saveToMapCoords is now in utils.js
 */
function leafletMapComponent() {
    return {
        map: null,
        mapElement: null,
        markers: [],
        playerMarkers: [],
        alphaPalMarkers: [],
        fastTravelMarkers: [],
        mapReady: false,
        resizeObserver: null,
        
        // Filter state
        showBases: true,
        showPlayers: true,
        showAlphaPals: true,
        showFastTravel: false,
        filtersCollapsed: false,
        isRefreshing: false,
        
        // Static map objects (loaded once)
        mapObjects: null,
        mapObjectsLoaded: false,
        
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
                        
                        // Watch for changes to guild data (from parent Alpine component)
                        // This automatically triggers when SSE updates or manual reload happens
                        const bodyData = Alpine.$data(document.body);
                        if (bodyData) {
                            this.$watch(() => bodyData.guilds, () => {
                                console.log('🗺️ Map: Guild data changed, refreshing markers...');
                                this.loadBases();
                            }, { deep: true });
                            
                            this.$watch(() => bodyData.players, () => {
                                console.log('🗺️ Map: Player data changed, refreshing player markers...');
                                this.loadPlayers();
                            }, { deep: true });
                        }
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
                    maxZoom: 7,  // Allow zooming to level 7
                    
                    // --- PERFORMANCE OPTIMIZATIONS ---
                    zoomSnap: 1,      
                    zoomDelta: 1,      
                    wheelPxPerZoomLevel: 120,
                    
                    attributionControl: false,
                    zoomControl: false,  // Disable default zoom control
                    maxBounds: [[20, -20], [-276, 276]], 
                    maxBoundsViscosity: 0.8
                });

                // TILE LAYER
                L.tileLayer('/img/tiles/{z}/{x}/{y}.png', {
                    minZoom: 0,
                    maxZoom: 7,        // Allow zooming to level 7
                    maxNativeZoom: 5,  // Real tiles up to level 5, digital zoom for 7
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
                    this.loadPlayers();
                    this.loadStaticMapObjects();
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
            
            // Calculate real in-game coordinates for display
            const gameX = (base.y - 158000) / 625;
            const gameY = (base.x + 123888) / 625;
            
            const icon = L.divIcon({
                className: 'base-marker',
                html: `
                    <div class="relative group">
                        <img src="/img/t_icon_compass_camp.webp" class="w-12 h-12 object-contain transition-transform transform group-hover:scale-125 cursor-pointer drop-shadow-lg" alt="Base" />
                        <div class="absolute -bottom-16 left-1/2 transform -translate-x-1/2 bg-gray-900/95 text-white text-xs px-3 py-2 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none border border-gray-600 z-[9999] shadow-lg max-w-[280px]">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="font-semibold truncate">${base.base_name}</span>
                                <span class="text-gray-400 text-[10px] truncate flex-shrink-0">${guild.guild_name}</span>
                            </div>
                            <div class="text-gray-400">X: ${Math.round(gameX)} | Y: ${Math.round(gameY)}</div>
                        </div>
                    </div>
                `,
                iconSize: [48, 48],
                iconAnchor: [24, 24]
            });
            
            const marker = L.marker(coords, { icon: icon }).addTo(this.map);
            
            marker.on('click', () => {
                window.dispatchEvent(new CustomEvent('navigate-to-base', { 
                    detail: { guildId: guild.guild_id, baseId: base.base_id } 
                }));
            });
            
            this.markers.push(marker);
        },

        loadPlayers(retries = 0) {
            // Clear old player markers
            this.playerMarkers.forEach(marker => marker.remove());
            this.playerMarkers = [];
            
            // Try to get player data
            const bodyData = Alpine.$data(document.body);
            let players = bodyData && bodyData.players ? bodyData.players : (this.$root && this.$root.players ? this.$root.players : []);
            
            // Retry logic
            if ((!players || players.length === 0) && retries < 10) {
                console.log(`⏳ Map waiting for player data... (Attempt ${retries + 1}/10)`);
                setTimeout(() => this.loadPlayers(retries + 1), 500);
                return;
            }
            
            console.log(`👤 Loading markers for ${players.length} players...`);

            for (const player of players) {
                if (player.location && player.location.x !== undefined && player.location.y !== undefined) {
                    this.addPlayerMarker(player);
                }
            }
        },

        addPlayerMarker(player) {
            const coords = saveToMapCoords(player.location.x, player.location.y);
            
            // Calculate real in-game coordinates for display
            const gameX = (player.location.y - 158000) / 625;
            const gameY = (player.location.x + 123888) / 625;
            
            const icon = L.divIcon({
                className: 'player-marker',
                html: `
                    <div class="relative group">
                        <div class="w-6 h-6 bg-green-500 rounded-full border-2 border-white shadow-lg flex items-center justify-center transition-transform transform group-hover:scale-110 cursor-pointer">
                            <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clip-rule="evenodd" />
                            </svg>
                        </div>
                        <div class="absolute -bottom-16 left-1/2 transform -translate-x-1/2 bg-gray-900/95 text-white text-xs px-3 py-2 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none border border-gray-600 z-[9999] shadow-lg max-w-[280px]">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="font-semibold">${player.player_name}</span>
                                <span class="text-green-400 text-[10px]">Lv ${player.level}</span>
                            </div>
                            <div class="text-gray-400">X: ${Math.round(gameX)} | Y: ${Math.round(gameY)}</div>
                        </div>
                    </div>
                `,
                iconSize: [24, 24],
                iconAnchor: [12, 12]
            });
            
            const marker = L.marker(coords, { 
                icon: icon,
                zIndexOffset: 1000  // Player markers always on top
            }).addTo(this.map);
            this.playerMarkers.push(marker);
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

        refresh() {
            this.isRefreshing = true;
            this.loadBases();
            this.loadPlayers();
            // Reset loading state after a short delay
            setTimeout(() => {
                this.isRefreshing = false;
            }, 600);
        },

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
        },
        
        async loadStaticMapObjects() {
            // Only load once
            if (this.mapObjectsLoaded) {
                console.log('📍 Static map objects already loaded, refreshing markers...');
                this.loadAlphaPals();
                this.loadFastTravelPoints();
                return;
            }
            
            try {
                console.log('📍 Loading static map objects from API...');
                const response = await fetch('/api/map-objects', {
                    credentials: 'include',
                    headers: { 'Accept': 'application/json' }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const data = await response.json();
                // Store in the format we expect (array of objects)
                this.mapObjects = [...data.alpha_pals, ...data.fast_travel];
                this.mapObjectsLoaded = true;
                
                console.log(`📍 Loaded ${data.alpha_pals.length} alpha pals, ${data.fast_travel.length} fast travel points`);
                
                // Load both types of markers
                this.loadAlphaPals();
                this.loadFastTravelPoints();
            } catch (error) {
                console.error('❌ Failed to load map objects:', error);
            }
        },
        
        loadAlphaPals() {
            if (!this.mapObjects) return;
            
            // Clear old markers
            this.alphaPalMarkers.forEach(marker => marker.remove());
            this.alphaPalMarkers = [];
            
            const alphaPals = this.mapObjects.filter(obj => obj.type === 'alpha_pal');
            console.log(`🐲 Loading ${alphaPals.length} alpha pal markers...`);
            
            for (const alphaPal of alphaPals) {
                if (alphaPal.x !== undefined && alphaPal.y !== undefined) {
                    this.addAlphaPalMarker(alphaPal);
                }
            }
        },
        
        addAlphaPalMarker(alphaPal) {
            const coords = saveToMapCoords(alphaPal.x, alphaPal.y);
            
            // Get pal image ID in the format: t_{paild}_icon_normal.webp
            let imageId = alphaPal.pal.toLowerCase();
            if (imageId.startsWith('boss_')) {
                imageId = imageId.substring(5);
            }
            const iconPath = `/img/t_${imageId}_icon_normal.webp`;
            
            // Use enriched data from backend
            const palName = alphaPal.pal_name || alphaPal.pal;
            const level = alphaPal.level;
            
            const icon = L.divIcon({
                className: 'alpha-pal-marker',
                html: `
                    <div class="relative group">
                        <div class="w-8 h-8 bg-black rounded-full border-2 border-white shadow-lg flex items-center justify-center transition-transform transform group-hover:scale-110 cursor-pointer overflow-hidden">
                            <img src="${iconPath}" class="w-6 h-6 object-contain" alt="${palName}" onerror="this.src='/img/t_icon_item_pal.webp'" />
                        </div>
                        <div class="absolute top-10 left-1/2 transform -translate-x-1/2 bg-gray-900/95 text-white text-xs px-2 py-1.5 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none border border-gray-600 z-[9999] shadow-lg max-w-[280px]">
                            <div class="font-semibold text-yellow-400 break-words">⚔️ ${palName}</div>
                            ${level ? `<div class="text-gray-300 text-[11px]">Level ${level}</div>` : ''}
                            <div class="text-gray-400 text-[10px]">Alpha Pal</div>
                        </div>
                    </div>
                `,
                iconSize: [32, 32],
                iconAnchor: [16, 16]
            });
            
            const marker = L.marker(coords, { 
                icon: icon,
                zIndexOffset: 500  // Below players, above bases
            });
            
            if (this.showAlphaPals) {
                marker.addTo(this.map);
            }
            this.alphaPalMarkers.push(marker);
        },
        
        loadFastTravelPoints() {
            if (!this.mapObjects) return;
            
            // Clear old markers
            this.fastTravelMarkers.forEach(marker => marker.remove());
            this.fastTravelMarkers = [];
            
            const fastTravelPoints = this.mapObjects.filter(obj => obj.type === 'fast_travel');
            console.log(`🚀 Loading ${fastTravelPoints.length} fast travel markers...`);
            
            for (const point of fastTravelPoints) {
                if (point.x !== undefined && point.y !== undefined) {
                    this.addFastTravelMarker(point);
                }
            }
        },
        
        addFastTravelMarker(point) {
            const coords = saveToMapCoords(point.x, point.y);
            
            const icon = L.divIcon({
                className: 'fast-travel-marker',
                html: `
                    <div class="relative group">
                        <div class="w-7 h-7 bg-cyan-500/90 rounded-full border-2 border-white shadow-lg flex items-center justify-center transition-transform transform group-hover:scale-110 cursor-pointer overflow-hidden">
                            <img src="/img/t_icon_compass_fttower.webp" class="w-6 h-6 object-contain" alt="Fast Travel" />
                        </div>
                        <div class="absolute -bottom-16 left-1/2 transform -translate-x-1/2 bg-gray-900/95 text-white text-xs px-3 py-2 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none border border-gray-600 z-[9999] shadow-lg max-w-[280px]">
                            <div class="font-semibold text-cyan-400 break-words">${point.localized_name}</div>
                            <div class="text-gray-400 text-[10px] mt-1">Fast Travel Point</div>
                        </div>
                    </div>
                `,
                iconSize: [28, 28],
                iconAnchor: [14, 14]
            });
            
            const marker = L.marker(coords, { 
                icon: icon,
                zIndexOffset: 100  // Lowest priority
            });
            
            if (this.showFastTravel) {
                marker.addTo(this.map);
            }
            this.fastTravelMarkers.push(marker);
        },
        
        toggleBases() {
            this.showBases = !this.showBases;
            this.markers.forEach(marker => {
                if (this.showBases) {
                    marker.addTo(this.map);
                } else {
                    marker.remove();
                }
            });
        },
        
        togglePlayers() {
            this.showPlayers = !this.showPlayers;
            this.playerMarkers.forEach(marker => {
                if (this.showPlayers) {
                    marker.addTo(this.map);
                } else {
                    marker.remove();
                }
            });
        },
        
        toggleAlphaPals() {
            this.showAlphaPals = !this.showAlphaPals;
            this.alphaPalMarkers.forEach(marker => {
                if (this.showAlphaPals) {
                    marker.addTo(this.map);
                } else {
                    marker.remove();
                }
            });
        },
        
        toggleFastTravel() {
            this.showFastTravel = !this.showFastTravel;
            this.fastTravelMarkers.forEach(marker => {
                if (this.showFastTravel) {
                    marker.addTo(this.map);
                } else {
                    marker.remove();
                }
            });
        },
        
        toggleFilters() {
            this.filtersCollapsed = !this.filtersCollapsed;
        },
        
        zoomIn() {
            if (this.map) {
                this.map.zoomIn();
            }
        },
        
        zoomOut() {
            if (this.map) {
                this.map.zoomOut();
            }
        },
        
        centerOnLocation(x, y, zoom = 5) {
            if (this.map && x !== undefined && y !== undefined) {
                const coords = saveToMapCoords(x, y);
                this.map.setView(coords, zoom);
            }
        }
    };
}