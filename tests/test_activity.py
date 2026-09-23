"""Base activity: machines, crops, incubators, expeditions and the lab, from the save's work records."""
import json
from pathlib import Path
from types import SimpleNamespace

from backend.common.activity import (build_activity_tables, crop_phase, expedition_state, fraction, lab_summary, MIN_GENERATORS,
                                     MIN_LAB_RESEARCH, MIN_MISSIONS, TICKS_PER_SECOND)
from backend.parser.builders.activity import build_activity
from backend.parser.extractors.activity import get_activity_objects, get_guild_labs, get_real_time_ticks, index_works
from backend.parser.extractors.bases import BaseMeta

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'json'


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------
def test_build_activity_tables_names_research_and_missions_and_keeps_only_odd_recipes():
    lab_rows = {'Mining1': {'TextId': 'NAME_MINING1', 'RequiredWorkAmount': 50000,
                            'LabCategoryWorkSuitability': 'EPalWorkSuitability::Mining', 'RequiredResearchId': 'None'},
                'Mining1_2': {'TextId': 'NAME_MINING12', 'RequiredWorkAmount': 200000,
                              'LabCategoryWorkSuitability': 'EPalWorkSuitability::Mining', 'RequiredResearchId': 'Mining1'}}
    lab_text = {'NAME_MINING1': {'TextData': {'LocalizedString': 'Mining Speed 1'}},
                'NAME_MINING12': {'TextData': {'SourceString': 'Mining Speed 2'}}}
    missions = {'Dungeon_Grass': {'TitleTextId': 'DUNGEON_GRASS', 'RequiredSeconds': 1800,
                                  'Difficulty': 'EPalCharacterTeamMissionDifficulty::Easy'}}
    mission_text = {'DUNGEON_GRASS': {'TextData': {'LocalizedString': 'Verdant Hollow'}}}
    recipes = {'IronIngot': {'Product_Id': 'IronIngot'}, 'Head001_1': {'Product_Id': 'Head001'}, 'X': {'Product_Id': 'None'}}
    blueprints = {'ElectricGenerator': [{'Type': 'Function'}, {'Properties': {'MaxEnergyStorage': 250000.0}}],
                  'ElectricGenerator_Large': [{'Properties': {'GenerateEnergyRateByWorker': 3.0, 'MaxEnergyStorage': 1000000.0}}],
                  'Lamp': [{'Properties': {'Brightness': 3}}]}
    doc = build_activity_tables(lab_rows, lab_text, missions, mission_text, recipes, blueprints)
    assert doc['generators'] == {'ElectricGenerator': {'capacity': 250000.0, 'rate': None},
                                 'ElectricGenerator_Large': {'capacity': 1000000.0, 'rate': 3.0}}, 'no MaxEnergyStorage, no row'
    assert doc['lab']['Mining1'] == {'name': 'Mining Speed 1', 'work': 50000.0, 'category': 'Mining', 'requires': None}
    assert doc['lab']['Mining1_2']['requires'] == 'Mining1' and doc['lab']['Mining1_2']['name'] == 'Mining Speed 2'
    assert doc['expeditions'] == {'Dungeon_Grass': {'name': 'Verdant Hollow', 'seconds': 1800, 'difficulty': 'Easy'}}
    assert doc['recipe_products'] == {'Head001_1': 'Head001'}


def test_crop_phase_reads_the_field_that_moves_in_each_phase():
    assert crop_phase(5, 0.754, 0.0, 0.0, 330.0) == {'phase': 'planting', 'progress': 0.754}
    assert crop_phase(2, 0.0, 0.37, 0.0, 270.0) == {'phase': 'watering', 'progress': 0.37}
    assert crop_phase(3, 0.0, 0.0, 45.0, 180.0) == {'phase': 'growing', 'progress': 0.25}
    assert crop_phase(4, None, 0.0, 0.0, 180.0, unit=4500.0, done=2876.1)['progress'] == 2876.1 / 4500.0, 'work record as fallback'
    assert crop_phase(4, 0.947, 0.0, 0.0, 390.0)['phase'] == 'harvesting'
    assert crop_phase(0, 0.0, 0.0, 0.0, 0.0) == {'phase': None, 'progress': None}
    assert crop_phase(None, None, None, None, None) == {'phase': None, 'progress': None}


