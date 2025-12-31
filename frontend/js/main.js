/**
 * Main entry point for Vite bundling
 * Imports Alpine.js and all modules, registers components properly
 */

// Import Alpine.js
import Alpine from 'alpinejs';

// Expose Alpine globally BEFORE any DOM parsing
window.Alpine = Alpine;

// Import utility functions
import * as utils from './utils.js';

// Import Alpine.js components
import { app } from './app.js';
import { leafletMapComponent } from './map-leaflet.js';
import { serverInfoModal } from './components/serverInfoModal.js';
import { containerModal } from './components/containerModal.js';
import { palModal } from './components/palModal.js';

// Register components with Alpine using proper API
Alpine.data('app', app);
Alpine.data('leafletMapComponent', leafletMapComponent);
Alpine.data('serverInfoModal', serverInfoModal);
Alpine.data('containerModal', containerModal);
Alpine.data('palModal', palModal);

// Expose utility functions globally (required by Alpine.js inline expressions in x-text, x-bind, etc.)
Object.assign(window, utils);

// Start Alpine (will automatically process x-data elements)
Alpine.start();

console.log('✅ Palworld Lens loaded with Alpine.js');
