"""backend/common/partner_skills.py -- per-level rendering of the game's partner skill text."""
from backend.common.partner_skills import (
    Resolver, build_partner_skills, clamp_level, clean_text, format_number, strip_markup,
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


def test_markup_resolves_to_words_and_style_tags_keep_their_text():
    s = ('<img id=|ElemIcon_Neutral|/><uiCommon id=|COMMON_ELEMENT_NAME_Normal| style=|Elem_Neutral|/> Pals; '
         '<characterName id=|LizardMan|/> hides; drops <itemName id=|Wool| style=|Status_Keyword|/> at '
         '<mapObjectName id=|MonsterFarm|/>; uses <activeSkillName id=|Unique_Baphomet_SwallowKite| style=|Status_Keyword|/> '
         'for <Status_Up>x2</> damage; unknown <itemName id=|Mystery|/>')
    assert strip_markup(s, LOOKUPS) == ('Neutral Pals; Leezpunk hides; drops Wool at Ranch; uses Hellfire Claw '
                                        'for x2 damage; unknown Mystery')


def test_clean_text_joins_hard_wraps_and_keeps_paragraphs():
    assert clean_text('When activated, \r\nhides the player\r\nfor a while.\r\n\r\n\r\n(Does not  stack)\r\n') == \
        'When activated, hides the player for a while.\n\n(Does not stack)'


def test_passive_values_change_with_level():
    r = Resolver(CATMAGE, PASSIVES, {})
    lv1 = r.render(CATMAGE_TEMPLATE, 0, LOOKUPS)
    lv5 = r.render(CATMAGE_TEMPLATE, 4, LOOKUPS)
    assert lv1 == ('While in party, Neutral Pals drop 40% more items when defeated.\n\n'
                   'Also has a 10% chance to prevent Pal Sphere consumption when thrown. (Does not stack)')
    assert '80% more items' in lv5 and '50% chance' in lv5
    assert not r.missing


def test_active_reference_and_append_placeholders():
    t = ('<characterName id=|LizardMan|/> hides for <Status_Up>{ActiveSkillOverWriteEffectTime}</> seconds, '
         'x{ActiveSkillMainValueByRank} damage, Attack +{ReferencePassive1_EffectValue1}%.\r\n{ReferenceMsgId_CooldownReduction}')
    r = Resolver(STEALTH, PASSIVES, APPENDS)
    assert r.render(t, 0, LOOKUPS) == 'Leezpunk hides for 10 seconds, x1.1 damage, Attack +50%.'
    assert r.render(t, 1, LOOKUPS) == 'Leezpunk hides for 12 seconds, x1.3 damage, Attack +50%.\n\n(Cooldown Reduction: S)'
    assert r.render(t, 4, LOOKUPS).endswith('x2.5 damage, Attack +200%.\n\n(Cooldown Reduction: XL)')


def test_single_level_species_clamps_and_unknown_placeholder_is_reported():
    param = {'PassiveSkills': [_rank('CatMage_Fire_PartnerSkill_1')], 'ActiveSkill': {}, 'TextReferencePassiveSkills': []}
    r = Resolver(param, PASSIVES, {})
    assert r.render('{Passive1_EffectValue1}% and {Nope}', 4, {}) == '10% and {Nope}'
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
    assert out['Sheepball']['levels'] == ['Becomes a shield.'] * 5      # no numbers: same text every level
    assert rep['unresolved'] == ['Human']
    assert rep['no_name'] == ['WindChimes_Ice'] and out['Windchimes_Ice']['name'] == 'WindChimes_Ice'
    assert not rep['unfilled'] and not rep['leftover_markup']


def test_clamp_level():
    assert [clamp_level(v) for v in (None, 0, 1, 3, 5, 9, 'x')] == [1, 1, 1, 3, 5, 5, 1]
