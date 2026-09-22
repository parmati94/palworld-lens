"""backend/common/partner_skills.py -- per-level rendering of the game's partner skill text."""
from backend.common.partner_skills import (
    Resolver, build_partner_skills, clamp_level, clean_text, format_number, has_foreign_markup, resolve_markup,
)

# Shapes as the extractor dumps them (trimmed to what the renderer reads).
PASSIVES = {
    'ElementAddDrop_Normal_1_PAL': {'EffectValue1': 40.0, 'EffectValue2': 40.0},
    'ElementAddDrop_Normal_5_PAL': {'EffectValue1': 80.0, 'EffectValue2': 80.0},
    'CatMage_Fire_PartnerSkill_1': {'EffectValue1': 10.0},
    'CatMage_Fire_PartnerSkill_5': {'EffectValue1': 50.0},
    'Attack_ACC_up1': {'EffectValue1': 50.0},
    'Attack_ACC_up5': {'EffectValue1': 200.0},
}


def _rank(*keys):
    return {'SkillAndParametersArray': [{'SkillName': {'Key': k}} for k in keys]}


CATMAGE = {
    'ActiveSkill': {'SkillName': 'Unknown', 'ActiveSkill_MainValueByRank': [], 'ActiveSkill_OverWriteEffectTimeByRank': []},
    'PassiveSkills': [_rank('ElementAddDrop_Normal_1_PAL', 'CatMage_Fire_PartnerSkill_1')] * 4
                     + [_rank('ElementAddDrop_Normal_5_PAL', 'CatMage_Fire_PartnerSkill_5')],
    'TextReferencePassiveSkills': [],
}
CATMAGE_TEMPLATE = ('While in party,\r\n<img id=|ElemIcon_Neutral|/><uiCommon id=|COMMON_ELEMENT_NAME_Normal| style=|Elem_Neutral|/> '
                    'Pals drop <Status_Up>{Passive1_EffectValue1}%</> more items when defeated.\r\n\r\n'
                    'Also has a <Status_Up>{Passive2_EffectValue1}%</> chance to prevent Pal Sphere consumption when thrown. \r\n'
                    '(Does not stack)')
STEALTH = {
    'ActiveSkill': {'SkillName': 'Stealth', 'ActiveSkill_MainValueByRank': [1.1, 1.3, 1.6, 2.0, 2.5],
                    'ActiveSkill_OverWriteEffectTimeByRank': [10.0, 12.0, 14.0, 16.0, 20.0]},
    'PassiveSkills': [],
    'TextReferencePassiveSkills': [{'PassiveSkillIds': [{'Key': 'Attack_ACC_up1'}]}] * 4
                                  + [{'PassiveSkillIds': [{'Key': 'Attack_ACC_up5'}]}],
}
APPENDS = {'CooldownReduction_Rank_1': ' ', 'CooldownReduction_Rank_2': '(Cooldown Reduction: <Status_Up>S</>)',
           'CooldownReduction_Rank_5': '(Cooldown Reduction: <Status_Up>XL</>)'}
LOOKUPS = {
    'uiCommon': {'COMMON_ELEMENT_NAME_Normal': 'Neutral'}.get,
    'characterName': {'LizardMan': 'Leezpunk'}.get,
    'itemName': {'Wool': 'Wool'}.get,
    'mapObjectName': {'MonsterFarm': 'Ranch'}.get,
    'activeSkillName': {'Unique_Baphomet_SwallowKite': 'Hellfire Claw'}.get,
}


def test_format_number():
    assert [format_number(v) for v in (40.0, 1.1, 0.15, 200, '7')] == ['40', '1.1', '0.15', '200', '7']


def test_markup_resolves_to_words_and_keeps_the_games_highlights():
    s = ('<img id=|ElemIcon_Neutral|/><uiCommon id=|COMMON_ELEMENT_NAME_Normal| style=|Elem_Neutral|/> Pals; '
         '<characterName id=|LizardMan|/> hides; drops <itemName id=|Wool| style=|Status_Keyword|/> at '
         '<mapObjectName id=|MonsterFarm|/>; uses <activeSkillName id=|Unique_Baphomet_SwallowKite| style=|Status_Keyword|/> '
         'for <Status_Up>x2</> damage; can <Status_Keyword>double jump</>; immune to '
         '<uiCommon id=|ADDITIONAL_EFFECT_Freeze| style=|Effect_Freeze|/>. (Does not stack) unknown <itemName id=|Mystery|/>')
    got = resolve_markup(s, LOOKUPS)
    assert got == ('<el Normal>Neutral</el> Pals; Leezpunk hides; drops <kw>Wool</kw> at Ranch; uses <kw>Hellfire Claw</kw> '
                   'for <up>x2</up> damage; can <kw>double jump</kw>; immune to <kw>ADDITIONAL_EFFECT_Freeze</kw>. '
                   '<mu>(Does not stack)</mu> unknown Mystery')
    assert not has_foreign_markup(got)
    assert has_foreign_markup('<b>no</b>') and has_foreign_markup('a < b')


