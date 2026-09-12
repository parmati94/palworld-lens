"""ID -> display transforms shared by the builders.

Elements and work types are passed through as game ids (`Leaf`, `EmitFlame`);
the UI resolves names, icons and colours from /api/game-data. Only things the
UI never looks up by id (skill names, building names) are localised here.
"""
from typing import Dict, List

from backend.models.models import SkillInfo
from backend.parser.loaders.data_loader import DataLoader


def map_active_skills(skill_ids: List[str], data: DataLoader) -> List[SkillInfo]:
    """Waza ids -> SkillInfo with localized name, element id and power."""
    skills = []
    for skill_id in skill_ids:
        row = data.active_skills.get(skill_id)
        if row:
            skills.append(SkillInfo(
                skill_id=skill_id,
                name=row.get('localized_name') or skill_id,
                description=row.get('description') or '',
                element=row.get('element'),
                power=row.get('power'),
            ))
        else:
            skills.append(SkillInfo(skill_id=skill_id, name=skill_id.replace('EPalWazaID::', ''), description=''))
    return skills


def map_passive_skills(skill_ids: List[str], data: DataLoader) -> List[SkillInfo]:
    """Passive ids -> SkillInfo with localized name, rank and stat effects."""
    skills = []
    for skill_id in skill_ids:
        row = data.passive_skills.get(skill_id)
        if row:
            skills.append(SkillInfo(
                skill_id=skill_id,
                name=row.get('localized_name') or skill_id,
                description=row.get('description') or '',
                rank=row.get('rank'),
                effects=row.get('effects', []),
            ))
        else:
            skills.append(SkillInfo(skill_id=skill_id, name=skill_id, description=''))
    return skills


# Save files call chests ItemChest / ItemChest_02 / ...; technologies.json calls
# them Infra_ItemChest_Grade_01 / _02 / ... (ItemChest_04 exists under its own name).
_CHEST_TECH_KEYS: Dict[str, str] = {
    'ItemChest': 'Infra_ItemChest_Grade_01',
    'ItemChest_02': 'Infra_ItemChest_Grade_02',
    'ItemChest_03': 'Infra_ItemChest_Grade_03',
}


def map_building_name(building_type: str, data: DataLoader) -> str:
    """Building/map-object id -> localized name, with the chest-key fallback."""
    for key in (building_type, _CHEST_TECH_KEYS.get(building_type)):
        if not key:
            continue
        name = (data.technologies.get(key) or {}).get('localized_name')
        if name:
            return name
        name = (data.buildings.get(key) or {}).get('localized_name')
        if name:
            return name
    return building_type.replace('_', ' ').title()