def test_fraction_and_expedition_state():
    assert fraction(50, 200) == 0.25 and fraction(300, 200) == 1.0 and fraction(1, 0) is None and fraction(None, 5) is None
    now = 100 * TICKS_PER_SECOND
    assert expedition_state(None, 0, now, 1800)['state'] == 'idle'
    out = expedition_state('Dungeon_Grass', 40 * TICKS_PER_SECOND, now, 1800)
    assert out['state'] == 'out' and out['seconds_left'] == 1740 and out['elapsed'] == 60
    back = expedition_state('Dungeon_Grass', 0, now + 1800 * TICKS_PER_SECOND, 1800)
    assert back['state'] == 'back' and back['seconds_left'] == 0
    assert expedition_state('Dungeon_Grass', None, now, 1800)['state'] == 'out', 'no clock: still out, no timer'


def test_lab_summary_reports_the_research_in_hand_and_counts_the_done_ones():
    table = {'Mining1': {'name': 'Mining Speed 1', 'work': 50000, 'category': 'Mining'},
             'Mining1_2': {'name': 'Mining Speed 2', 'work': 200000, 'category': 'Mining'},
             'Handcraft1': {'name': 'Handiwork Speed 1', 'work': 50000, 'category': 'Handcraft'}}
    progress = {'Mining1': 50002.0, 'Mining1_2': 60000.0, 'Handcraft1': 10.0}
    s = lab_summary(table, 'Mining1_2', progress)
    assert s['current']['name'] == 'Mining Speed 2' and s['current']['progress'] == 0.3 and not s['current']['complete']
    assert s['completed'] == 1 and s['known'] == 3
    assert [p['research_id'] for p in s['parked']] == ['Handcraft1'], 'started, not complete, not in hand'
    assert lab_summary(table, None, {})['current'] is None


# ---------------------------------------------------------------------------
# extractor, over save-shaped dicts
# ---------------------------------------------------------------------------
def _raw(d):
    return {'value': {'RawData': {'value': d}}}


def _obj(map_object_id, concrete, base='b1', model_id='m1', modules=None):
    return {
        'MapObjectId': {'value': map_object_id},
        'Model': _raw({'instance_id': model_id, 'base_camp_id_belong_to': base, 'hp': {'current': 900, 'max': 1000}}),
        'ConcreteModel': {'value': {'RawData': {'value': concrete},
                                    'ModuleMap': {'value': [{'key': f'EPalMapObjectConcreteModelModuleType::{k}', 'value': {'RawData': {'value': v}}}
                                                            for k, v in (modules or {}).items()]}}},
    }


def _work(wid, unit, done, assigned=(), wtype='Progress', owner='m1'):
    return {'WorkableType': {'value': {'value': f'EPalWorkableType::{wtype}'}},
            'WorkAssignMap': {'value': [{'key': i, 'value': {'RawData': {'value': {'assigned_individual_id': {'instance_id': pid}}}}}
                                        for i, pid in enumerate(assigned)]},
            'RawData': {'value': {'id': wid, 'current_state': 1, 'current_work_amount': unit,
                                  'auto_work_self_amount_by_sec': done, 'owner_map_object_model_id': owner}}}


