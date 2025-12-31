/**
 * Utility functions for Palworld Lens
 */

/**
 * Format a date string to localized format
 */
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString();
}

/**
 * Format bytes to human-readable file size
 */
function formatFileSize(bytes) {
    if (!bytes) return 'N/A';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 B';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 10) / 10 + ' ' + sizes[i];
}

/**
 * Get element icon filename
 */
function getElementIcon(element) {
    const iconMap = {
        'Fire': 'fire.webp',
        'Water': 'water.webp',
        'Grass': 'grass.webp',
        'Electric': 'electric.webp',
        'Ice': 'ice.webp',
        'Ground': 'ground.webp',
        'Dark': 'dark.webp',
        'Dragon': 'dragon.webp',
        'Normal': 'neutral.webp'
    };
    return iconMap[element] || 'neutral.webp';
}

/**
 * Get white element icon filename for active skills
 */
function getElementIconWhite(element) {
    const iconMap = {
        'Fire': 'fire_white.webp',
        'Water': 'water_white.webp',
        'Grass': 'grass_white.webp',
        'Electric': 'electric_white.webp',
        'Ice': 'ice_white.webp',
        'Ground': 'ground_white.webp',
        'Dark': 'dark_white.webp',
        'Dragon': 'dragon_white.webp',
        'Normal': 'neutral_white.webp'
    };
    return iconMap[element] || 'neutral_white.webp';
}

/**
 * Get element color for active skill badges
 */
function getElementColor(element) {
    const colorMap = {
        'Fire': '#ef4444',      // red-500
        'Water': '#3b82f6',     // blue-500
        'Grass': '#22c55e',     // green-500
        'Electric': '#eab308',  // yellow-500
        'Ice': '#06b6d4',       // cyan-500
        'Ground': '#a16207',    // yellow-700
        'Dark': '#7c3aed',      // violet-600
        'Dragon': '#9333ea',    // purple-600
        'Normal': '#6b7280'     // gray-500
    };
    return colorMap[element] || '#6b7280';
}

/**
 * Generate element-themed gradient for pal header
 */
function getPalHeaderGradient(elements) {
    if (!elements || elements.length === 0) {
        return 'linear-gradient(135deg, #3b82f6, #8b5cf6, #3b82f6)';
    }
    
    const elementColors = {
        'Fire': ['#dc2626', '#f97316', '#dc2626'],      // red-600 to orange-500
        'Water': ['#0284c7', '#06b6d4', '#0284c7'],     // sky-600 to cyan-500
        'Grass': ['#16a34a', '#22c55e', '#16a34a'],     // green-600 to green-500
        'Electric': ['#ca8a04', '#eab308', '#ca8a04'],  // yellow-600 to yellow-500
        'Ice': ['#0891b2', '#67e8f9', '#0891b2'],       // cyan-600 to cyan-300
        'Ground': ['#92400e', '#d97706', '#92400e'],    // yellow-800 to amber-600
        'Dark': ['#5b21b6', '#7c3aed', '#5b21b6'],      // violet-800 to violet-600
        'Dragon': ['#7c3aed', '#a855f7', '#7c3aed'],    // violet-600 to purple-500
        'Normal': ['#4b5563', '#6b7280', '#4b5563']     // gray-600 to gray-500
    };
    
    const primaryElement = elements[0];
    const colors = elementColors[primaryElement] || elementColors['Normal'];
    
    if (elements.length > 1) {
        // Dual element - blend both colors
        const secondaryElement = elements[1];
        const secondaryColors = elementColors[secondaryElement] || elementColors['Normal'];
        return `linear-gradient(135deg, ${colors[0]}, ${colors[1]}, ${secondaryColors[1]}, ${colors[2]})`;
    }
    
    return `linear-gradient(135deg, ${colors[0]}, ${colors[1]}, ${colors[2]})`;
}

/**
 * Get rank icon filename for passive skills
 */
function getRankIcon(rank) {
    if (rank < 0) {
        // Use negative rank icons: rank_-1.webp, rank_-2.webp, rank_-3.webp
        return `img/rank_${rank}.webp`;
    } else {
        // Use rank_1 through rank_4, ignore rank_0
        const iconRank = Math.max(1, Math.min(rank, 4));
        return `img/rank_${iconRank}.webp`;
    }
}

/**
 * Get rank color filter for passive skills
 */
