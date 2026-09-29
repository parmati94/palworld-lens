/**
 * Landmark layers on the world map: the static markers from
 * data/json/map_objects.json (/api/map-objects), one toggle each, in the order
 * the layer panel lists them. Pure -- the map component draws from this table
 * and the panel renders it; the tooltip copy is tested.
 *
 * Icons are the game's own compass sprites, tinted by
 * scripts/datagen/compose_map_icons.py. Alpha pals draw their own marker (the
 * species portrait), so they carry no sprite here.
 */
export const LANDMARKS = [
    { kind: 'alpha_pal',   label: 'Alpha Pals',  pref: 'mapAlphaPals',   on: true,  z: 500, icon: '/img/alpha.webp', panelIcon: 'w-5 h-5' },
    { kind: 'tower',       label: 'Towers',      pref: 'mapTowers',      on: true,  z: 350, icon: '/img/t_icon_compass_tower_red.webp',        size: 'w-11 h-11' },
    { kind: 'watchtower',  label: 'Watchtowers', pref: 'mapWatchtowers', on: true,  z: 150, icon: '/img/t_icon_compass_ftunlockmap_cyan.webp', size: 'w-10 h-10' },
    { kind: 'fast_travel', label: 'Fast Travel', pref: 'mapFastTravel',  on: false, z: 120, icon: '/img/t_icon_compass_fttower_cyan.webp',     size: 'w-10 h-10' },
    { kind: 'dungeon',     label: 'Dungeons',    pref: 'mapDungeons',    on: false, z: 100, icon: '/img/t_icon_compass_dungeon_violet.webp',   size: 'w-8 h-8' },
];

export const LANDMARK_BY_KIND = Object.fromEntries(LANDMARKS.map(l => [l.kind, l]));

/** The dungeon portal's dressing, from the pak's marker class name. */
const BIOMES = {
    Grass1: 'Grassland', Forest: 'Forest', Desert: 'Desert', Snow: 'Snow', Volcano: 'Volcano',
    Sakura: 'Sakurajima', Skyland: 'Sky island', Viking: 'Feybreak', Viking_B: 'Feybreak', Viking_C: 'Feybreak',
    Yakushima: 'Yakushima',
};

export function biomeLabel(biome) {
    if (!biome) return '';
    return BIOMES[biome] || String(biome).replace(/_/g, ' ');
}

/**
 * Hover card copy for a landmark: {title, sub, note}. `sub` is the one fact
 * worth a second line (the tower's boss, the dungeon's biome); `note` is the
 * kind, in small print.
 */
export function landmarkTip(obj) {
    const name = obj.localized_name || '';
    switch (obj.type) {
        case 'tower':
            return { title: name || 'Syndicate tower', sub: obj.pal_name ? `Boss: ${obj.pal_name}` : '', note: 'Syndicate tower' };
        case 'watchtower':
            return { title: name || 'Watchtower', sub: 'Reveals the map around it', note: 'Watchtower · fast travel' };
        case 'fast_travel':
            return { title: name || 'Fast travel point', sub: '', note: 'Fast travel point' };
        case 'dungeon':
            return { title: 'Dungeon', sub: biomeLabel(obj.biome), note: 'Dungeon entrance' };
        default:
            return { title: name || obj.type || '', sub: '', note: '' };
    }
}
