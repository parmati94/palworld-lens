/**
 * Alpine.js + MapLibre GL map component.
 *
 * Replaces the Leaflet component. Same Alpine name and the same public methods
 * (the template in partials/modals.html binds to them unchanged), but the map is
 * rendered in WebGL: tiles are GPU textures scaled continuously, so zoom is a
 * smooth float rather than integer steps with a tile-container rebuild between
 * them, and scroll input is applied per frame instead of queued behind a CSS
 * animation.
 *
 * Assets are unchanged. The XYZ WebP pyramids under /img/tiles and
 * /img/tiles_tree are consumed as ordinary raster sources; each map layer is a
 * source + layer pair and switching toggles visibility.
 *
 * Coordinates: MapLibre speaks Web Mercator lng/lat. Our tile pyramids are cut
 * from a square image that fills the whole z0 tile, so a normalised image
 * position (u, v) is exactly a Mercator fraction -- utils.saveToLngLat() does
 * the world -> image -> lng/lat conversion.
 *
 * Zoom levels: MapLibre's zoom 0 is a 512px world; Leaflet's was 256px. So a
 * MapLibre zoom is one less than the equivalent Leaflet zoom. The z5 tiles are
 * 1:1 at MapLibre zoom 4; above that the raster source is overscaled on the GPU.
 */
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { saveToLngLat, layerForCoords, MAP_LAYERS, palIconSrc, palIconError } from './utils.js';
import { loadPrefs, savePref, pref } from './prefs.js';

const prefs = loadPrefs();

const NATIVE_MAX_ZOOM = 4;   // tiles exist through source z5 == map z4
const MAX_ZOOM = 7;          // 3 levels of GPU overzoom past native
const MIN_ZOOM = 0.5;        // ~724px world: lets the whole square fit in a 70vh container

// Stacking: players over alphas over bases over fast travel (was zIndexOffset).
const Z = { fastTravel: 100, base: 300, alphaPal: 500, player: 1000 };

const OCEAN = '#0b101b';

