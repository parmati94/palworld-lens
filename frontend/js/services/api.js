/**
 * API service layer for all backend communication
 */
import { fetchWithRetry } from '../utils.js';

export const api = {
    /**
     * Get save file information
     */
    async getSaveInfo() {
        const res = await fetchWithRetry('/api/info');
        return await res.json();
    },

    /**
     * Get all players
     */
    async getPlayers() {
        const res = await fetchWithRetry('/api/players');
        const data = await res.json();
        return data.players;
    },

    /**
     * Get all pals
     */
    async getPals() {
        const res = await fetchWithRetry('/api/pals');
        const data = await res.json();
        return data.pals;
    },

    /**
     * Get all guilds
     */
    async getGuilds() {
        const res = await fetchWithRetry('/api/guilds');
        const data = await res.json();
        return data.guilds;
    },

    /**
     * Static reference data: elements, work types, conditions, map layers
     */
    async getGameData() {
        const res = await fetchWithRetry('/api/game-data');
        return await res.json();
    },

    /**
     * Wild spawner groups + searchable species list (data/json/spawns.json)
     */
    async getSpawns() {
        const res = await fetchWithRetry('/api/spawns');
        return await res.json();
    },

    /**
     * Breeding calculator (data/json/breeding.json via backend/common/breeding.py)
     */
    async getBreedingSpecies() {
        const res = await fetchWithRetry('/api/breeding/species');
        return await res.json();
    },
    async getBreedingChild(a, b) {
        const res = await fetchWithRetry(`/api/breeding/child?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
        return await res.json();
    },
    async getBreedingParents(child) {
        const res = await fetchWithRetry(`/api/breeding/parents?child=${encodeURIComponent(child)}`);
        return await res.json();
    },

    /**
     * Get base containers
     */
    async getBaseContainers() {
        const res = await fetchWithRetry('/api/base-containers');
        return await res.json();
    },

    /**
     * Load all data in parallel
     */
    async loadAll() {
        const [saveInfo, gameData, players, pals, guilds, baseContainers] = await Promise.all([
            this.getSaveInfo(),
            this.getGameData(),
            this.getPlayers(),
            this.getPals(),
            this.getGuilds(),
            this.getBaseContainers()
        ]);

        return {
            saveInfo,
            gameData,
            players,
            pals,
            guilds,
            baseContainers
        };
    },

    /**
     * Reload save file
     */
    async reloadSave() {
        const res = await fetchWithRetry('/api/reload', { method: 'POST' });
        return await res.json();
    },

    /**
     * Check auto-watch status
     */
    async getWatchStatus() {
        const res = await fetchWithRetry('/api/watch/status');
        return await res.json();
    },

    /**
     * Start auto-watch
     */
    async startWatch() {
        const res = await fetch('/api/watch/start', { method: 'POST' });
        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || 'Failed to start auto-watch');
        }
        return await res.json();
    },

    /**
     * Stop auto-watch
     */
    async stopWatch() {
        const res = await fetch('/api/watch/stop', { method: 'POST' });
        return await res.json();
    }
};
