import { formatUptime, fetchWithRetry } from '../utils.js';

export function serverInfoModal() {
    return {
        showServerInfo: false,
        serverInfo: null,
        serverInfoLoading: false,
        serverInfoError: null,
        serverInfoNotConfigured: false,
        serverInfoTab: 'overview',

        async show() {
            this.showServerInfo = true;
            await this.loadServerInfo();
        },

        hide() {
            this.showServerInfo = false;
        },

        async loadServerInfo() {
            this.serverInfoLoading = true;
            this.serverInfoError = null;
            this.serverInfoNotConfigured = false;
            this.serverInfo = null;
            
            try {
                const response = await fetchWithRetry('/api/rcon/status', {
                    credentials: 'same-origin'
                });
                
                const data = await response.json();
                
                // Check if there are any errors in the response
                if (data.errors && Object.keys(data.errors).length > 0) {
                    console.warn('Some RCON endpoints failed:', data.errors);
                }
                
                this.serverInfo = data;
            } catch (error) {
                console.error('Failed to load server info:', error);
                
                // Check if it's a 503 error (RCON not configured)
                if (error.message && error.message.includes('503')) {
                    this.serverInfoNotConfigured = true;
                } else {
                    this.serverInfoError = error.message || 'Failed to connect to server';
                }
            } finally {
                this.serverInfoLoading = false;
            }
        },

        formatUptime(seconds) {
            return formatUptime(seconds);
        },

        init() {
            this.$watch('showServerInfo', value => {
                if (value) {
                    document.body.style.overflow = 'hidden';
                } else {
                    document.body.style.overflow = '';
                }
            });

            // Listen for custom event to show modal
            window.addEventListener('show-server-info', () => {
                this.show();
            });
        }
    };
}
