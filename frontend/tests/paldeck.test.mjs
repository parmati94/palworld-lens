// node --test 'frontend/tests/*.test.mjs'
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
    spawnLabel, spawnTip, bonusOf, bonusPips, deckMatches, filterDeck, sortDeck, bonusSummary, expBar,
} from '../js/paldeck.js';

const row = (id, name, number, extra = {}) => ({ id, name, number, element_types: [], work_suitability: {}, owned: 0, spawn: null, ...extra });
const wild = (lo, hi, extra = {}) => ({ how: 'wild', min_level: lo, max_level: hi, night: false, alpha: false, groups: 2, ...extra });

const deck = [
    row('Sheepball', 'Lamball', '1', { element_types: ['Normal'], work_suitability: { Handcraft: 1 }, owned: 3, spawn: wild(1, 3) }),
    row('Kitsunebi', 'Foxparks', '5', { element_types: ['Fire'], work_suitability: { EmitFlame: 1 }, spawn: wild(2, 6, { night: true }) }),
    row('Kitsunebi_Ice', 'Foxcicle', '5B', { element_types: ['Ice'], spawn: { how: 'dungeon', min_level: 20, max_level: 25, night: false, alpha: false, groups: 1 } }),
    row('IceHorse', 'Frostallion', '200', { element_types: ['Ice'], owned: 19, spawn: { how: 'alpha', min_level: 60, max_level: 60, night: false, alpha: true, groups: 1 } }),
    row('JetDragon', 'Jetragon', '211', { element_types: ['Dragon'], owned: 1, drops: ['PalCrystal_Ex'], learns: ['EPalWazaID::BeamComet'] }),
];
deck[0].drops = ['Wool', 'Meat_SheepBall']; deck[0].learns = ['EPalWazaID::WindShot'];
deck[3].drops = ['IceOrgan', 'Diamond', 'PalCrystal_Ex']; deck[3].learns = ['EPalWazaID::AirCanon', 'EPalWazaID::IceMissile'];
const progress = { name: 'Envy', level: 72, bonus: { Sheepball: 5, Kitsunebi: 2, IceHorse: 5 }, caught: { Sheepball: 40, Kitsunebi: 2, IceHorse: 108 },
    bonus_index: 697, next_bonus_exp: 7384, exp_to_next_level: 512406, catches_to_next_level: 65, species_done: 2, bonus_left: 13 };

test('spawnLabel and spawnTip say how you get one', () => {
    assert.equal(spawnLabel(wild(1, 3)), 'Wild · Lv 1–3');
    assert.equal(spawnLabel({ how: 'alpha', min_level: 60, max_level: 60 }), 'Alpha · Lv 60');
    assert.equal(spawnLabel({ how: 'dungeon', min_level: 20, max_level: 25 }), 'Dungeons · Lv 20–25');
    assert.equal(spawnLabel(null), 'No wild spawn');
    assert.match(spawnTip(wild(2, 6, { night: true })), /2 field zones, at night only/);
    assert.match(spawnTip(null), /breeding/);
});

test('deckMatches searches name, id and number', () => {
    const r = deck[2];
    assert.ok(deckMatches(r, 'foxc') && deckMatches(r, 'kitsunebi_ice') && deckMatches(r, '#5B') && deckMatches(r, '5b') && deckMatches(r, ''));
    assert.ok(!deckMatches(r, '5'));   // the number must match whole, so "5" is not every 5x
});

test('filterDeck combines search, element, work, spawn kind and the missing overlay', () => {
    const ids = opts => filterDeck(deck, opts).map(r => r.id);
    assert.deepEqual(ids({ element: 'Ice' }), ['Kitsunebi_Ice', 'IceHorse']);
    assert.deepEqual(ids({ work: 'EmitFlame' }), ['Kitsunebi']);
    assert.deepEqual(ids({ how: 'catchable' }), ['Sheepball', 'Kitsunebi', 'IceHorse']);
    assert.deepEqual(ids({ how: 'alpha' }), ['IceHorse']);
    assert.deepEqual(ids({ how: 'none' }), ['JetDragon']);
    assert.deepEqual(ids({ progress, missingOnly: true }), ['Kitsunebi', 'Kitsunebi_Ice', 'JetDragon']);
    assert.deepEqual(ids({ progress, missingOnly: true, how: 'catchable' }), ['Kitsunebi']);
    assert.deepEqual(ids({ missingOnly: true }), deck.map(r => r.id), 'missing needs a player');
    assert.deepEqual(ids({ drop: 'PalCrystal_Ex' }), ['IceHorse', 'JetDragon']);
    assert.deepEqual(ids({ skill: 'EPalWazaID::AirCanon' }), ['IceHorse']);
    assert.deepEqual(ids({ drop: 'Wool', element: 'Ice' }), []);
});

test('sortDeck orders by name, spawn level, owned or fewest bonus catches', () => {
    const ids = (sort, p = null) => sortDeck(deck, sort, p).map(r => r.id);
    assert.deepEqual(ids('number'), deck.map(r => r.id));
    assert.deepEqual(ids('name'), ['Kitsunebi_Ice', 'Kitsunebi', 'IceHorse', 'JetDragon', 'Sheepball']);
    assert.deepEqual(ids('level'), ['Sheepball', 'Kitsunebi', 'Kitsunebi_Ice', 'IceHorse', 'JetDragon']);
    assert.deepEqual(ids('owned'), ['IceHorse', 'Sheepball', 'JetDragon', 'Kitsunebi_Ice', 'Kitsunebi']);
    // never caught first (lowest spawn level breaks ties), then partial, then maxed
    assert.deepEqual(ids('missing', progress), ['Kitsunebi_Ice', 'JetDragon', 'Kitsunebi', 'Sheepball', 'IceHorse']);
    assert.equal(sortDeck(deck, 'name').length, deck.length, 'sorts a copy');
    assert.equal(deck[0].id, 'Sheepball');
});

test('bonusOf and bonusPips draw the pips', () => {
    assert.equal(bonusOf(progress, 'Kitsunebi'), 2);
    assert.equal(bonusOf(progress, 'JetDragon'), 0);
    assert.equal(bonusOf(null, 'Kitsunebi'), 0);
    assert.deepEqual(bonusPips(2).map(p => p.full), [true, true, false, false, false]);
});

test('bonusSummary shapes the strip and expBar the level bar', () => {
    assert.deepEqual(bonusSummary(progress, 288), { done: 2, total: 288, left: 13, index: 697, nextExp: 7384, toLevel: 65, expToLevel: 512406, level: 72 });
    assert.equal(bonusSummary(null, 288), null);
    assert.equal(bonusSummary({ bonus_index: 10 }, 4).left, 10);   // without the API figure: cap * species - index
    const bar = expBar({ level: 72, exp: 22552286, exp_progress: { into: 1637776, span: 2150182, to_next: 512406 } });
    assert.equal(Math.round(bar.pct), 76);
    assert.equal(bar.label, '512,406 to Lv 73');
    assert.match(bar.tip, /22,552,286 total/);
    assert.equal(expBar({ level: 100, exp: 1, exp_progress: null }), null);
});