function getRankFilter(rank) {
    if (rank < 0) {
        // Negative ranks: red
        return 'brightness(0) saturate(100%) invert(27%) sepia(51%) saturate(2878%) hue-rotate(346deg) brightness(104%) contrast(97%)';
    } else if (rank === 1) {
        // Rank 1: grey
        return 'brightness(0) saturate(100%) invert(75%) sepia(0%) saturate(0%) hue-rotate(0deg) brightness(92%) contrast(88%)';
    } else if (rank === 2 || rank === 3) {
        // Rank 2-3: gold
        return 'brightness(0) saturate(100%) invert(77%) sepia(72%) saturate(441%) hue-rotate(360deg) brightness(102%) contrast(104%)';
    } else if (rank >= 4) {
        // Rank 4+: purple
        return 'brightness(0) saturate(100%) invert(32%) sepia(90%) saturate(2476%) hue-rotate(262deg) brightness(91%) contrast(101%)';
    }
    return 'none';
}

/**
 * Get passive skill background class based on rank
 */
function getPassiveBackgroundClass(rank) {
    if (rank < 0) {
        // Negative: red gradient with downward stripes
        return 'passive-bg-negative';
    } else if (rank === 1) {
        // Rank 1: muted grey (default)
        return 'bg-gray-700/50 hover:bg-gray-700/60';
    } else if (rank === 2 || rank === 3) {
        // Rank 2-3: gold gradient with diagonal stripes
        return 'passive-bg-gold';
    } else if (rank >= 4) {
        // Rank 4: cyan-purple gradient with pattern
        return 'passive-bg-legendary';
    }
    return 'bg-gray-700/50 hover:bg-gray-700/60';
}

/**
 * Get passive skill text color based on rank
 */
function getPassiveTextClass(rank) {
    if (rank >= 2 && rank <= 3) {
        // Gold background needs dark text
        return 'text-gray-900';
    }
    // All others use white text
    return 'text-gray-200';
}

/**
 * Get passive skill description color based on rank
 */
function getPassiveDescriptionClass(rank) {
    if (rank >= 2 && rank <= 3) {
        // Gold background needs darker description
        return 'text-gray-700';
    }
    // All others use lighter description
    return 'text-gray-400';
}

/**
 * Convert Palworld save coordinates to Leaflet map coordinates
 * SYSTEM: 0-256 Virtual World (Standard Leaflet Scale)
 * [0,0] is Top-Left. [-256, 256] is Bottom-Right.
 */
function saveToMapCoords(saveX, saveY) {
    const scaleDivisor = 630; 
    const manualOffsetX = 275;
    const manualOffsetY = 242;

    const gameX = (saveY - 158000) / scaleDivisor;
    const gameY = (saveX + 123888) / scaleDivisor;
    
    // Virtual World Bounds (Game Units)
    const worldMin = -1150;
    const worldMax = 1150;
    const worldRange = worldMax - worldMin; 

    // 1. Normalize to 0.0 -> 1.0
    const normX = ((gameX + manualOffsetX) - worldMin) / worldRange;
    const normY = ((gameY + manualOffsetY) - worldMin) / worldRange;

    // 2. Scale to Leaflet 256 Unit System
    const leafletX = normX * 256;
    
    // 3. Invert Y Axis for Mapping
    const leafletY = (1 - normY) * 256; 

    // Return [Lat, Lng]
    return [-leafletY, leafletX];
}

/**
 * Fetch with automatic retry logic
 */
async function fetchWithRetry(url, options = {}, retries = 3, delay = 1000) {
    options = { ...options, credentials: 'same-origin' };
    
    for (let i = 0; i < retries; i++) {
        try {
            const response = await fetch(url, options);
            
            // If unauthorized, redirect to login immediately (don't retry)
            if (response.status === 401) {
                console.log('🔒 Got 401 Unauthorized, redirecting to login...');
                window.location.replace('/login.html');
                return new Promise(() => {});
            }
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response;
        } catch (err) {
            console.warn(`Fetch attempt ${i + 1}/${retries} failed for ${url}:`, err.message);
            
            // If this is the last retry, throw the error
            if (i === retries - 1) {
                throw err;
            }
            
            // Wait before retrying with exponential backoff
            const waitTime = delay * (i + 1);
            console.log(`Retrying in ${waitTime}ms...`);
            await new Promise(resolve => setTimeout(resolve, waitTime));
        }
    }
}
