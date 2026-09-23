/**
 * Main Alpine.js application for Palworld Lens
 */
import {
    formatDate,
    formatFileSize,
    elementInfo,
    elementBackdrop,
    workSuitabilityDisplay,
    partnerSkillFor,
    baseLabel,
    partnerSkillHtml,
    mountLabel,
    getRankIcon,
    getRankFilter,
    getPassiveBackgroundClass,
    getPassiveTextClass,
    getPassiveDescriptionClass,
    formatUptime,
    buildPageList,
    formatRelativeTime,
    WORK_LEVEL_COLORS, searchContainers, sumItemCounts, searchElsewhere, activityGroups } from './utils.js';
import { api } from './services/api.js';
import { WatchService } from './services/watch.js';
import { loadPrefs, savePref, pref } from './prefs.js';
import { breedingState, BREED_MODES } from './breeding-state.js';

const prefs = loadPrefs();
const TABS = ['overview', 'players', 'pals', 'bases', 'tools', 'map'];
// Tools: helpers over the save, grouped under one tab (frontend/partials/tabs/tools-tab.html)
export const TOOLS = [
    { id: 'breeding', label: 'Breeding', title: 'What two pals make, which of yours can make a pal, and the route to one you cannot',
      icon: 'M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z' },
    { id: 'workers', label: 'Best workers', title: 'Best pal for a job: who has it, what you could catch, and what you could breed',
      icon: 'M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z' },
];
const TOOL_IDS = TOOLS.map(t => t.id);
// Accent themes: ids match the [data-theme] blocks in css/styles.css.
export const THEMES = [
    { id: 'sky', label: 'Sky', swatch: '#0ea5e9' },
    { id: 'blue', label: 'Blue', swatch: '#3b82f6' },
    { id: 'emerald', label: 'Emerald', swatch: '#10b981' },
    { id: 'violet', label: 'Violet', swatch: '#8b5cf6' },
    { id: 'rose', label: 'Rose', swatch: '#f43f5e' },
];
const SORT_COLUMNS = ['name', 'level', 'hp', 'hunger', 'sanity', 'owner', 'base', 'attack', 'defense'];