def test_clean_text_joins_hard_wraps_and_keeps_paragraphs():
    assert clean_text('When activated, \r\nhides the player\r\nfor a while.\r\n\r\n\r\n(Does not  stack)\r\n') == \
        'When activated, hides the player for a while.\n\n(Does not stack)'


def test_passive_values_change_with_level():
    r = Resolver(CATMAGE, PASSIVES, {})
    lv1 = r.render(CATMAGE_TEMPLATE, 0, LOOKUPS)
    lv5 = r.render(CATMAGE_TEMPLATE, 4, LOOKUPS)
    assert lv1 == {'text': ('While in party, <el Normal>Neutral</el> Pals drop <up>40%</up> more items when defeated.\n\n'
                            'Also has a <up>10%</up> chance to prevent Pal Sphere consumption when thrown. <mu>(Does not stack)</mu>'),
                   'mount': None, 'bonus': []}
    assert '<up>80%</up> more items' in lv5['text'] and '<up>50%</up> chance' in lv5['text']
    assert not r.missing


def test_active_reference_and_append_placeholders():
    t = ('<characterName id=|LizardMan|/> hides for <Status_Up>{ActiveSkillOverWriteEffectTime}</> seconds, '
         'x{ActiveSkillMainValueByRank} damage, Attack +{ReferencePassive1_EffectValue1}%.\r\n{ReferenceMsgId_CooldownReduction}')
    r = Resolver(STEALTH, PASSIVES, APPENDS)
    assert r.render(t, 0, LOOKUPS) == {'text': 'Leezpunk hides for <up>10</up> seconds, x1.1 damage, Attack +50%.', 'mount': None, 'bonus': []}
    lv2 = r.render(t, 1, LOOKUPS)
    assert lv2['text'] == 'Leezpunk hides for <up>12</up> seconds, x1.3 damage, Attack +50%.' and lv2['bonus'] == ['Cooldown Reduction: S']
    lv5 = r.render(t, 4, LOOKUPS)
    assert lv5['text'].endswith('x2.5 damage, Attack +200%.') and lv5['bonus'] == ['Cooldown Reduction: XL']


def test_ridden_opener_becomes_the_mount_flag():
    r = Resolver({}, PASSIVES, {})
    assert r.render('Can be ridden.\r\n\r\nWhile mounted, faster.', 0, {}) == {'text': 'While mounted, faster.', 'mount': 'ground', 'bonus': []}
    assert r.render('Can be ridden as a flying mount.\r\n\r\nSoars.', 0, {})['mount'] == 'flying'
    assert r.render('Can be ridden to travel on water.', 0, {}) == {'text': 'Can be ridden to travel on water.', 'mount': 'water', 'bonus': []}
    got = r.render('Can be ridden. \r\nCan <Status_Keyword>double jump</> while mounted.', 0, {})
    assert got == {'text': 'Can <kw>double jump</kw> while mounted.', 'mount': 'ground', 'bonus': []}
    assert r.render('While in party, rides are unaffected.', 0, {})['mount'] is None


def test_single_level_species_clamps_and_unknown_placeholder_is_reported():
    param = {'PassiveSkills': [_rank('CatMage_Fire_PartnerSkill_1')], 'ActiveSkill': {}, 'TextReferencePassiveSkills': []}
    r = Resolver(param, PASSIVES, {})
    assert r.render('{Passive1_EffectValue1}% and {Nope}', 4, {})['text'] == '10% and {Nope}'
    assert r.missing == ['Nope']


def test_build_keys_on_pals_json_ids_and_reports_gaps():
    names = {'CatMage': 'Mystical Black Magic', 'SheepBall': 'Fluffy Shield'}
    templates = {'CatMage': CATMAGE_TEMPLATE, 'SheepBall': 'Becomes a shield.', 'Human': 'n/a', 'WindChimes_Ice': 'Glides.'}
    params = {'CatMage': CATMAGE}
    known = {'catmage': 'CatMage', 'sheepball': 'Sheepball', 'windchimes_ice': 'Windchimes_Ice'}
    got = build_partner_skills(names, templates, params, PASSIVES, {}, LOOKUPS, lambda k: known.get(k.lower()))
    out, rep = got['species'], got['report']
    assert list(out) == ['CatMage', 'Sheepball', 'Windchimes_Ice']        # pals.json casing wins
    assert out['CatMage']['name'] == 'Mystical Black Magic' and len(out['CatMage']['levels']) == 5
    assert out['Sheepball']['levels'] == [{'text': 'Becomes a shield.', 'mount': None, 'bonus': []}] * 5   # no numbers: same every level
    assert rep['unresolved'] == ['Human']
    assert rep['no_name'] == ['WindChimes_Ice'] and out['Windchimes_Ice']['name'] == 'WindChimes_Ice'
    assert not rep['unfilled'] and not rep['leftover_markup']


def test_clamp_level():
    assert [clamp_level(v) for v in (None, 0, 1, 3, 5, 9, 'x')] == [1, 1, 1, 3, 5, 5, 1]