WORLD = {
    'GameTimeSaveData': {'value': {'RealDateTimeTicks': {'value': 1000 * TICKS_PER_SECOND}}},
    'WorkSaveData': {'value': {'values': [
        _work('w-furnace', 4666.67, 2298.1, assigned=['pal-a']),
        _work('w-egg', 180.0, 180.0),
        _work('w-idle', -1.0, 0.0),
        _work('w-lab', 0.0, 0.0, assigned=['pal-b'], wtype='OnlyJoin'),
    ]}},
    'MapObjectSaveData': {'value': {'values': [
        _obj('BlastFurnace2', {'concrete_model_type': 'PalMapObjectConvertItemModel', 'current_recipe_id': 'IronIngot',
                               'remain_product_num': 4999, 'requested_product_num': 3271, 'work_speed_additional_rate': 1.5},
             model_id='m-furnace', modules={'ItemContainer': {'target_container_id': 'c-furnace'}, 'Workee': {'target_work_id': 'w-furnace'}}),
        _obj('Workbench', {'concrete_model_type': 'PalMapObjectConvertItemModel', 'current_recipe_id': 'None',
                           'remain_product_num': 0, 'requested_product_num': 0},
             model_id='m-bench', modules={'Workee': {'target_work_id': 'w-idle'}}),
        _obj('HatchingPalEgg', {'concrete_model_type': 'PalMapObjectHatchingEggModel', 'current_pal_egg_temp_diff': 0,
                                'hatched_character_save_parameter': {'SaveParameter': {'value': {'CharacterID': {'value': 'LazyCatfish_Gold'}}}}},
             model_id='m-egg', modules={'ItemContainer': {'target_container_id': 'c-egg'}, 'Workee': {'target_work_id': 'w-egg'}}),
        _obj('FarmBlockV2_Berries', {'concrete_model_type': 'PalMapObjectFarmBlockV2Model', 'crop_data_id': 'Berries', 'current_state': 3,
                                     'water_stack_rate_value': 1.0, 'state_machine': {'growup_required_time': 180.0, 'growup_progress_time': 45.0}},
             model_id='m-crop'),
        _obj('FarmBlockV2_Wheat', {'concrete_model_type': 'PalMapObjectFarmBlockV2Model', 'crop_data_id': 'Wheat', 'current_state': 2,
                                   'water_stack_rate_value': 0.0, 'crop_progress_rate_value': 0.0,
                                   'state_machine': {'growup_required_time': 270.0, 'growup_progress_time': 0.0}},
             model_id='m-bare'),
        _obj('FarmBlockV2_Tomato', {'concrete_model_type': 'PalMapObjectFarmBlockV2Model', 'crop_data_id': 'Tomato', 'current_state': 5,
                                    'water_stack_rate_value': 0.0, 'crop_progress_rate_value': 0.803,
                                    'state_machine': {'growup_required_time': 300.0, 'growup_progress_time': 0.0}},
             model_id='m-planting'),
        _obj('Expedition', {'concrete_model_type': 'PalMapObjectCharacterTeamMissionModel', 'mission_id': 'Dungeon_Grass', 'state': 1,
                            'start_time': 400 * TICKS_PER_SECOND, 'assigned_individuals': [{'player_uid': '0', 'instance_id': 'pal-c'}]},
             model_id='m-exp', modules={'ItemContainer': {'target_container_id': 'c-exp'}}),
        _obj('Lab', {'concrete_model_type': 'PalMapObjectLabModel'}, model_id='m-lab', modules={'Workee': {'target_work_id': 'w-lab'}}),
        _obj('Wooden_foundation', {'concrete_model_type': 'PalBuildObject'}, model_id='m-wall'),
        _obj('BlastFurnace', {'concrete_model_type': 'PalMapObjectConvertItemModel', 'current_recipe_id': 'CopperIngot'},
             base='00000000-0000-0000-0000-000000000000', model_id='m-wild'),
    ]}},
    'GuildExtraSaveDataMap': {'value': [
        {'key': 'g1', 'value': {'Lab': _raw({'current_research_id': 'Mining1_2',
                                             'research_info': [{'research_id': 'Mining1', 'work_amount': 50002.0},
                                                               {'research_id': 'Mining1_2', 'work_amount': 60000.0},
                                                               {'research_id': 'Handcraft1', 'work_amount': 0.0}]})}},
        {'key': 'g2', 'value': {'Lab': _raw({'current_research_id': 'None', 'research_info': []})}},
    ]},
}


