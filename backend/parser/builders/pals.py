"""Pal building from save data"""
from typing import Dict, List

from backend.models.models import PalInfo
from backend.parser.utils.mappers import map_active_skills, map_passive_skills
from backend.parser.loaders.schema_loader import SchemaManager
from backend.parser.loaders.data_loader import DataLoader
from backend.parser.utils.stats import calculate_pal_stats, calculate_work_suitabilities, calculate_trust_level
from backend.common.pal_ids import is_boss_id
from backend.common.logging_config import get_logger

logger = get_logger(__name__)

pal_schema = SchemaManager.get("pals.yaml")

DEFAULT_MAX_STOMACH = 150


def build_pals(char_data: Dict, base_assignments: Dict, data: DataLoader, pal_to_owner: Dict[str, str]) -> List[PalInfo]:
    """Build every non-player character into a PalInfo.

    Args:
        char_data: {instance_id: SaveParameter dict} from the characters collection
        base_assignments: {instance_id: {base_id, guild_id, base_name}} for pals at bases
        data: static game data
        pal_to_owner: {instance_id: owner player name}
    """
    pals: List[PalInfo] = []
    unknown_species: set = set()

    for instance_id, char_info in char_data.items():
        if pal_schema.extract_field(char_info, "IsPlayer"):
            continue

        char_id = str(pal_schema.extract_field(char_info, "CharacterID"))
        species_id = data.species.resolve(char_id)
        species = data.pals.get(species_id, {}) if species_id else {}
        if not species:
            unknown_species.add(char_id)
        pal_name = data.pal_name(species_id) if species_id else char_id

        hunger_raw = pal_schema.extract_field(char_info, "FullStomach")
        max_stomach = species.get("max_full_stomach") or DEFAULT_MAX_STOMACH
        hunger = min((hunger_raw / max_stomach) * 100, 100.0)

        is_boss = bool(pal_schema.extract_field(char_info, "IsBoss")) or is_boss_id(char_id)

        active_skills = map_active_skills([str(s) for s in pal_schema.extract_list(char_info, "EquipWaza")], data)
        passive_skills = map_passive_skills([str(s) for s in pal_schema.extract_list(char_info, "PassiveSkillList")], data)

        rank = pal_schema.extract_field(char_info, "Rank")

        # Work suitability: species base + condenser bonus + manual (book) upgrades
        work_suitability: Dict[str, int] = {}
        if species:
            manual_upgrades: Dict[str, int] = {}
            for entry in pal_schema.extract_list(char_info, "GotWorkSuitabilityAddRankList"):
                work_type, bonus = entry.get("work_type"), entry.get("rank_bonus")
                if work_type and bonus:
                    manual_upgrades[work_type] = manual_upgrades.get(work_type, 0) + bonus
            work_suitability = calculate_work_suitabilities(
                species.get("work_suitability", {}), rank, manual_upgrades or None, passive_skills)

        level = pal_schema.extract_field(char_info, "Level")
        talent_hp = pal_schema.extract_field(char_info, "Talent_HP")
        talent_melee = pal_schema.extract_field(char_info, "Talent_Melee")
        talent_shot = pal_schema.extract_field(char_info, "Talent_Shot")
        talent_defense = pal_schema.extract_field(char_info, "Talent_Defense")
        friendship_points = pal_schema.extract_field(char_info, "Friendship")
        trust_level = calculate_trust_level(friendship_points, data.trust_thresholds)

        soul_hp = pal_schema.extract_field(char_info, "Rank_HP") or 0
        soul_attack = pal_schema.extract_field(char_info, "Rank_Attack") or 0
        soul_defense = pal_schema.extract_field(char_info, "Rank_Defense") or 0
        soul_work_speed = pal_schema.extract_field(char_info, "Rank_CraftSpeed") or 0

        calculated_stats = calculate_pal_stats(
            species_scaling=species.get("scaling"),
            level=level,
            talent_hp=talent_hp,
            talent_melee=talent_melee,
            talent_shot=talent_shot,
            talent_defense=talent_defense,
            rank=rank,
            trust_level=trust_level,
            friendship_multipliers={
                "friendship_hp": species.get("friendship_hp", 0),
                "friendship_shotattack": species.get("friendship_shotattack", 0),
                "friendship_defense": species.get("friendship_defense", 0),
                "friendship_craftspeed": species.get("friendship_craftspeed", 0),
            } if species else None,
            is_alpha=is_boss_id(char_id),
            passive_skills=passive_skills,
            soul_hp=soul_hp,
            soul_attack=soul_attack,
            soul_defense=soul_defense,
            soul_work_speed=soul_work_speed,
        )

        assignment = base_assignments.get(str(instance_id), {})

        pals.append(PalInfo(
            instance_id=str(instance_id),
            character_id=char_id,
            species_id=species_id,
            name=str(pal_name),
            nickname=pal_schema.extract_field(char_info, "NickName"),
            level=level,
            exp=pal_schema.extract_field(char_info, "Exp"),
            owner_uid=pal_to_owner.get(str(instance_id)),
            gender=pal_schema.extract_field(char_info, "Gender"),
            hp=pal_schema.extract_field(char_info, "Hp"),
            max_hp=calculated_stats["hp"],
            mp=pal_schema.extract_field(char_info, "MP"),
            max_mp=pal_schema.extract_field(char_info, "MaxMP"),
            hunger=hunger,
            sanity=pal_schema.extract_field(char_info, "SanityValue"),
            rank=rank,
            rank_hp=soul_hp,
            rank_attack=soul_attack,
            rank_defense=soul_defense,
            rank_craftspeed=soul_work_speed,
            talent_hp=talent_hp,
            talent_melee=talent_melee,
            talent_shot=talent_shot,
            talent_defense=talent_defense,
            active_skills=active_skills,
            passive_skills=passive_skills,
            element_types=list(species.get("element_types", [])),
            work_suitability=work_suitability,
            is_lucky=pal_schema.extract_field(char_info, "IsRarePal"),
            is_boss=is_boss,
            base_id=assignment.get("base_id"),
            guild_id=assignment.get("guild_id"),
            base_name=assignment.get("base_name"),
            condition=pal_schema.extract_field(char_info, "WorkerSick"),
            hunger_type=pal_schema.extract_field(char_info, "HungerType"),
            calculated_attack=calculated_stats["attack"],
            calculated_defense=calculated_stats["defense"],
            calculated_hp=calculated_stats["hp"],
            calculated_work_speed=calculated_stats["work_speed"],
            friendship_points=friendship_points,
            trust_level=trust_level,
        ))

    if unknown_species:
        logger.warning(f"{len(unknown_species)} character id(s) not in pals.json (shown by raw id, no stats): "
                       + ", ".join(sorted(unknown_species)[:10]) + (" ..." if len(unknown_species) > 10 else ""))
    return pals
