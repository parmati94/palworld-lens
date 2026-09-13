// node --test 'frontend/tests/*.test.mjs'
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
    palsBySpecies, arrangements, pairOwned, bestCandidates, ownedPassives, passiveIds, comparePairRows,
} from '../js/breeding.js';

const pal = (id, species, gender, passives = [], level = 1) => ({
    instance_id: id, species_id: species, gender, level,
    passive_skills: passives.map(p => (typeof p === 'string' ? { skill_id: p, name: p, rank: 1 } : p)),
});

const pals = [
    pal('m1', 'Sheepball', 'Male', ['Runner']),
    pal('f1', 'Sheepball', 'Female', ['Legend', 'Runner'], 10),
    pal('f2', 'Sheepball', 'Female', [], 30),
    pal('m2', 'Anubis', 'Male', ['Legend']),
    pal('x1', 'Anubis', 'Unknown'),
    pal('m3', 'CatMage', 'Male', []),
    pal('f3', 'FoxMage', 'Female', []),
];
const by = palsBySpecies(pals);

test('palsBySpecies buckets by species and gender, skipping unknown genders', () => {
    assert.deepEqual(Object.keys(by).sort(), ['Anubis', 'CatMage', 'FoxMage', 'Sheepball']);
    assert.equal(by.Sheepball.Male.length, 1);
    assert.equal(by.Sheepball.Female.length, 2);
    assert.equal(by.Anubis.Female.length, 0);
});

test('arrangements: either parent can be the male unless the combo is gated', () => {
    assert.equal(arrangements({ parent_a: 'A', parent_b: 'B' }).length, 2);
    assert.deepEqual(arrangements({ parent_a: 'A', parent_b: 'A' }), [{ a: 'Male', b: 'Female' }]);
    assert.deepEqual(arrangements({ parent_a: 'CatMage', parent_b: 'FoxMage', parent_a_gender: 'Male', parent_b_gender: 'Female' }),
        [{ a: 'Male', b: 'Female' }]);
});

test('pairOwned: feasible only when an owned male and female fit the pair', () => {
    assert.equal(pairOwned({ parent_a: 'Sheepball', parent_b: 'Sheepball' }, by).feasible, true);
    // Anubis is male only, Sheepball has a female -> feasible either way round
    assert.equal(pairOwned({ parent_a: 'Anubis', parent_b: 'Sheepball' }, by).feasible, true);
    assert.equal(pairOwned({ parent_a: 'Sheepball', parent_b: 'Anubis' }, by).feasible, true);
    // two males only
    assert.equal(pairOwned({ parent_a: 'Anubis', parent_b: 'Anubis' }, by).feasible, false);
    const r = pairOwned({ parent_a: 'Anubis', parent_b: 'Nope' }, by);
    assert.equal(r.feasible, false);
    assert.equal(r.ownsA, true);
    assert.equal(r.ownsB, false);
    assert.deepEqual(r.counts.b, { Male: 0, Female: 0 });
});

test('pairOwned honours a gender gate', () => {
    const gated = { parent_a: 'CatMage', parent_b: 'FoxMage', parent_a_gender: 'Male', parent_b_gender: 'Female' };
    assert.equal(pairOwned(gated, by).feasible, true);
    const reversed = { ...gated, parent_a_gender: 'Female', parent_b_gender: 'Male' };
    assert.equal(pairOwned(reversed, by).feasible, false);
});

test('bestCandidates ranks couples by target passives covered, never pairs a pal with itself', () => {
    const best = bestCandidates({ parent_a: 'Sheepball', parent_b: 'Sheepball' }, by, ['Legend', 'Runner']);
    assert.equal(best.length, 2);
    assert.equal(best[0].a.instance_id, 'm1');
    assert.equal(best[0].b.instance_id, 'f1');
    assert.deepEqual(best[0].matched.sort(), ['Legend', 'Runner']);
    assert.equal(best[1].b.instance_id, 'f2');
    assert.equal(best[1].score, 1);
    for (const c of best) assert.notEqual(c.a.instance_id, c.b.instance_id);
});

test('bestCandidates with no targets prefers more good passives, then level', () => {
    const best = bestCandidates({ parent_a: 'Sheepball', parent_b: 'Sheepball' }, by);
    assert.equal(best[0].b.instance_id, 'f1');   // 2 passives beats level 30 with none
});

test('ownedPassives lists each passive once, highest rank first', () => {
    const list = ownedPassives([...pals, pal('z', 'Sheepball', 'Male', [{ skill_id: 'Legend', name: 'Legend', rank: 4 }])]);
    assert.deepEqual(list.map(p => p.id), ['Legend', 'Runner']);
    assert.equal(passiveIds(pals[1]).length, 2);
});

test('comparePairRows puts breedable-now pairs first, then partial ownership, then special combos', () => {
    const row = (feasible, ownsA, unique, score = 0, name = 'a') =>
        ({ owned: { feasible, ownsA, ownsB: false }, pair: { unique }, best: { score }, nameA: name, nameB: '' });
    const rows = [row(false, false, true, 0, 'z'), row(false, true, false), row(true, true, false, 1), row(true, true, false, 2)];
    rows.sort(comparePairRows);
    assert.deepEqual(rows.map(r => [r.owned.feasible, r.best.score, r.owned.ownsA, r.pair.unique]),
        [[true, 2, true, false], [true, 1, true, false], [false, 0, true, false], [false, 0, false, true]]);
});