def test_extractors_read_works_buildings_labs_and_the_clock():
    works = index_works(WORLD)
    assert works['w-furnace'] == {'type': 'Progress', 'state': 1, 'unit': 4666.67, 'done': 2298.1, 'assigned': ['pal-a'], 'owner_model_id': 'm1'}
    assert works['w-lab']['type'] == 'OnlyJoin' and works['w-lab']['assigned'] == ['pal-b']

    objs = {o['map_object_id']: o for o in get_activity_objects(WORLD)}
    assert set(objs) == {'BlastFurnace2', 'Workbench', 'HatchingPalEgg', 'FarmBlockV2_Berries', 'FarmBlockV2_Wheat', 'FarmBlockV2_Tomato', 'Expedition', 'Lab'}, \
        'walls are not activity; a furnace outside any base is skipped'
    f = objs['BlastFurnace2']
    assert (f['kind'], f['recipe_id'], f['order_remaining'], f['craftable_now'], f['container_id'], f['work_id']) == \
        ('machine', 'IronIngot', 4999, 3271, 'c-furnace', 'w-furnace')
    assert objs['Workbench']['recipe_id'] is None
    assert objs['HatchingPalEgg']['hatched_character_id'] == 'LazyCatfish_Gold'
    assert objs['FarmBlockV2_Berries']['crop_progress'] == 45.0 and objs['FarmBlockV2_Berries']['crop_watered'] == 1.0
    assert objs['Expedition']['mission_pals'] == ['pal-c'] and objs['Expedition']['mission_start_ticks'] == 400 * TICKS_PER_SECOND
    assert objs['Lab']['work_id'] == 'w-lab'

    labs = get_guild_labs(WORLD)
    assert labs['g1'] == {'current': 'Mining1_2', 'progress': {'Mining1': 50002.0, 'Mining1_2': 60000.0}}
    assert labs['g2'] == {'current': None, 'progress': {}}
    assert get_real_time_ticks(WORLD) == 1000 * TICKS_PER_SECOND


# ---------------------------------------------------------------------------
# builder
# ---------------------------------------------------------------------------
class _Data:
    buildings = {'BlastFurnace2': {'icon': 'i_furnace'}, 'HatchingPalEgg': {'icon': 'i_egg'}, 'Expedition': {'icon': 'i_exp'},
                 'FarmBlockV2_Berries': {'icon': 'i_berry'}, 'Workbench': {'icon': 'i_bench'}, 'Lab': {'icon': 'i_lab'}}
    technologies = {'Lab': {'localized_name': 'Pal Labor Research Lab'}}
    activity = {'lab': {'Mining1': {'name': 'Mining Speed 1', 'work': 50000, 'category': 'Mining'},
                        'Mining1_2': {'name': 'Mining Speed 2', 'work': 200000, 'category': 'Mining'}},
                'expeditions': {'Dungeon_Grass': {'name': 'Verdant Hollow', 'seconds': 1800, 'difficulty': 'Easy'}},
                'recipe_products': {},
                'generators': {'ElectricGenerator': {'capacity': 250000.0, 'rate': None}}}
    _items = {'IronIngot': {'localized_name': 'Refined Ingot', 'icon': 'i_ingot', 'rarity': 0},
              'CopperOre': {'localized_name': 'Ore', 'icon': 'i_ore', 'rarity': 0},
              'Coal': {'localized_name': 'Coal', 'icon': 'i_coal', 'rarity': 0},
              'Berries': {'localized_name': 'Red Berries', 'icon': 'i_berries', 'rarity': 0},
              'PalEgg_Earth_03': {'localized_name': 'Large Rocky Egg', 'icon': 'i_rockyegg', 'rarity': 2},
              'Gold': {'localized_name': 'Gold Coin', 'icon': 'i_gold', 'rarity': 0}}

    def item(self, item_id):
        return self._items.get(item_id) or {}

    def pal_name(self, sid):
        return {'LazyCatfish_Gold': 'Dumud (Gold)'}.get(sid, sid)


def _pal(iid, name, species):
    return SimpleNamespace(instance_id=iid, name=name, nickname=None, species_id=species, level=30,
                           image_candidates=[species.lower()])


META = {'b1': BaseMeta(base_id='b1', guild_id='g1', name='Base 1', container_id=None)}
PALS = [_pal('pal-a', 'Ragnahawk', 'FlameBird'), _pal('pal-b', 'Digtoise', 'Digtoise'), _pal('pal-c', 'Lamball', 'SheepBall')]
ITEMS = {'c-furnace': [{'static_id': 'CopperOre', 'count': 6542}, {'static_id': 'Coal', 'count': 6542}, {'static_id': 'IronIngot', 'count': 1728}],
         'c-egg': [{'static_id': 'PalEgg_Earth_03', 'count': 1}], 'c-exp': [{'static_id': 'Gold', 'count': 500}]}


