/**
 * Main Alpine.js application for Palworld Lens
 */
import {
    formatDate,
    formatFileSize,
    getElementIcon,
    getElementIconWhite,
    getElementColor,
    getPalHeaderGradient,
    getRankIcon,
    getRankFilter,
    getPassiveBackgroundClass,
    getPassiveTextClass,
    getPassiveDescriptionClass,
    formatUptime
} from './utils.js';
import { api } from './services/api.js';
import { WatchService } from './services/watch.js';

export function app() {
    return {
        currentTab: 'overview',
        saveInfo: { loaded: false },
        players: [],
        pals: [],
        guilds: [],
        bases: [],
        baseContainers: null,
        loading: false,
        error: null,
        palSearch: '',
        currentPage: 1,
        pageSize: 10,
        sortColumn: 'level',
        sortDirection: 'desc',
        // Filter state
        filterElement: '',
        filterWorkType: '',
        filterPassiveSkill: '',
        filterOwner: '',
        // Base navigation state
        selectedGuildId: null,
        selectedBaseId: null,
        hasPrevBase: false,
        hasNextBase: false,
        // Watch service state
        watchService: null,
        autoWatchActive: false,
        autoWatchAllowed: true,
        watchToggling: false,
        lastRefreshTime: 0,
        refreshCooldown: 30000, // Only refresh if page was hidden for 30+ seconds
        
        async init() {
            // Initialize watch service
            this.watchService = new WatchService();
            
            // Set up callbacks for watch service
            this.watchService.onUpdate = (data) => this.updateFromSSE(data);
            this.watchService.onError = (error) => { this.error = error; };
            
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
            
            // Listen for page visibility changes (e.g., wake from sleep)
            this.setupVisibilityListener();
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
                this.autoWatchActive = data.active;
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
            console.log('✅ Data updated from SSE, last_updated:', this.saveInfo.last_updated);
        },
        
        async loadAllData(silent = false) {
            if (!silent) {
                this.loading = true;
            }
            
            try {
                const data = await api.loadAll();
                
                this.saveInfo = data.saveInfo;
                
                if (this.saveInfo.loaded) {
                    this.players = data.players;
                    this.pals = data.pals;
                    this.guilds = data.guilds;
                    this.baseContainers = data.baseContainers;
                    this.error = null;
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
        
        // Use utility functions from utils.js
        formatDate,
        formatFileSize,
        getElementIcon,
        getElementIconWhite,
        getElementColor,
        getPalHeaderGradient,
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
            const pages = [];
            const total = this.totalPages;
            const current = this.currentPage;
            
            // Always show first page
            pages.push(1);
            
            // Show pages around current page
            for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
                if (!pages.includes(i)) {
                    pages.push(i);
                }
            }
            
            // Always show last page
            if (total > 1 && !pages.includes(total)) {
                pages.push(total);
            }
            
            return pages;
        },
        
        // Filter options getters - get unique values from all pals
        get availableElements() {
            if (!Array.isArray(this.pals)) return [];
            const elements = new Set();
            this.pals.forEach(pal => {
                if (pal.element_types && pal.element_types.length > 0) {
                    pal.element_types.forEach(element => elements.add(element));
                }
            });
            return Array.from(elements).sort();
        },
        
        get availableWorkTypes() {
            if (!Array.isArray(this.pals)) return [];
            const workTypes = new Map(); // Map of key -> display name
            this.pals.forEach(pal => {
                if (pal.work_suitability && pal.work_suitability_names) {
                    Object.entries(pal.work_suitability).forEach(([key, level]) => {
                        // Only include work types with level > 0
                        if (level > 0 && !workTypes.has(key)) {
                            workTypes.set(key, pal.work_suitability_names[key] || key);
                        }
                    });
                }
            });
            // Return array of {key, name} objects sorted by name
            return Array.from(workTypes.entries())
                .map(([key, name]) => ({ key, name }))
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
        },
        
        // Get count of active filters
        get activeFilterCount() {
            let count = 0;
            if (this.palSearch) count++;
            if (this.filterElement) count++;
            if (this.filterWorkType) count++;
            if (this.filterPassiveSkill) count++;
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
        formatUptime
    }
}