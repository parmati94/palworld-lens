"""Localised strings reach the API without Unreal rich-text markup."""
from backend.parser.loaders.data_loader import strip_rich_text


def test_strip_rich_text_keeps_the_text():
    assert strip_rich_text("Farming's Work Suitability<NumBlue_13> +1</>") == "Farming's Work Suitability +1"
    assert strip_rich_text("Hunger decreases <NumBlue_13>+10.0%</> slower.") == "Hunger decreases +10.0% slower."
    assert strip_rich_text("<Status_Up>Immune</> to Explosion Damage") == "Immune to Explosion Damage"
    assert strip_rich_text("Player Stamina Consumption -<NumBlue_13>5.0</>%") == "Player Stamina Consumption -5.0%"


def test_strip_rich_text_passes_plain_values_through():
    assert strip_rich_text("Attack +10%") == "Attack +10%"
    assert strip_rich_text(None) is None
    assert strip_rich_text(3) == 3


def test_loaded_passives_have_no_markup(tmp_path):
    from backend.parser.loaders.data_loader import DataLoader
    data = DataLoader()
    dirty = [k for k, row in data.passive_skills.items()
             if '<' in (row.get('description') or '') or '<' in (row.get('localized_name') or '')]
    assert dirty == []