def test_build_activity_makes_cards_for_the_base_and_the_guild():
    payload = build_activity(get_activity_objects(WORLD), index_works(WORLD), get_guild_labs(WORLD), META, ITEMS, PALS, _Data(),
                             get_real_time_ticks(WORLD))
    base = payload.bases['b1']
    by_type = {j.building_type: j for j in base.jobs}
    assert [j.building_type for j in base.jobs] == ['HatchingPalEgg', 'BlastFurnace2', 'FarmBlockV2_Berries', 'FarmBlockV2_Tomato', 'FarmBlockV2_Wheat', 'Workbench'], \
        'ready first, then working, idle last'
    assert (base.ready, base.working, base.stuck, base.idle) == (1, 3, 0, 2)
    assert by_type['FarmBlockV2_Wheat'].status == 'idle', 'a bare plot: nothing planted, nothing watered, nobody on it'

    furnace = by_type['BlastFurnace2']
    assert furnace.status == 'working' and furnace.product.item_name == 'Refined Ingot'
    assert furnace.order_remaining == 4999 and furnace.craftable_now == 3271
    assert round(furnace.progress, 3) == 0.492 and furnace.unit_work == 4666.67
    assert [(i.item_id, i.count) for i in furnace.inputs] == [('CopperOre', 6542), ('Coal', 6542)]
    assert [(o.item_id, o.count) for o in furnace.outputs] == [('IronIngot', 1728)]
    assert [p.name for p in furnace.assigned] == ['Ragnahawk'] and furnace.is_damaged

    egg = by_type['HatchingPalEgg']
    assert egg.status == 'ready' and egg.egg.egg.item_name == 'Large Rocky Egg'
    assert egg.egg.hatched_species_id == 'LazyCatfish_Gold' and egg.egg.hatched_name == 'Dumud (Gold)'
    assert egg.egg.hatched_image_candidates[0] == 'lazycatfish_gold'

    crop = by_type['FarmBlockV2_Berries']
    assert crop.status == 'working' and crop.crop.name == 'Red Berries' and crop.crop.phase == 'growing' and crop.crop.progress == 0.25
    bare = by_type['FarmBlockV2_Wheat']
    assert bare.crop.phase == 'watering' and bare.crop.progress == 0.0 and bare.status == 'idle', 'waiting for a waterer'
    planting = by_type['FarmBlockV2_Tomato']
    assert planting.crop.phase == 'planting' and planting.crop.progress == 0.803 and planting.status == 'working'

    assert by_type['Workbench'].status == 'idle' and by_type['Workbench'].product is None

    guild = payload.guilds['g1']
    exp = guild.expeditions[0].expedition
    assert exp.name == 'Verdant Hollow' and exp.state == 'out' and exp.seconds_left == 1200 and exp.elapsed == 600
    assert [p.name for p in exp.pals] == ['Lamball'] and exp.haul[0].item_name == 'Gold Coin'
    assert guild.expeditions[0].status == 'working'
    lab = guild.lab
    assert lab.base_id == 'b1' and lab.current.name == 'Mining Speed 2' and lab.current.progress == 0.3
    assert lab.completed == 1 and [p.name for p in lab.assigned] == ['Digtoise']
    assert 'g2' not in payload.guilds, 'a guild with no lab building and no research shows nothing'
    assert payload.as_of_ticks == 1000 * TICKS_PER_SECOND


def test_generator_fill_comes_from_the_blueprint_capacity():
    world = {'WorkSaveData': {'value': {'values': []}}, 'GuildExtraSaveDataMap': {'value': []},
             'MapObjectSaveData': {'value': {'values': [
                 _obj('ElectricGenerator', {'concrete_model_type': 'PalMapObjectGenerateEnergyModel', 'stored_energy_amount': 62500.0},
                      model_id='m-gen'),
                 _obj('ManualElectricGenerator', {'concrete_model_type': 'PalMapObjectGenerateEnergyModel', 'stored_energy_amount': 100.0},
                      model_id='m-manual'),
             ]}}}
    payload = build_activity(get_activity_objects(world), {}, {}, META, {}, [], _Data(), None)
    gen, manual = sorted(payload.bases['b1'].jobs, key=lambda j: j.instance_id)
    assert gen.kind == 'generator' and gen.stored_energy == 62500.0 and gen.energy_max == 250000.0 and gen.progress == 0.25
    assert manual.energy_max is None and manual.progress is None, 'no capacity in the table, no percentage'


