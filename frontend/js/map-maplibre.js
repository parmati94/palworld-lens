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
import { saveToLngLat, layerForCoords, MAP_LAYERS, MAP_LAYER_ORDER, palIconSrc, palIconError, shadeHex } from './utils.js';
import { loadPrefs, savePref, pref } from './prefs.js';
import { api } from './services/api.js';

const prefs = loadPrefs();

const NATIVE_MAX_ZOOM = 4;   // tiles exist through source z5 == map z4
const MAX_ZOOM = 7;          // 3 levels of GPU overzoom past native
const MIN_ZOOM = 0.5;        // ~724px world: lets the whole square fit in a 70vh container

// Stacking: players over alphas over bases over fast travel (was zIndexOffset).
const Z = { fastTravel: 100, base: 300, alphaPal: 500, player: 1000 };

const OCEAN = '#0b101b';
const MAX_RECENT = 5;        // spawn search: recent picks shown before you type

// Spawn-search caches. One map component per page, so module level is fine;
// keyed so a layer switch or the dungeon toggle invalidates them.
let statsCache = { key: '', map: new Map() };
const colorCache = new Map();

/** `#rrggbb` -> the same hue with saturation >= 0.7 and lightness in 0.42..0.56. */
function normaliseTone(hex) {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
    if (!m) return hex;
    const n = parseInt(m[1], 16);
    const r = (n >> 16) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
    let h = 0, s = 0, l = (max + min) / 2;
    if (d > 0) {
        s = d / (1 - Math.abs(2 * l - 1));
        if (max === r) h = ((g - b) / d) % 6;
        else if (max === g) h = (b - r) / d + 2;
        else h = (r - g) / d + 4;
        h = (h * 60 + 360) % 360;
    }
    s = Math.max(s, 0.7);
    l = Math.min(0.56, Math.max(0.42, l));
    const c = (1 - Math.abs(2 * l - 1)) * s, x = c * (1 - Math.abs(((h / 60) % 2) - 1)), m0 = l - c / 2;
    const [r1, g1, b1] = h < 60 ? [c, x, 0] : h < 120 ? [x, c, 0] : h < 180 ? [0, c, x]
                        : h < 240 ? [0, x, c] : h < 300 ? [x, 0, c] : [c, 0, x];
    const to = (v) => Math.round((v + m0) * 255);
    return '#' + ((to(r1) << 16) | (to(g1) << 8) | to(b1)).toString(16).padStart(6, '0');
}

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

        // Wild spawn zones (data/json/spawns.json via /api/spawns, loaded once).
        // Pick a species in the search box and every spawner group that rolls it
        // is drawn as a translucent disc (its real spawn radius), tinted with the
        // species' element colour and weighted by its share of the group.
        spawns: null,              // {groupName: {kind, radius, points: {layer: [[x, y]]}, pals: {id: {share, level, time?, boss?}}}}
        spawnSpecies: [],          // [{id, name, image_candidates, element_types, groups}]
        spawnById: {},
        spawnsLoaded: false,
        spawnPal: '',              // selected species id ('' = nothing lit)
        spawnPalName: '',          // display name, kept even when the id has no zones
        spawnQuery: '',
        spawnPanel: false,         // search panel slid out (toggle button in the control column)
        spawnOpen: false,          // results list showing
        spawnCursor: 0,
        spawnBrowse: false,        // empty query: recents (default) or the whole list
        spawnRecent: Array.isArray(prefs.mapSpawnRecent) ? prefs.mapSpawnRecent.filter(x => typeof x === 'string').slice(0, MAX_RECENT) : [],
        spawnDungeons: pref(prefs, 'mapSpawnDungeons', false),
        // Phones: the open panel spans the map's full width (over the control
        // column) and the results list is capped to what is visible above the
        // on-screen keyboard, measured from the visual viewport. Otherwise the
        // list ran under the keyboard and a drag scrolled the page instead.
        spawnPhone: typeof window !== 'undefined' && window.matchMedia('(max-width: 639px)').matches,
        spawnListMax: 0,           // px; 0 = no cap (desktop)

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

                    // "Where to find" in the pal modal: light up a species' zones.
                    window.addEventListener('show-pal-spawns', (e) => {
                        const d = (e && e.detail) || {};
                        this.showSpawnsFor(d.species, d.name);
                    });

                    // Phone list cap (see spawnPhone). The visual viewport shrinks
                    // when the keyboard opens; the layout viewport doesn't on iOS.
                    const phone = window.matchMedia('(max-width: 639px)');
                    phone.addEventListener('change', (e) => { this.spawnPhone = e.matches; this.measureSpawnList(); });
                    const vv = window.visualViewport;
                    if (vv) {
                        vv.addEventListener('resize', () => this.measureSpawnList());
                        vv.addEventListener('scroll', () => this.measureSpawnList());
                    } else {
                        window.addEventListener('resize', () => this.measureSpawnList());
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
                    this.loadSpawns();
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
            this.setSpawnFeatures([]);

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
                this.renderSpawns();
                if (this._fitSpawnsAfterSwitch) { this._fitSpawnsAfterSwitch = false; this.fitSpawns(); }
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
                    <div class="w-6 h-6 bg-ok-500 rounded-full border-2 border-white shadow-lg flex items-center justify-center transition-transform transform group-hover:scale-110 cursor-pointer">
                        <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clip-rule="evenodd" />
                        </svg>
                    </div>
                    <div class="absolute -bottom-16 left-1/2 transform -translate-x-1/2 bg-gray-900/95 text-white text-xs px-3 py-2 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none border border-gray-600 z-[9999] shadow-lg max-w-[280px]">
                        <div class="flex items-center gap-2 mb-1">
                            <span class="font-semibold">${player.player_name}</span>
                            <span class="text-ok-400 text-[10px]">Lv ${player.level}</span>
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
                        <div class="font-semibold text-warn-400 break-words">⚔️ ${palName}</div>
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
                        <div class="font-semibold text-accent-400 break-words">${point.localized_name}</div>
                        <div class="text-gray-400 text-[10px] mt-1">Fast Travel Point</div>
                    </div>
                </div>`;

            const marker = this.makeMarker(html, point.x, point.y, Z.fastTravel);
            if (this.showFastTravel) marker.addTo(this.map);
            this.fastTravelMarkers.push(marker);
        },

        // ------------------------------------------------------------------
        // Wild spawn zones
        // ------------------------------------------------------------------

        async loadSpawns() {
            if (this.spawnsLoaded) { this.renderSpawns(); return; }
            try {
                const data = await api.getSpawns();
                this.spawns = data.groups || {};
                this.spawnSpecies = data.species || [];
                this.spawnById = Object.fromEntries(this.spawnSpecies.map(s => [s.id, s]));
                this.spawnsLoaded = true;
                console.log(`🌿 Loaded ${Object.keys(this.spawns).length} spawner groups for ${this.spawnSpecies.length} species`);
                this.renderSpawns();
                if (this.spawnPal) this.fitSpawns();   // picked before the data arrived
            } catch (error) {
                console.error('❌ Failed to load spawn data:', error);
            }
        },

        /**
         * Search results. Typed: prefix matches, then anywhere in the name or
         * id; within each tier, species with zones on the showing map layer
         * first. Empty: the last few picks (or, after "Browse all", every
         * species alphabetically).
         */
        get spawnList() {
            const q = this.spawnQuery.trim().toLowerCase();
            if (!q) {
                if (this.spawnBrowse) return this.spawnSpecies;
                return this.spawnRecent.map(id => this.spawnById[id]).filter(Boolean);
            }
            const starts = [], within = [];
            for (const s of this.spawnSpecies) {
                const name = s.name.toLowerCase(), id = s.id.toLowerCase();
                if (name.startsWith(q) || id.startsWith(q)) starts.push(s);
                else if (name.includes(q) || id.includes(q)) within.push(s);
            }
            const hereFirst = (a, b) => (this.spawnStats(b).here > 0) - (this.spawnStats(a).here > 0);
            return starts.sort(hereFirst).concat(within.sort(hereFirst));
        },

        get spawnShowingRecents() {
            return !this.spawnQuery.trim() && !this.spawnBrowse;
        },

        /**
         * Phone: cap the results list to the space between its top and the
         * nearer of the visual viewport's bottom (keyboard-aware) and the map's
         * bottom, so it never runs under the keyboard or out of the card.
         */
        measureSpawnList() {
            if (!(this.spawnPhone && this.spawnPanel)) { this.spawnListMax = 0; return; }
            this.$nextTick(() => {
                const list = this.$refs.spawnItems, mapEl = this.$refs.worldMap;
                if (!list || !mapEl) return;
                const vv = window.visualViewport;
                const vvBottom = vv ? vv.offsetTop + vv.height : window.innerHeight;
                const bottom = Math.min(vvBottom, mapEl.getBoundingClientRect().bottom) - 12;
                this.spawnListMax = Math.max(140, Math.round(bottom - list.getBoundingClientRect().top));
            });
        },

        get spawnListStyle() {
            return this.spawnListMax ? `max-height:${this.spawnListMax}px` : '';
        },

        get spawnSelected() {
            return (this.spawnPal && this.spawnById[this.spawnPal]) || null;
        },

        /** Dungeon rooms are instanced, so they're off by default. */
        spawnKindShown(kind) {
            return this.spawnDungeons || kind === 'field' || kind === 'field_boss';
        },

        /** Counts for the strip under the search box: zones, level range, night-only. */
        get spawnSummary() {
            const sel = this.spawnSelected;
            if (!sel || !this.spawns) return null;
            const out = { zones: 0, lvMin: Infinity, lvMax: 0, night: 0, dungeons: 0, perLayer: {} };
            for (const name of sel.groups) {
                const g = this.spawns[name];
                const e = g && g.pals[sel.id];
                if (!e) continue;
                const n = Object.values(g.points).reduce((a, p) => a + p.length, 0);
                if (!this.spawnKindShown(g.kind)) { if (g.kind !== 'field_boss') out.dungeons += n; continue; }
                for (const [layer, pts] of Object.entries(g.points)) out.perLayer[layer] = (out.perLayer[layer] || 0) + pts.length;
                out.zones += n;
                out.lvMin = Math.min(out.lvMin, e.level[0]);
                out.lvMax = Math.max(out.lvMax, e.level[1]);
                if (e.time === 'night') out.night += n;
            }
            out.onThisLayer = out.perLayer[this.mapLayer] || 0;
            return out;
        },

        /** Zones of the lit species on the layer that is NOT showing: {layer, label, count} or null. */
        get spawnOtherLayer() {
            const s = this.spawnSummary;
            if (!s) return null;
            for (const layer of MAP_LAYER_ORDER) {
                if (layer !== this.mapLayer && s.perLayer[layer]) {
                    return { layer, label: MAP_LAYERS[layer].label, count: s.perLayer[layer] };
                }
            }
            return null;
        },

        /**
         * Per-row numbers for the results list: shown zones in total and on the
         * current layer (sort key), and the level range. Cached per
         * (dungeon toggle, layer) since the list re-renders on every keystroke.
         */
        spawnStats(species) {
            const key = `${this.spawnsLoaded ? 1 : 0}|${this.spawnDungeons ? 1 : 0}|${this.mapLayer}`;
            if (statsCache.key !== key) statsCache = { key, map: new Map() };
            let st = statsCache.map.get(species.id);
            if (st) return st;
            st = { zones: 0, here: 0, lvMin: Infinity, lvMax: 0 };
            for (const name of species.groups) {
                const g = this.spawns && this.spawns[name];
                const e = g && g.pals[species.id];
                if (!e || !this.spawnKindShown(g.kind)) continue;
                for (const [layer, pts] of Object.entries(g.points)) {
                    st.zones += pts.length;
                    if (layer === this.mapLayer) st.here += pts.length;
                }
                st.lvMin = Math.min(st.lvMin, e.level[0]);
                st.lvMax = Math.max(st.lvMax, e.level[1]);
            }
            if (!st.zones) st.lvMin = 0;
            statsCache.map.set(species.id, st);
            return st;
        },

        spawnZoneCount(species) {
            return this.spawnStats(species).zones;
        },

        spawnLevelText(species) {
            const st = this.spawnStats(species);
            return st.lvMin === st.lvMax ? `Lv ${st.lvMin}` : `Lv ${st.lvMin}–${st.lvMax}`;
        },

        openSpawnPanel() {
            this.spawnPanel = true;
            this.spawnBrowse = false;
            // On the phone sheet the list is always showing and nothing is
            // pre-highlighted (a highlighted first row reads as "selected" on touch).
            this.spawnOpen = this.spawnPhone;
            this.spawnCursor = this.spawnPhone ? -1 : 0;
            this.measureSpawnList();
            this.$nextTick(() => this.$refs.spawnQuery && this.$refs.spawnQuery.focus());
        },

        closeSpawnPanel() {
            this.spawnPanel = false;
            this.spawnOpen = false;
            this.spawnBrowse = false;
            this.spawnListMax = 0;
            if (this.$refs.spawnQuery) this.$refs.spawnQuery.blur();
        },

        spawnInput() {
            this.spawnOpen = true;
            this.spawnCursor = this.spawnPhone ? -1 : 0;
            if (this.$refs.spawnItems) this.$refs.spawnItems.scrollTop = 0;   // new query, start at the top
            this.measureSpawnList();
        },

        browseAllSpawns() {
            this.spawnBrowse = true;
            this.spawnOpen = true;
            this.spawnCursor = this.spawnPhone ? -1 : 0;
            if (this.$refs.spawnItems) this.$refs.spawnItems.scrollTop = 0;
        },

        toggleSpawnPanel() {
            if (this.spawnPanel) this.closeSpawnPanel();
            else this.openSpawnPanel();
        },

        spawnMove(delta) {
            if (!this.spawnOpen) { this.spawnOpen = true; return; }
            const n = this.spawnList.length;
            if (!n) return;
            this.spawnCursor = (this.spawnCursor + delta + n) % n;
            this.$nextTick(() => {
                const el = this.$refs.spawnItems && this.$refs.spawnItems.children[this.spawnCursor];
                if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' });
            });
        },

        spawnPickCursor() {
            const s = this.spawnList[Math.max(0, this.spawnCursor)];   // phone "Go" with nothing highlighted: first match
            if (s) this.pickSpawnPal(s.id);
        },

        rememberSpawnPick(id) {
            if (!this.spawnById[id]) return;
            this.spawnRecent = [id].concat(this.spawnRecent.filter(x => x !== id)).slice(0, MAX_RECENT);
            savePref('mapSpawnRecent', this.spawnRecent);
        },

        pickSpawnPal(id) {
            const s = this.spawnById[id];
            this.spawnPal = id;
            this.spawnPalName = s ? s.name : id;
            this.spawnQuery = '';
            this.spawnOpen = false;
            this.spawnPanel = false;   // collapse to the chip so the map is clear
            this.spawnBrowse = false;
            this.spawnCursor = 0;
            this.spawnListMax = 0;
            if (this.$refs.spawnQuery) this.$refs.spawnQuery.blur();
            this.rememberSpawnPick(id);
            this.renderSpawns();
            this.fitSpawns();
        },

        /** The × : with the panel open, keep it open for another search; on the chip, hide everything. */
        clearSpawnPal() {
            this.spawnPal = '';
            this.spawnPalName = '';
            this.spawnQuery = '';
            this.spawnOpen = false;
            if (this.spawnPanel) this.$nextTick(() => this.$refs.spawnQuery && this.$refs.spawnQuery.focus());
            this.renderSpawns();
        },

        /** Entry point from the pal modal (and anything else): select by species id. */
        showSpawnsFor(speciesId, name) {
            if (!speciesId) return;
            this.spawnPal = speciesId;
            this.spawnPalName = (this.spawnById[speciesId] || {}).name || name || speciesId;
            this.spawnQuery = '';
            this.spawnOpen = false;
            this.spawnPanel = false;
            this.spawnBrowse = false;
            this.rememberSpawnPick(speciesId);
            this.renderSpawns();
            this.fitSpawns();
        },

        toggleSpawnDungeons() {
            this.spawnDungeons = !this.spawnDungeons;
            savePref('mapSpawnDungeons', this.spawnDungeons);
            this.renderSpawns();
        },

        /**
         * Zone tint: the species' first element colour, pulled into a mid-tone
         * band. The raw game colours run from near-white (Normal, Electric) to
         * near-black (Dark); on the map art both vanish, so saturation is floored
         * and lightness clamped before use. Chikipi ends up terracotta, not white.
         */
        spawnColor(species) {
            const hit = colorCache.get(species.id);
            if (hit) return hit;
            const app = Alpine.$data(document.body);
            const el = species.element_types && species.element_types[0];
            const info = app && app.gameData && app.gameData.elements && app.gameData.elements[el];
            const color = normaliseTone((info && info.color) || '#f472b6');
            if (info) colorCache.set(species.id, color);   // only once the element table is here
            return color;
        },

        /** A spawn radius as a lng/lat ring. World space is square-scaled, so a circle stays a circle. */
        circleRing(x, y, r, steps = 36) {
            const ring = [];
            for (let i = 0; i <= steps; i++) {
                const t = (i / steps) * Math.PI * 2;
                ring.push(saveToLngLat(x + r * Math.cos(t), y + r * Math.sin(t), this.mapLayer));
            }
            return ring;
        },

        ensureSpawnLayers() {
            if (!this.map || this.map.getSource('spawns')) return;
            // Two sources from the same zones: the spawner centres drive a heatmap
            // (the visible layer -- overlapping spawners read as density instead of
            // sixty stacked discs), and the discs themselves stay in an invisible
            // fill layer purely for hover hit-testing at the real spawn radius.
            this.map.addSource('spawns-pts', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
            this.map.addSource('spawns', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
            this.map.addLayer({
                id: 'spawns-fill', type: 'fill', source: 'spawns',
                paint: { 'fill-color': '#000', 'fill-opacity': 0 },
            });
            this.addSpawnHeatLayer('#f472b6');

            const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10, className: 'pw-popup', maxWidth: '240px' });
            this.map.on('mousemove', 'spawns-fill', (e) => {
                const f = e.features && e.features[0];
                if (!f) return;
                this.map.getCanvas().style.cursor = 'pointer';
                popup.setLngLat(e.lngLat).setHTML(this.spawnPopupHtml(f.properties)).addTo(this.map);
            });
            this.map.on('mouseleave', 'spawns-fill', () => {
                this.map.getCanvas().style.cursor = '';
                popup.remove();
            });
            this.map.on('click', 'spawns-fill', (e) => {
                this.map.easeTo({ center: e.lngLat, zoom: Math.max(this.map.getZoom(), 3.2), duration: 400 });
            });
        },

        /**
         * (Re)create the heatmap layer in a species' colour. MapLibre 5 throws inside
         * its colour-ramp texture update when heatmap-color is changed with
         * setPaintProperty on a live layer, so the layer is rebuilt instead -- it
         * is one GPU pass over a few hundred points, so this costs nothing visible.
         */
        addSpawnHeatLayer(color) {
            if (!this.map) return;
            if (this.map.getLayer('spawns-heat')) {
                if (this._spawnHeatColor === color) return;
                this.map.removeLayer('spawns-heat');
            }
            this._spawnHeatColor = color;
            // Dark halo under the colour, like a stroke on text: gives any hue an
            // edge against sand, snow and grass. Created once, radius follows the layer.
            if (!this.map.getLayer('spawns-halo')) {
                this.map.addLayer({
                    id: 'spawns-halo', type: 'heatmap', source: 'spawns-pts',
                    paint: {
                        'heatmap-weight': ['+', 0.45, ['*', 0.55, ['get', 'w']]],
                        'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1.6, 3, 1],
                        'heatmap-opacity': 0.55,
                        'heatmap-radius': this.spawnHeatRadius(1.3),
                        'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'],
                                          0, 'rgba(0,0,0,0)', 0.05, 'rgba(6,10,20,0.7)', 1, 'rgba(6,10,20,0.7)'],
                    },
                }, 'spawns-fill');
            }
            this.map.addLayer({
                id: 'spawns-heat', type: 'heatmap', source: 'spawns-pts',
                paint: {
                    // A lone spawner still shows; a herd of them saturates to the area's colour.
                    'heatmap-weight': ['+', 0.45, ['*', 0.55, ['get', 'w']]],
                    // Kernels are only ~5px at the whole-map view, so lift them there.
                    'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1.6, 3, 1],
                    'heatmap-opacity': 0.85,
                    'heatmap-radius': this.spawnHeatRadius(),
                    'heatmap-color': this.spawnHeatRamp(color),
                },
            }, 'spawns-fill');   // under the hit-test fill, above the raster
        },

        /**
         * Heatmap kernel radius in pixels that matches each spawner's world radius
         * on the active layer. The square texture is 512px at zoom 0 and doubles
         * per level, so px = units * (512 / layerSpan) * 2^zoom.
         */
        spawnHeatRadius(scale = 1) {
            const m = MAP_LAYERS[this.mapLayer] || MAP_LAYERS.MainMap;
            const k0 = scale * 512 / (m.maxX - m.minX);
            return ['interpolate', ['exponential', 2], ['zoom'],
                    0, ['*', ['get', 'r'], k0],
                    MAX_ZOOM, ['*', ['get', 'r'], k0 * Math.pow(2, MAX_ZOOM)]];
        },

        /** Density ramp in the species' colour: clear edge, solid core, lighter peak. */
        spawnHeatRamp(hex) {
            const rgb = (h) => { const n = parseInt(h.slice(1), 16); return `${n >> 16}, ${(n >> 8) & 255}, ${n & 255}`; };
            const c = rgb(hex), hi = rgb(shadeHex(hex, 22));
            return ['interpolate', ['linear'], ['heatmap-density'],
                    0,    'rgba(0,0,0,0)',
                    0.04, `rgba(${c}, 0)`,
                    0.15, `rgba(${c}, 0.5)`,
                    0.5,  `rgba(${c}, 0.75)`,
                    1,    `rgba(${hi}, 0.9)`];
        },

        spawnPopupHtml(p) {
            const kind = { field: 'Field', dungeon: 'Dungeon', dungeon_boss: 'Dungeon boss', field_boss: 'Alpha', prison_boss: 'Sealed realm' }[p.kind] || p.kind;
            const lv = p.lvMin === p.lvMax ? `Lv ${p.lvMin}` : `Lv ${p.lvMin}–${p.lvMax}`;
            const share = Math.round(p.share * 100);
            const bits = [lv, `${share}% of spawns here`];
            if (p.night === true || p.night === 'true') bits.push('night only');
            return `<div class="font-semibold text-gray-100">${this.spawnPalName}</div>`
                 + `<div class="text-gray-400 text-[11px]">${kind} · ${bits.join(' · ')}</div>`;
        },

        setSpawnFeatures(features, points = [], color = null) {
            const src = this.map && this.map.getSource('spawns');
            if (src) src.setData({ type: 'FeatureCollection', features });
            const pts = this.map && this.map.getSource('spawns-pts');
            if (pts) pts.setData({ type: 'FeatureCollection', features: points });
            if (this.map && this.map.getLayer('spawns-heat')) {
                if (color) this.addSpawnHeatLayer(color);
                this.map.setPaintProperty('spawns-heat', 'heatmap-radius', this.spawnHeatRadius());
                this.map.setPaintProperty('spawns-halo', 'heatmap-radius', this.spawnHeatRadius(1.3));
            }
            this._spawnFeatures = features;
        },

        /** Rebuild the zone polygons for the selected species on the active layer. */
        renderSpawns() {
            if (!this.map || !this.mapReady || !this.spawns) return;
            this.ensureSpawnLayers();
            const sel = this.spawnSelected;
            const features = [], points = [];
            let color = null;
            if (sel) {
                color = this.spawnColor(sel);
                for (const name of sel.groups) {
                    const g = this.spawns[name];
                    const e = g && g.pals[sel.id];
                    if (!e || !this.spawnKindShown(g.kind)) continue;
                    const r = g.radius || 15000;
                    for (const [x, y] of (g.points[this.mapLayer] || [])) {
                        points.push({
                            type: 'Feature',
                            properties: { w: e.share, r },
                            geometry: { type: 'Point', coordinates: saveToLngLat(x, y, this.mapLayer) },
                        });
                        features.push({
                            type: 'Feature',
                            properties: {
                                name, kind: g.kind, share: e.share, lvMin: e.level[0], lvMax: e.level[1],
                                night: e.time === 'night', boss: !!e.boss,
                            },
                            geometry: { type: 'Polygon', coordinates: [this.circleRing(x, y, r)] },
                        });
                    }
                }
                // Rarer (lower-share) zones hit-test first so they aren't buried under herds.
                features.sort((a, b) => b.properties.share - a.properties.share);
            }
            this.setSpawnFeatures(features, points, color);
        },

        /**
         * Frame the lit zones. If the species only spawns on the other map layer,
         * travel there first (switchMapLayer redraws and then fits).
         */
        fitSpawns() {
            if (!this.map || !this.mapReady || !this.spawnSelected) return;
            const s = this.spawnSummary;
            if (s && !s.onThisLayer) {
                const other = MAP_LAYER_ORDER.find(l => l !== this.mapLayer && s.perLayer[l]);
                if (other) { this._fitSpawnsAfterSwitch = true; this.switchMapLayer(other); }
                return;
            }
            const feats = this._spawnFeatures || [];
            if (!feats.length) return;
            let minLng = 180, maxLng = -180, minLat = 90, maxLat = -90;
            for (const f of feats) {
                for (const [lng, lat] of f.geometry.coordinates[0]) {
                    if (lng < minLng) minLng = lng; if (lng > maxLng) maxLng = lng;
                    if (lat < minLat) minLat = lat; if (lat > maxLat) maxLat = lat;
                }
            }
            this.map.fitBounds([[minLng, minLat], [maxLng, maxLat]], { padding: 70, maxZoom: 4, duration: 600 });
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
