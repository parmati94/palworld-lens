// node --test 'frontend/tests/*.test.mjs'   (no test framework needed)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
    MAP_LAYERS, layerForCoords, saveToLngLat, elementInfo, elementBackdrop, hexAlpha, shadeHex,
    workSuitabilityDisplay, buildPageList, palIconSrc, partnerSkillFor, partnerSkillHtml, mountLabel, baseLabel,
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
        { type: 'EmitFlame', name: 'Kindling', level: 2, icon: 't_icon_research_palwork_00_0', color: '#22c55e', badge: '' },
        { type: 'Unknown', name: 'Unknown', level: 1, icon: 'unknown', color: '#9ca3af', badge: '' },
    ]);
});

test('work suitability colours run to 8, then 9 and 10 get the legendary badge', () => {
    const out = workSuitabilityDisplay(gameData, { work_suitability: { EmitFlame: 8, Mining: 9, Unknown: 10 } });
    assert.deepEqual(out.map(w => [w.level, w.color, w.badge]), [
        [8, '#f43f5e', ''], [9, '#f43f5e', 'work-badge-legendary'], [10, '#f43f5e', 'work-badge-max'],
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

test('partnerSkillFor picks the text for the pal\'s condensing level', () => {
    const lv = (text, bonus = []) => ({ text, mount: null, bonus });
    const gd = { partner_skills: {
        CatMage: { name: 'Mystical Black Magic', levels: [lv('40%'), lv('50%'), lv('60%'), lv('70%'), lv('80%')] },
        Garm: { name: 'Direhowl Rider', levels: [lv('Fast.'), lv('Fast.', ['Ride Speed Up: 10%']), lv('Fast.'), lv('Fast.'), lv('Fast.')] },
        Sheepball: { name: 'Fluffy Shield', levels: Array(5).fill(lv('Becomes a shield.')) },
    } };
    assert.equal(partnerSkillFor(gd, { species_id: 'CatMage' }).level, 1);
    assert.equal(partnerSkillFor(gd, { species_id: 'CatMage', rank: 3 }).current.text, '60%');
    assert.equal(partnerSkillFor(gd, { species_id: 'CatMage', rank: 9 }).level, 5);     // clamped
    assert.equal(partnerSkillFor(gd, { species_id: 'CatMage', rank: 2 }).grows, true);
    assert.equal(partnerSkillFor(gd, { species_id: 'Garm', rank: 2 }).grows, true);      // only the bonus differs
    assert.equal(partnerSkillFor(gd, { species_id: 'Sheepball', rank: 5 }).grows, false);
    assert.equal(partnerSkillFor(gd, { species_id: 'Nope', rank: 2 }), null);
    assert.equal(partnerSkillFor({}, { species_id: 'CatMage' }), null);
    assert.deepEqual(['ground', 'flying', 'water', null].map(mountLabel), ['Mount', 'Flying mount', 'Water mount', '']);
});

test('partnerSkillHtml styles the four generator tags and escapes everything else', () => {
    const html = partnerSkillHtml(gameData, 'Drop <up>40%</up> more <el Leaf>Grass</el> loot.\n\n<kw>double jump</kw> <mu>(Does not stack)</mu> <b>x</b> & y');
    assert.equal(html, 'Drop <span class="text-amber-200 font-semibold tabular-nums">40%</span> more '
        + '<span class="font-medium" style="color:#2e8b57">Grass</span> loot.<br><br>'
        + '<span class="text-gray-50 font-medium">double jump</span> <span class="text-gray-500">(Does not stack)</span> '
        + '&lt;b&gt;x&lt;/b&gt; &amp; y');
    assert.equal(partnerSkillHtml(gameData, ''), '');
});

test('baseLabel joins the name and the place, once', () => {
    assert.equal(baseLabel({ base_name: 'Base 3', place: 'Kelpsea Hill' }), 'Base 3 · Kelpsea Hill');
    assert.equal(baseLabel({ base_name: 'Kelp Farm', place: 'Kelpsea Hill' }), 'Kelp Farm · Kelpsea Hill');
    assert.equal(baseLabel({ base_name: 'Kelpsea Hill', place: 'Kelpsea Hill' }), 'Kelpsea Hill');
    assert.equal(baseLabel({ base_name: 'Base 1' }), 'Base 1');
    assert.equal(baseLabel({ base_name: 'Base 1', base_place: 'Oasis Isle' }), 'Base 1 · Oasis Isle');   // pal shape
    assert.equal(baseLabel(null), '');
});

test('schematic slots get a tooltip naming what they unlock', async () => {
    const { itemTip } = await import('../js/utils.js');
    assert.equal(itemTip({ item_id: 'Wood' }), '');
    assert.equal(itemTip({ item_id: 'Wood', item_name: 'Wood', count: 1 }), 'Wood');
    assert.equal(itemTip({ item_id: 'Salad', item_name: 'Salad', count: 12345 }), 'Salad ×12.3K');
    assert.equal(itemTip({ schematic: { kind: 'item', product_name: 'Musket', rarity_name: 'Epic' } }),
        'Schematic: unlocks the Musket recipe (Epic)');
    assert.equal(itemTip({ schematic: { kind: 'building', product_name: 'Majestic Wall Torch', rarity_name: 'Common' } }),
        'Schematic: lets you build Majestic Wall Torch (Common)');
});

test('storage search: matches by name, id or unlocked product; cards keep only the hits', async () => {
    const { itemMatches, searchContainers, sumItemCounts, searchElsewhere, rarityRingClass } = await import('../js/utils.js');
    const paldium = { item_id: 'PalIum_Fragment', item_name: 'Paldium Fragment', count: 100 };
    const musketBp = { item_id: 'Blueprint_Musket_4', item_name: 'Musket Schematic 3', count: 1, schematic: { product_name: 'Musket' } };
    const wood = { item_id: 'Wood', item_name: 'Wood', count: 9999 };
    assert.equal(itemMatches(paldium, 'pald'), true);
    assert.equal(itemMatches(paldium, 'PalIum'), true);
    assert.equal(itemMatches(musketBp, 'musket'), true);
    assert.equal(itemMatches(wood, 'musket'), false);
    assert.equal(itemMatches(wood, '  '), true, 'blank query matches everything');

    const chests = [
        { container_id: 'a', base_name: 'Base 2', container_type: 'storage', items: [paldium, wood] },
        { container_id: 'b', base_name: 'Base 2', container_type: 'storage', items: [musketBp] },
    ];
    assert.equal(searchContainers(chests, ''), chests, 'blank query returns the list untouched');
    const hits = searchContainers(chests, 'pald');
    assert.deepEqual(hits.map(c => [c.container_id, c.items.length]), [['a', 1]]);
    assert.equal(sumItemCounts(hits), 100);
    assert.equal(chests[0].items.length, 2, 'the original container is not mutated');

    const byBase = {
        b2: chests,
        b1: [{ container_id: 'c', base_name: 'Base 1', container_type: 'storage', items: [{ ...paldium, count: 40 }] },
             { container_id: 'f', base_name: 'Base 1', container_type: 'food_bowl', items: [{ ...paldium, count: 5 }] }],
        b4: [{ container_id: 'a', base_name: 'Base 4', container_type: 'guild', shared: true, items: [paldium] },      // same shared chest as here
             { container_id: 'd', base_name: 'Base 4', container_type: 'storage', items: [{ ...paldium, count: 300 }] }],
        // another guild: its shared chest stands at two bases (counted once), and it also calls a base "Base 1"
        b7: [{ container_id: 'g', base_name: 'Base 1', container_type: 'guild', shared: true, display_name: 'Guild Chest',
               shared_at: [{ base_id: 'b7', base_name: 'Base 1' }, { base_id: 'b8', base_name: 'Base 2' }], items: [{ ...paldium, count: 70 }] },
             { container_id: 'h', base_name: 'Base 1', container_type: 'storage', items: [{ ...paldium, count: 1 }] }],
        b8: [{ container_id: 'g', base_name: 'Base 2', container_type: 'guild', shared: true, display_name: 'Guild Chest',
               shared_at: [{ base_id: 'b7', base_name: 'Base 1' }, { base_id: 'b8', base_name: 'Base 2' }], items: [{ ...paldium, count: 70 }] }],
        b9: [{ container_id: 'k', base_name: 'Camp', container_type: 'guild', shared: true, display_name: 'Guild Chest',
               shared_at: [{ base_id: 'b9', base_name: 'Camp' }], items: [{ ...paldium, count: 60 }] }],
    };
    const owners = { b1: 'Envy', b4: 'Envy', b7: 'Rival', b8: 'Rival', b9: 'Third' };
    const away = searchElsewhere(byBase, 'b2', 'pald', { ownerOf: id => owners[id] || '' });
    assert.deepEqual(away.map(r => [r.label, r.count, r.chests, r.shared, r.ambiguous, r.owner]), [
        ['Base 4', 300, 1, false, false, 'Envy'],
        ['Guild Chest', 70, 1, true, true, 'Rival'],
        ['Guild Chest', 60, 1, true, true, 'Third'],
        ['Base 1', 40, 1, false, true, 'Envy'],
        ['Base 1', 1, 1, false, true, 'Rival'],
    ], 'biggest first; food bowls and the shared chest already on screen skipped; a shared chest once; clashing labels flagged');
    assert.deepEqual(away[1].at, ['Base 1', 'Base 2']);
    assert.equal(away[1].base_id, 'b7', 'a shared chest row opens the first base it stands at');
    assert.deepEqual(searchElsewhere(byBase, 'b2', ''), []);
    const mine = searchElsewhere(byBase, 'b2', 'pald', { ownerOf: () => 'Envy', onlyBases: new Set(['b1', 'b2', 'b4']) });
    assert.deepEqual(mine.map(r => [r.label, r.count, r.ambiguous]), [['Base 4', 300, false], ['Base 1', 40, false]],
        'limited to the guild\'s own bases, nothing clashes');

    assert.equal(rarityRingClass(4), 'ring-amber-400/90');
    assert.equal(rarityRingClass(null), rarityRingClass(0));
});

test('activity: groups by attention, formats durations and order lines', async () => {
    const { activityGroups, activityStatus, formatDuration, orderLine, formatCount } = await import('../js/utils.js');
    const jobs = [
        { instance_id: 'a', status: 'working' }, { instance_id: 'b', status: 'ready' },
        { instance_id: 'c', status: 'idle' }, { instance_id: 'd', status: 'no_materials' },
    ];
    assert.deepEqual(activityGroups(jobs).map(g => [g.id, g.jobs.map(j => j.instance_id)]),
        [['attention', ['b', 'd']], ['working', ['a']], ['idle', ['c']]]);
    assert.deepEqual(activityGroups([{ status: 'working' }]).map(g => g.id), ['working'], 'empty groups are dropped');
    const mixed = [{ status: 'working', kind: 'crop', display_name: 'Berry Plantation' }, { status: 'working', kind: 'machine', display_name: 'Mill' },
                   { status: 'working', kind: 'station', display_name: 'Coal Quarry' }, { status: 'working', kind: 'machine', display_name: 'Crusher' }];
    assert.deepEqual(activityGroups(mixed)[0].jobs.map(j => j.display_name), ['Crusher', 'Mill', 'Coal Quarry', 'Berry Plantation'], 'same shapes sit together');
    assert.equal(activityStatus('unstaffed').label, 'Nobody on it');
    assert.equal(activityStatus('???').label, 'Idle');
    assert.equal(formatDuration(4320), '1h 12m');
    assert.equal(formatDuration(725), '12m');
    assert.equal(formatDuration(45), '45s');
    assert.equal(formatDuration(null), '');
    assert.equal(orderLine({ recipe_id: 'Flour', order_total: 1335, order_left: 559, order_made: 776 }), '776 / 1,335 made');
    assert.equal(orderLine({ recipe_id: 'IronIngot', order_total: 1841, order_left: 0, order_made: 1841 }), '1,841 made · complete');
    assert.equal(orderLine({ recipe_id: 'IronIngot', order_total: 0, order_left: 0 }), 'no order');
    const { itemTip } = await import('../js/utils.js');
    assert.equal(itemTip({ item_id: 'IronIngot', note: '1,728 made so far, 3,271 to come' }), '1,728 made so far, 3,271 to come');
    assert.equal(orderLine({ recipe_id: null }), '');
    assert.deepEqual([1234, 12345, 250000, 1234567, 1000000, null].map(formatCount), ['1,234', '12.3K', '250K', '1.2M', '1M', '']);
});

test('activity: cards lead with the product and take the family colour', async () => {
    const { activityHero, activityKind, eggTemperature } = await import('../js/utils.js');
    const ingot = { item_id: 'IronIngot', item_name: 'Ingot', icon: 'i', rarity: 0 };
    assert.deepEqual(activityHero({ kind: 'machine', display_name: 'Furnace', product: ingot }), { item: ingot, pal: null, title: 'Ingot', caption: 'Furnace' });
    assert.equal(activityHero({ kind: 'crop', display_name: 'Berry Plantation', crop: { crop_id: 'Berries', name: 'Red Berries', icon: 'b' } }).title, 'Red Berries');
    const hatched = activityHero({ kind: 'incubator', display_name: 'Egg Incubator', eggs: [{ hatched: true, species_id: 'Dumud', name: 'Dumud', image_candidates: ['Dumud'] }] });
    assert.equal(hatched.pal.name, 'Dumud'); assert.equal(hatched.item, null);
    assert.equal(activityHero({ kind: 'incubator', display_name: 'Large Incubator', eggs: [{ hatched: false }, { hatched: true }] }).title, 'Large Incubator');
    const { eggSummary, eggModalDetail } = await import('../js/utils.js');
    assert.equal(eggSummary([{ hatched: true }, { hatched: false }, { hatched: false }]), '1 hatched · 2 incubating');
    assert.equal(eggSummary([]), '');
    assert.equal(eggModalDetail({ display_name: 'Large Incubator', eggs: [{ hatched: true }, { hatched: false }] }).subtitle, '2 eggs · 1 hatched · 1 incubating');
    assert.deepEqual(activityHero({ kind: 'generator', display_name: 'Power Generator' }), { item: null, pal: null, title: 'Power Generator', caption: '' });
    assert.deepEqual(activityHero({ kind: 'expedition', display_name: 'Pal Expedition Station', expedition: { state: 'out', name: 'Astral Frost Cavern' } }),
        { item: null, pal: null, title: 'Astral Frost Cavern', caption: 'Pal Expedition Station' });
    assert.equal(activityHero({ kind: 'expedition', display_name: 'Pal Expedition Station', expedition: { state: 'idle' } }).title, 'Pal Expedition Station');
    assert.equal(activityKind('machine').bar, 'bg-orange-400');
    assert.equal(activityKind('nope').label, '');
    assert.equal(eggTemperature({ temp_diff: 0 }), null);
    assert.equal(eggTemperature({ temp_diff: -3 }).label, 'Wrong temperature');
    assert.equal(eggTemperature(null), null);
    const { fillBarClass, activityStatus: st } = await import('../js/utils.js');
    assert.deepEqual([0.5, 0.95, 1, null].map(f => fillBarClass(f, 'bg-teal-400')), ['bg-teal-400', 'bg-amber-400', 'bg-red-400', 'bg-teal-400']);
    assert.equal(st('full').label, 'Full');
    assert.equal(st('empty').label, 'No power');
    const { activityCrew, crewModalDetail, CREW_INLINE_MAX } = await import('../js/utils.js');
    const many = Array.from({ length: 100 }, (_, i) => ({ instance_id: 'p' + i, name: 'Pal ' + i, level: 1, image_candidates: [] }));
    const trip = { display_name: 'Pal Expedition Station', expedition: { name: 'Astral Frost Cavern', state: 'out', seconds_left: 3480, pals: many } };
    assert.equal(activityCrew(trip).length, 100); assert.ok(100 > CREW_INLINE_MAX);
    assert.deepEqual([crewModalDetail(trip).title, crewModalDetail(trip).subtitle], ['Astral Frost Cavern', '100 pals · On expedition, 58m left']);
    assert.equal(activityCrew({ assigned: [{ instance_id: 'a' }] }).length, 1);
});

test('activity: a breeding farm keeps its own picture, stacks its eggs into a button and says when the cake is gone', async () => {
    const { activityHero, breedingLine, eggStack, farmEggsModalDetail } = await import('../js/utils.js');
    const egg = { item_id: 'PalEgg_Ice_05', item_name: 'Huge Frozen Egg', icon: 'e', count: 14 };
    const rocky = { item_id: 'PalEgg_Earth_03', item_name: 'Large Rocky Egg', icon: 'r', count: 2 };
    const cake = { item_id: 'Cake', item_name: 'Cake', icon: 'c', count: 4 };
    const laid = { kind: 'breeding', display_name: 'Breeding Farm', held: 16, inputs: [cake], outputs: [egg, rocky] };
    assert.equal(activityHero(laid).title, 'Breeding Farm', 'the farm, not the egg, leads the card');
    assert.deepEqual(eggStack(laid).map(e => e.item_id), Array(5).fill('PalEgg_Ice_05'), 'five tiles at most');
    assert.deepEqual(eggStack({ outputs: [{ ...egg, count: 1 }, rocky] }).map(e => e.key), ['PalEgg_Ice_05-0', 'PalEgg_Earth_03-0', 'PalEgg_Earth_03-1']);
    assert.deepEqual(farmEggsModalDetail(laid), { title: 'Breeding Farm', subtitle: '16 eggs on the ground', items: [egg, rocky] });
    assert.equal(breedingLine(laid, 2), '16 eggs to collect');
    assert.equal(breedingLine({ ...laid, held: 1, inputs: [] }, 2), '1 egg to collect · no cake');
    assert.equal(breedingLine({ kind: 'breeding', held: 0, inputs: [], outputs: [] }, 2), 'no cake');
    assert.equal(breedingLine({ kind: 'breeding', held: 0, inputs: [cake], outputs: [] }, 2), 'breeding');
    assert.equal(breedingLine({ kind: 'breeding', held: 0, inputs: [], outputs: [] }, 0), 'nobody on it');
});

test('player card: the bag opens as an items modal and the records strip reads tech first', async () => {
    const { bagModalDetail, playerRecordCells } = await import('../js/utils.js');
    const salad = { item_id: 'Salad', item_name: 'Salad', count: 75 };
    const player = {
        player_name: 'Ricky', bag: [salad],
        tech: { unlocked: 201, points: 19, ancient_points: 43 },
        records: { towers: 5, alphas: 62, paldeck: 161, caught: 614, fast_travels: 100, dungeons: 13 },
    };
    assert.deepEqual(bagModalDetail(player), { title: 'Ricky', subtitle: '1 stack in the bag', items: [salad] });
    assert.equal(bagModalDetail({ player_name: 'bagel' }).subtitle, '0 stacks in the bag');
    const cells = playerRecordCells(player);
    assert.deepEqual(cells.map(c => [c.label, c.value]),
        [['Tech', 201], ['Paldeck', 161], ['Towers', 5], ['Alphas', 62], ['Dungeons', 13], ['Fast travel', 100]]);
    assert.equal(cells[0].tip, '19 tech pts, 43 ancient pts to spend');
    assert.equal(cells[1].tip, '614 pals caught');
    assert.equal(playerRecordCells({ tech: { unlocked: 3, points: 0, ancient_points: 0 } })[0].tip, 'nothing to spend');
    assert.deepEqual(playerRecordCells({}), []);
});