def test_idle_expedition_station_with_a_haul_inside_is_ready():
    world = {'WorkSaveData': {'value': {'values': []}}, 'GuildExtraSaveDataMap': {'value': []},
             'MapObjectSaveData': {'value': {'values': [
                 _obj('Expedition', {'concrete_model_type': 'PalMapObjectCharacterTeamMissionModel', 'mission_id': 'None', 'state': 3,
                                     'start_time': 0, 'assigned_individuals': []}, model_id='m-exp',
                      modules={'ItemContainer': {'target_container_id': 'c-exp'}})]}}}
    payload = build_activity(get_activity_objects(world), {}, {}, META, {'c-exp': [{'static_id': 'Gold', 'count': 500}]}, [], _Data(), None)
    job = payload.guilds['g1'].expeditions[0]
    assert job.status == 'ready' and job.expedition.state == 'idle' and job.expedition.haul[0].count == 500


def test_machine_status_tells_unstaffed_from_out_of_materials():
    world = {'WorkSaveData': {'value': {'values': [_work('w1', 1000.0, 0.0), _work('w2', 1000.0, 0.0), _work('w3', 1000.0, 0.0)]}},
             'MapObjectSaveData': {'value': {'values': [
                 _obj('BlastFurnace2', {'concrete_model_type': 'PalMapObjectConvertItemModel', 'current_recipe_id': 'IronIngot',
                                        'remain_product_num': 10, 'requested_product_num': 5}, model_id='m1',
                      modules={'ItemContainer': {'target_container_id': 'c1'}, 'Workee': {'target_work_id': 'w1'}}),
                 _obj('BlastFurnace2', {'concrete_model_type': 'PalMapObjectConvertItemModel', 'current_recipe_id': 'IronIngot',
                                        'remain_product_num': 10, 'requested_product_num': 0}, model_id='m2',
                      modules={'ItemContainer': {'target_container_id': 'c2'}, 'Workee': {'target_work_id': 'w2'}}),
                 _obj('BlastFurnace2', {'concrete_model_type': 'PalMapObjectConvertItemModel', 'current_recipe_id': 'IronIngot',
                                        'remain_product_num': 0, 'requested_product_num': 0}, model_id='m3',
                      modules={'ItemContainer': {'target_container_id': 'c3'}, 'Workee': {'target_work_id': 'w3'}}),
             ]}}, 'GuildExtraSaveDataMap': {'value': []}}
    items = {'c1': [{'static_id': 'CopperOre', 'count': 10}], 'c2': [], 'c3': [{'static_id': 'IronIngot', 'count': 10}]}
    payload = build_activity(get_activity_objects(world), index_works(world), {}, META, items, [], _Data(), None)
    statuses = [(j.instance_id, j.status) for j in payload.bases['b1'].jobs]
    assert sorted(statuses) == [('m1', 'unstaffed'), ('m2', 'no_materials'), ('m3', 'ready')]
    assert payload.bases['b1'].stuck == 2 and payload.bases['b1'].ready == 1


def test_shipped_activity_tables_are_complete():
    p = DATA / 'activity.json'
    if not p.exists():
        import pytest
        pytest.skip('activity.json not generated')
    doc = json.loads(p.read_text(encoding='utf-8'))
    assert len(doc['lab']) >= MIN_LAB_RESEARCH and len(doc['expeditions']) >= MIN_MISSIONS
    assert all(v['name'] and v['work'] > 0 for v in doc['lab'].values())
    assert all(v['name'] and v['seconds'] > 0 for v in doc['expeditions'].values())
    assert doc['expeditions']['Dungeon_Grass'] == {'name': 'Verdant Hollow', 'seconds': 1800, 'difficulty': 'Easy'}
    assert doc['lab']['Mining1']['category'] == 'Mining'
    assert doc['generators']['ElectricGenerator'] == {'capacity': 250000.0, 'rate': None}
    assert doc['generators']['ElectricGenerator_Large']['capacity'] == 1000000.0
    assert len(doc['generators']) >= MIN_GENERATORS
    items = json.loads((DATA / 'items.json').read_text(encoding='utf-8'))
    assert all(v in items for v in doc['recipe_products'].values()), 'every recipe product is an item'
