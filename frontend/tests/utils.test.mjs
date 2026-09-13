// node --test 'frontend/tests/*.test.mjs'   (no test framework needed)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
    MAP_LAYERS, layerForCoords, saveToLngLat, elementInfo, elementBackdrop, hexAlpha, shadeHex,
    workSuitabilityDisplay, buildPageList, palIconSrc,
} from '../js/utils.js';

const gameData = {
    elements: { Leaf: { name: 'Grass', color: '#2e8b57', icon: 'grass', icon_white: 'grass_white' } },
    work_types: { EmitFlame: { name: 'Kindling', icon: 't_icon_research_palwork_00_0' } },
};

test('map layers come from data/json/map_layers.json', () => {
    assert.deepEqual(Object.keys(MAP_LAYERS), ['MainMap', 'Tree']);
    assert.equal(MAP_LAYERS.MainMap.tiles, '/img/tiles');
    assert.equal(MAP_LAYERS.Tree.tiles, '/img/tiles_tree');
});

test('layerForCoords picks the layer whose bounds contain the point', () => {
    assert.equal(layerForCoords(0, 0), 'MainMap');
    assert.equal(layerForCoords(500000, -600000), 'Tree');
    assert.equal(layerForCoords(9e9, 9e9), 'MainMap');   // out of both: default
});

test('saveToLngLat maps the layer corners to the Mercator square', () => {
    const m = MAP_LAYERS.MainMap;
    const [lng0, lat0] = saveToLngLat(m.maxX, m.minY);   // top-left of the image
    assert.ok(Math.abs(lng0 + 180) < 1e-9 && lat0 > 85);
    const [lng1, lat1] = saveToLngLat(m.minX, m.maxY);   // bottom-right
    assert.ok(Math.abs(lng1 - 180) < 1e-9 && lat1 < -85);
    const [lngC, latC] = saveToLngLat((m.minX + m.maxX) / 2, (m.minY + m.maxY) / 2);
    assert.ok(Math.abs(lngC) < 1e-9 && Math.abs(latC) < 1e-9);
});

test('elementInfo resolves ids and falls back safely', () => {
    assert.equal(elementInfo(gameData, 'Leaf').name, 'Grass');
    assert.deepEqual(elementInfo(gameData, 'Mystery'), { color: '#6b7280', icon: 'neutral', icon_white: 'neutral_white', name: 'Mystery' });
    assert.equal(elementInfo(null, undefined).name, 'Unknown');
});

test('shadeHex, hexAlpha and elementBackdrop', () => {
    assert.equal(shadeHex('#2e8b57', 0), '#2e8b57');
    assert.equal(shadeHex('#000000', 50), '#808080');
    assert.equal(shadeHex('nope', 10), 'nope');
    assert.equal(hexAlpha('#2e8b57', 0.5), '#2e8b5780');
    assert.equal(hexAlpha('#2e8b57', 2), '#2e8b57ff');
    assert.equal(hexAlpha('nope', 0.5), 'nope');
    // First element glows from the top-left, second from the bottom-right, over the card surface
    assert.match(elementBackdrop(gameData, ['Leaf']), /^radial-gradient\(.*#2e8b5773, transparent 60%\), radial-gradient\(.*#2e8b574d.*\), #111827$/);
    assert.match(elementBackdrop(gameData, []), /^radial-gradient\(.*var\(--accent-500\).*\), #111827$/);
});

test('workSuitabilityDisplay only lists levels > 0 with names and icons', () => {
    const out = workSuitabilityDisplay(gameData, { work_suitability: { EmitFlame: 2, Mining: 0, Unknown: 1 } });
    assert.deepEqual(out, [
        { type: 'EmitFlame', name: 'Kindling', level: 2, icon: 't_icon_research_palwork_00_0', color: '#22c55e' },
        { type: 'Unknown', name: 'Unknown', level: 1, icon: 'unknown', color: '#9ca3af' },
    ]);
});

test('buildPageList elides long ranges', () => {
    assert.deepEqual(buildPageList(3, 1), [1, 2, 3]);
    const long = buildPageList(20, 10);
    assert.equal(long[0], 1); assert.equal(long[long.length - 1], 20); assert.ok(long.includes('…'));
});

test('palIconSrc uses the first candidate', () => {
    assert.equal(palIconSrc({ image_candidates: ['anubis'] }), '/img/t_anubis_icon_normal.webp');
    assert.equal(palIconSrc(null), '/img/t_unknown_icon_normal.webp');
});
