"""Pal conditions: the save drops Hp at 0, so a knocked-out pal has no Hp field and PhysicalHealth = Dying."""
from backend.models.models import PalInfo
from backend.parser.loaders.schema_loader import SchemaManager


def _pal(**kw):
    base = dict(instance_id="x", character_id="IceHorse", name="Frostallion", level=40, exp=0,
                gender="Male", hp=500, max_hp=3600, hunger=100.0, sanity=100.0)
    return PalInfo(**{**base, **kw})


def test_knocked_out_pal_is_incapacitated_before_any_sickness():
    pal = _pal(hp=0, physical_health="Dying", condition="Weakness")
    assert pal.condition_display == "Incapacitated"
    assert [c["type"] for c in pal.all_conditions] == ["injury", "sickness"]


def test_healthy_pal_has_no_condition():
    assert _pal().condition_display is None


def test_missing_hp_reads_as_zero():
    pal_schema = SchemaManager.get("pals.yaml")
    assert pal_schema.extract_field({}, "Hp") == 0
