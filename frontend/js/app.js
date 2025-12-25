/**
 * Main Alpine.js application for Palworld Lens
 */
function app() {
    return {
        currentTab: 'overview',
        saveInfo: { loaded: false },
        players: [],
        pals: [],
        guilds: [],
        bases: [],
        loading: false,
        error: null,
        palSearch: '',
        currentPage: 1,
        pageSize: 10,
        sortColumn: 'level',
        sortDirection: 'desc',
        eventSource: null,
        autoWatchActive: false,
        autoWatchAllowed: true,
        watchToggling: false,
        reconnectAttempts: 0,
        maxReconnectAttempts: 5,
        reconnectDelay: 2000,
        lastRefreshTime: 0,
        refreshCooldown: 30000, // Only refresh if page was hidden for 30+ seconds
        
        async init() {
            // Check auto-watch status from backend
            await this.checkWatchStatus();
            
            console.log('🔍 Init state:', { 
                autoWatchAllowed: this.autoWatchAllowed, 
                autoWatchActive: this.autoWatchActive 
            });
            
            // If auto-watch is already active on backend, connect to it
            if (this.autoWatchActive) {
                console.log('📡 Auto-watch already active on backend, connecting SSE...');
                this.connectSSE();
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
                    if (this.autoWatchActive && this.eventSource && this.eventSource.readyState !== EventSource.OPEN) {
                        console.log('🔄 SSE disconnected, reconnecting...');
                        this.reconnectSSE();
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
                const res = await fetchWithRetry('/api/watch/status');
                const data = await res.json();
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
                    await this.stopAutoWatch();
                } else {
                    await this.startAutoWatch();
                }
            } catch (err) {
                console.error('Failed to toggle auto-watch:', err);
                this.error = err.message || 'Failed to toggle auto-watch';
            } finally {
                this.watchToggling = false;
            }
        },
        
        async startAutoWatch() {
            try {
                const res = await fetch('/api/watch/start', { method: 'POST' });
                if (!res.ok) {
                    const error = await res.json();
                    throw new Error(error.detail || 'Failed to start auto-watch');
                }
                const data = await res.json();
                this.autoWatchActive = data.active;
                
                // Save preference
                localStorage.setItem('autoWatchEnabled', 'true');
                
                // Connect SSE
                this.connectSSE();
                
                console.log('✅ Auto-watch started');
            } catch (err) {
                console.error('Failed to start auto-watch:', err);
                throw err;
            }
        },
        
        async stopAutoWatch() {
            try {
                const res = await fetch('/api/watch/stop', { method: 'POST' });
                const data = await res.json();
                this.autoWatchActive = data.active;
                
                // Save preference
                localStorage.setItem('autoWatchEnabled', 'false');
                
                // Close SSE connection
                if (this.eventSource) {
                    this.eventSource.close();
                    this.eventSource = null;
                }
                
                console.log('🛑 Auto-watch stopped');
            } catch (err) {
                console.error('Failed to stop auto-watch:', err);
                throw err;
            }
        },
        
        connectSSE() {
            if (!this.autoWatchActive) {
                console.log('Auto-watch not active, skipping SSE connection');
                return;
            }
            
            // Close existing connection if any
            if (this.eventSource) {
                this.eventSource.close();
                this.eventSource = null;
            }
            
            try {
                this.eventSource = new EventSource('/api/watch');
                
                this.eventSource.addEventListener('init', (event) => {
                    console.log('📡 SSE: Received initial data');
                    const data = JSON.parse(event.data);
                    this.updateFromSSE(data);
                    this.reconnectAttempts = 0; // Reset on successful connection
                });
                
                this.eventSource.addEventListener('update', (event) => {
                    console.log('🔄 SSE: Save updated!');
                    const data = JSON.parse(event.data);
                    this.updateFromSSE(data);
                    this.reconnectAttempts = 0; // Reset on successful message
                });
                
                this.eventSource.addEventListener('ping', () => {
                    // Keepalive ping, do nothing
                });
                
                this.eventSource.addEventListener('error', (event) => {
                    console.error('❌ SSE: Error event', event);
                    if (event.data) {
                        try {
                            const error = JSON.parse(event.data);
                            this.error = error.error;
                        } catch (e) {
                            console.error('Failed to parse SSE error', e);
                        }
                    }
                });
                
                this.eventSource.onerror = (error) => {
                    console.error('❌ SSE: Connection error', error);
                    
                    // If the connection is closing or closed, attempt to reconnect
                    if (this.eventSource && this.eventSource.readyState === EventSource.CLOSED) {
                        console.log('⚠️  SSE connection closed, will attempt to reconnect...');
                        this.eventSource = null;
                        this.scheduleReconnect();
                    }
                };
                
                console.log('✅ SSE: Connected to real-time updates');
            } catch (err) {
                console.error('Failed to connect SSE:', err);
                this.scheduleReconnect();
            }
        },
        
        scheduleReconnect() {
            if (!this.autoWatchActive) {
                console.log('Auto-watch not active, skipping reconnect');
                return;
            }
            
            if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                console.error('❌ Max reconnect attempts reached, falling back to manual data loading');
                this.loadAllData().catch(err => {
                    this.error = 'Failed to fetch data. Please try reloading the page.';
                });
                return;
            }
            
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * this.reconnectAttempts; // Exponential backoff
            console.log(`🔄 Scheduling SSE reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms...`);
            
            setTimeout(() => {
                console.log(`🔄 Attempting SSE reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
                this.connectSSE();
            }, delay);
        },
        
        reconnectSSE() {
            // Reset reconnect attempts and immediately try to reconnect
            this.reconnectAttempts = 0;
            console.log('🔄 Forcing SSE reconnection...');
            this.connectSSE();
        },
        
        updateFromSSE(data) {
            this.saveInfo = data.info;
            this.players = data.players || [];
            this.pals = data.pals || [];
            this.guilds = data.guilds || [];
            this.bases = data.bases || [];
            this.loading = false;
            this.error = null;
            console.log('✅ Data updated from SSE, last_updated:', this.saveInfo.last_updated);
        },
        
        startPolling() {
            // Fallback: Auto-reload every 30 seconds
            console.log('⏰ Starting fallback polling (30s interval)');
            setInterval(() => {
                this.loadAllData(true);
            }, 30000);
        },
        
        async loadAllData(silent = false) {
            if (!silent) {
                this.loading = true;
            }
            
            try {
                // Load save info with retry
                const infoRes = await fetchWithRetry('/api/info');
                this.saveInfo = await infoRes.json();
                
                if (this.saveInfo.loaded) {
                    // Load all data in parallel with retry
                    const [playersRes, palsRes, guildsRes] = await Promise.all([
                        fetchWithRetry('/api/players'),
                        fetchWithRetry('/api/pals'),
                        fetchWithRetry('/api/guilds')
                    ]);
                    
                    this.players = (await playersRes.json()).players;
                    this.pals = (await palsRes.json()).pals;
                    this.guilds = (await guildsRes.json()).guilds;
                    
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
                const res = await fetchWithRetry('/api/reload', { method: 'POST' });
                const data = await res.json();
                
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
            for (const pal of basesPals) {
                if (!guildMap[pal.guild_id]) {
                    const guild = this.guilds.find(g => g.guild_id === pal.guild_id);
                    guildMap[pal.guild_id] = {
                        guild_id: pal.guild_id,
                        guild_name: guild ? guild.guild_name : 'Unnamed Guild',
                        bases: {}
                    };
                }
                
                // Group by base_id within guild
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
        
        // Pal detail modal
        selectedPal: null,
        showPalModal: false,
        
        openPalModal(pal) {
            this.selectedPal = pal;
            this.showPalModal = true;
        },
        
        closePalModal() {
            this.showPalModal = false;
            setTimeout(() => this.selectedPal = null, 300);
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
        }
    }
}
