/**
 * SSE (Server-Sent Events) watch service for real-time updates
 */
import { api } from './api.js';

export class WatchService {
    constructor() {
        this.eventSource = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
        this.onUpdate = null; // Callback for data updates
        this.onError = null; // Callback for errors
        this.isActive = false;
    }

    /**
     * Check if watch is active on backend
     */
    async checkStatus() {
        const data = await api.getWatchStatus();
        this.isActive = data.active;
        return data;
    }

    /**
     * Start auto-watch and connect SSE
     */
    async start() {
        const data = await api.startWatch();
        this.isActive = data.active;
        localStorage.setItem('autoWatchEnabled', 'true');
        this.connect();
        console.log('✅ Auto-watch started');
        return data;
    }

    /**
     * Stop auto-watch and disconnect SSE
     */
    async stop() {
        const data = await api.stopWatch();
        this.isActive = data.active;
        localStorage.setItem('autoWatchEnabled', 'false');
        this.disconnect();
        console.log('🛑 Auto-watch stopped');
        return data;
    }

    /**
     * Connect to SSE endpoint
     */
    connect() {
        if (!this.isActive) {
            console.log('Auto-watch not active, skipping SSE connection');
            return;
        }

        // Close existing connection if any
        this.disconnect();

        try {
            this.eventSource = new EventSource('/api/watch');

            this.eventSource.addEventListener('init', (event) => {
                console.log('📡 SSE: Received initial data');
                const data = JSON.parse(event.data);
                this.reconnectAttempts = 0;
                if (this.onUpdate) {
                    this.onUpdate(data);
                }
            });

            this.eventSource.addEventListener('update', (event) => {
                console.log('🔄 SSE: Save updated!');
                const data = JSON.parse(event.data);
                this.reconnectAttempts = 0;
                if (this.onUpdate) {
                    this.onUpdate(data);
                }
            });

            this.eventSource.addEventListener('ping', () => {
                // Keepalive ping, do nothing
            });

            this.eventSource.addEventListener('error', (event) => {
                console.error('❌ SSE: Error event', event);
                if (event.data) {
                    try {
                        const error = JSON.parse(event.data);
                        if (this.onError) {
                            this.onError(error.error);
                        }
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
    }

    /**
     * Disconnect from SSE
     */
    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

    /**
     * Schedule a reconnection attempt
     */
    scheduleReconnect() {
        if (!this.isActive) {
            console.log('Auto-watch not active, skipping reconnect');
            return;
        }

        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('❌ Max reconnect attempts reached');
            if (this.onError) {
                this.onError('Failed to connect to real-time updates. Please refresh the page.');
            }
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * this.reconnectAttempts;
        console.log(`🔄 Scheduling SSE reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms...`);

        setTimeout(() => {
            console.log(`🔄 Attempting SSE reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            this.connect();
        }, delay);
    }

    /**
     * Force reconnect (reset attempts and reconnect immediately)
     */
    reconnect() {
        this.reconnectAttempts = 0;
        console.log('🔄 Forcing SSE reconnection...');
        this.connect();
    }

    /**
     * Check if SSE is connected
     */
    isConnected() {
        return this.eventSource && this.eventSource.readyState === EventSource.OPEN;
    }
}