export function app() {
    return {
        // Land on the last tab used unless the URL names one (applyHash runs in init)
        currentTab: pref(prefs, 'lastTab', 'overview', TABS),
        tool: pref(prefs, 'lastTool', 'breeding', TOOL_IDS),   // which tool the Tools tab shows
        // Set by findOnMap(): where the map was opened from, so it can offer a way back
        // ({label, tab, tool?, pal?, route?}); cleared when you leave the map any other way.
        mapReturn: null,
        saveInfo: { loaded: false },
        // Reference data from /api/game-data: elements, work types, conditions, map layers.
        // Every element/work id the API sends is resolved through this.
        gameData: { elements: {}, work_types: {}, conditions: {}, map_layers: {} },
        baseNames: { names: {}, writable: false },   // custom base names (/api/base-names)
        baseRename: { id: null, value: '', busy: false, error: '' },
        players: [],
        pals: [],
        guilds: [],
        bases: [],
        baseContainers: null,
        activity: null,           // /api/activity: {bases: {id: BaseActivity}, guilds: {id: GuildActivity}, as_of_ticks}
        storageSearch: '',        // Storage sub-tab: filter this base's chests by item, see where else it is
        loading: false,
        error: null,
        palSearch: '',
        currentPage: 1,
        pageSize: pref(prefs, 'pageSize', 10, [10, 25, 50, 100]),
        sortColumn: pref(prefs, 'sortColumn', 'level', SORT_COLUMNS),
        sortDirection: pref(prefs, 'sortDirection', 'desc', ['asc', 'desc']),
        // Bases tab sub-tab and page size (shared with the Bases partial)
        baseTab: pref(prefs, 'baseTab', 'pals', ['pals', 'food', 'storage', 'activity']),
        basePalPageSize: pref(prefs, 'basePalPageSize', 10, [10, 25, 50]),
        // Filter state
        filterElement: '',
        filterWorkType: '',
        filterPassiveSkill: '',
        filterOwner: '',
        // Best workers tool ("Best <work> on the server"): Tools tab, also reached from the Pals tab's work filter
        workers: null,              // last /api/workers payload
        workersLoading: false,
        workersType: '',            // work type showing (its own picker; seeded from the Pals filter the first time)
        workersMaxLevel: 0,         // "spawns at or under this level" -- the reader's own call; seeded from a player's level
        workersOwner: '',           // whose pals count as breeding stock ('' = everyone); the "I am" preset
        _workersRequest: 0,
        // Base navigation state (shared with the Bases tab and deep links)
        selectedGuildId: null,
        selectedBaseId: null,
        // Ticks once a minute so "Updated 3m ago" stays honest
        now: Date.now(),
        // Set when the URL names a pal to open once data has loaded
        pendingPalId: null,
        hashSyncing: false,
        // Watch service state
        watchService: null,
        // Settings modal: device-local preferences (head.html applies them before first paint)
        showSettings: false,
        themes: THEMES,
        theme: pref(prefs, 'theme', 'sky', THEMES.map(t => t.id)),
        reduceMotion: pref(prefs, 'reduceMotion', false),
        autoWatchActive: false,
        autoWatchAllowed: true,
        watchToggling: false,
        remoteMode: false,
        remotePollInterval: null,
        remoteProtocol: null,
        remoteUser: null,
        remoteHost: null,
        lastRefreshTime: 0,
        refreshCooldown: 30000, // Only refresh if page was hidden for 30+ seconds
        // Breeding tab (js/breeding-state.js): species list, pickers, results
        ...breedingState(),
        
        async init() {
            // Initialize watch service
            this.watchService = new WatchService();
            
            // Set up callbacks for watch service
            this.watchService.onUpdate = (data) => this.updateFromSSE(data);
            this.watchService.onError = (error) => { this.error = error; };
            
            // Reference data (element/work names, icons, colours) is needed on
            // EVERY data path: the manual load below, and the SSE init event
            // when auto-watch is already running on the backend (production).
            // Fetch it once here so neither path can render ids.
            await this.loadGameData();

            // Check auto-watch status from backend
            await this.checkWatchStatus();

            console.log('🔍 Init state:', { 
                autoWatchAllowed: this.autoWatchAllowed, 
                autoWatchActive: this.autoWatchActive 
            });
            
            // If auto-watch is already active on backend, connect to it
            if (this.autoWatchActive) {
                console.log('📡 Auto-watch already active on backend, connecting SSE...');
                this.watchService.connect();
            }
            // If allowed but not active, respect the backend state (don't auto-start)
            // User must manually enable it via the toggle
            else {
                console.log('📂 Loading data manually (auto-watch not active on backend)');
                this.loadAllData();
            }
            
            // Reset to page 1 when search changes
            this.$watch('palSearch', () => {
                this.currentPage = 1;
            });
            
            // Reset to page 1 when filters change
            this.$watch('filterElement', () => this.currentPage = 1);
            this.$watch('filterWorkType', () => this.currentPage = 1);
            this.$watch('pals', () => { if (this.workersActive) this.loadWorkers(this.workersType, true); });
            this.$watch('workersType', t => { if (this.workersActive && t) this.loadWorkers(t); });
            this.$watch('workersOwner', () => { if (this.workersActive) this.loadWorkers(this.workersType, true); });
            this.$watch('filterPassiveSkill', () => this.currentPage = 1);
            this.$watch('filterOwner', () => this.currentPage = 1);
            
            // Listen for page visibility changes (e.g., wake from sleep)
            this.setupVisibilityListener();

            // Keep relative timestamps fresh
            setInterval(() => { this.now = Date.now(); }, 60000);

            // URL hash carries tab + selection so refreshes and shared links land
            // on the same view. Read it once now, re-apply after data loads (ids
            // may not resolve until then), and write it whenever state changes.
            this.applyHash();
            window.addEventListener('hashchange', () => this.applyHash());
            ['currentTab', 'tool', 'selectedGuildId', 'selectedBaseId', 'palSearch', 'filterElement',
             'filterWorkType', 'filterPassiveSkill', 'filterOwner', 'workersType', 'workersMaxLevel', 'workersOwner'].forEach(key => {
                this.$watch(key, () => this.writeHash());
            });
            // Leaving the map by any route other than its own "back" button forgets where it came from
            this.$watch('currentTab', t => { if (t !== 'map') this.mapReturn = null; });

            // Remember the settings people expect to stick between visits.
            [['currentTab', 'lastTab'], ['tool', 'lastTool'], ['pageSize', 'pageSize'], ['sortColumn', 'sortColumn'],
             ['sortDirection', 'sortDirection'], ['baseTab', 'baseTab'], ['basePalPageSize', 'basePalPageSize'],
             ['theme', 'theme'], ['reduceMotion', 'reduceMotion']]
                .forEach(([key, name]) => this.$watch(key, v => savePref(name, v)));
            this.applyTheme(this.theme);
            this.applyReduceMotion();

            // Bases tab: always have a guild and a base selected when data allows it.
            this.$watch('guilds', () => this.ensureBaseSelection());
            this.$watch('pals', () => this.ensureBaseSelection());
            this.$watch('selectedGuildId', () => this.ensureBaseSelection());

            // Tools: each loads what it needs the first time it shows (or when a deep
            // link / the pal modal lands there); owned-pal matches follow the pal list.
            this.$watch('currentTab', () => this.onToolShown());
            this.$watch('tool', () => this.onToolShown());
            this.onToolShown();
            this.$watch('pals', () => { this.breedInvalidateOwned(); this.loadBreedingRoute(); });
            this.$watch('breedOwner', () => { this.breedInvalidateOwned(); this.loadBreedingRoute(); this.writeHash(); });
            ['breedMode', 'breedA', 'breedB', 'breedChild'].forEach(key => {
                this.$watch(key, () => { this.runBreeding(); this.writeHash(); });
            });
            // applyHash() above ran before these watchers existed, so a deep link
            // such as #breeding?mode=child&a=X&b=Y needs one explicit lookup.
            this.runBreeding();
        },

        // `icon` is a heroicons outline path; the phone tab bar and tool tabs draw it.
        get tabs() {
            return [
                { id: 'overview', label: 'Overview', count: null,
                  icon: 'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z' },
                { id: 'players', label: 'Players', count: this.players.length,
                  icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z' },
                { id: 'pals', label: 'Pals', count: this.pals.length,
                  icon: 'M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
                { id: 'bases', label: 'Bases', count: this.basePals.reduce((n, g) => n + g.bases.length, 0),
                  icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
                { id: 'map', label: 'Map', count: null,
                  icon: 'M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7' },
                // Tools (tool: true) render after a divider: helpers over the save, not views of it
                { id: 'tools', label: 'Tools', count: null, tool: true, title: 'Tools: breeding calculator, best workers',
                  icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' }
            ];
        },
        get tools() { return TOOLS; },
        /** True while the Best workers tool is on screen. */
        get workersActive() { return this.currentTab === 'tools' && this.tool === 'workers'; },
        /** Switch to a tool (Tools tab + pill). */
        goToTool(id) {
            if (!TOOL_IDS.includes(id)) return;
            this.tool = id;
            this.currentTab = 'tools';
            this.jumpToTop();
        },
        /** Land a tab switch at the top. Instant on purpose: a smooth scroll gets cancelled on
         *  phones when the new tab lays itself out (the map does), leaving the page half-way
         *  down. Done again after the swap because the old tab's height is what was scrolled. */
        jumpToTop() {
            window.scrollTo({ top: 0 });
            this.$nextTick(() => window.scrollTo({ top: 0 }));
        },
        onToolShown() {
            if (this.currentTab !== 'tools') return;
            if (this.tool === 'breeding') this.ensureBreedingSpecies();
            if (this.tool === 'workers') {
                if (!this.workersType) this.workersType = this.workersDefaultType();
                this.loadWorkers(this.workersType);
            }
        },

        // ---- URL hash state -------------------------------------------------

        applyHash() {
            const raw = window.location.hash.replace(/^#\/?/, '');
            if (!raw) return;
            const [path, query = ''] = raw.split('?');
            let [tab, sub] = path.split('/');
            if (tab === 'breeding') { tab = 'tools'; sub = 'breeding'; }   // pre-Tools links keep working
            const params = new URLSearchParams(query);
            this.hashSyncing = true;
            try {
                if (TABS.includes(tab)) this.currentTab = tab;
                if (tab === 'tools' && TOOL_IDS.includes(sub)) this.tool = sub;
                if (params.has('guild')) this.selectedGuildId = params.get('guild');
                if (params.has('base')) this.selectedBaseId = params.get('base');
                if (tab === 'pals') {
                    this.palSearch = params.get('q') || '';
                    this.filterElement = params.get('element') || '';
                    this.filterWorkType = params.get('work') || '';
                    this.filterPassiveSkill = params.get('passive') || '';
                    this.filterOwner = params.get('owner') || '';
                }
                if (tab === 'tools' && this.tool === 'breeding') {
                    const mode = params.get('mode');
                    if (BREED_MODES.includes(mode)) this.breedMode = mode;
                    if (params.has('a')) this.breedA = params.get('a');
                    if (params.has('b')) this.breedB = params.get('b');
                    if (params.has('child')) this.breedChild = params.get('child');
                    this.breedOwner = params.get('owner') || '';
                }
                if (tab === 'tools' && this.tool === 'workers') {
                    if (params.has('job')) this.workersType = params.get('job');
                    if (params.has('level')) this.workersMaxLevel = parseInt(params.get('level'), 10) || 0;
                    this.workersOwner = params.get('owner') || '';
                }
                if (params.has('pal')) this.openPalById(params.get('pal'));
            } finally {
                this.hashSyncing = false;
            }
        },

        writeHash() {
            if (this.hashSyncing) return;
            const params = new URLSearchParams();
            if (this.currentTab === 'bases') {
                if (this.selectedGuildId) params.set('guild', this.selectedGuildId);
                if (this.selectedBaseId) params.set('base', this.selectedBaseId);
            }
            if (this.currentTab === 'pals') {
                if (this.palSearch) params.set('q', this.palSearch);
                if (this.filterElement) params.set('element', this.filterElement);
                if (this.filterWorkType) params.set('work', this.filterWorkType);
                if (this.filterPassiveSkill) params.set('passive', this.filterPassiveSkill);
                if (this.filterOwner) params.set('owner', this.filterOwner);
            }
            if (this.currentTab === 'tools' && this.tool === 'breeding') {
                params.set('mode', this.breedMode);
                if (this.breedOwner) params.set('owner', this.breedOwner);
                if (this.breedMode === 'child') {
                    if (this.breedA) params.set('a', this.breedA);
                    if (this.breedB) params.set('b', this.breedB);
                } else if (this.breedChild) {
                    params.set('child', this.breedChild);
                }
            }
            if (this.currentTab === 'tools' && this.tool === 'workers') {
                if (this.workersType) params.set('job', this.workersType);
                if (this.workersMaxLevel) params.set('level', this.workersMaxLevel);
                if (this.workersOwner) params.set('owner', this.workersOwner);
            }
            const qs = params.toString();
            const next = '#' + this.currentTab + (this.currentTab === 'tools' ? '/' + this.tool : '') + (qs ? '?' + qs : '');
            if (window.location.hash !== next) history.replaceState(null, '', next);
        },

        // ---- Cross-tab navigation -------------------------------------------

        /** Open the Pals tab filtered to one owner (player name). */
        viewPalsOf(owner) {
            this.clearFilters();
            this.filterOwner = owner || '';
            this.currentTab = 'pals';
            window.scrollTo({ top: 0, behavior: 'smooth' });
        },

        /** Open the map with this species' wild spawn zones lit.
         *  `from` ({label, tab, tool?, pal?, route?}) is where the reader came from; the map
         *  shows it as a "Back to ..." button so a look at the map is a round trip, not a reset. */
        findOnMap(speciesId, name, from = null) {
            this.currentTab = 'map';
            this.mapReturn = from;
            this.jumpToTop();
            this.$nextTick(() => window.dispatchEvent(new CustomEvent('show-pal-spawns', {
                detail: { species: speciesId, name },
            })));
        },
        /** The map's "Back to ..." button: return to whatever opened the map, as it was. */
        mapReturnGo() {
            const r = this.mapReturn;
            if (!r) return;
            this.mapReturn = null;
            if (r.tool) this.goToTool(r.tool);
            else if (r.tab) { this.currentTab = r.tab; this.jumpToTop(); }
            if (r.pal) this.openPalById(r.pal);
            if (r.route) this.$nextTick(() => this.breedShowRoute());
        },

        /** Open the Bases tab on a specific base. */
        goToBase(guildId, baseId) {
            this.selectedGuildId = guildId || null;
            this.selectedBaseId = baseId || null;
            this.currentTab = 'bases';
            window.scrollTo({ top: 0, behavior: 'smooth' });
        },

        /** Open the pal modal for a pal by instance id (used by deep links). */
        openPalById(instanceId) {
            const pal = this.pals.find(p => p.instance_id === instanceId);
            if (pal) {
                this.pendingPalId = null;
                window.dispatchEvent(new CustomEvent('open-pal-modal', { detail: pal }));
            } else {
                this.pendingPalId = instanceId;
            }
        },

        get currentBaseIndex() {
            const guild = this.basePals.find(g => g.guild_id === this.selectedGuildId);
            return guild ? guild.bases.findIndex(b => b.base_id === this.selectedBaseId) : -1;
        },
        get hasPrevBase() {
            return this.currentBaseIndex > 0;
        },
        get hasNextBase() {
            const guild = this.basePals.find(g => g.guild_id === this.selectedGuildId);
            return !!guild && this.currentBaseIndex >= 0 && this.currentBaseIndex < guild.bases.length - 1;
        },
        navigateToPrevBase() {
            const guild = this.basePals.find(g => g.guild_id === this.selectedGuildId);
            if (guild && this.hasPrevBase) {
                this.selectedBaseId = guild.bases[this.currentBaseIndex - 1].base_id;
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        },
        navigateToNextBase() {
            const guild = this.basePals.find(g => g.guild_id === this.selectedGuildId);
            if (guild && this.hasNextBase) {
                this.selectedBaseId = guild.bases[this.currentBaseIndex + 1].base_id;
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        },

        /** Keep guild/base selection valid; pick the first of each when nothing is chosen. */
        ensureBaseSelection() {
            const guilds = this.basePals;
            if (guilds.length === 0) return;
            let guild = guilds.find(g => g.guild_id === this.selectedGuildId);
            if (!guild) {
                guild = guilds[0];
                this.selectedGuildId = guild.guild_id;
            }
            if (!guild.bases.some(b => b.base_id === this.selectedBaseId)) {
                this.selectedBaseId = guild.bases.length ? guild.bases[0].base_id : null;
            }
        },

        /** Base pals with an active condition, for the Overview attention list. */
        get unhealthyBasePals() {
            return this.pals
                .filter(p => p.base_id && p.condition_display)
                .sort((a, b) => (a.base_name || '').localeCompare(b.base_name || '') || (a.level || 0) - (b.level || 0));
        },

        /** Players ordered by most recent activity. */
        get playersByActivity() {
            return [...this.players].sort((a, b) => {
                const ta = a.last_online ? Date.parse(a.last_online) : 0;
                const tb = b.last_online ? Date.parse(b.last_online) : 0;
                return tb - ta;
            });
        },
        
        setupVisibilityListener() {
            let hiddenTime = 0;
            
            document.addEventListener('visibilitychange', () => {
                if (document.visibilityState === 'hidden') {
                    // Record when page was hidden
                    hiddenTime = Date.now();
                } else if (document.visibilityState === 'visible') {
                    const timeHidden = Date.now() - hiddenTime;
                    const timeSinceLastRefresh = Date.now() - this.lastRefreshTime;
                    
                    // Only act if page was hidden for a significant time (30+ seconds)
                    // This prevents unnecessary refreshes on quick tab switches
                    if (timeHidden < this.refreshCooldown) {
                        console.log(`👀 Page visible (hidden for ${Math.round(timeHidden/1000)}s, skipping refresh)`);
                        return;
                    }
                    
                    console.log(`👀 Page visible after ${Math.round(timeHidden/1000)}s, checking connection...`);
                    
                    // If auto-watch is active and SSE is dead or errored, reconnect
                    if (this.autoWatchActive && !this.watchService.isConnected()) {
                        console.log('🔄 SSE disconnected, reconnecting...');
                        this.watchService.reconnect();
                    } 
                    // If not using auto-watch and enough time has passed, refresh data
                    else if (!this.autoWatchActive && timeSinceLastRefresh >= this.refreshCooldown) {
                        console.log('🔄 Refreshing data...');
                        this.loadAllData(true);
                    }
                }
            });
        },
        
        async checkWatchStatus() {
            try {
                const data = await this.watchService.checkStatus();
                this.remoteMode = data.remote_mode || false;
                this.remotePollInterval = data.remote_config?.poll_interval || null;
                this.remoteProtocol = data.remote_config?.protocol || null;
                this.remoteUser = data.remote_config?.user || null;
                this.remoteHost = data.remote_config?.host || null;
                
                // Auto-watch/polling is active?
                this.autoWatchActive = data.active;
                
                // Toggle is allowed based on backend's 'allowed' flag
                // (ENABLE_AUTO_WATCH for local, REMOTE_POLL_INTERVAL > 0 for remote)
                this.autoWatchAllowed = data.allowed;
                
                console.log('👀 Watch status:', data);
            } catch (err) {
                console.error('Failed to check watch status:', err);
                this.autoWatchAllowed = false;
            }
        },
        
        /** Sets the accent: flips `data-theme` on <html> so every accent-* utility retints. */
        applyTheme(id) {
            if (!THEMES.some(t => t.id === id)) id = 'sky';
            this.theme = id;
            document.documentElement.setAttribute('data-theme', id);
        },

        toggleReduceMotion() {
            this.reduceMotion = !this.reduceMotion;
            this.applyReduceMotion();
        },

        applyReduceMotion() {
            document.documentElement.classList.toggle('reduce-motion', !!this.reduceMotion);
        },

        async toggleAutoWatch() {
            if (!this.autoWatchAllowed) {
                return; // Can't toggle if not allowed
            }
            
            this.watchToggling = true;
            
            try {
                if (this.autoWatchActive) {
                    const data = await this.watchService.stop();
                    this.autoWatchActive = data.active;
                } else {
                    const data = await this.watchService.start();
                    this.autoWatchActive = data.active;
                }
            } catch (err) {
                console.error('Failed to toggle auto-watch:', err);
                this.error = err.message || 'Failed to toggle auto-watch';
            } finally {
                this.watchToggling = false;
            }
        },
        
        updateFromSSE(data) {
            this.saveInfo = data.info;
            if (data.base_names) this.baseNames = data.base_names;   // else the REST load owns it
            this.players = data.players || [];
            this.pals = data.pals || [];
            this.guilds = data.guilds || [];
            this.bases = data.bases || [];
            this.baseContainers = data.base_containers || null;
            if (data.activity) this.activity = data.activity;
            this.loading = false;
            this.error = null;
            this.afterDataLoaded();
            console.log('✅ Data updated from SSE, last_updated:', this.saveInfo.last_updated);
        },

        async loadGameData() {
            try {
                this.gameData = await api.getGameData();
            } catch (err) {
                console.error('Failed to load game reference data:', err);
            }
        },

        afterDataLoaded() {
            this.ensureBaseSelection();
            if (this.pendingPalId) this.openPalById(this.pendingPalId);
            this.writeHash();
        },
        
        async loadAllData(silent = false) {
            if (!silent) {
                this.loading = true;
            }
            
            try {
                const data = await api.loadAll();
                
                this.saveInfo = data.saveInfo;
                if (data.gameData) this.gameData = data.gameData;
                
                if (data.baseNames) this.baseNames = data.baseNames;
                if (this.saveInfo.loaded) {
                    this.players = data.players;
                    this.pals = data.pals;
                    this.guilds = data.guilds;
                    this.baseContainers = data.baseContainers;
                    if (data.activity) this.activity = data.activity;
                    this.error = null;
                    this.afterDataLoaded();
                }
                
                // Track last successful refresh time
                this.lastRefreshTime = Date.now();
            } catch (err) {
                this.error = err.message || 'Failed to load data';
                console.error('Error loading data:', err);
            } finally {
                this.loading = false;
            }
        },
        
        async reloadSave() {
            this.loading = true;
            try {
                const data = await api.reloadSave();
                
                if (data.success) {
                    await this.loadAllData();
                } else {
                    this.error = 'Failed to reload save';
                }
            } catch (err) {
                this.error = err.message || 'Failed to reload save';
            } finally {
                this.loading = false;
            }
        },
        
        getPlayerName(uid) {
            const player = this.players.find(p => p.uid === uid);
            return player ? player.player_name : null;
        },
        
        get basePals() {
            // Organize pals that are at bases into guild -> bases -> pals structure
            const basesPals = this.pals.filter(p => p.base_id);
            
            // Group by guild_id
            const guildMap = {};
            
            // First, populate guildMap with all guilds and their bases from guild data
            for (const guild of this.guilds) {
                guildMap[guild.guild_id] = {
                    guild_id: guild.guild_id,
                    guild_name: guild.guild_name,
                    bases: {}
                };
                
                // Add all bases from base_locations (even if they have no pals)
                if (guild.base_locations && Array.isArray(guild.base_locations)) {
                    for (const baseInfo of guild.base_locations) {
                        guildMap[guild.guild_id].bases[baseInfo.base_id] = {
                            base_id: baseInfo.base_id,
                            base_name: baseInfo.base_name,
                            number: baseInfo.number,
                            place: baseInfo.place,
                            x: baseInfo.x,
                            y: baseInfo.y,
                            pals: []
                        };
                    }
                }
            }
            
            // Now add pals to their respective bases
            for (const pal of basesPals) {
                // Ensure guild exists (fallback)
                if (!guildMap[pal.guild_id]) {
                    const guild = this.guilds.find(g => g.guild_id === pal.guild_id);
                    guildMap[pal.guild_id] = {
                        guild_id: pal.guild_id,
                        guild_name: guild ? guild.guild_name : 'Unnamed Guild',
                        bases: {}
                    };
                }
                
                // Ensure base exists (fallback if not in base_locations)
                if (!guildMap[pal.guild_id].bases[pal.base_id]) {
                    guildMap[pal.guild_id].bases[pal.base_id] = {
                        base_id: pal.base_id,
                        base_name: pal.base_name,
                        place: pal.base_place,
                        pals: []
                    };
                }
                
                guildMap[pal.guild_id].bases[pal.base_id].pals.push(pal);
            }
            
            // Convert to array format expected by template and sort bases by name
            return Object.values(guildMap).map(guild => ({
                ...guild,
                // The game's own per-guild number keeps the order stable whatever a base is called
                bases: Object.values(guild.bases).sort((a, b) =>
                    (a.number || 0) - (b.number || 0) || (a.base_name || '').localeCompare(b.base_name || ''))
            }));
        },
        
        getGuildName(guildId) {
            if (!guildId) return 'Unnamed Guild';
            
            // Look up guild name in guilds array
            const guild = this.guilds.find(g => g.guild_id === guildId);
            return guild ? guild.guild_name : 'Unnamed Guild';
        },
        
        // Reference-data lookups (ids -> display), bound to this.gameData
        elementName(id) { return elementInfo(this.gameData, id).name; },
        elementIcon(id) { return `/img/${elementInfo(this.gameData, id).icon}.webp`; },
        elementIconWhite(id) { return `/img/${elementInfo(this.gameData, id).icon_white}.webp`; },
        elementColor(id) { return elementInfo(this.gameData, id).color; },
        palHeaderBackdrop(ids) { return elementBackdrop(this.gameData, ids); },
        workTypeName(id) { return (this.gameData.work_types[id] || {}).name || id; },
        workDisplay(pal) { return workSuitabilityDisplay(this.gameData, pal); },
        partnerSkill(pal) { return partnerSkillFor(this.gameData, pal); },
        partnerSkillHtml(text) { return partnerSkillHtml(this.gameData, text); },
        mountLabel,
        workTypeIcon(id) { return `/img/${(this.gameData.work_types[id] || {}).icon || 'unknown'}.webp`; },

        /** Every work type the game data knows, for the modal's picker. */
        workersTypeList() {
            return Object.entries(this.gameData.work_types || {})
                .map(([id, w]) => ({ id, name: w.name || id }))
                .sort((a, b) => a.name.localeCompare(b.name));
        },
        /** The job to show when none was ever picked: the Pals filter, else Kindling (the game's first slot). */
        workersDefaultType() {
            const known = this.workersTypeList().map(t => t.id);
            if (this.filterWorkType && known.includes(this.filterWorkType)) return this.filterWorkType;
            return known.includes('EmitFlame') ? 'EmitFlame' : (known[0] || '');
        },
        /** Open Best workers on a job. With none given it stays on the job last looked at. */
        openWorkers(type) {
            this.workersType = type || this.workersType || this.workersDefaultType();
            this.goToTool('workers');
        },
        workersCatchOnMap(speciesId, name) {
            this.findOnMap(speciesId, name, { label: 'Back to Best workers', tool: 'workers' });
        },
        /** "I am <player>": their level for the catch list, their pals as breeding stock. Tap again for everyone. */
        workersPickPlayer(p) {
            this.workersMaxLevel = p.level;
            this.workersOwner = this.workersOwner === p.name ? '' : p.name;
        },
        /** Breedable species worth listing: at least as good as the best the server owns. */
        workersBreedList() {
            const all = (this.workers && this.workers.breedable) || [];
            const best = (this.workers && this.workers.best_owned_level) || 0;
            return all.filter(b => b.work_level >= best);
        },
        /** A breedable row: open the route to it, for the same breeder, over this tool. */
        workersBreedRoute(speciesId) {
            this.ensureBreedingSpecies();
            this.breedOwner = this.workersOwner;
            this.breedMode = 'parents';
            this.breedChild = speciesId;
            this.breedShowRoute();
        },
        /** Level presets: one per player, highest first. The filtered owner (if any) is the default. */
        workersPlayers() { return (this.workers && this.workers.players) || []; },
        workersSeedLevel() {
            const ps = this.workersPlayers();
            if (!ps.length) return 50;
            const who = this.workersOwner || this.filterOwner;
            const mine = who && ps.find(p => p.name === who);
            return (mine || ps[0]).level;
        },
        /** Catchable species that spawn at or under the chosen level, best job level first, then easiest. */
        workersCatchList() {
            const all = (this.workers && this.workers.catchable) || [];
            return all.filter(c => c.spawn_level <= this.workersMaxLevel);
        },
        /** How many of those beat (or match) the best the server already owns. */
        workersUpgradeCount() {
            const best = (this.workers && this.workers.best_owned_level) || 0;
            return this.workersCatchList().filter(c => c.work_level >= best).length;
        },
        workersNextUp() {
            // First species just out of reach -- "raise the level to N and X becomes possible"
            const all = (this.workers && this.workers.catchable) || [];
            const best = (this.workers && this.workers.best_owned_level) || 0;
            const beyond = all.filter(c => c.spawn_level > this.workersMaxLevel && c.work_level >= Math.max(best, 1));
            beyond.sort((a, b) => a.spawn_level - b.spawn_level || b.work_level - a.work_level);
            return beyond[0] || null;
        },

        /** Fetch the best-owned list and every catchable species for one work type. */
        async loadWorkers(type, force = false) {
            if (!type) { this.workers = null; this.workersLoading = false; return; }
            if (!force && this.workers && this.workers.work_type === type && (this.workers.owner || '') === (this.workersOwner || '') && !this.workersLoading) return;
            const req = ++this._workersRequest;
            this.workersLoading = true;
            try {
                const data = await api.getWorkers(type, this.workersOwner);
                if (req !== this._workersRequest) return;   // a newer pick won
                this.workers = data;
                if (!this.workersMaxLevel) this.workersMaxLevel = this.workersSeedLevel();
            } catch (e) {
                if (req !== this._workersRequest) return;
                console.error('Failed to load workers', e);
                this.workers = null;
            } finally {
                if (req === this._workersRequest) this.workersLoading = false;
            }
        },
        /** "Envy 34 · Franky 31 · Ricky 28" -- every player's level, so each reader can judge their own margin. */
        workersPlayersLine() {
            const ps = (this.workers && this.workers.players) || [];
            return ps.map(p => `${p.name} ${p.level}`).join(' · ');
        },
        workersOpenPal(instanceId) {
            const pal = this.pals.find(p => p.instance_id === instanceId);
            if (pal) window.dispatchEvent(new CustomEvent('open-pal-modal', { detail: pal }));
        },
        workLevelColor(level) { return WORK_LEVEL_COLORS[Math.min(level, 8)] || '#9ca3af'; },

        // --- Guild chest (1.0): one shared container per guild -------------------
        baseLabel,
        /** Custom name for a base if one is stored, else ''. */
        customBaseName(baseId) { return (this.baseNames.names || {})[baseId] || ''; },
        startBaseRename(base) {
            this.baseRename = { id: base.base_id, value: this.customBaseName(base.base_id) || '', busy: false, error: '' };
            this.$nextTick(() => { const el = document.getElementById('base-rename-input'); if (el) { el.focus(); el.select(); } });
        },
        cancelBaseRename() { this.baseRename = { id: null, value: '', busy: false, error: '' }; },
        /** Save the name being edited (blank = back to "Base N"), then re-pull the data so every surface agrees. */
        async saveBaseRename(name = this.baseRename.value) {
            const id = this.baseRename.id;
            if (!id || this.baseRename.busy) return;
            this.baseRename.busy = true;
            this.baseRename.error = '';
            try {
                const res = await api.setBaseName(id, name);
                this.baseNames = { names: res.names, writable: res.writable };
                await this.loadAllData(true);
                this.cancelBaseRename();
            } catch (err) {
                this.baseRename.busy = false;
                this.baseRename.error = err.message || 'Could not rename the base';
            }
        },
        // Storage sub-tab search. Non-food containers at the selected base, cut down to the
        // matching items when a query is set; blank query = everything, five items per card.
        get storageQuery() { return (this.storageSearch || '').trim(); },
        storageContainersAt(baseId) {
            const all = (this.baseContainers?.containers?.[baseId] || []).filter(c => c.container_type !== 'food_bowl' && c.items && c.items.length > 0);
            return searchContainers(all, this.storageQuery);
        },
        /** Items to list on a chest card: every match while searching, else the first five. */
        storageCardItems(container) {
            return this.storageQuery ? container.items : (container.items || []).slice(0, 5);
        },
        get storageMatchTotal() { return sumItemCounts(this.storageContainersAt(this.selectedBaseId)); },
        /** Distinct items the search hits at this base, counts summed across chests, biggest first. */
        get storageMatchedItems() {
            const acc = new Map();
            for (const c of this.storageContainersAt(this.selectedBaseId)) {
                for (const i of c.items || []) {
                    const e = acc.get(i.item_id);
                    if (e) e.count += i.count || 0; else acc.set(i.item_id, { ...i });
                }
            }
            return [...acc.values()].sort((a, b) => b.count - a.count);
        },
        /** An "also at" chip: show that base (and its guild, so the pills above follow) without losing the search. */
        storageGoToBase(baseId) {
            const g = this.guilds.find(g => (g.base_locations || []).some(b => b.base_id === baseId));
            if (g) this.selectedGuildId = g.guild_id;
            this.selectedBaseId = baseId;
        },
        /** Other bases of the guild that owns the current base: the search sweeps your chests, not the neighbours'. */
        get storageElsewhere() {
            const guild = this.guilds.find(g => (g.base_locations || []).some(b => b.base_id === this.selectedBaseId));
            const onlyBases = new Set((guild?.base_locations || []).map(b => b.base_id));
            const ownerOf = () => (guild ? this.baseOwner(guild.guild_id) : '');
            return searchElsewhere(this.baseContainers?.containers, this.selectedBaseId, this.storageQuery, { ownerOf, onlyBases });
        },
        // Activity sub-tab: what the base is doing, as of the last save.
        activityFor(baseId) { return (this.activity?.bases || {})[baseId] || null; },
        /** The guild-level part (expeditions, lab) for the guild that owns `baseId`. */
        guildActivityFor(baseId) {
            const guild = this.guilds.find(g => (g.base_locations || []).some(b => b.base_id === baseId));
            return guild ? ((this.activity?.guilds || {})[guild.guild_id] || null) : null;
        },
        /** Cards grouped the way the eye wants them: attention first, then working, idle last. */
        activityGroups(act) { return activityGroups(act ? act.jobs : []); },
        /** Sub-tab badge: jobs that want a look (something to collect, nobody on it, out of materials). */
        activityAttention(baseId) { const a = this.activityFor(baseId); return a ? a.ready + a.stuck : 0; },
        /** "Base 3 and Base 5" / "Base 1, Base 3 and Base 4" from a list of {base_name}. */
        baseNamesSentence(bases) {
            const names = (bases || []).map(b => b.base_name);
            if (names.length <= 1) return names[0] || '';
            return names.slice(0, -1).join(', ') + ' and ' + names[names.length - 1];
        },
        /** Short contents line for the overview row: "Wood, Stone, Pal Fluid +11 more". */
        guildChestContents(g) {
            const items = g?.container?.items || [];
            if (!items.length) return 'Empty';
            const top = items.slice(0, 3).map(i => i.item_name || i.item_id);
            const more = items.length - top.length;
            return top.join(', ') + (more > 0 ? ` +${more} more` : '');
        },
        
        // "Envy" for a base owned by Envy's guild; falls back to the guild name.
        // Bases can't be named in-game, so "Base 2" alone doesn't say whose it is.
        baseOwner(guildId) {
            const guild = this.guilds.find(g => g.guild_id === guildId);
            return guild ? (guild.admin_player_name || guild.guild_name) : '';
        },
        
        // Use utility functions from utils.js
        formatDate,
        formatFileSize,
        getRankIcon,
        getRankFilter,
        getPassiveBackgroundClass,
        getPassiveTextClass,
        getPassiveDescriptionClass,
        
        sortBy(column) {
            if (this.sortColumn === column) {
                // Toggle direction if clicking same column
                this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                // New column, default to descending for numbers, ascending for text
                this.sortColumn = column;
                this.sortDirection = ['level', 'hp', 'hunger', 'sanity'].includes(column) ? 'desc' : 'asc';
            }
            // Reset to first page when sorting
            this.currentPage = 1;
        },
        
        get filteredPals() {
            let filtered = this.pals;
            
            // Apply search filter
            if (this.palSearch) {
                const search = this.palSearch.toLowerCase();
                filtered = filtered.filter(pal => 
                    (pal.name && pal.name.toLowerCase().includes(search)) ||
                    (pal.nickname && pal.nickname.toLowerCase().includes(search)) ||
                    (pal.character_id && pal.character_id.toLowerCase().includes(search))
                );
            }
            
            // Apply element filter
            if (this.filterElement) {
                filtered = filtered.filter(pal => 
                    pal.element_types && pal.element_types.includes(this.filterElement)
                );
            }
            
            // Apply work type filter
            if (this.filterWorkType) {
                filtered = filtered.filter(pal => 
                    pal.work_suitability && 
                    this.filterWorkType in pal.work_suitability &&
                    pal.work_suitability[this.filterWorkType] > 0
                );
            }
            
            // Apply passive skill filter
            if (this.filterPassiveSkill) {
                filtered = filtered.filter(pal => 
                    pal.passive_skills && pal.passive_skills.some(skill => 
                        skill.skill_id === this.filterPassiveSkill
                    )
                );
            }
            
            // Apply owner filter
            if (this.filterOwner) {
                filtered = filtered.filter(pal => 
                    pal.owner_uid === this.filterOwner
                );
            }
            
            // Apply sorting
            const sorted = [...filtered].sort((a, b) => {
                let aVal, bVal;
                
                switch(this.sortColumn) {
                    case 'name':
                        aVal = (a.nickname || a.display_name || '').toLowerCase();
                        bVal = (b.nickname || b.display_name || '').toLowerCase();
                        break;
                    case 'level':
                        aVal = a.level || 0;
                        bVal = b.level || 0;
                        break;
                    case 'hp':
                        aVal = a.hp || 0;
                        bVal = b.hp || 0;
                        break;
                    case 'hunger':
                        aVal = a.hunger || 0;
                        bVal = b.hunger || 0;
                        break;
                    case 'sanity':
                        aVal = a.sanity || 0;
                        bVal = b.sanity || 0;
                        break;
                    case 'owner':
                        // owner_uid is actually the player name, not a UID
                        aVal = (a.owner_uid || 'No Owner').toLowerCase();
                        bVal = (b.owner_uid || 'No Owner').toLowerCase();
                        break;
                    case 'base':
                        aVal = (a.base_name || 'None').toLowerCase();
                        bVal = (b.base_name || 'None').toLowerCase();
                        break;
                    case 'attack':
                        aVal = a.calculated_attack || 0;
                        bVal = b.calculated_attack || 0;
                        break;
                    case 'defense':
                        aVal = a.calculated_defense || 0;
                        bVal = b.calculated_defense || 0;
                        break;
                    default:
                        return 0;
                }
                
                if (aVal < bVal) return this.sortDirection === 'asc' ? -1 : 1;
                if (aVal > bVal) return this.sortDirection === 'asc' ? 1 : -1;
                return 0;
            });
            
            return sorted;
        },
        
        get paginatedPals() {
            const start = (this.currentPage - 1) * this.pageSize;
            const end = start + this.pageSize;
            return this.filteredPals.slice(start, end);
        },
        
        get totalPages() {
            return Math.ceil(this.filteredPals.length / this.pageSize);
        },
        
        changePage(page) {
            if (page >= 1 && page <= this.totalPages) {
                this.currentPage = page;
            }
        },
        
        changePageSize(size) {
            this.pageSize = size;
            this.currentPage = 1; // Reset to first page when changing page size
        },
        
        get pageNumbers() {
            return buildPageList(this.totalPages, this.currentPage);
        },
        
        // Filter options getters - get unique values from all pals
        // Filter options: [{key, name}] for every element / work type any pal has
        get availableElements() {
            if (!Array.isArray(this.pals)) return [];
            const keys = new Set();
            this.pals.forEach(pal => (pal.element_types || []).forEach(e => keys.add(e)));
            return Array.from(keys)
                .map(key => ({ key, name: this.elementName(key) }))
                .sort((a, b) => a.name.localeCompare(b.name));
        },
        
        get availableWorkTypes() {
            if (!Array.isArray(this.pals)) return [];
            const keys = new Set();
            this.pals.forEach(pal => {
                Object.entries(pal.work_suitability || {}).forEach(([key, level]) => { if (level > 0) keys.add(key); });
            });
            return Array.from(keys)
                .map(key => ({ key, name: this.workTypeName(key) }))
                .sort((a, b) => a.name.localeCompare(b.name));
        },
        
        get availablePassiveSkills() {
            if (!Array.isArray(this.pals)) return [];
            const skills = new Map(); // Map of skill_id -> {skill_id, name}
            this.pals.forEach(pal => {
                if (pal.passive_skills && pal.passive_skills.length > 0) {
                    pal.passive_skills.forEach(skill => {
                        if (skill.skill_id && !skills.has(skill.skill_id)) {
                            skills.set(skill.skill_id, {
                                skill_id: skill.skill_id,
                                name: skill.name || skill.skill_id
                            });
                        }
                    });
                }
            });
            return Array.from(skills.values()).sort((a, b) => a.name.localeCompare(b.name));
        },
        
        get availableOwners() {
            if (!Array.isArray(this.pals)) return [];
            const owners = new Set();
            this.pals.forEach(pal => {
                if (pal.owner_uid) {
                    owners.add(pal.owner_uid);
                }
            });
            return Array.from(owners).sort();
        },
        
        // Clear all filters
        clearFilters() {
            this.palSearch = '';
            this.filterElement = '';
            this.filterWorkType = '';
            this.filterPassiveSkill = '';
            this.filterOwner = '';
        },
        
        // Get count of active filters
        get activeFilterCount() {
            let count = 0;
            if (this.palSearch) count++;
            if (this.filterElement) count++;
            if (this.filterWorkType) count++;
            if (this.filterPassiveSkill) count++;
            if (this.filterOwner) count++;
            return count;
        },
        
        // Helper to get condition badge color class
        getConditionClass(condition) {
            // Tinted chips, never solid blocks. Sickness = violet, injury / hunger = danger.
            if (!condition || !condition.type) {
                return 'bg-ok-500/15 text-ok-300 border border-ok-500/30';
            }
            return condition.type === 'sickness'
                ? 'bg-violet-500/15 text-violet-200 border border-violet-500/30'
                : 'bg-danger-500/15 text-danger-300 border border-danger-500/30';
        },
        
        // Helper to get all bases with coordinates for map
        getAllBasesWithCoords() {
            const bases = [];
            const guilds = this.guilds || [];
            
            for (const guild of guilds) {
                if (guild.base_locations) {
                    for (const base of guild.base_locations) {
                        // Only include bases with coordinates
                        if (base.x && base.y) {
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
        },
        
        
        // Expose utility functions for use in HTML
        formatUptime,
        formatRelativeTime
    }
}