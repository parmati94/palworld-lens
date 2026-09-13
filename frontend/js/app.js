/**
 * Main Alpine.js application for Palworld Lens
 */
import {
    formatDate,
    formatFileSize,
    elementInfo,
    elementGradient,
    workSuitabilityDisplay,
    getRankIcon,
    getRankFilter,
    getPassiveBackgroundClass,
    getPassiveTextClass,
    getPassiveDescriptionClass,
    formatUptime,
    buildPageList,
    formatRelativeTime
} from './utils.js';
import { api } from './services/api.js';
import { WatchService } from './services/watch.js';
import { loadPrefs, savePref, pref } from './prefs.js';
import { breedingState, BREED_MODES } from './breeding-state.js';

const prefs = loadPrefs();
const TABS = ['overview', 'players', 'pals', 'bases', 'breeding', 'map'];
const SORT_COLUMNS = ['name', 'level', 'hp', 'hunger', 'sanity', 'owner', 'base', 'attack', 'defense'];

export function app() {
    return {
        // Land on the last tab used unless the URL names one (applyHash runs in init)
        currentTab: pref(prefs, 'lastTab', 'overview', TABS),
        saveInfo: { loaded: false },
        // Reference data from /api/game-data: elements, work types, conditions, map layers.
        // Every element/work id the API sends is resolved through this.
        gameData: { elements: {}, work_types: {}, conditions: {}, map_layers: {} },
        players: [],
        pals: [],
        guilds: [],
        bases: [],
        baseContainers: null,
        loading: false,
        error: null,
        palSearch: '',
        currentPage: 1,
        pageSize: pref(prefs, 'pageSize', 10, [10, 25, 50, 100]),
        sortColumn: pref(prefs, 'sortColumn', 'level', SORT_COLUMNS),
        sortDirection: pref(prefs, 'sortDirection', 'desc', ['asc', 'desc']),
        // Bases tab sub-tab and page size (shared with the Bases partial)
        baseTab: pref(prefs, 'baseTab', 'pals', ['pals', 'food', 'storage']),
        basePalPageSize: pref(prefs, 'basePalPageSize', 10, [10, 25, 50]),
        // Filter state
        filterElement: '',
        filterWorkType: '',
        filterPassiveSkill: '',
        filterOwner: '',
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
            ['currentTab', 'selectedGuildId', 'selectedBaseId', 'palSearch', 'filterElement',
             'filterWorkType', 'filterPassiveSkill', 'filterOwner'].forEach(key => {
                this.$watch(key, () => this.writeHash());
            });

            // Remember the settings people expect to stick between visits.
            [['currentTab', 'lastTab'], ['pageSize', 'pageSize'], ['sortColumn', 'sortColumn'],
             ['sortDirection', 'sortDirection'], ['baseTab', 'baseTab'], ['basePalPageSize', 'basePalPageSize']]
                .forEach(([key, name]) => this.$watch(key, v => savePref(name, v)));

            // Bases tab: always have a guild and a base selected when data allows it.
            this.$watch('guilds', () => this.ensureBaseSelection());
            this.$watch('pals', () => this.ensureBaseSelection());
            this.$watch('selectedGuildId', () => this.ensureBaseSelection());

            // Breeding: species list on first visit (or when a deep link / the pal
            // modal lands there); owned-pal matches follow the pal list.
            this.$watch('currentTab', t => { if (t === 'breeding') this.ensureBreedingSpecies(); });
            if (this.currentTab === 'breeding') this.ensureBreedingSpecies();
            this.$watch('pals', () => this.breedInvalidateOwned());
            this.$watch('breedOwner', () => { this.breedInvalidateOwned(); this.writeHash(); });
            ['breedMode', 'breedA', 'breedB', 'breedChild'].forEach(key => {
                this.$watch(key, () => { this.runBreeding(); this.writeHash(); });
            });
            // applyHash() above ran before these watchers existed, so a deep link
            // such as #breeding?mode=child&a=X&b=Y needs one explicit lookup.
            this.runBreeding();
        },

        get tabs() {
            return [
                { id: 'overview', label: 'Overview', count: null },
                { id: 'players', label: 'Players', count: this.players.length },
                { id: 'pals', label: 'Pals', count: this.pals.length },
                { id: 'bases', label: 'Bases', count: this.basePals.reduce((n, g) => n + g.bases.length, 0) },
                { id: 'map', label: 'Map', count: null },
                // Tools (tool: true) render after a divider: helpers over the save, not views of it
                { id: 'breeding', label: 'Breeding', count: null, tool: true, title: 'Breeding calculator: what two pals make, and which of yours can make a pal' }
            ];
        },

        // ---- URL hash state -------------------------------------------------

        applyHash() {
            const raw = window.location.hash.replace(/^#\/?/, '');
            if (!raw) return;
            const [tab, query = ''] = raw.split('?');
            const params = new URLSearchParams(query);
            this.hashSyncing = true;
            try {
                if (TABS.includes(tab)) this.currentTab = tab;
                if (params.has('guild')) this.selectedGuildId = params.get('guild');
                if (params.has('base')) this.selectedBaseId = params.get('base');
                if (tab === 'pals') {
                    this.palSearch = params.get('q') || '';
                    this.filterElement = params.get('element') || '';
                    this.filterWorkType = params.get('work') || '';
                    this.filterPassiveSkill = params.get('passive') || '';
                    this.filterOwner = params.get('owner') || '';
                }
                if (tab === 'breeding') {
                    const mode = params.get('mode');
                    if (BREED_MODES.includes(mode)) this.breedMode = mode;
                    if (params.has('a')) this.breedA = params.get('a');
                    if (params.has('b')) this.breedB = params.get('b');
                    if (params.has('child')) this.breedChild = params.get('child');
                    this.breedOwner = params.get('owner') || '';
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
            if (this.currentTab === 'breeding') {
                params.set('mode', this.breedMode);
                if (this.breedOwner) params.set('owner', this.breedOwner);
                if (this.breedMode === 'child') {
                    if (this.breedA) params.set('a', this.breedA);
                    if (this.breedB) params.set('b', this.breedB);
                } else if (this.breedChild) {
                    params.set('child', this.breedChild);
                }
            }
            const qs = params.toString();
            const next = '#' + this.currentTab + (qs ? '?' + qs : '');
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
            this.players = data.players || [];
            this.pals = data.pals || [];
            this.guilds = data.guilds || [];
            this.bases = data.bases || [];
            this.baseContainers = data.base_containers || null;
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
                
                if (this.saveInfo.loaded) {
                    this.players = data.players;
                    this.pals = data.pals;
                    this.guilds = data.guilds;
                    this.baseContainers = data.baseContainers;
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
                        pals: []
                    };
                }
                
                guildMap[pal.guild_id].bases[pal.base_id].pals.push(pal);
            }
            
            // Convert to array format expected by template and sort bases by name
            return Object.values(guildMap).map(guild => ({
                ...guild,
                bases: Object.values(guild.bases).sort((a, b) => {
                    // Extract number from "Base N" format for proper numeric sorting
                    const numA = parseInt(a.base_name.match(/\d+/)?.[0] || '0');
                    const numB = parseInt(b.base_name.match(/\d+/)?.[0] || '0');
                    return numA - numB;
                })
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
        palHeaderGradient(ids) { return elementGradient(this.gameData, ids); },
        workTypeName(id) { return (this.gameData.work_types[id] || {}).name || id; },
        workDisplay(pal) { return workSuitabilityDisplay(this.gameData, pal); },
        
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
            if (!condition || !condition.type) {
                return 'bg-green-600 text-white border border-green-500';
            }
            // Sickness = purple, Injury/Hunger = red
            return condition.type === 'sickness' 
                ? 'bg-purple-600 text-white border border-purple-500'
                : 'bg-red-600 text-white border border-red-500';
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