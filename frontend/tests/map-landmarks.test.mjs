// node --test 'frontend/tests/*.test.mjs'
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { LANDMARKS, LANDMARK_BY_KIND, biomeLabel, landmarkTip } from '../js/map-landmarks.js';

test('every landmark kind has a pref, an icon and its own stacking order', () => {
    const kinds = LANDMARKS.map(l => l.kind);
    assert.deepEqual(kinds, ['alpha_pal', 'tower', 'watchtower', 'fast_travel', 'dungeon']);
    for (const l of LANDMARKS) {
        assert.ok(l.pref.startsWith('map'), l.kind);
        assert.ok(l.icon.startsWith('/img/'), l.kind);
        assert.equal(typeof l.on, 'boolean', l.kind);
    }
    const zs = LANDMARKS.map(l => l.z);
    assert.equal(new Set(zs).size, zs.length, 'z values collide');
    assert.ok(LANDMARK_BY_KIND.tower.z > LANDMARK_BY_KIND.watchtower.z, 'towers sit over the statues');
    // the busy layers start hidden; the landmarks a player navigates by start shown
    assert.equal(LANDMARK_BY_KIND.dungeon.on, false);
    assert.equal(LANDMARK_BY_KIND.fast_travel.on, false);
    assert.equal(LANDMARK_BY_KIND.tower.on, true);
    assert.equal(LANDMARK_BY_KIND.watchtower.on, true);
});

test('the tower card names the tower and its boss', () => {
    const t = landmarkTip({ type: 'tower', localized_name: 'Rayne Syndicate Tower', pal: 'GYM_ElecPanda', pal_name: 'Zoe & Grizzbolt' });
    assert.deepEqual(t, { title: 'Rayne Syndicate Tower', sub: 'Boss: Zoe & Grizzbolt', note: 'Syndicate tower' });
    assert.equal(landmarkTip({ type: 'tower', localized_name: 'X' }).sub, '', 'no boss name, no boss line');
});

test('watchtowers and statues say what they are', () => {
    assert.equal(landmarkTip({ type: 'watchtower', localized_name: 'Loess Plains Watchtower' }).note, 'Watchtower · fast travel');
    assert.equal(landmarkTip({ type: 'fast_travel', localized_name: 'Thawtide Cape' }).title, 'Thawtide Cape');
    assert.equal(landmarkTip({ type: 'fast_travel' }).title, 'Fast travel point');
});

test('dungeons read the biome off the portal class', () => {
    assert.deepEqual(landmarkTip({ type: 'dungeon', biome: 'Viking_B' }), { title: 'Dungeon', sub: 'Feybreak', note: 'Dungeon entrance' });
    assert.equal(landmarkTip({ type: 'dungeon' }).sub, '');
    assert.equal(biomeLabel('Grass1'), 'Grassland');
    assert.equal(biomeLabel('Some_New_Biome'), 'Some New Biome');
});