export function mapComponent() {
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
        showBases: pref(prefs, 'mapBases', true),
        showPlayers: pref(prefs, 'mapPlayers', true),
        showAlphaPals: pref(prefs, 'mapAlphaPals', true),
        showFastTravel: pref(prefs, 'mapFastTravel', false),
        // Panel starts collapsed on phones unless the viewer chose otherwise.
        filtersCollapsed: pref(prefs, 'mapFiltersCollapsed', typeof window !== 'undefined' && window.matchMedia('(max-width: 767px)').matches),
        isRefreshing: false,

        // Static map objects (loaded once)
        mapObjects: null,
        mapObjectsLoaded: false,

        // Which map texture is showing. Palworld 1.0 added the World Tree as a
        // separate map layer with its own texture and coordinate bounds; objects
        // are tagged with `map` and only the active layer's are drawn.
        mapLayer: 'MainMap',

        init() {
            this.$nextTick(() => {
                setTimeout(() => {
                    const mapEl = this.$refs.worldMap || document.getElementById('worldMap');
                    if (!mapEl) return;
                    this.mapElement = mapEl;

                    // The map tab is x-show'd, so this component initialises while
                    // its container is display:none (0x0). MapLibre can't build its
                    // view matrices for a zero-size viewport (constrain() with
                    // maxBounds throws), so create the map on the first non-zero
                    // size instead, and just resize on later changes (tab switches,
                    // sidebars, window resizes).
                    const sized = () => this.mapElement.clientWidth > 0 && this.mapElement.clientHeight > 0;
                    const ensure = () => {
                        if (!this.map) { if (sized()) this.initMap(); }
                        else this.map.resize();
                    };
                    this.resizeObserver = new ResizeObserver(ensure);
                    this.resizeObserver.observe(this.mapElement);
                    ensure();

                    // Re-render markers when the parent app's data changes
                    // (SSE updates, manual reloads).
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
                }, 100);
            });
        },

        /**
         * Zoom at which the map exactly fills the container width. Fractional --
         * MapLibre doesn't need integer levels, so this fits precisely instead of
         * rounding up to the next whole level like the Leaflet version did.
         */
        fitZoom() {
            const width = (this.mapElement && this.mapElement.clientWidth) || 1000;
            const fill = Math.log2(width / 512);
            return Math.max(MIN_ZOOM, Math.min(NATIVE_MAX_ZOOM, fill));
        },

        initMap() {
            if (this.map) return;

            try {
                const sources = {};
                const layers = [{ id: 'ocean', type: 'background', paint: { 'background-color': OCEAN } }];
                for (const [name, cfg] of Object.entries(MAP_LAYERS)) {
                    sources[`src-${name}`] = {
                        type: 'raster',
                        tiles: [`${cfg.tiles}/{z}/{x}/{y}.webp`],
                        tileSize: 256,
                        minzoom: 0,
                        maxzoom: 5,
                        // The pyramid covers exactly the z0 world tile; nothing
                        // outside it, so don't request (or wrap) beyond it.
                        bounds: [-180, -85.0511, 180, 85.0511],
                    };
                    // Every layer stays 'visible'; the inactive one is hidden with
                    // raster-opacity 0 rather than visibility:none. A hidden layer
                    // doesn't load tiles, so the first switch to it would fade onto
                    // an empty layer and then pop when its tiles arrived. At opacity
                    // 0 MapLibre keeps its tiles for the current view loaded, so the
                    // cross-fade has real pixels on both sides from the first frame.
                    layers.push({
                        id: `map-${name}`,
                        type: 'raster',
                        source: `src-${name}`,
                        paint: { 'raster-resampling': 'linear', 'raster-fade-duration': 0,
                                 'raster-opacity': name === this.mapLayer ? 1 : 0 },
                    });
                }

                this.map = new maplibregl.Map({
                    container: this.mapElement,
                    style: { version: 8, sources, layers },
                    center: [0, 0],
                    zoom: this.fitZoom(),
                    minZoom: MIN_ZOOM,
                    maxZoom: MAX_ZOOM,
                    renderWorldCopies: false,
                    attributionControl: false,
                    // Don't let the map be rotated or tilted -- it's a flat game map.
                    dragRotate: false,
                    pitchWithRotate: false,
                    touchPitch: false,
                    // No maxBounds: with renderWorldCopies:false, bounds equal to the
                    // whole Mercator world make MapLibre 5's constraint solver throw
                    // inside the constructor (null matrix in _calcMatrices), and
                    // bounds wider than the world pin the centre to lng 180. minZoom
                    // below keeps the texture at least viewport-sized instead.
                });
                this.map.touchZoomRotate.disableRotation();
                this.map.keyboard.disableRotation();

                this.map.on('load', () => {
                    this.mapReady = true;
                    this.map.resize();
                    this.loadBases();
                    this.loadPlayers();
                    this.loadStaticMapObjects();
                });

                this.map.on('error', (e) => {
                    // Missing tiles outside the island area 404 by design now
                    // (nginx no longer serves index.html for them); don't spam.
                    if (e && e.error && /404/.test(String(e.error.message || ''))) return;
                    console.error('Map error:', e && e.error ? e.error : e);
                });
            } catch (error) {
                console.error('Map error:', error);
            }
        },

        /**
         * Swap the visible map texture with a cross-fade, and redraw everything
         * for the new layer.
         *
         * Both raster layers are kept in the style; the outgoing one fades to
         * raster-opacity 0 while the incoming fades to 1 (a GPU paint transition,
         * so it's free), and the camera eases back out to the full-map view at
         * the same time so the switch reads as travelling to the other map rather
         * than a hard cut. Markers come off at the start and go on once the new
         * texture is fully in.
         */
        switchMapLayer(layer) {
            if (!this.map || layer === this.mapLayer || !MAP_LAYERS[layer] || this._switching) return;
            this._switching = true;

            const from = this.mapLayer;
            this.mapLayer = layer;               // button tint updates immediately
            const FADE = 280;

            // Old markers off first so they don't hang over the wrong texture.
            this.setVisible(this.markers, false);
            this.setVisible(this.playerMarkers, false);
            this.setVisible(this.alphaPalMarkers, false);
            this.setVisible(this.fastTravelMarkers, false);

            const inId = `map-${layer}`, outId = `map-${from}`;
            this.map.setPaintProperty(inId, 'raster-opacity-transition', { duration: FADE, delay: 0 });
            this.map.setPaintProperty(outId, 'raster-opacity-transition', { duration: FADE, delay: 0 });
            this.map.setPaintProperty(inId, 'raster-opacity', 1);
            this.map.setPaintProperty(outId, 'raster-opacity', 0);

            // Both textures share the same Mercator square; pull back to the
            // whole-map view of the new one.
            this.map.easeTo({ center: [0, 0], zoom: this.fitZoom(), duration: FADE + 80,
                              easing: t => 1 - Math.pow(1 - t, 3) });

            setTimeout(() => {
                this._switching = false;
                this.loadBases();
                this.loadPlayers();
                this.renderStaticMapObjects();
            }, FADE + 20);
        },

        // ------------------------------------------------------------------
        // Marker helpers
        // ------------------------------------------------------------------

        /** Build a DOM marker from an HTML template and place it. */
        makeMarker(html, saveX, saveY, zIndex, onClick) {
            const el = document.createElement('div');
            el.className = 'pw-marker';
            el.style.zIndex = String(zIndex);
            if (html instanceof Node) el.appendChild(html); else el.innerHTML = html;
            if (onClick) el.addEventListener('click', onClick);

            return new maplibregl.Marker({ element: el, anchor: 'center' })
                .setLngLat(saveToLngLat(saveX, saveY, this.mapLayer));
        },

        /**
         * Coalesce repeated loader calls into one per animation frame. The map
         * 'load' handler and the deep $watch on app data both fire loadBases /
         * loadPlayers at startup; running them back-to-back removes markers that
         * MapLibre hasn't finished attaching (its first DOM update is rAF-deferred),
         * which throws inside the library. One run per frame avoids that, and
         * cancelling the pending retry timer stops a second loop overlapping.
         */
        _coalesce(key, fn) {
            this._pending = this._pending || {};
            if (this._pending[key]) return;
            this._pending[key] = true;
            requestAnimationFrame(() => { this._pending[key] = false; fn(); });
        },

        loadBases(retries = 0) {
            if (retries === 0) {
                clearTimeout(this._baseRetry);
                return this._coalesce('bases', () => this._loadBasesNow(0));
            }
            this._loadBasesNow(retries);
        },

        _loadBasesNow(retries) {
            if (!this.map) return;   // not created yet (tab hidden); 'load' will draw
            this.markers.forEach(m => m.remove());
            this.markers = [];

            const bodyData = Alpine.$data(document.body);
            let guilds = bodyData && bodyData.guilds ? bodyData.guilds : (this.$root && this.$root.guilds ? this.$root.guilds : []);

            if ((!guilds || guilds.length === 0) && retries < 10) {
                console.log(`⏳ Map waiting for data... (Attempt ${retries + 1}/10)`);
                this._baseRetry = setTimeout(() => this._loadBasesNow(retries + 1), 500);
                return;
            }

            console.log(`📍 Loading markers for ${guilds.length} guilds...`);

            for (const guild of guilds) {
                if (!guild.base_locations) continue;
                for (const base of guild.base_locations) {
                    // Skip bases that live on the other map layer -- projecting
                    // them with this layer's bounds would scatter them off-texture.
                    if (base.x !== undefined && base.y !== undefined
                        && layerForCoords(base.x, base.y) === this.mapLayer) {
                        this.addBaseMarker(base, guild);
                    }
                }
            }
        },

        addBaseMarker(base, guild) {
            // In-game display coordinates (the numbers the game shows the player)
            const gameX = (base.y - 158000) / 625;
            const gameY = (base.x + 123888) / 625;

            const html = `
                <div class="relative group">
                    <img src="/img/t_icon_compass_camp.webp" class="w-12 h-12 object-contain transition-transform transform group-hover:scale-125 cursor-pointer drop-shadow-lg" alt="Base" />
                    <div class="absolute -bottom-16 left-1/2 transform -translate-x-1/2 bg-gray-900/95 text-white text-xs px-3 py-2 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none border border-gray-600 z-[9999] shadow-lg max-w-[280px]">
                        <div class="flex items-center gap-2 mb-1">
                            <span class="font-semibold truncate">${base.base_name}</span>
                            <span class="text-gray-400 text-[10px] truncate flex-shrink-0">${guild.guild_name}</span>
                        </div>
                        <div class="text-gray-400">X: ${Math.round(gameX)} | Y: ${Math.round(gameY)}</div>
                    </div>
                </div>`;

            const marker = this.makeMarker(html, base.x, base.y, Z.base, () => {
                // Open this base in the Bases tab. The tab listens for
                // navigate-to-base, but it only selects the base -- it doesn't
                // switch tabs -- so switch first (same as the Overview tab does),
                // then dispatch on the next tick once it's shown.
                const app = Alpine.$data(document.body);
                if (app) app.currentTab = 'bases';
                this.$nextTick(() => {
                    window.dispatchEvent(new CustomEvent('navigate-to-base', {
                        detail: { guildId: guild.guild_id, baseId: base.base_id }
                    }));
                });
            });
            if (this.showBases) marker.addTo(this.map);
            this.markers.push(marker);
        },

        loadPlayers(retries = 0) {
            if (retries === 0) {
                clearTimeout(this._playerRetry);
                return this._coalesce('players', () => this._loadPlayersNow(0));
            }
            this._loadPlayersNow(retries);
        },

        _loadPlayersNow(retries) {
            if (!this.map) return;   // not created yet (tab hidden); 'load' will draw
            this.playerMarkers.forEach(m => m.remove());
            this.playerMarkers = [];

            const bodyData = Alpine.$data(document.body);
            let players = bodyData && bodyData.players ? bodyData.players : (this.$root && this.$root.players ? this.$root.players : []);

            if ((!players || players.length === 0) && retries < 10) {
                console.log(`⏳ Map waiting for player data... (Attempt ${retries + 1}/10)`);
                this._playerRetry = setTimeout(() => this._loadPlayersNow(retries + 1), 500);
                return;
            }

            console.log(`👤 Loading markers for ${players.length} players...`);

            for (const player of players) {
                if (player.location && player.location.x !== undefined && player.location.y !== undefined
                    && layerForCoords(player.location.x, player.location.y) === this.mapLayer) {
                    this.addPlayerMarker(player);
                }
            }
        },

        addPlayerMarker(player) {
            const gameX = (player.location.y - 158000) / 625;
            const gameY = (player.location.x + 123888) / 625;

            const html = `
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
                </div>`;

            const marker = this.makeMarker(html, player.location.x, player.location.y, Z.player);
            if (this.showPlayers) marker.addTo(this.map);
            this.playerMarkers.push(marker);
        },

        resetView() {
            if (!this.map) return;
            this.map.resize();
            this.map.easeTo({ center: [0, 0], zoom: this.fitZoom(), duration: 300 });
        },

        refresh() {
            this.isRefreshing = true;
            this.loadBases();
            this.loadPlayers();
            setTimeout(() => { this.isRefreshing = false; }, 600);
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

        /** Redraw the static markers for the active layer (no refetch). */
        renderStaticMapObjects() {
            this.loadAlphaPals();
            this.loadFastTravelPoints();
        },

        async loadStaticMapObjects() {
            if (this.mapObjectsLoaded) {
                this.renderStaticMapObjects();
                return;
            }
            try {
                console.log('📍 Loading static map objects from API...');
                const response = await fetch('/api/map-objects', {
                    credentials: 'include',
                    headers: { 'Accept': 'application/json' }
                });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);

                const data = await response.json();
                // Every static marker, any type; each loader filters what it draws.
                this.mapObjects = data.objects || [];
                this.mapObjectsLoaded = true;
                const counts = {};
                for (const o of this.mapObjects) counts[o.type] = (counts[o.type] || 0) + 1;
                console.log('📍 Loaded static map objects:', counts);
                this.renderStaticMapObjects();
            } catch (error) {
                console.error('❌ Failed to load map objects:', error);
            }
        },

        loadAlphaPals() {
            if (!this.map || !this.mapObjects) return;   // map not created yet (tab hidden); 'load' will draw
            this.alphaPalMarkers.forEach(m => m.remove());
            this.alphaPalMarkers = [];

            // Only objects belonging to the visible layer. Older data has no
            // 'map' field, so treat missing as MainMap.
            const alphaPals = this.mapObjects.filter(
                obj => obj.type === 'alpha_pal' && (obj.map ?? 'MainMap') === this.mapLayer);
            console.log(`🐲 Loading ${alphaPals.length} alpha pal markers...`);

            for (const alphaPal of alphaPals) {
                if (alphaPal.x !== undefined && alphaPal.y !== undefined) this.addAlphaPalMarker(alphaPal);
            }
        },

        addAlphaPalMarker(alphaPal) {
            const palName = alphaPal.pal_name || alphaPal.pal;
            const level = alphaPal.level;

            const root = document.createElement('div');
            root.className = 'relative group';
            root.innerHTML = `
                    <div class="w-8 h-8 bg-black rounded-full border-2 border-white shadow-lg flex items-center justify-center transition-transform transform group-hover:scale-110 cursor-pointer overflow-hidden">
                        <img class="w-6 h-6 object-contain" alt="${palName}" />
                    </div>
                    <div class="absolute top-10 left-1/2 transform -translate-x-1/2 bg-gray-900/95 text-white text-xs px-2 py-1.5 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none border border-gray-600 z-[9999] shadow-lg max-w-[280px]">
                        <div class="font-semibold text-yellow-400 break-words">⚔️ ${palName}</div>
                        ${level ? `<div class="text-gray-300 text-[11px]">Level ${level}</div>` : ''}
                        <div class="text-gray-400 text-[10px]">Alpha Pal</div>
                    </div>`;
            // Same icon rule and fallback chain as the pals tab (image_candidates
            // from the API); the map no longer derives icon names itself.
            const img = root.querySelector('img');
            img.src = palIconSrc(alphaPal);
            img.onerror = () => palIconError(img, alphaPal);

            const marker = this.makeMarker(root, alphaPal.x, alphaPal.y, Z.alphaPal);
            if (this.showAlphaPals) marker.addTo(this.map);
            this.alphaPalMarkers.push(marker);
        },

        loadFastTravelPoints() {
            if (!this.map || !this.mapObjects) return;
            this.fastTravelMarkers.forEach(m => m.remove());
            this.fastTravelMarkers = [];

            const points = this.mapObjects.filter(
                obj => obj.type === 'fast_travel' && (obj.map ?? 'MainMap') === this.mapLayer);
            console.log(`🚀 Loading ${points.length} fast travel markers...`);

            for (const point of points) {
                if (point.x !== undefined && point.y !== undefined) this.addFastTravelMarker(point);
            }
        },

        addFastTravelMarker(point) {
            const html = `
                <div class="relative group">
                    <!-- Fast-travel emblem: the game's compass eagle in the cyan the
                         in-game world map draws it. Baked from the white pak sprite by
                         scripts/datagen/compose_fast_travel_icon.py. -->
                    <img src="/img/t_icon_compass_fttower_cyan.webp"
                         class="w-10 h-10 object-contain drop-shadow-[0_0_3px_rgba(0,0,0,0.9)] transition-transform transform group-hover:scale-125 cursor-pointer"
                         alt="Fast Travel" />
                    <div class="absolute top-full mt-2 left-1/2 transform -translate-x-1/2 bg-gray-900/95 text-white text-xs px-3 py-2 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none border border-gray-600 z-[9999] shadow-lg max-w-[280px]">
                        <div class="font-semibold text-cyan-400 break-words">${point.localized_name}</div>
                        <div class="text-gray-400 text-[10px] mt-1">Fast Travel Point</div>
                    </div>
                </div>`;

            const marker = this.makeMarker(html, point.x, point.y, Z.fastTravel);
            if (this.showFastTravel) marker.addTo(this.map);
            this.fastTravelMarkers.push(marker);
        },

        // ------------------------------------------------------------------
        // Filters / controls (bound from the template)
        // ------------------------------------------------------------------

        setVisible(list, visible) {
            if (!this.map) return;   // not created yet (tab hidden); 'load' will draw
            list.forEach(m => visible ? m.addTo(this.map) : m.remove());
        },
        toggleBases()      { this.showBases = !this.showBases;           this.setVisible(this.markers, this.showBases);               savePref('mapBases', this.showBases); },
        togglePlayers()    { this.showPlayers = !this.showPlayers;       this.setVisible(this.playerMarkers, this.showPlayers);       savePref('mapPlayers', this.showPlayers); },
        toggleAlphaPals()  { this.showAlphaPals = !this.showAlphaPals;   this.setVisible(this.alphaPalMarkers, this.showAlphaPals);   savePref('mapAlphaPals', this.showAlphaPals); },
        toggleFastTravel() { this.showFastTravel = !this.showFastTravel; this.setVisible(this.fastTravelMarkers, this.showFastTravel); savePref('mapFastTravel', this.showFastTravel); },
        toggleFilters()    { this.filtersCollapsed = !this.filtersCollapsed; savePref('mapFiltersCollapsed', this.filtersCollapsed); },

        zoomIn()  { if (this.map) this.map.zoomIn({ duration: 200 }); },
        zoomOut() { if (this.map) this.map.zoomOut({ duration: 200 }); },

        /** Centre on a world coordinate. `zoom` is in the old Leaflet scale (z5 = native). */
        centerOnLocation(x, y, zoom = 5) {
            if (this.map && x !== undefined && y !== undefined) {
                this.map.easeTo({ center: saveToLngLat(x, y, this.mapLayer), zoom: zoom - 1, duration: 500 });
            }
        }
    };
}
