# File: sensor.py
# Using private coordinator methods for state checks
# pyright: reportIncompatibleVariableOverride=false
# ^ Suppresses Pylance warnings about @property overriding @cached_property from base classes.
#   This is intentional: our sensors compute dynamic values on each access (chore status, points),
#   so we use @property instead of @cached_property to avoid stale cached data.
"""Sensors for the ChoreOps integration.

This file defines modern sensor entities for each Assignee, Chore, Reward, and Badge.
Legacy/optional sensors are imported from sensor_legacy.py.

Module-level functions for dynamic entity creation (used by services).

Sensors Defined in This File (14):

# Modern Assignee-Specific Sensors (9)
01. AssigneeChoreStatusSensor
02. AssigneePointsSensor
03. AssigneeChoresSensor
04. AssigneeBadgesSensor
05. AssigneeBadgeProgressSensor
06. AssigneeRewardStatusSensor
07. AssigneeAchievementProgressSensor
08. AssigneeChallengeProgressSensor
09. AssigneeDashboardHelperSensor

# Modern System-Level Sensors (5)
10. SystemBadgeSensor
11. SystemChoreSharedStateSensor
12. SystemAchievementSensor
13. SystemChallengeSensor
14. SystemDashboardTranslationSensor

Legacy Sensors Imported from sensor_legacy.py (13):
    Assignee Chore Completion Sensors (4):
    1. AssigneeChoreCompletionSensor - Total chores completed (data in AssigneeChoresSensor attributes)
    2. AssigneeChoreCompletionDailySensor - Daily chores completed (data in AssigneeChoreCompletionSensor attributes)
    3. AssigneeChoreCompletionWeeklySensor - Weekly chores completed (data in AssigneeChoreCompletionSensor attributes)
    4. AssigneeChoreCompletionMonthlySensor - Monthly chores completed (data in AssigneeChoreCompletionSensor attributes)

    Pending Approval Sensors (2):
    5. SystemChoresPendingApprovalSensor - Pending chore approvals (global)
    6. SystemRewardsPendingApprovalSensor - Pending reward approvals (global)

    Assignee Points Earned Sensors (4):
    7. AssigneePointsEarnedDailySensor - Daily points earned (data in AssigneePointsSensor attributes)
    8. AssigneePointsEarnedWeeklySensor - Weekly points earned (data in AssigneePointsSensor attributes)
    9. AssigneePointsEarnedMonthlySensor - Monthly points earned (data in AssigneePointsSensor attributes)
    10. AssigneePointsMaxEverSensor - Maximum points ever reached (data in AssigneePointsSensor attributes)

    Streak Sensor (1):
    11. AssigneeChoreStreakSensor - Highest chore streak (data in AssigneePointsSensor attributes)

    Bonus/Penalty Sensors (2):
    12. AssigneePenaltyAppliedSensor - Penalty application count (data in dashboard helper)
    13. AssigneeBonusAppliedSensor - Bonus application count (data in dashboard helper)
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, cast

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get
from homeassistant.util import dt as dt_util

from . import const
from .coordinator import ChoreOpsConfigEntry, ChoreOpsDataCoordinator
from .engines.chore_engine import ChoreEngine
from .entity import ChoreOpsCoordinatorEntity
from .helpers.device_helpers import (
    create_assignee_device_info_from_coordinator,
    create_system_device_info,
)
from .helpers.entity_helpers import (
    get_assignee_name_by_id,
    get_friendly_label,
    get_item_name_or_log_error,
    is_user_feature_gated_profile,
    should_create_entity,
    should_create_entity_for_user_assignee,
    should_create_gamification_entities,
    should_create_workflow_buttons,
)
from .helpers.translation_helpers import load_dashboard_translation
from .sensor_legacy import (
    AssigneeBonusAppliedSensor,
    AssigneeChoreCompletionDailySensor,
    AssigneeChoreCompletionMonthlySensor,
    AssigneeChoreCompletionSensor,
    AssigneeChoreCompletionWeeklySensor,
    AssigneeChoreStreakSensor,
    AssigneePenaltyAppliedSensor,
    AssigneePointsEarnedDailySensor,
    AssigneePointsEarnedMonthlySensor,
    AssigneePointsEarnedWeeklySensor,
    AssigneePointsMaxEverSensor,
    SystemChoresPendingApprovalSensor,
    SystemRewardsPendingApprovalSensor,
)
from .type_defs import (
    AchievementData,
    AchievementProgress,
    AssigneeData,
    BadgeData,
    BonusData,
    ChallengeData,
    ChallengeProgress,
    ChoreData,
    PenaltyData,
    PeriodicStatsEntry,
    RewardData,
)
from .utils.dt_utils import (
    dt_add_interval,
    dt_format,
    dt_now_local,
    dt_time_until,
    dt_to_utc,
    dt_today_local,
)

# Platinum requirement: Parallel Updates
# Set to 0 (unlimited) for coordinator-based entities that don't poll
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChoreOpsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for ChoreOps integration."""
    coordinator = entry.runtime_data

    points_label = entry.options.get(
        const.CONF_POINTS_LABEL, const.DEFAULT_POINTS_LABEL
    )
    points_icon = entry.options.get(const.CONF_POINTS_ICON, const.DEFAULT_POINTS_ICON)
    show_legacy_entities = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
    entities: list[SensorEntity] = []

    # System-level pending approval sensors (EXTRA requirement)
    if should_create_entity(
        const.SENSOR_KC_UID_SUFFIX_PENDING_CHORE_APPROVALS_SENSOR,
        extra_enabled=show_legacy_entities,
    ):
        entities.append(SystemChoresPendingApprovalSensor(coordinator, entry))
    if should_create_entity(
        const.SENSOR_KC_UID_SUFFIX_PENDING_REWARD_APPROVALS_SENSOR,
        extra_enabled=show_legacy_entities,
    ):
        entities.append(SystemRewardsPendingApprovalSensor(coordinator, entry))

    # For each assignee profile, add standard sensors
    for assignee_id, assignee_info in coordinator.assignees_data.items():
        assignee_name = get_item_name_or_log_error(
            "assignee", assignee_id, assignee_info, const.DATA_USER_NAME
        )
        if not assignee_name:
            continue

        # Points counter sensor (GAMIFICATION requirement)
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_SENSOR,
            coordinator,
            assignee_id,
        ):
            entities.append(
                AssigneePointsSensor(
                    coordinator,
                    entry,
                    assignee_id,
                    assignee_name,
                    points_label,
                    points_icon,
                )
            )

        # Chores sensor with all stats (ALWAYS created)
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_CHORES_SENSOR,
            coordinator,
            assignee_id,
        ):
            entities.append(
                AssigneeChoresSensor(coordinator, entry, assignee_id, assignee_name)
            )

        # Chore completion sensors (EXTRA requirement)
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_COMPLETED_TOTAL_SENSOR,
            coordinator,
            assignee_id,
            extra_enabled=show_legacy_entities,
        ):
            entities.append(
                AssigneeChoreCompletionSensor(
                    coordinator, entry, assignee_id, assignee_name
                )
            )
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_COMPLETED_DAILY_SENSOR,
            coordinator,
            assignee_id,
            extra_enabled=show_legacy_entities,
        ):
            entities.append(
                AssigneeChoreCompletionDailySensor(
                    coordinator, entry, assignee_id, assignee_name
                )
            )
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_COMPLETED_WEEKLY_SENSOR,
            coordinator,
            assignee_id,
            extra_enabled=show_legacy_entities,
        ):
            entities.append(
                AssigneeChoreCompletionWeeklySensor(
                    coordinator, entry, assignee_id, assignee_name
                )
            )
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_COMPLETED_MONTHLY_SENSOR,
            coordinator,
            assignee_id,
            extra_enabled=show_legacy_entities,
        ):
            entities.append(
                AssigneeChoreCompletionMonthlySensor(
                    coordinator, entry, assignee_id, assignee_name
                )
            )

        # Assignee Badges (displays highest cumulative badge) (GAMIFICATION requirement)
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_BADGES_SENSOR,
            coordinator,
            assignee_id,
        ):
            entities.append(
                AssigneeBadgesSensor(coordinator, entry, assignee_id, assignee_name)
            )

        # Points earned sensors (EXTRA requirement)
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_EARNED_DAILY_SENSOR,
            coordinator,
            assignee_id,
            extra_enabled=show_legacy_entities,
        ):
            entities.append(
                AssigneePointsEarnedDailySensor(
                    coordinator,
                    entry,
                    assignee_id,
                    assignee_name,
                    points_label,
                    points_icon,
                )
            )
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_EARNED_WEEKLY_SENSOR,
            coordinator,
            assignee_id,
            extra_enabled=show_legacy_entities,
        ):
            entities.append(
                AssigneePointsEarnedWeeklySensor(
                    coordinator,
                    entry,
                    assignee_id,
                    assignee_name,
                    points_label,
                    points_icon,
                )
            )
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_EARNED_MONTHLY_SENSOR,
            coordinator,
            assignee_id,
            extra_enabled=show_legacy_entities,
        ):
            entities.append(
                AssigneePointsEarnedMonthlySensor(
                    coordinator,
                    entry,
                    assignee_id,
                    assignee_name,
                    points_label,
                    points_icon,
                )
            )

        # Maximum points sensor (EXTRA requirement)
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_MAX_POINTS_EVER_SENSOR,
            coordinator,
            assignee_id,
            extra_enabled=show_legacy_entities,
        ):
            entities.append(
                AssigneePointsMaxEverSensor(
                    coordinator,
                    entry,
                    assignee_id,
                    assignee_name,
                    points_label,
                    points_icon,
                )
            )

        # Penalty applied sensors (EXTRA requirement)
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_PENALTY_APPLIES_SENSOR,
            coordinator,
            assignee_id,
            extra_enabled=show_legacy_entities,
        ):
            for penalty_id, penalty_info in coordinator.penalties_data.items():
                penalty_name = get_item_name_or_log_error(
                    "penalty", penalty_id, penalty_info, const.DATA_PENALTY_NAME
                )
                if not penalty_name:
                    continue
                entities.append(
                    AssigneePenaltyAppliedSensor(
                        coordinator,
                        entry,
                        assignee_id,
                        assignee_name,
                        penalty_id,
                        penalty_name,
                    )
                )

        # Bonus applied sensors (EXTRA requirement)
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_BONUS_APPLIES_SENSOR,
            coordinator,
            assignee_id,
            extra_enabled=show_legacy_entities,
        ):
            for bonus_id, bonus_info in coordinator.bonuses_data.items():
                bonus_name = get_item_name_or_log_error(
                    "bonus", bonus_id, bonus_info, const.DATA_BONUS_NAME
                )
                if not bonus_name:
                    continue
                entities.append(
                    AssigneeBonusAppliedSensor(
                        coordinator,
                        entry,
                        assignee_id,
                        assignee_name,
                        bonus_id,
                        bonus_name,
                    )
                )

        # Badge progress sensors (GAMIFICATION requirement)
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR,
            coordinator,
            assignee_id,
        ):
            badge_progress_data = assignee_info.get(
                const.DATA_ASSIGNEE_BADGE_PROGRESS, {}
            )
            for badge_id, progress_info in badge_progress_data.items():
                badge_type = progress_info.get(const.DATA_ASSIGNEE_BADGE_PROGRESS_TYPE)
                if badge_type != const.BADGE_TYPE_CUMULATIVE:
                    badge_name = get_item_name_or_log_error(
                        "badge",
                        badge_id,
                        progress_info,
                        const.DATA_ASSIGNEE_BADGE_PROGRESS_NAME,
                    )
                    if not badge_name:
                        continue
                    entities.append(
                        AssigneeBadgeProgressSensor(
                            coordinator,
                            entry,
                            assignee_id,
                            assignee_name,
                            badge_id,
                            badge_name,
                        )
                    )

        # Achievement Progress per Assignee (GAMIFICATION requirement)
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_PROGRESS_SENSOR,
            coordinator,
            assignee_id,
        ):
            for achievement_id, achievement in coordinator.achievements_data.items():
                if assignee_id in achievement.get(
                    const.DATA_ACHIEVEMENT_ASSIGNED_ASSIGNEES, []
                ):
                    achievement_name = get_item_name_or_log_error(
                        "achievement",
                        achievement_id,
                        achievement,
                        const.DATA_ACHIEVEMENT_NAME,
                    )
                    if not achievement_name:
                        continue
                    entities.append(
                        AssigneeAchievementProgressSensor(
                            coordinator,
                            entry,
                            assignee_id,
                            assignee_name,
                            achievement_id,
                            achievement_name,
                        )
                    )

        # Challenge Progress per Assignee (GAMIFICATION requirement)
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_CHALLENGE_PROGRESS_SENSOR,
            coordinator,
            assignee_id,
        ):
            for challenge_id, challenge in coordinator.challenges_data.items():
                if assignee_id in challenge.get(
                    const.DATA_CHALLENGE_ASSIGNED_ASSIGNEES, []
                ):
                    challenge_name = get_item_name_or_log_error(
                        "challenge", challenge_id, challenge, const.DATA_CHALLENGE_NAME
                    )
                    if not challenge_name:
                        continue
                    entities.append(
                        AssigneeChallengeProgressSensor(
                            coordinator,
                            entry,
                            assignee_id,
                            assignee_name,
                            challenge_id,
                            challenge_name,
                        )
                    )

        # Highest Streak Sensor per Assignee (EXTRA requirement)
        if should_create_entity_for_user_assignee(
            const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_HIGHEST_STREAK_SENSOR,
            coordinator,
            assignee_id,
            extra_enabled=show_legacy_entities,
        ):
            entities.append(
                AssigneeChoreStreakSensor(
                    coordinator, entry, assignee_id, assignee_name
                )
            )

        # Dashboard helper sensor will be created after all individual entities

    # For each chore assigned to each assignee, add a AssigneeChoreStatusSensor
    for chore_id, chore_info in coordinator.chores_data.items():
        chore_name = get_item_name_or_log_error(
            "chore", chore_id, chore_info, const.DATA_CHORE_NAME
        )
        if not chore_name:
            continue
        assigned_assignees_ids = chore_info.get(const.DATA_CHORE_ASSIGNED_ASSIGNEES, [])
        for assignee_id in assigned_assignees_ids:
            assignee_data: AssigneeData = cast(
                "AssigneeData", coordinator.assignees_data.get(assignee_id, {})
            )
            assignee_name = get_item_name_or_log_error(
                "assignee", assignee_id, assignee_data, const.DATA_USER_NAME
            )
            if not assignee_name:
                continue
            entities.append(
                AssigneeChoreStatusSensor(
                    coordinator,
                    entry,
                    assignee_id,
                    assignee_name,
                    chore_id,
                    chore_name,
                )
            )

    # For each shared chore, add a global state sensor
    for chore_id, chore_info in coordinator.chores_data.items():
        completion_criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
        if completion_criteria in (
            const.COMPLETION_CRITERIA_SHARED,
            const.COMPLETION_CRITERIA_SHARED_FIRST,
        ):
            chore_name = get_item_name_or_log_error(
                "chore", chore_id, chore_info, const.DATA_CHORE_NAME
            )
            if not chore_name:
                continue
            entities.append(
                SystemChoreSharedStateSensor(coordinator, entry, chore_id, chore_name)
            )

    # For each Reward, add a AssigneeRewardStatusSensor (GAMIFICATION requirement)
    for reward_id, reward_info in coordinator.rewards_data.items():
        reward_name = get_item_name_or_log_error(
            "reward", reward_id, reward_info, const.DATA_REWARD_NAME
        )
        if not reward_name:
            continue

        # For each assignee with gamification enabled, create the reward status sensor
        for assignee_id, assignee_info in coordinator.assignees_data.items():
            if not should_create_entity_for_user_assignee(
                const.SENSOR_KC_UID_SUFFIX_REWARD_STATUS_SENSOR,
                coordinator,
                assignee_id,
            ):
                continue
            assignee_name = get_item_name_or_log_error(
                "assignee", assignee_id, assignee_info, const.DATA_USER_NAME
            )
            if not assignee_name:
                continue
            entities.append(
                AssigneeRewardStatusSensor(
                    coordinator,
                    entry,
                    assignee_id,
                    assignee_name,
                    reward_id,
                    reward_name,
                )
            )

    # For each Badge, add a BadgeSensor (GAMIFICATION requirement - system-level)
    for badge_id, badge_info in coordinator.badges_data.items():
        badge_name = get_item_name_or_log_error(
            "badge", badge_id, badge_info, const.DATA_BADGE_NAME
        )
        if not badge_name:
            continue
        entities.append(SystemBadgeSensor(coordinator, entry, badge_id, badge_name))

    # For each Achievement, add an AchievementSensor (GAMIFICATION requirement - system-level)
    for achievement_id, achievement in coordinator.achievements_data.items():
        achievement_name = get_item_name_or_log_error(
            "achievement", achievement_id, achievement, const.DATA_ACHIEVEMENT_NAME
        )
        if not achievement_name:
            continue
        entities.append(
            SystemAchievementSensor(
                coordinator, entry, achievement_id, achievement_name
            )
        )

    # For each Challenge, add a ChallengeSensor (GAMIFICATION requirement - system-level)
    for challenge_id, challenge in coordinator.challenges_data.items():
        challenge_name = get_item_name_or_log_error(
            "challenge", challenge_id, challenge, const.DATA_CHALLENGE_NAME
        )
        if not challenge_name:
            continue
        entities.append(
            SystemChallengeSensor(coordinator, entry, challenge_id, challenge_name)
        )

    # Collect unique dashboard languages in use across all assignees and approvers
    languages_in_use: set[str] = set()
    for assignee_info in coordinator.assignees_data.values():
        lang = assignee_info.get(
            const.DATA_ASSIGNEE_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
        )
        languages_in_use.add(lang)
    for approver_info in coordinator.approvers_data.values():
        lang = approver_info.get(
            const.DATA_APPROVER_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
        )
        languages_in_use.add(lang)

    # Ensure at least English exists (fallback)
    if not languages_in_use:
        languages_in_use.add(const.DEFAULT_DASHBOARD_LANGUAGE)

    # Register the async_add_entities callback on coordinator for dynamic sensor creation
    # This enables creating new translation sensors when a assignee changes to a new language
    coordinator.ui_manager.register_translation_sensor_callback(async_add_entities)

    # Register callback for dynamic chore/reward sensor creation (services)
    register_chore_reward_callback(async_add_entities)

    # Create one translation sensor per unique language
    # Track created sensors on coordinator for lifecycle management
    for lang_code in languages_in_use:
        entities.append(SystemDashboardTranslationSensor(coordinator, entry, lang_code))
        coordinator.ui_manager.mark_translation_sensor_created(lang_code)

    # Dashboard helper sensors: Created last to ensure all referenced entities exist
    # This prevents entity ID lookup failures during initial setup
    for assignee_id, assignee_data in coordinator.assignees_data.items():
        assignee_name = get_item_name_or_log_error(
            "assignee", assignee_id, assignee_data, const.DATA_USER_NAME
        )
        if not assignee_name:
            continue
        entities.append(
            AssigneeDashboardHelperSensor(
                coordinator,
                entry,
                assignee_id,
                assignee_name,
                points_label,
            )
        )

    async_add_entities(entities)


# ------------------------------------------------------------------------------------------
# Module-level callback storage for dynamic entity creation
# ------------------------------------------------------------------------------------------

_async_add_entities_callback: Callable | None = None


def register_chore_reward_callback(
    async_add_entities: Callable,
) -> None:
    """Register async_add_entities callback for dynamic chore/reward sensor creation.

    Called once during platform setup to enable services to create new sensor entities
    after chores/rewards are added at runtime.
    """
    global _async_add_entities_callback  # noqa: PLW0603
    _async_add_entities_callback = async_add_entities


def create_chore_entities(coordinator: ChoreOpsDataCoordinator, chore_id: str) -> None:
    """Create chore status sensor entities for a newly created chore.

    Called by create_chore service after adding chore to storage.
    Creates AssigneeChoreStatusSensor for each assigned assignee.
    """
    if _async_add_entities_callback is None:
        const.LOGGER.warning("Cannot create chore entities: callback not registered")
        return

    chore_info = coordinator.chores_data.get(chore_id)
    if not chore_info:
        const.LOGGER.warning(
            "Cannot create chore entities: chore %s not found", chore_id
        )
        return

    chore_name = get_item_name_or_log_error(
        "chore", chore_id, chore_info, const.DATA_CHORE_NAME
    )
    if not chore_name:
        return

    assigned_assignees_ids = chore_info.get(const.DATA_CHORE_ASSIGNED_ASSIGNEES, [])
    entities: list[AssigneeChoreStatusSensor] = []

    for assignee_id in assigned_assignees_ids:
        assignee_data: AssigneeData = cast(
            "AssigneeData", coordinator.assignees_data.get(assignee_id) or {}
        )
        assignee_name = get_item_name_or_log_error(
            "assignee", assignee_id, assignee_data, const.DATA_USER_NAME
        )
        if not assignee_name:
            continue

        entities.append(
            AssigneeChoreStatusSensor(
                coordinator,
                coordinator.config_entry,
                assignee_id,
                assignee_name,
                chore_id,
                chore_name,
            )
        )

    if entities:
        _async_add_entities_callback(entities)
        const.LOGGER.debug(
            "Created %d chore status sensors for chore: %s", len(entities), chore_name
        )


def create_reward_entities(
    coordinator: ChoreOpsDataCoordinator, reward_id: str
) -> None:
    """Create reward status sensor entities for a newly created reward.

    Called by create_reward service after adding reward to storage.
    Creates AssigneeRewardStatusSensor for each assignee with gamification enabled.
    """
    if _async_add_entities_callback is None:
        const.LOGGER.warning("Cannot create reward entities: callback not registered")
        return

    reward_info = coordinator.rewards_data.get(reward_id)
    if not reward_info:
        const.LOGGER.warning(
            "Cannot create reward entities: reward %s not found", reward_id
        )
        return

    reward_name = get_item_name_or_log_error(
        "reward", reward_id, reward_info, const.DATA_REWARD_NAME
    )
    if not reward_name:
        return

    entities = []

    for assignee_id, assignee_info in coordinator.assignees_data.items():
        # Skip linked profiles without gamification
        if not should_create_gamification_entities(coordinator, assignee_id):
            continue

        assignee_name = get_item_name_or_log_error(
            "assignee", assignee_id, assignee_info, const.DATA_USER_NAME
        )
        if not assignee_name:
            continue

        entities.append(
            AssigneeRewardStatusSensor(
                coordinator,
                coordinator.config_entry,
                assignee_id,
                assignee_name,
                reward_id,
                reward_name,
            )
        )

    if entities:
        _async_add_entities_callback(entities)
        const.LOGGER.debug(
            "Created %d reward status sensors for reward: %s",
            len(entities),
            reward_name,
        )


# ------------------------------------------------------------------------------------------
class AssigneeChoreStatusSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Sensor for chore status: pending/claimed/approved/etc.
    Tracks individual assignee chore state independent of shared chore global state.
    Provides comprehensive attributes including per-chore statistics (claims, approvals,
    streaks, points earned), chore configuration, and button entity IDs for UI integration.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORE_STATUS_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        chore_id: str,
        chore_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            chore_id: Unique identifier for the chore.
            chore_name: Display name of the chore.
        """

        super().__init__(coordinator)
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._chore_id = chore_id
        self._chore_name = chore_name
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{chore_id}{const.SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR}"
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{assignee_name}{const.SENSOR_KC_EID_MIDFIX_CHORE_STATUS_SENSOR}{chore_name}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_SENSOR_ATTR_CHORE_NAME: chore_name,
        }
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> Any:
        """Return the chore's state based on shared or individual tracking.

        Uses get_chore_status_context() for single bulk fetch instead of
        multiple individual manager calls. State priority is handled by
        the context provider.
        """
        ctx = self.coordinator.chore_manager.get_chore_status_context(
            self._assignee_id, self._chore_id
        )

        return ctx[const.CHORE_CTX_STATE]

    @staticmethod
    def _format_claimed_completed_by(value: str | list[str] | None) -> str | None:
        """Format claimed_by or completed_by value for display.

        Args:
            value: The value from assignee_chore_data (str for INDEPENDENT/SHARED_FIRST,
                   list[str] for SHARED_ALL, or None)

        Returns:
            Formatted string (comma-separated if list) or None
        """
        if value is None:
            return None
        if isinstance(value, list):
            return ", ".join(value) if value else None
        return value

    def _get_due_window_start_iso(self) -> str | None:
        """Get the due window start time as ISO string."""
        due_window_start = self.coordinator.chore_manager.get_due_window_start(
            self._chore_id, self._assignee_id
        )
        return due_window_start.isoformat() if due_window_start else None

    def _get_time_until_due(self) -> str | None:
        """Get human-readable time remaining until due window starts.

        Returns "0d 0h 0m" if window already started (past) or if due window
        is disabled (0), returns same as time_until_overdue.
        """
        chore_info: ChoreData = cast(
            "ChoreData", self.coordinator.chores_data.get(self._chore_id, {})
        )
        due_window_offset = chore_info.get(
            const.DATA_CHORE_DUE_WINDOW_OFFSET, const.DEFAULT_DUE_WINDOW_OFFSET
        )

        # If due window disabled (0), match due date behavior
        if due_window_offset == "0":
            return self._get_time_until_overdue()

        due_window_start = self.coordinator.chore_manager.get_due_window_start(
            self._chore_id, self._assignee_id
        )
        if not due_window_start:
            return None

        # Calculate time until window start
        result = dt_time_until(due_window_start)
        # If already past (None), return 0d 0h 0m
        return result or "0d 0h 0m"

    def _get_time_until_overdue(self) -> str | None:
        """Get human-readable time remaining until due date (overdue).

        Returns "0d 0h 0m" if already overdue (past).
        """
        due_date = self.coordinator.chore_manager.get_due_date(
            self._chore_id, self._assignee_id
        )
        if not due_date:
            return None

        result = dt_time_until(due_date)
        # If already past (None), return 0d 0h 0m
        return result or "0d 0h 0m"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Include points, description, etc. Uses new per-chore data where possible.

        Provides comprehensive chore metadata including:
        - Configuration: points, labels, assigned assignees, recurrence, due date
        - Statistics: all-time and daily claims/approvals/streaks via periods data structure
        - UI Integration: button entity IDs for claim/approve/disapprove actions
        - State tracking: individual vs shared/global state differentiation
        """
        chore_info: ChoreData = cast(
            "ChoreData", self.coordinator.chores_data.get(self._chore_id, {})
        )
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_INDEPENDENT
        )
        global_state = chore_info.get(const.DATA_CHORE_STATE, const.CHORE_STATE_UNKNOWN)

        assigned_assignees_ids = chore_info.get(const.DATA_CHORE_ASSIGNED_ASSIGNEES, [])
        assigned_assignees_names = [
            name
            for k_id in assigned_assignees_ids
            if (name := get_assignee_name_by_id(self.coordinator, k_id))
        ]

        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_INDEPENDENT
        )
        global_state = chore_info.get(const.DATA_CHORE_STATE, const.CHORE_STATE_UNKNOWN)

        assigned_assignees_ids = chore_info.get(const.DATA_CHORE_ASSIGNED_ASSIGNEES, [])
        assigned_assignees_names = [
            name
            for k_id in assigned_assignees_ids
            if (name := get_assignee_name_by_id(self.coordinator, k_id))
        ]

        assignee_chore_data = assignee_info.get(const.DATA_ASSIGNEE_CHORE_DATA, {}).get(
            self._chore_id, {}
        )
        periods = assignee_chore_data.get(const.DATA_ASSIGNEE_CHORE_DATA_PERIODS, {})

        # Use get_period_total for all_time metrics (replaces manual nested navigation)
        period_key_mapping = {
            const.PERIOD_ALL_TIME: const.DATA_ASSIGNEE_CHORE_DATA_PERIODS_ALL_TIME
        }

        claims_count = self.coordinator.stats.get_period_total(
            periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_CLAIMED,
            period_key_mapping=period_key_mapping,
        )
        approvals_count = self.coordinator.stats.get_period_total(
            periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_APPROVED,
            period_key_mapping=period_key_mapping,
        )

        # Get today's and yesterday's ISO dates
        today_local_iso = dt_today_local().isoformat()
        yesterday_local_iso = dt_add_interval(
            today_local_iso,
            interval_unit=const.TIME_UNIT_DAYS,
            delta=-1,
            require_future=False,
            return_type=const.HELPER_RETURN_ISO_DATE,
        )

        daily_periods = periods.get(const.DATA_ASSIGNEE_CHORE_DATA_PERIODS_DAILY, {})

        # Phase 5: Read current streak from assignee_chore_data level (survives retention)
        # Fallback to period data for backward compatibility
        current_streak = (
            assignee_chore_data.get(const.DATA_ASSIGNEE_CHORE_DATA_CURRENT_STREAK)
            or daily_periods.get(today_local_iso, {}).get(
                const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_STREAK_TALLY
            )
            or daily_periods.get(yesterday_local_iso, {}).get(
                const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_STREAK_TALLY, const.DEFAULT_ZERO
            )
        )

        # Phase 5: Read current missed streak from assignee_chore_data level
        current_missed_streak = assignee_chore_data.get(
            const.DATA_ASSIGNEE_CHORE_DATA_CURRENT_MISSED_STREAK, const.DEFAULT_ZERO
        )

        highest_streak = self.coordinator.stats.get_period_total(
            periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_LONGEST_STREAK,
            period_key_mapping=period_key_mapping,
        )
        # Phase 5: Add missed tracking stats
        longest_missed_streak = self.coordinator.stats.get_period_total(
            periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_MISSED_LONGEST_STREAK,
            period_key_mapping=period_key_mapping,
        )
        missed_count = self.coordinator.stats.get_period_total(
            periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_MISSED,
            period_key_mapping=period_key_mapping,
        )
        points_earned = self.coordinator.stats.get_period_total(
            periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_POINTS,
            period_key_mapping=period_key_mapping,
        )
        overdue_count = self.coordinator.stats.get_period_total(
            periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_OVERDUE,
            period_key_mapping=period_key_mapping,
        )
        disapproved_count = self.coordinator.stats.get_period_total(
            periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_DISAPPROVED,
            period_key_mapping=period_key_mapping,
        )
        completed_count = self.coordinator.stats.get_period_total(
            periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_COMPLETED,
            period_key_mapping=period_key_mapping,
        )
        last_longest_streak_date = assignee_chore_data.get(
            const.DATA_ASSIGNEE_CHORE_DATA_LAST_LONGEST_STREAK_ALL_TIME
        )

        # Collect timestamp fields
        last_claimed = assignee_chore_data.get(
            const.DATA_ASSIGNEE_CHORE_DATA_LAST_CLAIMED
        )
        last_approved = assignee_chore_data.get(
            const.DATA_ASSIGNEE_CHORE_DATA_LAST_APPROVED
        )
        # Use unified helper for INDEPENDENT vs SHARED last_completed resolution
        last_completed = self.coordinator.chore_manager.get_chore_last_completed(
            self._chore_id, self._assignee_id
        )
        last_disapproved = assignee_chore_data.get(
            const.DATA_ASSIGNEE_CHORE_DATA_LAST_DISAPPROVED
        )
        last_overdue = assignee_chore_data.get(
            const.DATA_ASSIGNEE_CHORE_DATA_LAST_OVERDUE
        )

        stored_labels = chore_info.get(const.DATA_CHORE_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label)
            for label in cast("list", stored_labels)
        ]

        # Phase 4: Add v0.5.0 rotation and lock status attributes
        # Get current chore state for lock_reason calculation
        ctx = self.coordinator.chore_manager.get_chore_status_context(
            self._assignee_id, self._chore_id
        )
        lock_reason = ctx.get(const.CHORE_CTX_LOCK_REASON)

        # turn_assignee_name: resolve rotation_current_assignee_id to assignee name (if rotation mode)
        turn_assignee_name = None
        if ChoreEngine.is_rotation_mode(chore_info):
            current_turn_assignee_id = chore_info.get(
                const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID
            )
            if current_turn_assignee_id:
                turn_assignee_name = get_assignee_name_by_id(
                    self.coordinator, current_turn_assignee_id
                )

        available_at = ctx.get(const.CHORE_CTX_AVAILABLE_AT)

        attributes = {
            # --- 1. Identity & Meta ---
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_CHORE_STATUS,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_CHORE_NAME: self._chore_name,
            const.ATTR_DESCRIPTION: chore_info.get(
                const.DATA_CHORE_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_ASSIGNED_ASSIGNEES: assigned_assignees_names,
            const.ATTR_LABELS: friendly_labels,
            # --- 2. State info ---
            const.ATTR_GLOBAL_STATE: global_state,
            const.ATTR_CHORE_LOCK_REASON: lock_reason,
            # --- 3. Configuration ---
            const.ATTR_DEFAULT_POINTS: chore_info.get(
                const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_ZERO
            ),
            const.ATTR_COMPLETION_CRITERIA: completion_criteria,
            const.ATTR_CHORE_TURN_ASSIGNEE_NAME: turn_assignee_name,
            const.ATTR_APPROVAL_RESET_TYPE: chore_info.get(
                const.DATA_CHORE_APPROVAL_RESET_TYPE,
                const.DEFAULT_APPROVAL_RESET_TYPE,
            ),
            const.ATTR_RECURRING_FREQUENCY: chore_info.get(
                const.DATA_CHORE_RECURRING_FREQUENCY, const.SENTINEL_NONE_TEXT
            ),
            # For INDEPENDENT chores, use per_assignee_applicable_days; for SHARED, use chore-level
            # Empty list [] means all days are applicable
            const.ATTR_APPLICABLE_DAYS: (
                chore_info.get(const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS, {}).get(
                    self._assignee_id,
                    chore_info.get(const.DATA_CHORE_APPLICABLE_DAYS, []),
                )
                if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
                else chore_info.get(const.DATA_CHORE_APPLICABLE_DAYS, [])
            ),
            # Return None (not translation key) when no due_date - dashboard templates
            # use None to trigger "no_due_date" display text
            const.ATTR_DUE_DATE: (
                due_dt.isoformat()
                if (
                    due_dt := self.coordinator.chore_manager.get_due_date(
                        self._chore_id, self._assignee_id
                    )
                )
                else None
            ),
            const.ATTR_DUE_WINDOW_START: self._get_due_window_start_iso(),
            const.ATTR_CHORE_AVAILABLE_AT: available_at,
            const.ATTR_TIME_UNTIL_DUE: self._get_time_until_due(),
            const.ATTR_TIME_UNTIL_OVERDUE: self._get_time_until_overdue(),
            # --- 4. Statistics (counts) ---
            const.ATTR_CHORE_POINTS_EARNED: points_earned,
            const.ATTR_CHORE_CLAIMS_COUNT: claims_count,
            const.ATTR_CHORE_COMPLETED_COUNT: completed_count,
            const.ATTR_CHORE_APPROVALS_COUNT: approvals_count,
            const.ATTR_CHORE_DISAPPROVED_COUNT: disapproved_count,
            const.ATTR_CHORE_OVERDUE_COUNT: overdue_count,
            # --- 5. Statistics (streaks) ---
            const.ATTR_CHORE_CURRENT_STREAK: current_streak,
            const.ATTR_CHORE_LONGEST_STREAK: highest_streak,
            const.ATTR_CHORE_LAST_LONGEST_STREAK_DATE: last_longest_streak_date,
            # Phase 5: Missed tracking stats
            const.ATTR_CHORE_CURRENT_MISSED_STREAK: current_missed_streak,
            const.ATTR_CHORE_LONGEST_MISSED_STREAK: longest_missed_streak,
            const.ATTR_CHORE_MISSED_COUNT: missed_count,
            const.ATTR_CHORE_LAST_MISSED: assignee_chore_data.get(
                const.DATA_ASSIGNEE_CHORE_DATA_LAST_MISSED
            ),
            # --- 6. Timestamps (last_* events) ---
            const.ATTR_LAST_CLAIMED: last_claimed,
            const.ATTR_LAST_APPROVED: last_approved,
            const.ATTR_LAST_COMPLETED: last_completed,
            const.ATTR_LAST_DISAPPROVED: last_disapproved,
            const.ATTR_LAST_OVERDUE: last_overdue,
            # --- 7. Chore claim/completion tracking (all chore types) ---
            # INDEPENDENT: assignee's own name
            # SHARED_FIRST: winner's name (stored in other assignees' data)
            # SHARED_ALL: list of assignee names (converted to comma-separated string)
            const.ATTR_CLAIMED_BY: self._format_claimed_completed_by(
                assignee_chore_data.get(const.DATA_CHORE_CLAIMED_BY)
            ),
            const.ATTR_COMPLETED_BY: self._format_claimed_completed_by(
                assignee_chore_data.get(const.DATA_CHORE_COMPLETED_BY)
            ),
            # Use coordinator helper to correctly handle INDEPENDENT (per-assignee) vs SHARED (chore-level)
            const.ATTR_APPROVAL_PERIOD_START: self.coordinator.chore_manager.get_approval_period_start(
                self._assignee_id, self._chore_id
            ),
        }

        if (
            chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY)
            == const.FREQUENCY_CUSTOM
        ):
            attributes[const.ATTR_CUSTOM_FREQUENCY_INTERVAL] = chore_info.get(
                const.DATA_CHORE_CUSTOM_INTERVAL
            )
            attributes[const.ATTR_CUSTOM_FREQUENCY_UNIT] = chore_info.get(
                const.DATA_CHORE_CUSTOM_INTERVAL_UNIT
            )

        # Show today's approvals if approval_reset_type allows multiple
        approval_reset_type = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE, const.DEFAULT_APPROVAL_RESET_TYPE
        )
        if approval_reset_type in (
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
            const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
            const.APPROVAL_RESET_UPON_COMPLETION,
        ):
            today_approvals = (
                periods.get(const.DATA_ASSIGNEE_CHORE_DATA_PERIODS_DAILY, {})
                .get(dt_today_local().isoformat(), {})
                .get(const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_APPROVED, const.DEFAULT_ZERO)
            )
            attributes[const.ATTR_CHORE_APPROVALS_TODAY] = today_approvals

        # Add can_claim and can_approve computed attributes using coordinator helpers
        can_claim, _ = self.coordinator.chore_manager.can_claim_chore(
            self._assignee_id, self._chore_id
        )
        can_approve, _ = self.coordinator.chore_manager.can_approve_chore(
            self._assignee_id, self._chore_id
        )
        attributes[const.ATTR_CAN_CLAIM] = can_claim
        attributes[const.ATTR_CAN_APPROVE] = can_approve

        # Add claim, approve, disapprove button entity ids to attributes for direct ui access.
        button_types = [
            (
                const.BUTTON_KC_UID_SUFFIX_APPROVE,
                const.ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID,
            ),
            (
                const.BUTTON_KC_UID_SUFFIX_DISAPPROVE,
                const.ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID,
            ),
            (const.BUTTON_KC_UID_SUFFIX_CLAIM, const.ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID),
        ]
        button_entity_ids = {}
        try:
            entity_registry = async_get(self.hass)
            for suffix, attr_name in button_types:
                unique_id = f"{self._entry.entry_id}_{self._assignee_id}_{self._chore_id}{suffix}"
                entity_id = entity_registry.async_get_entity_id(
                    "button", const.DOMAIN, unique_id
                )
                button_entity_ids[attr_name] = entity_id
        except (KeyError, ValueError, AttributeError):
            for _, attr_name in button_types:
                button_entity_ids[attr_name] = None

        # Add button entity IDs to the attributes
        attributes.update(button_entity_ids)

        return attributes

    @property
    def icon(self) -> str | None:
        """Return the icon based on chore state.

        Maps chore status to an appropriate Material Design Icon:
        - pending: checkbox-blank (not started)
        - claimed: clipboard-check (assignee claims)
        - approved: checkbox-marked-circle (approver approves)
        - overdue: alert-circle (not done in time)
        - fallback: chore's custom icon or default
        """
        chore_info: ChoreData = cast(
            "ChoreData", self.coordinator.chores_data.get(self._chore_id, {})
        )

        # Fallback: use chore's custom icon or None for icons.json
        return chore_info.get(const.DATA_CHORE_ICON) or None


# ------------------------------------------------------------------------------------------
class AssigneePointsSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Sensor for a assignee's total points balance.

    Primary currency sensor - tracks current spendable points balance. Uses
    MEASUREMENT state class for graphing. Exposes comprehensive point statistics
    in attributes including earnings, spending, bonuses, and penalties.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_ASSIGNEE_POINTS_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        points_label: str,
        points_icon: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            points_label: User-configured label for points (e.g., "Points", "Stars").
            points_icon: User-configured icon for points display.
        """

        super().__init__(coordinator)
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._points_label = points_label
        self._points_icon = points_icon
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_SENSOR}"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_SENSOR_ATTR_POINTS: self._points_label,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # Legacy entity_id template kept as a comment-only reference
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> Any:
        """Return the assignee's total points."""
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )
        return assignee_info.get(const.DATA_ASSIGNEE_POINTS, const.DEFAULT_ZERO)

    @property
    def native_unit_of_measurement(self):
        """Return the points label."""
        return self._points_label or const.LABEL_POINTS

    @property
    def icon(self) -> str | None:
        """Return custom icon or None for icons.json fallback.

        Returns user-configured points icon if set, otherwise None to allow
        icons.json to provide range-based icon based on current points.
        """
        return self._points_icon or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose all point stats as attributes.

        Phase 7G.1: All point data now comes from two sources:
        1. Persistent all_time stats from point_data.periods.all_time.all_time
           (earned, spent, by_source, highest_balance)
        2. Temporal stats from PRES_* cache (today, week, month, year)

        Net values are DERIVED (earned + spent), never stored.

        Attribute order: common fields first (purpose, assignee_name),
        then all point_stat_* fields sorted alphabetically.
        """
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )

        # Common fields first (consistent ordering across sensors)
        attributes: dict[str, Any] = {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_POINTS,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_POINTS_MULTIPLIER: assignee_info.get(
                const.DATA_ASSIGNEE_POINTS_MULTIPLIER,
                const.DEFAULT_ASSIGNEE_POINTS_MULTIPLIER,
            ),
        }

        # === Phase 7G.1: Get persistent all_time stats using get_period_total ===
        point_periods: dict[str, Any] = assignee_info.get(
            const.DATA_ASSIGNEE_POINT_PERIODS, {}
        )
        period_key_mapping = {
            const.PERIOD_ALL_TIME: const.DATA_ASSIGNEE_POINT_PERIODS_ALL_TIME
        }

        # Extract all_time values using get_period_total
        earned_all_time = self.coordinator.stats.get_period_total(
            point_periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_POINT_PERIOD_POINTS_EARNED,
            period_key_mapping=period_key_mapping,
        )
        spent_all_time = self.coordinator.stats.get_period_total(
            point_periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_POINT_PERIOD_POINTS_SPENT,
            period_key_mapping=period_key_mapping,
        )
        highest_balance = self.coordinator.stats.get_period_total(
            point_periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_POINT_PERIOD_HIGHEST_BALANCE,
            period_key_mapping=period_key_mapping,
        )

        # Get by_source dict (nested structure requires manual access)
        all_time_periods: dict[str, Any] = point_periods.get(
            const.DATA_ASSIGNEE_POINT_PERIODS_ALL_TIME, {}
        )
        all_time_entry: dict[str, Any] = all_time_periods.get(const.PERIOD_ALL_TIME, {})
        by_source_all_time = dict(
            all_time_entry.get(const.DATA_ASSIGNEE_POINT_PERIOD_BY_SOURCE, {})
        )

        # Add persistent all_time stats with backward-compatible attribute names
        attributes[f"{const.ATTR_PREFIX_POINT_STAT}points_earned_all_time"] = (
            earned_all_time
        )
        attributes[f"{const.ATTR_PREFIX_POINT_STAT}highest_balance_all_time"] = (
            highest_balance
        )
        attributes[f"{const.ATTR_PREFIX_POINT_STAT}points_spent_all_time"] = (
            spent_all_time
        )
        attributes[f"{const.ATTR_PREFIX_POINT_STAT}points_net_all_time"] = round(
            earned_all_time + spent_all_time, const.DATA_FLOAT_PRECISION
        )
        attributes[f"{const.ATTR_PREFIX_POINT_STAT}points_by_source_all_time"] = (
            by_source_all_time
        )

        # === Add temporal stats from presentation cache ===
        # PRES_KID_* keys map to backward-compatible names by stripping "pres_assignee_" prefix
        pres_stats = self.coordinator.statistics_manager.get_stats(self._assignee_id)
        for pres_key, value in pres_stats.items():
            if pres_key.startswith(
                ("pres_assignee_points_", "pres_assignee_avg_points_")
            ):
                # Strip "pres_assignee_" prefix to get backward-compatible attribute name
                attr_key = pres_key.removeprefix("pres_assignee_")
                attributes[f"{const.ATTR_PREFIX_POINT_STAT}{attr_key}"] = value

        return attributes


# ------------------------------------------------------------------------------------------
class AssigneeChoresSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Sensor showing chores count with all chore statistics as attributes.

    This sensor provides a central view of all chore-related metrics for a assignee,
    similar to how AssigneePointsSensor works for points tracking.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORES_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
        """
        super().__init__(coordinator)
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._attr_unique_id = (
            f"{entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_CHORES_SENSOR}"
        )
        # Icon defined in icons.json
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # Legacy entity_id template kept as a comment-only reference
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> Any:
        """Return the total number of chores completed by the assignee."""
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )
        # Use get_period_total for all_time approved count
        chore_periods: dict[str, Any] = cast(
            "dict[str, Any]", assignee_info.get(const.DATA_ASSIGNEE_CHORE_PERIODS, {})
        )
        period_key_mapping = {
            const.PERIOD_ALL_TIME: const.DATA_ASSIGNEE_CHORE_DATA_PERIODS_ALL_TIME
        }
        return self.coordinator.stats.get_period_total(
            chore_periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_APPROVED,
            period_key_mapping=period_key_mapping,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose all chore stats as attributes.

        Dynamically includes all DATA_KID_CHORE_STATS fields prefixed with
        'chore_stat_' for frontend access (approved, claimed, overdue counts, etc.).

        Phase 7.5: Merges persistent stats (all_time, streak) from storage
        with temporal stats (today, week, month, year) from presentation cache.
        Temporal stats use PRES_* keys mapped to backward-compatible attribute names.

        Attribute order organized into logical groups for better UX:
        1. Identity (purpose, assignee_name)
        2. Current Status (current_due_today, current_claimed, current_approved, current_overdue)
        3. Today (approved_today, claimed_today, missed_today, completed_today, points_today)
        4. This Week (approved_week, claimed_week, missed_week, completed_week, points_week)
        5. This Month (approved_month, claimed_month, missed_month, completed_month, points_month)
        6. This Year (approved_year, claimed_year, missed_year, completed_year, points_year)
        7. All-Time (approved_all_time, claimed_all_time, missed_all_time, completed_all_time,
                 disapproved_all_time, overdue_all_time, points_all_time,
                 longest_streak, longest_missed_streak)
        """
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )
        # Use get_period_total for persistent all-time stats
        chore_periods: dict[str, Any] = cast(
            "dict[str, Any]", assignee_info.get(const.DATA_ASSIGNEE_CHORE_PERIODS, {})
        )
        period_key_mapping = {
            const.PERIOD_ALL_TIME: const.DATA_ASSIGNEE_CHORE_DATA_PERIODS_ALL_TIME
        }

        # Get temporal stats from presentation cache
        pres_stats = self.coordinator.statistics_manager.get_stats(self._assignee_id)

        # Build unified lookup dict for easier access
        all_stats: dict[str, Any] = {}

        # Add persistent all-time stats using get_period_total
        all_stats["approved_all_time"] = self.coordinator.stats.get_period_total(
            chore_periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_APPROVED,
            period_key_mapping=period_key_mapping,
        )
        all_stats["claimed_all_time"] = self.coordinator.stats.get_period_total(
            chore_periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_CLAIMED,
            period_key_mapping=period_key_mapping,
        )
        all_stats["missed_all_time"] = self.coordinator.stats.get_period_total(
            chore_periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_MISSED,
            period_key_mapping=period_key_mapping,
        )
        all_stats["completed_all_time"] = self.coordinator.stats.get_period_total(
            chore_periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_COMPLETED,
            period_key_mapping=period_key_mapping,
        )
        all_stats["points_all_time"] = self.coordinator.stats.get_period_total(
            chore_periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_POINTS,
            period_key_mapping=period_key_mapping,
        )
        all_stats["longest_streak"] = self.coordinator.stats.get_period_total(
            chore_periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_LONGEST_STREAK,
            period_key_mapping=period_key_mapping,
        )
        all_stats["longest_missed_streak"] = self.coordinator.stats.get_period_total(
            chore_periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_MISSED_LONGEST_STREAK,
            period_key_mapping=period_key_mapping,
        )

        # Add temporal stats (strip PRES prefixes)
        # NOTE: all_time stats are storage-only, not in cache (can't calculate due to retention)
        for pres_key, value in pres_stats.items():
            if pres_key.startswith("pres_assignee_chores_"):
                attr_key = pres_key.removeprefix(
                    "pres_assignee_chores_"
                )  # "pres_assignee_chores_approved_today" -> "approved_today"
                # Skip all_time keys - they come from storage only
                if not attr_key.endswith("_all_time"):
                    all_stats[attr_key] = value
            elif pres_key.startswith("pres_assignee_top_chores_"):
                attr_key = pres_key.removeprefix(
                    "pres_assignee_"
                )  # "pres_assignee_top_chores_xxx" -> "top_chores_xxx"
                all_stats[attr_key] = value

        # Build attributes in logical order
        attributes: dict[str, Any] = {}

        # Group 1: Identity
        attributes[const.ATTR_PURPOSE] = const.TRANS_KEY_PURPOSE_CHORES
        attributes[const.ATTR_ASSIGNEE_NAME] = self._assignee_name

        # Group 2: Current Status
        for key in [
            "current_due_today",
            "current_claimed",
            "current_approved",
            "current_overdue",
        ]:
            if key in all_stats:
                attributes[f"{const.ATTR_PREFIX_CHORE_STAT}{key}"] = all_stats[key]

        # Group 3: Today
        for key in [
            "approved_today",
            "claimed_today",
            "missed_today",
            "completed_today",
            "points_today",
        ]:
            if key in all_stats:
                attributes[f"{const.ATTR_PREFIX_CHORE_STAT}{key}"] = all_stats[key]

        # Group 4: This Week
        for key in [
            "approved_week",
            "claimed_week",
            "missed_week",
            "completed_week",
            "points_week",
            "avg_per_day_week",
        ]:
            if key in all_stats:
                attributes[f"{const.ATTR_PREFIX_CHORE_STAT}{key}"] = all_stats[key]

        # Group 5: This Month
        for key in [
            "approved_month",
            "claimed_month",
            "missed_month",
            "completed_month",
            "points_month",
            "avg_per_day_month",
        ]:
            if key in all_stats:
                attributes[f"{const.ATTR_PREFIX_CHORE_STAT}{key}"] = all_stats[key]

        # Group 6: This Year
        for key in [
            "approved_year",
            "claimed_year",
            "missed_year",
            "completed_year",
            "points_year",
            "avg_per_day_year",
        ]:
            if key in all_stats:
                attributes[f"{const.ATTR_PREFIX_CHORE_STAT}{key}"] = all_stats[key]

        # Group 7: All-Time
        for key in [
            "approved_all_time",
            "claimed_all_time",
            "missed_all_time",
            "completed_all_time",
            "disapproved_all_time",
            "overdue_all_time",
            "points_all_time",
            "longest_streak",
            "longest_missed_streak",
        ]:
            if key in all_stats:
                attributes[f"{const.ATTR_PREFIX_CHORE_STAT}{key}"] = all_stats[key]

        # Group 8: Top Chores (if present)
        for key in sorted([k for k in all_stats if k.startswith("top_chores_")]):
            attributes[f"{const.ATTR_PREFIX_CHORE_STAT}{key}"] = all_stats[key]

        return attributes


# ------------------------------------------------------------------------------------------
class AssigneeBadgesSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Sensor that returns the highest cumulative badge a assignee currently has,
    and calculates how many points are needed to reach the next cumulative badge.

    Tracks cumulative badge progression including maintenance requirements, grace periods,
    baseline/cycle points, and provides comprehensive badge metadata in attributes.
    Icon dynamically reflects the current highest badge.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_ASSIGNEE_BADGES_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
        """

        super().__init__(coordinator)
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_BADGES_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # Legacy entity_id template kept as a comment-only reference
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> str:
        """Return the badge name of the highest-threshold badge the assignee has earned."""
        # Phase 3A: Use computed progress instead of storage read
        cumulative_badge_progress_info = (
            self.coordinator.gamification_manager.get_cumulative_badge_progress(
                self._assignee_id
            )
        )
        return str(
            cumulative_badge_progress_info.get(
                const.CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_NAME,
                const.SENTINEL_NONE_TEXT,
            )
        )

    @property
    def icon(self):
        """Return the icon for the highest badge."""
        # Phase 3A: Use computed progress instead of storage read
        cumulative_badge_progress_info = (
            self.coordinator.gamification_manager.get_cumulative_badge_progress(
                self._assignee_id
            )
        )
        highest_badge_id = cumulative_badge_progress_info.get(
            const.CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_ID,
            const.SENTINEL_NONE_TEXT,
        )
        highest_badge_info: BadgeData = cast(
            "BadgeData", self.coordinator.badges_data.get(highest_badge_id, {})
        )
        return highest_badge_info.get(const.DATA_BADGE_ICON) or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Provide additional details about the highest cumulative badge.

        Phase 3A: Use computed progress instead of storage reads. All derived
        fields (current/next/highest badge info) are computed on-read, only
        state fields (status, cycle_points, dates) read from storage.
        """
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )

        # Phase 3A: Get computed progress (all derived fields calculated here)
        cumulative_badge_progress_info = (
            self.coordinator.gamification_manager.get_cumulative_badge_progress(
                self._assignee_id
            )
        )

        # Extract computed fields from progress dict (using CUMULATIVE_BADGE_PROGRESS_* constants)
        current_badge_id = cumulative_badge_progress_info.get(
            const.CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID, const.SENTINEL_NONE_TEXT
        )
        current_badge_name = cumulative_badge_progress_info.get(
            const.CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_NAME,
            const.SENTINEL_NONE_TEXT,
        )
        highest_earned_badge_id = cumulative_badge_progress_info.get(
            const.CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_ID,
            const.SENTINEL_NONE_TEXT,
        )
        highest_earned_badge_name = cumulative_badge_progress_info.get(
            const.CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_NAME,
            const.SENTINEL_NONE_TEXT,
        )
        next_higher_badge_id = cumulative_badge_progress_info.get(
            const.CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_ID,
            const.SENTINEL_NONE_TEXT,
        )
        next_higher_badge_name = cumulative_badge_progress_info.get(
            const.CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_NAME,
            const.SENTINEL_NONE_TEXT,
        )
        next_lower_badge_id = cumulative_badge_progress_info.get(
            const.CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_ID,
            const.SENTINEL_NONE_TEXT,
        )
        next_lower_badge_name = cumulative_badge_progress_info.get(
            const.CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_NAME,
            const.SENTINEL_NONE_TEXT,
        )
        badge_status = cumulative_badge_progress_info.get(
            const.CUMULATIVE_BADGE_PROGRESS_STATUS, const.SENTINEL_NONE_TEXT
        )
        highest_badge_threshold_value = cumulative_badge_progress_info.get(
            const.CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_THRESHOLD,
            const.DEFAULT_ZERO,
        )
        points_to_next_badge = cumulative_badge_progress_info.get(
            const.CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_POINTS_NEEDED,
            const.DEFAULT_ZERO,
        )
        cycle_points = cumulative_badge_progress_info.get(
            const.CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS, const.DEFAULT_ZERO
        )
        grace_end_date = cumulative_badge_progress_info.get(
            const.CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE, None
        )

        # Defensive: Handle badges_earned as either dict (v42+) or list (legacy v41)
        badges_earned_data = assignee_info.get(const.DATA_ASSIGNEE_BADGES_EARNED, {})
        if isinstance(badges_earned_data, dict):
            # V42+ format: dict of badge_id -> badge_info
            earned_badge_list = [
                badge_info.get(const.DATA_ASSIGNEE_BADGES_EARNED_NAME)
                for badge_info in badges_earned_data.values()
            ]
        elif isinstance(badges_earned_data, list):
            # Legacy v41 format: list of badge name strings (e.g., ["Badge 1", "Badge 2"])
            earned_badge_list = badges_earned_data
        else:
            # Fallback: empty list
            earned_badge_list = []

        maintenance_badge_id = (
            highest_earned_badge_id
            if highest_earned_badge_id
            and highest_earned_badge_id != const.SENTINEL_NONE_TEXT
            else current_badge_id
        )

        # Use current_badge_id from computed progress to look up badge details
        current_badge_info: BadgeData = cast(
            "BadgeData", self.coordinator.badges_data.get(current_badge_id, {})
        )

        # Maintenance metadata should always come from highest earned badge context
        maintenance_badge_info: BadgeData = cast(
            "BadgeData", self.coordinator.badges_data.get(maintenance_badge_id, {})
        )

        stored_labels = current_badge_info.get(const.DATA_BADGE_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label)
            for label in cast("list", stored_labels)
        ]

        # Get last awarded date and award count for the highest earned badge (if any)
        # Defensive: Handle badges_earned as either dict (v42+) or list (legacy v41)
        badges_earned_data = assignee_info.get(const.DATA_ASSIGNEE_BADGES_EARNED, {})
        if isinstance(badges_earned_data, dict):
            badge_earned = badges_earned_data.get(maintenance_badge_id, {})
        else:
            # Legacy v41: list format, no per-badge metadata
            badge_earned = {}

        last_awarded_date = badge_earned.get(
            const.DATA_ASSIGNEE_BADGES_EARNED_LAST_AWARDED, const.SENTINEL_NONE
        )
        # Phase 4B: Read award_count from periods.all_time.all_time (Lean Item pattern)
        periods = badge_earned.get(const.DATA_ASSIGNEE_BADGES_EARNED_PERIODS, {})
        period_key_mapping = {
            const.PERIOD_ALL_TIME: const.DATA_ASSIGNEE_BADGES_EARNED_PERIODS_ALL_TIME
        }
        award_count = self.coordinator.stats.get_period_total(
            periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_BADGES_EARNED_AWARD_COUNT,
            period_key_mapping=period_key_mapping,
        )

        extra_attrs = {}
        # Add description if present
        description = current_badge_info.get(const.DATA_BADGE_DESCRIPTION, "")
        if description:
            extra_attrs[const.DATA_BADGE_DESCRIPTION] = description

        # Phase 3A: No baseline field in storage - removed
        extra_attrs[const.ATTR_BADGE_CUMULATIVE_CYCLE_POINTS] = cycle_points

        # Read maintenance_end_date from storage (state field)
        assignee_cumulative_progress_storage = assignee_info.get(
            const.DATA_ASSIGNEE_CUMULATIVE_BADGE_PROGRESS, {}
        )
        maintenance_end_date = assignee_cumulative_progress_storage.get(
            const.DATA_ASSIGNEE_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE, None
        )

        target_info = maintenance_badge_info.get(const.DATA_BADGE_TARGET, {})

        # maintenance_rules is an int inside target_info
        maintenance_rules = target_info.get(const.DATA_BADGE_MAINTENANCE_RULES, 0)
        maintenance_end_date = cumulative_badge_progress_info.get(
            const.DATA_ASSIGNEE_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE, None
        )
        if maintenance_rules > 0 and maintenance_end_date:
            extra_attrs[const.ATTR_BADGE_CUMULATIVE_MAINTENANCE_END_DATE] = (
                maintenance_end_date
            )
            extra_attrs[const.ATTR_BADGE_CUMULATIVE_GRACE_END_DATE] = grace_end_date
            extra_attrs[const.ATTR_BADGE_CUMULATIVE_MAINTENANCE_POINTS_REQUIRED] = (
                maintenance_rules
            )
            points_to_maintenance = max(0, maintenance_rules - cycle_points)
            extra_attrs[const.ATTR_BADGE_CUMULATIVE_POINTS_TO_MAINTENANCE] = (
                points_to_maintenance
            )

        # Add reset_schedule fields if recurring_frequency is present
        reset_schedule = maintenance_badge_info.get(const.DATA_BADGE_RESET_SCHEDULE, {})
        if reset_schedule:
            extra_attrs[const.DATA_BADGE_RESET_SCHEDULE] = reset_schedule

        # Add Target fields if present
        if target_info:
            extra_attrs[const.DATA_BADGE_TARGET] = target_info

        # Add awards if present
        awards_info = maintenance_badge_info.get(const.DATA_BADGE_AWARDS, {})
        if awards_info:
            extra_attrs[const.DATA_BADGE_AWARDS] = awards_info

        # Look up SystemBadgeSensor entity IDs for current, next_higher, next_lower badges
        # These allow the dashboard to directly reference badge definition sensors
        badge_eid_map = [
            (current_badge_id, const.ATTR_CURRENT_BADGE_EID),
            (highest_earned_badge_id, const.ATTR_HIGHEST_EARNED_BADGE_EID),
            (next_higher_badge_id, const.ATTR_NEXT_HIGHER_BADGE_EID),
            (next_lower_badge_id, const.ATTR_NEXT_LOWER_BADGE_EID),
        ]
        badge_entity_ids: dict[str, str | None] = {}
        try:
            entity_registry = async_get(self.hass)
            for badge_id, attr_name in badge_eid_map:
                # Skip if badge_id is None/sentinel
                if not badge_id or badge_id == const.SENTINEL_NONE_TEXT:
                    badge_entity_ids[attr_name] = None
                    continue
                # Look up the SystemBadgeSensor entity ID (badge definition)
                unique_id = f"{self._entry.entry_id}_{badge_id}{const.SENSOR_KC_UID_SUFFIX_BADGE_SENSOR}"
                entity_id = entity_registry.async_get_entity_id(
                    "sensor", const.DOMAIN, unique_id
                )
                badge_entity_ids[attr_name] = entity_id
        except (KeyError, ValueError, AttributeError):
            for _, attr_name in badge_eid_map:
                badge_entity_ids[attr_name] = None

        return {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_ASSIGNEE_BADGES,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_LABELS: friendly_labels,
            const.ATTR_ALL_EARNED_BADGES: earned_badge_list,
            const.ATTR_HIGHEST_BADGE_THRESHOLD_VALUE: highest_badge_threshold_value,
            const.ATTR_POINTS_TO_NEXT_BADGE: points_to_next_badge,
            # Current badge (highest earned or target if none earned)
            const.ATTR_CURRENT_BADGE_NAME: current_badge_name,
            const.ATTR_CURRENT_BADGE_EID: badge_entity_ids.get(
                const.ATTR_CURRENT_BADGE_EID
            ),
            # Highest earned badge
            const.ATTR_HIGHEST_EARNED_BADGE_NAME: highest_earned_badge_name,
            const.ATTR_HIGHEST_EARNED_BADGE_EID: badge_entity_ids.get(
                const.ATTR_HIGHEST_EARNED_BADGE_EID
            ),
            # Next higher badge (goal/target)
            const.ATTR_NEXT_HIGHER_BADGE_NAME: next_higher_badge_name,
            const.ATTR_NEXT_HIGHER_BADGE_EID: badge_entity_ids.get(
                const.ATTR_NEXT_HIGHER_BADGE_EID
            ),
            # Next lower badge (previously earned)
            const.ATTR_NEXT_LOWER_BADGE_NAME: next_lower_badge_name,
            const.ATTR_NEXT_LOWER_BADGE_EID: badge_entity_ids.get(
                const.ATTR_NEXT_LOWER_BADGE_EID
            ),
            const.ATTR_BADGE_STATUS: badge_status,
            const.DATA_ASSIGNEE_BADGES_EARNED_LAST_AWARDED: last_awarded_date,
            const.DATA_ASSIGNEE_BADGES_EARNED_AWARD_COUNT: award_count,
            **extra_attrs,
        }


# ------------------------------------------------------------------------------------------
class AssigneeBadgeProgressSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Badge Progress Sensor for a assignee's progress on a specific non-cumulative badge.

    Tracks individual badge progress as percentage (0-100). Supports achievement,
    challenge, daily, and periodic badge types. Provides comprehensive progress
    metadata including criteria met, tracked chores, start/end dates, and award history.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_ASSIGNEE_BADGE_PROGRESS_SENSOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        badge_id: str,
        badge_name: str,
    ):
        """Initialize the AssigneeBadgeProgressSensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            badge_id: Unique identifier for the badge.
            badge_name: Display name of the badge.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._badge_id = badge_id
        self._badge_name = badge_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{badge_id}{const.SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_SENSOR_ATTR_BADGE_NAME: badge_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{assignee_name}{const.SENSOR_KC_EID_MIDFIX_BADGE_PROGRESS_SENSOR}{badge_name}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> float:
        """Return the badge's overall progress as a percentage."""
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )
        badge_progress = assignee_info.get(const.DATA_ASSIGNEE_BADGE_PROGRESS, {}).get(
            self._badge_id, {}
        )
        progress = badge_progress.get(
            const.DATA_ASSIGNEE_BADGE_PROGRESS_OVERALL_PROGRESS, 0.0
        )
        return round(progress * 100, const.DATA_FLOAT_PRECISION)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the badge progress details as attributes."""
        badge_info: BadgeData = cast(
            "BadgeData", self.coordinator.badges_data.get(self._badge_id, {})
        )
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )
        badge_progress = assignee_info.get(const.DATA_ASSIGNEE_BADGE_PROGRESS, {}).get(
            self._badge_id, {}
        )

        # Defensive: Handle badges_earned as either dict (v42+) or list (legacy v41)
        badges_earned_data = assignee_info.get(const.DATA_ASSIGNEE_BADGES_EARNED, {})
        if isinstance(badges_earned_data, dict):
            badge_earned = badges_earned_data.get(self._badge_id, {})
        else:
            # Legacy v41: list format, no per-badge metadata
            badge_earned = {}

        last_awarded_date = badge_earned.get(
            const.DATA_ASSIGNEE_BADGES_EARNED_LAST_AWARDED, const.SENTINEL_NONE
        )
        # Phase 4B: Read award_count from periods.all_time.all_time (Lean Item pattern)
        periods = badge_earned.get(const.DATA_ASSIGNEE_BADGES_EARNED_PERIODS, {})
        period_key_mapping = {
            const.PERIOD_ALL_TIME: const.DATA_ASSIGNEE_BADGES_EARNED_PERIODS_ALL_TIME
        }
        award_count = self.coordinator.stats.get_period_total(
            periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_BADGES_EARNED_AWARD_COUNT,
            period_key_mapping=period_key_mapping,
        )

        # Build a dictionary with only the requested fields
        attributes = {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_BADGE_PROGRESS,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_BADGE_NAME: badge_progress.get(
                const.DATA_ASSIGNEE_BADGE_PROGRESS_NAME
            ),
            const.DATA_ASSIGNEE_BADGE_PROGRESS_TYPE: badge_progress.get(
                const.DATA_ASSIGNEE_BADGE_PROGRESS_TYPE
            ),
            const.DATA_ASSIGNEE_BADGE_PROGRESS_STATUS: badge_progress.get(
                const.DATA_ASSIGNEE_BADGE_PROGRESS_STATUS
            ),
            const.DATA_ASSIGNEE_BADGE_PROGRESS_TARGET_TYPE: badge_progress.get(
                const.DATA_ASSIGNEE_BADGE_PROGRESS_TARGET_TYPE
            ),
            const.DATA_ASSIGNEE_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE: badge_progress.get(
                const.DATA_ASSIGNEE_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE
            ),
            const.DATA_ASSIGNEE_BADGE_PROGRESS_RECURRING_FREQUENCY: badge_progress.get(
                const.DATA_ASSIGNEE_BADGE_PROGRESS_RECURRING_FREQUENCY
            ),
            const.DATA_ASSIGNEE_BADGE_PROGRESS_START_DATE: badge_progress.get(
                const.DATA_ASSIGNEE_BADGE_PROGRESS_START_DATE
            ),
            const.DATA_ASSIGNEE_BADGE_PROGRESS_END_DATE: badge_progress.get(
                const.DATA_ASSIGNEE_BADGE_PROGRESS_END_DATE
            ),
            const.DATA_ASSIGNEE_BADGE_PROGRESS_LAST_UPDATE_DAY: badge_progress.get(
                const.DATA_ASSIGNEE_BADGE_PROGRESS_LAST_UPDATE_DAY
            ),
            const.DATA_ASSIGNEE_BADGE_PROGRESS_OVERALL_PROGRESS: badge_progress.get(
                const.DATA_ASSIGNEE_BADGE_PROGRESS_OVERALL_PROGRESS
            ),
            const.DATA_ASSIGNEE_BADGE_PROGRESS_CRITERIA_MET: badge_progress.get(
                const.DATA_ASSIGNEE_BADGE_PROGRESS_CRITERIA_MET
            ),
            const.DATA_ASSIGNEE_BADGES_EARNED_LAST_AWARDED: last_awarded_date,
            const.DATA_ASSIGNEE_BADGES_EARNED_AWARD_COUNT: award_count,
        }

        attributes[const.ATTR_DESCRIPTION] = str(
            badge_info.get(const.DATA_BADGE_DESCRIPTION, const.SENTINEL_EMPTY)
        )

        # Convert tracked chore IDs to friendly names and add to attributes
        tracked_chore_ids_raw: list[str] | Any = attributes.get(
            const.DATA_ASSIGNEE_BADGE_PROGRESS_TRACKED_CHORES, []
        )
        tracked_chore_ids: list[str] = (
            tracked_chore_ids_raw if isinstance(tracked_chore_ids_raw, list) else []
        )
        if tracked_chore_ids:
            chore_names: list[str] = [
                str(
                    cast(
                        "ChoreData", self.coordinator.chores_data.get(chore_id, {})
                    ).get(const.DATA_CHORE_NAME)
                    or chore_id
                )
                for chore_id in tracked_chore_ids
            ]
            attributes[const.DATA_ASSIGNEE_BADGE_PROGRESS_TRACKED_CHORES] = cast(
                "str", chore_names
            )

        return attributes

    @property
    def icon(self) -> str | None:
        """Return the icon for the badge."""
        badge_info: BadgeData = cast(
            "BadgeData", self.coordinator.badges_data.get(self._badge_id, {})
        )
        icon = badge_info.get(const.DATA_BADGE_ICON)
        return str(icon) if icon else None


# ------------------------------------------------------------------------------------------
class SystemBadgeSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Sensor representing a single badge in ChoreOps.

    Provides system-wide badge configuration and metadata including badge type
    (cumulative, achievement, challenge, daily, periodic, special), target values,
    associated achievements/challenges, tracked chores, and award items (points,
    rewards, bonuses, penalties, multipliers). Tracks which assignees have earned the
    badge and which assignees are assigned to it. Supports occasion-based badges for
    special events.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_BADGE_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        badge_id: str,
        badge_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            badge_id: Unique identifier for the badge.
            badge_name: Display name of the badge.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._badge_id = badge_id
        self._badge_name = badge_name
        self._attr_unique_id = (
            f"{entry.entry_id}_{badge_id}{const.SENSOR_KC_UID_SUFFIX_BADGE_SENSOR}"
        )
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_BADGE_NAME: badge_name
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{badge_name}{const.SENSOR_KC_EID_SUFFIX_BADGE_SENSOR}"
        self._attr_device_info = create_system_device_info(entry)

    @property
    def native_value(self) -> int:
        """State: number of assignees who have earned this badge."""
        badge_info: BadgeData = cast(
            "BadgeData", self.coordinator.badges_data.get(self._badge_id, {})
        )
        assignees_earned_ids = badge_info.get(const.DATA_BADGE_EARNED_BY, [])
        return len(assignees_earned_ids)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Full badge info, including per-assignee earned stats and periods."""
        badge_info: BadgeData = cast(
            "BadgeData", self.coordinator.badges_data.get(self._badge_id, {})
        )
        attributes: dict[str, Any] = {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_BADGE,
            const.ATTR_BADGE_NAME: self._badge_name,
            const.ATTR_DESCRIPTION: badge_info.get(
                const.DATA_BADGE_DESCRIPTION, const.SENTINEL_EMPTY
            ),
        }
        attributes[const.ATTR_BADGE_TYPE] = badge_info.get(
            const.DATA_BADGE_TYPE, const.BADGE_TYPE_CUMULATIVE
        )
        attributes[const.ATTR_LABELS] = [
            get_friendly_label(self.hass, label)
            for label in cast("list", badge_info.get(const.DATA_BADGE_LABELS, []))
        ]
        # Per-assignee earned stats
        assignees_earned_ids = badge_info.get(const.DATA_BADGE_EARNED_BY, [])
        assignees_earned = []
        for assignee_id in cast("list", assignees_earned_ids):
            assignee_info = self.coordinator.assignees_data.get(assignee_id)
            if not assignee_info:
                continue
            assignees_earned.append(
                assignee_info.get(const.DATA_USER_NAME, assignee_id)
            )

        attributes[const.ATTR_ASSIGNEES_EARNED] = assignees_earned

        # Per-assignee assigned stats
        assigned_assignees_ids = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
        assigned_assignees = []
        for assignee_id in assigned_assignees_ids:
            assignee_info = self.coordinator.assignees_data.get(assignee_id)
            if not assignee_info:
                continue
            assigned_assignees.append(
                assignee_info.get(const.DATA_USER_NAME, assignee_id)
            )

        attributes[const.ATTR_ASSIGNEES_ASSIGNED] = assigned_assignees

        attributes[const.ATTR_TARGET] = badge_info.get(const.DATA_BADGE_TARGET, None)
        attributes[const.ATTR_ASSOCIATED_ACHIEVEMENT] = badge_info.get(
            const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT, None
        )
        attributes[const.ATTR_ASSOCIATED_CHALLENGE] = badge_info.get(
            const.DATA_BADGE_ASSOCIATED_CHALLENGE, None
        )
        occasion_type = badge_info.get(const.DATA_BADGE_OCCASION_TYPE, None)
        if occasion_type:
            attributes[const.ATTR_OCCASION_TYPE] = occasion_type

        # Get tracked chores from nested structure: tracked_chores.selected_chores
        tracked_chores = badge_info.get(const.DATA_BADGE_TRACKED_CHORES, {})
        selected_chore_ids = tracked_chores.get(
            const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES, []
        )
        attributes[const.ATTR_REQUIRED_CHORES] = [
            cast("ChoreData", self.coordinator.chores_data.get(chore_id, {})).get(
                const.DATA_CHORE_NAME
            )
            or chore_id
            for chore_id in selected_chore_ids
        ]

        # Awards info
        awards_data = badge_info.get(const.DATA_BADGE_AWARDS, {})

        # Add friendly names for award items
        award_items = awards_data.get(const.DATA_BADGE_AWARDS_AWARD_ITEMS, [])
        friendly_award_names = []
        for item in award_items:
            if item.startswith(const.AWARD_ITEMS_PREFIX_REWARD):
                reward_id = item.split(":", 1)[1]
                reward_info: RewardData = cast(
                    "RewardData", self.coordinator.rewards_data.get(reward_id, {})
                )
                friendly_name = reward_info.get(
                    const.DATA_REWARD_NAME, f"Reward: {reward_id}"
                )
                friendly_award_names.append(
                    f"{const.AWARD_ITEMS_PREFIX_REWARD}{friendly_name}"
                )
            elif item.startswith(const.AWARD_ITEMS_PREFIX_BONUS):
                bonus_id = item.split(":", 1)[1]
                bonus_info: BonusData = cast(
                    "BonusData", self.coordinator.bonuses_data.get(bonus_id, {})
                )
                friendly_name = bonus_info.get(
                    const.DATA_BONUS_NAME, f"Bonus: {bonus_id}"
                )
                friendly_award_names.append(
                    f"{const.AWARD_ITEMS_PREFIX_BONUS}{friendly_name}"
                )
            elif item.startswith(const.AWARD_ITEMS_PREFIX_PENALTY):
                penalty_id = item.split(":", 1)[1]
                penalty_info: PenaltyData = cast(
                    "PenaltyData", self.coordinator.penalties_data.get(penalty_id, {})
                )
                friendly_name = penalty_info.get(
                    const.DATA_PENALTY_NAME, f"Penalty: {penalty_id}"
                )
                friendly_award_names.append(
                    f"{const.AWARD_ITEMS_PREFIX_PENALTY}{friendly_name}"
                )
            elif item == const.AWARD_ITEMS_KEY_POINTS:
                award_points = awards_data.get(const.DATA_BADGE_AWARDS_AWARD_POINTS, 0)
                friendly_award_names.append(f"Points: {award_points}")
            elif item == const.AWARD_ITEMS_KEY_POINTS_MULTIPLIER:
                points_multiplier = awards_data.get(
                    const.DATA_BADGE_AWARDS_POINT_MULTIPLIER, 1.0
                )
                friendly_award_names.append(f"Multiplier: {points_multiplier}")
        attributes[const.ATTR_BADGE_AWARDS] = friendly_award_names

        attributes[const.ATTR_RESET_SCHEDULE] = badge_info.get(
            const.DATA_BADGE_RESET_SCHEDULE, None
        )

        return attributes

    @property
    def icon(self) -> str | None:
        badge_info: BadgeData = cast(
            "BadgeData", self.coordinator.badges_data.get(self._badge_id, {})
        )
        icon = badge_info.get(const.DATA_BADGE_ICON)
        return str(icon) if icon else None


# ------------------------------------------------------------------------------------------
class SystemChoreSharedStateSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Sensor that shows the global state of a shared or shared_first chore.

    Tracks system-wide chore state independent of individual assignee status.
    Supports both SHARED (multiple assignees can complete) and SHARED_FIRST
    (first assignee to complete wins) completion criteria.

    Provides comprehensive chore configuration including recurring frequency
    (daily/weekly/monthly/custom), applicable days, due dates, default points,
    partial completion settings, multiple claims per day allowance, and total
    approvals today across all assigned assignees. Useful for monitoring chores that
    multiple assignees can claim simultaneously or competitively.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_SHARED_CHORE_GLOBAL_STATUS_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        chore_id: str,
        chore_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            chore_id: Unique identifier for the shared chore.
            chore_name: Display name of the shared chore.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._chore_id = chore_id
        self._chore_name = chore_name
        self._attr_unique_id = f"{entry.entry_id}_{chore_id}{const.SENSOR_KC_UID_SUFFIX_SHARED_CHORE_GLOBAL_STATE_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_CHORE_NAME: chore_name,
        }
        self._attr_device_info = create_system_device_info(entry)
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{const.SENSOR_KC_EID_MIDFIX_SHARED_CHORE_GLOBAL_STATUS_SENSOR}{chore_name}"

    @property
    def native_value(self) -> str:
        """Return the global state for the chore.

        Returns the stored chore state, but if it would be PENDING and
        the chore is within its due window, returns DUE instead.
        """
        chore_info: ChoreData = cast(
            "ChoreData", self.coordinator.chores_data.get(self._chore_id, {})
        )
        state = chore_info.get(const.DATA_CHORE_STATE, const.CHORE_STATE_UNKNOWN)

        # If state would be pending, check if in due window (None = use chore-level due date)
        if state == const.CHORE_STATE_PENDING:
            if self.coordinator.chore_manager.chore_is_due(None, self._chore_id):
                return const.CHORE_STATE_DUE

        return state

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes for the chore.

        Attributes organized by category:
        1. Identity & Meta - purpose, name, description, icon, assigned assignees, labels
        2. Configuration - points, completion_criteria, approval_reset, frequency, days, due_date
        3. Statistics - today's approvals across all assigned assignees
        4. Timestamps - last_claimed, last_completed (chore-level)
        """
        chore_info: ChoreData = cast(
            "ChoreData", self.coordinator.chores_data.get(self._chore_id, {})
        )
        assigned_assignees_ids = chore_info.get(const.DATA_CHORE_ASSIGNED_ASSIGNEES, [])
        assigned_assignees_names = [
            name
            for k_id in assigned_assignees_ids
            if (
                name := get_item_name_or_log_error(
                    "assignee",
                    k_id,
                    self.coordinator.assignees_data.get(k_id, {}),
                    const.DATA_USER_NAME,
                )
            )
        ]

        stored_labels = chore_info.get(const.DATA_CHORE_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label)
            for label in cast("list", stored_labels)
        ]

        # Get today's approvals from periods structure (not legacy flat field)
        total_approvals_today = const.DEFAULT_ZERO
        today_local_iso = dt_today_local().isoformat()

        for assignee_id in assigned_assignees_ids:
            assignee_data: AssigneeData = cast(
                "AssigneeData", self.coordinator.assignees_data.get(assignee_id, {})
            )
            # Access: assignee_data[DATA_ASSIGNEE_CHORE_DATA][chore_id][periods][daily][today_iso][approved]
            assignee_chore_data = assignee_data.get(
                const.DATA_ASSIGNEE_CHORE_DATA, {}
            ).get(self._chore_id, {})
            periods = assignee_chore_data.get(
                const.DATA_ASSIGNEE_CHORE_DATA_PERIODS, {}
            )
            daily_periods = periods.get(
                const.DATA_ASSIGNEE_CHORE_DATA_PERIODS_DAILY, {}
            )
            today_period = daily_periods.get(today_local_iso, {})
            total_approvals_today += today_period.get(
                const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_APPROVED, const.DEFAULT_ZERO
            )

        attributes = {
            # --- 1. Identity & Meta ---
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_SHARED_CHORE,
            const.ATTR_CHORE_NAME: self._chore_name,
            const.ATTR_DESCRIPTION: chore_info.get(
                const.DATA_CHORE_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_ASSIGNED_ASSIGNEES: assigned_assignees_names,
            const.ATTR_LABELS: friendly_labels,
            # --- 2. Configuration ---
            const.ATTR_DEFAULT_POINTS: chore_info.get(
                const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_ZERO
            ),
            const.ATTR_COMPLETION_CRITERIA: chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            ),
            const.ATTR_APPROVAL_RESET_TYPE: chore_info.get(
                const.DATA_CHORE_APPROVAL_RESET_TYPE,
                const.DEFAULT_APPROVAL_RESET_TYPE,
            ),
            const.ATTR_RECURRING_FREQUENCY: chore_info.get(
                const.DATA_CHORE_RECURRING_FREQUENCY, const.SENTINEL_NONE_TEXT
            ),
            const.ATTR_APPLICABLE_DAYS: chore_info.get(
                const.DATA_CHORE_APPLICABLE_DAYS, []
            ),
            # Return None when no due_date - dashboard templates use None check
            const.ATTR_DUE_DATE: chore_info.get(const.DATA_CHORE_DUE_DATE),
            const.ATTR_DUE_WINDOW_START: self._get_due_window_start_iso(),
            const.ATTR_TIME_UNTIL_DUE: self._get_time_until_due(),
            const.ATTR_TIME_UNTIL_OVERDUE: self._get_time_until_overdue(),
            # --- 3. Statistics ---
            const.ATTR_CHORE_APPROVALS_TODAY: total_approvals_today,
            # --- 4. Timestamps ---
            const.ATTR_LAST_CLAIMED: chore_info.get(const.DATA_CHORE_LAST_CLAIMED),
            const.ATTR_LAST_APPROVED: chore_info.get(const.DATA_CHORE_LAST_COMPLETED),
        }

        # Add SHARED_FIRST specific attributes (who claimed/completed)
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_INDEPENDENT
        )
        if completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # Get claimed_by and completed_by, resolve IDs to names
            claimed_by_id = chore_info.get(const.DATA_CHORE_CLAIMED_BY)
            completed_by_id = chore_info.get(const.DATA_CHORE_COMPLETED_BY)

            claimed_by_name = None
            if claimed_by_id:
                claimant_info = cast(
                    "AssigneeData",
                    self.coordinator.assignees_data.get(claimed_by_id, {}),  # type: ignore[call-overload]
                )
                claimed_by_name = claimant_info.get(const.DATA_USER_NAME, claimed_by_id)

            completed_by_name = None
            if completed_by_id:
                completer_info = cast(
                    "AssigneeData",
                    self.coordinator.assignees_data.get(completed_by_id, {}),  # type: ignore[call-overload]
                )
                completed_by_name = completer_info.get(
                    const.DATA_USER_NAME, completed_by_id
                )

            attributes[const.ATTR_CHORE_CLAIMED_BY] = claimed_by_name
            attributes[const.ATTR_CHORE_COMPLETED_BY] = completed_by_name

        if (
            chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY)
            == const.FREQUENCY_CUSTOM
        ):
            attributes[const.ATTR_CUSTOM_FREQUENCY_INTERVAL] = chore_info.get(
                const.DATA_CHORE_CUSTOM_INTERVAL
            )
            attributes[const.ATTR_CUSTOM_FREQUENCY_UNIT] = chore_info.get(
                const.DATA_CHORE_CUSTOM_INTERVAL_UNIT
            )

        return attributes

    def _get_due_window_start_iso(self) -> str | None:
        """Get the due window start time as ISO string."""
        due_window_start = self.coordinator.chore_manager.get_due_window_start(
            self._chore_id, None
        )
        return due_window_start.isoformat() if due_window_start else None

    def _get_time_until_due(self) -> str | None:
        """Get human-readable time remaining until due window starts.

        Returns "0d 0h 0m" if window already started (past) or if due window
        is disabled (0), returns same as time_until_overdue.
        """
        chore_info: ChoreData = cast(
            "ChoreData", self.coordinator.chores_data.get(self._chore_id, {})
        )
        due_window_offset = chore_info.get(
            const.DATA_CHORE_DUE_WINDOW_OFFSET, const.DEFAULT_DUE_WINDOW_OFFSET
        )

        # If due window disabled (0), match due date behavior
        if due_window_offset == "0":
            return self._get_time_until_overdue()

        due_window_start = self.coordinator.chore_manager.get_due_window_start(
            self._chore_id, None
        )
        if not due_window_start:
            return None

        # Calculate time until window start
        result = dt_time_until(due_window_start)
        # If already past (None), return 0d 0h 0m
        return result or "0d 0h 0m"

    def _get_time_until_overdue(self) -> str | None:
        """Get human-readable time remaining until due date (overdue).

        Returns "0d 0h 0m" if already overdue (past).
        """
        due_date = self.coordinator.chore_manager.get_due_date(self._chore_id, None)
        if not due_date:
            return None

        result = dt_time_until(due_date)
        # If already past (None), return 0d 0h 0m
        return result or "0d 0h 0m"

    @property
    def icon(self) -> str | None:
        """Return the icon for the chore sensor."""
        chore_info: ChoreData = cast(
            "ChoreData", self.coordinator.chores_data.get(self._chore_id, {})
        )
        return chore_info.get(const.DATA_CHORE_ICON) or None


# ------------------------------------------------------------------------------------------
class AssigneeRewardStatusSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Shows the status of a reward for a particular assignee.

    Tracks reward redemption lifecycle: Not Claimed → Claimed (pending approval) → Approved.
    Provides reward metadata including cost, claims/approvals counts, and button entity IDs
    for UI integration.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_REWARD_STATUS_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        reward_id: str,
        reward_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            reward_id: Unique identifier for the reward.
            reward_name: Display name of the reward.
        """

        super().__init__(coordinator)
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._reward_id = reward_id
        self._reward_name = reward_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{reward_id}{const.SENSOR_KC_UID_SUFFIX_REWARD_STATUS_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_SENSOR_ATTR_REWARD_NAME: reward_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{assignee_name}{const.SENSOR_KC_EID_MIDFIX_REWARD_STATUS_SENSOR}{reward_name}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> str:
        """Return the current reward status: 'locked', 'available', 'requested', or 'approved'."""
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )
        reward_data = assignee_info.get(const.DATA_ASSIGNEE_REWARD_DATA, {}).get(
            self._reward_id, {}
        )

        # Check pending_count for requested status
        pending_count = reward_data.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT, 0
        )
        if pending_count > 0:
            return const.REWARD_STATE_REQUESTED

        # Check if approved today using last_approved timestamp
        last_approved = reward_data.get(const.DATA_ASSIGNEE_REWARD_DATA_LAST_APPROVED)
        if last_approved:
            try:
                approved_dt = dt_to_utc(last_approved)
                if approved_dt and approved_dt.date() == dt_util.now().date():
                    return const.REWARD_STATE_APPROVED
            except (ValueError, TypeError):
                pass

        # Check if assignee can afford the reward
        assignee_points = assignee_info.get(const.DATA_ASSIGNEE_POINTS, 0)
        reward_info: RewardData = cast(
            "RewardData", self.coordinator.rewards_data.get(self._reward_id, {})
        )
        reward_cost = int(reward_info.get(const.DATA_REWARD_COST, 0))

        if assignee_points >= reward_cost:
            return const.REWARD_STATE_AVAILABLE
        return const.REWARD_STATE_LOCKED

    @property
    def extra_state_attributes(self) -> dict:
        """Provide comprehensive reward statistics as attributes.

        Returns period-based claims, approvals, disapprovals, points spent,
        timestamps, and calculated rates for dashboard and automation use.
        """
        reward_info: RewardData = cast(
            "RewardData", self.coordinator.rewards_data.get(self._reward_id, {})
        )
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )
        reward_data = assignee_info.get(const.DATA_ASSIGNEE_REWARD_DATA, {}).get(
            self._reward_id, {}
        )

        stored_labels = reward_info.get(const.DATA_REWARD_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label)
            for label in cast("list", stored_labels)
        ]

        # Get current period keys
        now_local = dt_now_local()
        today_local_iso = dt_today_local().isoformat()
        week_local_iso = now_local.strftime("%Y-W%V")
        month_local_iso = now_local.strftime("%Y-%m")
        year_local_iso = now_local.strftime("%Y")

        # Get period data
        periods = reward_data.get(const.DATA_ASSIGNEE_REWARD_DATA_PERIODS, {})
        daily = periods.get(const.DATA_ASSIGNEE_REWARD_DATA_PERIODS_DAILY, {})
        weekly = periods.get(const.DATA_ASSIGNEE_REWARD_DATA_PERIODS_WEEKLY, {})
        monthly = periods.get(const.DATA_ASSIGNEE_REWARD_DATA_PERIODS_MONTHLY, {})
        yearly = periods.get(const.DATA_ASSIGNEE_REWARD_DATA_PERIODS_YEARLY, {})
        all_time_bucket = periods.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIODS_ALL_TIME, {}
        )

        # Calculate period stats
        today_stats: PeriodicStatsEntry = daily.get(today_local_iso, {})
        week_stats: PeriodicStatsEntry = weekly.get(week_local_iso, {})
        month_stats: PeriodicStatsEntry = monthly.get(month_local_iso, {})
        year_stats: PeriodicStatsEntry = yearly.get(year_local_iso, {})
        all_time_stats: PeriodicStatsEntry = all_time_bucket.get(
            const.PERIOD_ALL_TIME, {}
        )

        claimed_today = today_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_CLAIMED, 0
        )
        claimed_week = week_stats.get(const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_CLAIMED, 0)
        claimed_month = month_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_CLAIMED, 0
        )
        claimed_year = year_stats.get(const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_CLAIMED, 0)
        claimed_all_time = all_time_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_CLAIMED, const.DEFAULT_ZERO
        )

        approved_today = today_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_APPROVED, 0
        )
        approved_week = week_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_APPROVED, 0
        )
        approved_month = month_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_APPROVED, 0
        )
        approved_year = year_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_APPROVED, 0
        )
        approved_all_time = all_time_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_APPROVED, const.DEFAULT_ZERO
        )

        disapproved_today = today_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_DISAPPROVED, 0
        )
        disapproved_week = week_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_DISAPPROVED, 0
        )
        disapproved_month = month_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_DISAPPROVED, 0
        )
        disapproved_year = year_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_DISAPPROVED, 0
        )
        disapproved_all_time = all_time_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_DISAPPROVED, const.DEFAULT_ZERO
        )

        points_spent_today = today_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_POINTS, 0
        )
        points_spent_week = week_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_POINTS, 0
        )
        points_spent_month = month_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_POINTS, 0
        )
        points_spent_year = year_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_POINTS, 0
        )
        points_spent_all_time = all_time_stats.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_POINTS, const.DEFAULT_ZERO
        )

        # Calculate rates
        approval_rate = (
            round((approved_all_time / claimed_all_time) * 100, 1)
            if claimed_all_time > 0
            else 0.0
        )

        # Calculate claim rate per day (week = 7 days, month = 30 days average)
        claim_rate_week = round(claimed_week / 7, 2) if claimed_week > 0 else 0.0
        claim_rate_month = round(claimed_month / 30, 2) if claimed_month > 0 else 0.0

        # Get timestamps
        last_claimed = reward_data.get(const.DATA_ASSIGNEE_REWARD_DATA_LAST_CLAIMED)
        last_approved = reward_data.get(const.DATA_ASSIGNEE_REWARD_DATA_LAST_APPROVED)
        last_disapproved = reward_data.get(
            const.DATA_ASSIGNEE_REWARD_DATA_LAST_DISAPPROVED
        )

        # Get pending claims count
        pending_claims = reward_data.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT, const.DEFAULT_ZERO
        )

        # Get claim, approve, and disapprove button entity IDs
        claim_button_eid = None
        approve_button_eid = None
        disapprove_button_eid = None
        try:
            entity_registry = async_get(self.hass)
            # Claim button uses UID suffix pattern (v0.43+)
            claim_unique_id = f"{self._entry.entry_id}_{self._assignee_id}_{self._reward_id}{const.BUTTON_KC_UID_SUFFIX_ASSIGNEE_REWARD_REDEEM}"
            claim_button_eid = entity_registry.async_get_entity_id(
                "button", const.DOMAIN, claim_unique_id
            )

            # Approve and disapprove buttons use UID suffixes
            approve_unique_id = f"{self._entry.entry_id}_{self._assignee_id}_{self._reward_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE_REWARD}"
            approve_button_eid = entity_registry.async_get_entity_id(
                "button", const.DOMAIN, approve_unique_id
            )

            disapprove_unique_id = f"{self._entry.entry_id}_{self._assignee_id}_{self._reward_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE_REWARD}"
            disapprove_button_eid = entity_registry.async_get_entity_id(
                "button", const.DOMAIN, disapprove_unique_id
            )
        except (KeyError, ValueError, AttributeError):
            pass

        # Return attributes in logical order: common, status, timestamps, periods, rates, buttons, labels
        return {
            # Common fields
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_REWARD_STATUS,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_REWARD_NAME: self._reward_name,
            const.ATTR_DESCRIPTION: reward_info.get(
                const.DATA_REWARD_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_COST: reward_info.get(
                const.DATA_REWARD_COST, const.DEFAULT_REWARD_COST
            ),
            # Status tracking
            const.ATTR_REWARD_PENDING_CLAIMS: pending_claims,
            # Timestamps
            const.ATTR_REWARD_LAST_CLAIMED: last_claimed,
            const.ATTR_REWARD_LAST_APPROVED: last_approved,
            const.ATTR_REWARD_LAST_DISAPPROVED: last_disapproved,
            # Claims by period
            const.ATTR_REWARD_CLAIMED_TODAY: claimed_today,
            const.ATTR_REWARD_CLAIMED_WEEK: claimed_week,
            const.ATTR_REWARD_CLAIMED_MONTH: claimed_month,
            const.ATTR_REWARD_CLAIMED_YEAR: claimed_year,
            const.ATTR_REWARD_CLAIMED_ALL_TIME: claimed_all_time,
            # Approvals by period
            const.ATTR_REWARD_APPROVED_TODAY: approved_today,
            const.ATTR_REWARD_APPROVED_WEEK: approved_week,
            const.ATTR_REWARD_APPROVED_MONTH: approved_month,
            const.ATTR_REWARD_APPROVED_YEAR: approved_year,
            const.ATTR_REWARD_APPROVED_ALL_TIME: approved_all_time,
            # Disapprovals by period
            const.ATTR_REWARD_DISAPPROVED_TODAY: disapproved_today,
            const.ATTR_REWARD_DISAPPROVED_WEEK: disapproved_week,
            const.ATTR_REWARD_DISAPPROVED_MONTH: disapproved_month,
            const.ATTR_REWARD_DISAPPROVED_YEAR: disapproved_year,
            const.ATTR_REWARD_DISAPPROVED_ALL_TIME: disapproved_all_time,
            # Points spent by period
            const.ATTR_REWARD_POINTS_SPENT_TODAY: points_spent_today,
            const.ATTR_REWARD_POINTS_SPENT_WEEK: points_spent_week,
            const.ATTR_REWARD_POINTS_SPENT_MONTH: points_spent_month,
            const.ATTR_REWARD_POINTS_SPENT_YEAR: points_spent_year,
            const.ATTR_REWARD_POINTS_SPENT_ALL_TIME: points_spent_all_time,
            # Calculated rates
            const.ATTR_REWARD_APPROVAL_RATE: approval_rate,
            const.ATTR_REWARD_CLAIM_RATE_WEEK: claim_rate_week,
            const.ATTR_REWARD_CLAIM_RATE_MONTH: claim_rate_month,
            # Button entity IDs
            const.ATTR_REWARD_CLAIM_BUTTON_ENTITY_ID: claim_button_eid,
            const.ATTR_REWARD_APPROVE_BUTTON_ENTITY_ID: approve_button_eid,
            const.ATTR_REWARD_DISAPPROVE_BUTTON_ENTITY_ID: disapprove_button_eid,
            # Labels
            const.ATTR_LABELS: friendly_labels,
        }

    @property
    def icon(self) -> str | None:
        """Use the reward's custom icon if set, else fallback to icons.json."""
        reward_info: RewardData = cast(
            "RewardData", self.coordinator.rewards_data.get(self._reward_id, {})
        )
        return reward_info.get(const.DATA_REWARD_ICON) or None


# ------------------------------------------------------------------------------------------
class SystemAchievementSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Sensor representing an achievement.

    Provides system-wide achievement definition and tracks aggregated progress
    across all assigned assignees as a percentage (0-100). Supports three achievement
    types: TOTAL (cumulative completions with baselines), STREAK (consecutive
    completions), and DAILY_MIN (minimum daily requirements). Includes achievement
    metadata such as target values, reward points, criteria, associated chore,
    and list of assignees who have earned the achievement.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_ACHIEVEMENT_STATE_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        achievement_id: str,
        achievement_name: str,
    ):
        """Initialize the SystemAchievementSensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            achievement_id: Unique identifier for the achievement.
            achievement_name: Display name of the achievement.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._achievement_id = achievement_id
        self._achievement_name = achievement_name
        self._attr_unique_id = f"{entry.entry_id}_{achievement_id}{const.SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_SENSOR}"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ACHIEVEMENT_NAME: achievement_name,
        }
        self._attr_device_info = create_system_device_info(entry)
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{const.SENSOR_KC_EID_MIDFIX_ACHIEVEMENT_SENSOR}{achievement_name}"

    @property
    def native_value(self) -> Any:
        """Return the overall progress percentage toward the achievement."""

        achievement: AchievementData = cast(
            "AchievementData",
            self.coordinator.achievements_data.get(self._achievement_id, {}),
        )
        target = achievement.get(const.DATA_ACHIEVEMENT_TARGET_VALUE, 1)
        assigned_assignees = achievement.get(
            const.DATA_ACHIEVEMENT_ASSIGNED_ASSIGNEES, []
        )

        if not assigned_assignees:
            return const.DEFAULT_ZERO

        ach_type = achievement.get(const.DATA_ACHIEVEMENT_TYPE)
        if ach_type == const.ACHIEVEMENT_TYPE_TOTAL:
            total_current = const.DEFAULT_ZERO
            total_effective_target = const.DEFAULT_ZERO

            for assignee_id in assigned_assignees:
                progress_data: AchievementProgress = achievement.get(
                    const.DATA_ACHIEVEMENT_PROGRESS, {}
                ).get(assignee_id, {})
                baseline = (
                    progress_data.get(
                        const.DATA_ACHIEVEMENT_BASELINE, const.DEFAULT_ZERO
                    )
                    if isinstance(progress_data, dict)
                    else const.DEFAULT_ZERO
                )
                # v43+: chore_stats deleted, use chore_periods.all_time.all_time (nested)
                assignee_data = cast(
                    "AssigneeData", self.coordinator.assignees_data.get(assignee_id, {})
                )
                chore_periods: dict[str, Any] = cast(
                    "dict[str, Any]",
                    assignee_data.get(const.DATA_ASSIGNEE_CHORE_PERIODS, {}),
                )
                all_time_container: dict[str, Any] = cast(
                    "dict[str, Any]",
                    chore_periods.get(
                        const.DATA_ASSIGNEE_CHORE_DATA_PERIODS_ALL_TIME, {}
                    ),
                )
                all_time_bucket: dict[str, Any] = cast(
                    "dict[str, Any]",
                    all_time_container.get(const.PERIOD_ALL_TIME, {}),
                )
                current_total = all_time_bucket.get(
                    const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_APPROVED, const.DEFAULT_ZERO
                )
                total_current += int(current_total)
                total_effective_target += baseline + target  # type: ignore[operator]

            percent = (
                (int(total_current) / total_effective_target * 100)
                if total_effective_target > const.DEFAULT_ZERO
                else const.DEFAULT_ZERO
            )

        elif ach_type == const.ACHIEVEMENT_TYPE_STREAK:
            total_current = const.DEFAULT_ZERO

            for assignee_id in assigned_assignees:
                progress_data_2: AchievementProgress = achievement.get(
                    const.DATA_ACHIEVEMENT_PROGRESS, {}
                ).get(assignee_id, {})
                total_current += (
                    progress_data_2.get(
                        const.DATA_ACHIEVEMENT_CURRENT_STREAK, const.DEFAULT_ZERO
                    )
                    if isinstance(progress_data_2, dict)
                    else const.DEFAULT_ZERO
                )

            global_target = target * len(assigned_assignees)

            percent = (
                (total_current / global_target * 100)
                if global_target > const.DEFAULT_ZERO
                else const.DEFAULT_ZERO
            )

        elif ach_type == const.ACHIEVEMENT_TYPE_DAILY_MIN:
            total_progress = const.DEFAULT_ZERO

            for assignee_id in assigned_assignees:
                # Use Phase 7.5 cache API for temporal stats (not storage)
                cache_stats = self.coordinator.statistics_manager.get_stats(assignee_id)
                daily = cache_stats.get(
                    const.PRES_ASSIGNEE_CHORES_APPROVED_TODAY, const.DEFAULT_ZERO
                )
                assignee_progress = (
                    100
                    if daily >= target
                    else (daily / target * 100)
                    if target > const.DEFAULT_ZERO
                    else const.DEFAULT_ZERO
                )
                total_progress += assignee_progress

            percent = total_progress / len(assigned_assignees)

        else:
            percent = const.DEFAULT_ZERO

        return min(100, round(percent, const.DATA_FLOAT_PRECISION))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes for this achievement."""
        achievement: AchievementData = cast(
            "AchievementData",
            self.coordinator.achievements_data.get(self._achievement_id, {}),
        )
        progress = achievement.get(const.DATA_ACHIEVEMENT_PROGRESS, {})
        assignees_progress = {}

        earned_by = []
        for assignee_id, data in progress.items():
            if data.get(const.DATA_ACHIEVEMENT_AWARDED, False):
                assignee_name = (
                    get_assignee_name_by_id(self.coordinator, assignee_id)
                    or assignee_id
                )
                earned_by.append(assignee_name)

        associated_chore = const.SENTINEL_EMPTY
        selected_chore_id = achievement.get(const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID)
        if selected_chore_id:
            associated_chore = (
                cast(
                    "ChoreData", self.coordinator.chores_data.get(selected_chore_id, {})
                ).get(const.DATA_CHORE_NAME)
                or const.SENTINEL_EMPTY
            )

        assigned_assignees_ids = achievement.get(
            const.DATA_ACHIEVEMENT_ASSIGNED_ASSIGNEES, []
        )
        assigned_assignees_names = [
            name
            for k_id in assigned_assignees_ids
            if (
                name := get_item_name_or_log_error(
                    "assignee",
                    k_id,
                    self.coordinator.assignees_data.get(k_id, {}),
                    const.DATA_USER_NAME,
                )
            )
        ]
        ach_type = achievement.get(const.DATA_ACHIEVEMENT_TYPE)
        for assignee_id in assigned_assignees_ids:
            assignee_name = (
                get_assignee_name_by_id(self.coordinator, assignee_id) or assignee_id
            )
            progress_data: AchievementProgress = achievement.get(
                const.DATA_ACHIEVEMENT_PROGRESS, {}
            ).get(assignee_id, {})
            if ach_type == const.ACHIEVEMENT_TYPE_TOTAL:
                assignees_progress[assignee_name] = progress_data.get(
                    const.DATA_ACHIEVEMENT_CURRENT_VALUE, const.DEFAULT_ZERO
                )
            elif ach_type == const.ACHIEVEMENT_TYPE_STREAK:
                assignees_progress[assignee_name] = progress_data.get(
                    const.DATA_ACHIEVEMENT_CURRENT_STREAK, const.DEFAULT_ZERO
                )
            elif (
                achievement.get(const.DATA_ACHIEVEMENT_TYPE)
                == const.ACHIEVEMENT_TYPE_DAILY_MIN
            ):
                # Use Phase 7.5 cache API for temporal stats (not storage)
                cache_stats = self.coordinator.statistics_manager.get_stats(assignee_id)
                assignees_progress[assignee_name] = cache_stats.get(
                    const.PRES_ASSIGNEE_CHORES_APPROVED_TODAY, const.DEFAULT_ZERO
                )
            else:
                assignees_progress[assignee_name] = const.DEFAULT_ZERO

        stored_labels = achievement.get(const.DATA_ACHIEVEMENT_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label)
            for label in cast("list", stored_labels)
        ]

        return {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_ACHIEVEMENT,
            const.ATTR_ACHIEVEMENT_NAME: self._achievement_name,
            const.ATTR_DESCRIPTION: achievement.get(
                const.DATA_ACHIEVEMENT_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_ASSIGNED_ASSIGNEES: assigned_assignees_names,
            const.ATTR_TYPE: ach_type,
            const.ATTR_ASSOCIATED_CHORE: associated_chore,
            const.ATTR_CRITERIA: achievement.get(
                const.DATA_ACHIEVEMENT_CRITERIA, const.SENTINEL_EMPTY
            ),
            const.ATTR_TARGET_VALUE: achievement.get(
                const.DATA_ACHIEVEMENT_TARGET_VALUE
            ),
            const.ATTR_REWARD_POINTS: achievement.get(
                const.DATA_ACHIEVEMENT_REWARD_POINTS
            ),
            const.ATTR_ASSIGNEES_EARNED: earned_by,
            const.ATTR_LABELS: friendly_labels,
        }

    @property
    def icon(self) -> str | None:
        """Return achievement custom icon or None for icons.json fallback."""
        achievement_info: AchievementData = cast(
            "AchievementData",
            self.coordinator.achievements_data.get(self._achievement_id, {}),
        )
        return achievement_info.get(const.DATA_ACHIEVEMENT_ICON) or None


# ------------------------------------------------------------------------------------------
class SystemChallengeSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Sensor representing a challenge.

    Provides system-wide challenge definition and tracks aggregated progress
    across all assigned assignees as a percentage (0-100). Supports two challenge
    types: TOTAL_WITHIN_WINDOW (simple count toward target within date range)
    and DAILY_MIN (required daily minimum summed across all days in window).
    Includes challenge metadata such as start/end dates, target values, reward
    points, criteria, associated chore, and list of assignees who have earned the
    challenge reward.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHALLENGE_STATE_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        challenge_id: str,
        challenge_name: str,
    ):
        """Initialize the ChallengeSensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            challenge_id: Unique identifier for the challenge.
            challenge_name: Display name of the challenge.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._challenge_id = challenge_id
        self._challenge_name = challenge_name
        self._attr_unique_id = f"{entry.entry_id}_{challenge_id}{const.SENSOR_KC_UID_SUFFIX_CHALLENGE_SENSOR}"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_CHALLENGE_NAME: challenge_name,
        }
        self._attr_device_info = create_system_device_info(entry)
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{const.SENSOR_KC_EID_MIDFIX_CHALLENGE_SENSOR}{challenge_name}"

    @property
    def native_value(self) -> Any:
        """Return the overall progress percentage toward the challenge."""

        challenge: ChallengeData = cast(
            "ChallengeData",
            self.coordinator.challenges_data.get(self._challenge_id, {}),
        )
        target = challenge.get(const.DATA_CHALLENGE_TARGET_VALUE, 1)
        assigned_assignees = challenge.get(const.DATA_CHALLENGE_ASSIGNED_ASSIGNEES, [])

        if not assigned_assignees:
            return const.DEFAULT_ZERO

        challenge_type = challenge.get(const.DATA_CHALLENGE_TYPE)
        total_progress = const.DEFAULT_ZERO

        for assignee_id in assigned_assignees:
            progress_data: ChallengeProgress = challenge.get(
                const.DATA_CHALLENGE_PROGRESS, {}
            ).get(assignee_id, {})

            if challenge_type == const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW:
                total_progress += progress_data.get(
                    const.DATA_CHALLENGE_COUNT, const.DEFAULT_ZERO
                )

            elif challenge_type == const.CHALLENGE_TYPE_DAILY_MIN:
                if isinstance(progress_data, dict):
                    daily_counts = progress_data.get(
                        const.DATA_CHALLENGE_DAILY_COUNTS, {}
                    )
                    total_progress += sum(daily_counts.values())

                else:
                    total_progress += const.DEFAULT_ZERO

            else:
                total_progress += const.DEFAULT_ZERO

        global_target = target * len(assigned_assignees)

        percent = (
            (total_progress / global_target * 100)
            if global_target > const.DEFAULT_ZERO
            else const.DEFAULT_ZERO
        )

        return min(100, round(percent, const.DATA_FLOAT_PRECISION))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes for this challenge."""
        challenge: ChallengeData = cast(
            "ChallengeData",
            self.coordinator.challenges_data.get(self._challenge_id, {}),
        )
        progress = challenge.get(const.DATA_CHALLENGE_PROGRESS, {})
        assignees_progress = {}
        challenge_type = challenge.get(const.DATA_CHALLENGE_TYPE)

        earned_by = []
        for assignee_id, data in progress.items():
            if data.get(const.DATA_CHALLENGE_AWARDED, False):
                assignee_name = (
                    get_assignee_name_by_id(self.coordinator, assignee_id)
                    or assignee_id
                )
                earned_by.append(assignee_name)

        associated_chore = const.SENTINEL_EMPTY
        selected_chore_id = challenge.get(const.DATA_CHALLENGE_SELECTED_CHORE_ID)
        if selected_chore_id:
            associated_chore = (
                cast(
                    "ChoreData", self.coordinator.chores_data.get(selected_chore_id, {})
                ).get(const.DATA_CHORE_NAME)
                or const.SENTINEL_EMPTY
            )

        assigned_assignees_ids = challenge.get(
            const.DATA_CHALLENGE_ASSIGNED_ASSIGNEES, []
        )
        assigned_assignees_names = [
            name
            for k_id in assigned_assignees_ids
            if (
                name := get_item_name_or_log_error(
                    "assignee",
                    k_id,
                    self.coordinator.assignees_data.get(k_id, {}),
                    const.DATA_USER_NAME,
                )
            )
        ]

        for assignee_id in assigned_assignees_ids:
            assignee_name = (
                get_assignee_name_by_id(self.coordinator, assignee_id) or assignee_id
            )
            progress_data: ChallengeProgress = challenge.get(
                const.DATA_CHALLENGE_PROGRESS, {}
            ).get(assignee_id, {})
            if challenge_type == const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW:
                assignees_progress[assignee_name] = progress_data.get(
                    const.DATA_CHALLENGE_COUNT, const.DEFAULT_ZERO
                )
            elif challenge_type == const.CHALLENGE_TYPE_DAILY_MIN:
                if isinstance(progress_data, dict):
                    assignees_progress[assignee_name] = sum(
                        progress_data.get(
                            const.DATA_CHALLENGE_DAILY_COUNTS, {}
                        ).values()
                    )
                else:
                    assignees_progress[assignee_name] = const.DEFAULT_ZERO
            else:
                assignees_progress[assignee_name] = const.DEFAULT_ZERO

        stored_labels = challenge.get(const.DATA_CHALLENGE_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label)
            for label in cast("list", stored_labels)
        ]

        return {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_CHALLENGE,
            const.ATTR_CHALLENGE_NAME: self._challenge_name,
            const.ATTR_DESCRIPTION: challenge.get(
                const.DATA_CHALLENGE_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_ASSIGNED_ASSIGNEES: assigned_assignees_names,
            const.ATTR_TYPE: challenge_type,
            const.ATTR_ASSOCIATED_CHORE: associated_chore,
            const.ATTR_CRITERIA: challenge.get(
                const.DATA_CHALLENGE_CRITERIA, const.SENTINEL_EMPTY
            ),
            const.ATTR_TARGET_VALUE: challenge.get(const.DATA_CHALLENGE_TARGET_VALUE),
            const.ATTR_REWARD_POINTS: challenge.get(const.DATA_CHALLENGE_REWARD_POINTS),
            const.ATTR_START_DATE: challenge.get(const.DATA_CHALLENGE_START_DATE),
            const.ATTR_END_DATE: challenge.get(const.DATA_CHALLENGE_END_DATE),
            const.ATTR_ASSIGNEES_EARNED: earned_by,
            const.ATTR_LABELS: friendly_labels,
        }

    @property
    def icon(self) -> str | None:
        """Return challenge custom icon or None for icons.json fallback."""
        challenge_info: ChallengeData = cast(
            "ChallengeData",
            self.coordinator.challenges_data.get(self._challenge_id, {}),
        )
        return challenge_info.get(const.DATA_CHALLENGE_ICON) or None


# ------------------------------------------------------------------------------------------
class AssigneeAchievementProgressSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Sensor representing a assignee's progress toward a specific achievement.

    Tracks achievement progress as a percentage (0-100) for individual assignee/achievement
    combinations. Supports multiple achievement types: TOTAL (cumulative count with
    baseline), STREAK (consecutive completions), and DAILY_MIN (daily minimum
    requirements). Provides comprehensive metadata including target value, reward
    points, criteria, associated chore, and award status.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_ACHIEVEMENT_PROGRESS_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        achievement_id: str,
        achievement_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            achievement_id: Unique identifier for the achievement.
            achievement_name: Display name of the achievement.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._achievement_id = achievement_id
        self._achievement_name = achievement_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{achievement_id}{const.SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_PROGRESS_SENSOR}"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_SENSOR_ATTR_ACHIEVEMENT_NAME: achievement_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{assignee_name}{const.SENSOR_KC_EID_MIDFIX_ACHIEVEMENT_PROGRESS_SENSOR}{achievement_name}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> float:
        """Return the progress percentage toward the achievement.

        Calculates percentage based on achievement type:
        - TOTAL: (current_value / (baseline + target)) * 100
        - STREAK: (current_streak / target) * 100
        - DAILY_MIN: (daily_completions / target) * 100

        Returns:
            Progress percentage capped at 100.0, rounded to 1 decimal place.
        """
        achievement: AchievementData = cast(
            "AchievementData",
            self.coordinator.achievements_data.get(self._achievement_id, {}),
        )
        target = achievement.get(const.DATA_ACHIEVEMENT_TARGET_VALUE, 1)
        ach_type = achievement.get(const.DATA_ACHIEVEMENT_TYPE)

        if ach_type == const.ACHIEVEMENT_TYPE_TOTAL:
            progress_data: AchievementProgress = achievement.get(
                const.DATA_ACHIEVEMENT_PROGRESS, {}
            ).get(self._assignee_id, {})

            baseline = (
                progress_data.get(const.DATA_ACHIEVEMENT_BASELINE, const.DEFAULT_ZERO)
                if isinstance(progress_data, dict)
                else const.DEFAULT_ZERO
            )

            # v43+: chore_stats deleted, use chore_periods.all_time.all_time (nested)
            assignee_data = cast(
                "AssigneeData",
                self.coordinator.assignees_data.get(self._assignee_id, {}),
            )
            chore_periods: dict[str, Any] = cast(
                "dict[str, Any]",
                assignee_data.get(const.DATA_ASSIGNEE_CHORE_PERIODS, {}),
            )
            all_time_container: dict[str, Any] = cast(
                "dict[str, Any]",
                chore_periods.get(const.DATA_ASSIGNEE_CHORE_DATA_PERIODS_ALL_TIME, {}),
            )
            all_time_bucket: dict[str, Any] = cast(
                "dict[str, Any]",
                all_time_container.get(const.PERIOD_ALL_TIME, {}),
            )
            current_total = all_time_bucket.get(
                const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_APPROVED, const.DEFAULT_ZERO
            )

            effective_target = baseline + target  # type: ignore[operator]

            percent = (
                (int(current_total) / effective_target * 100)
                if effective_target > const.DEFAULT_ZERO
                else const.DEFAULT_ZERO
            )

        elif ach_type == const.ACHIEVEMENT_TYPE_STREAK:
            progress_data_elif: AchievementProgress = achievement.get(
                const.DATA_ACHIEVEMENT_PROGRESS, {}
            ).get(self._assignee_id, {})

            progress = (
                progress_data_elif.get(
                    const.DATA_ACHIEVEMENT_CURRENT_STREAK, const.DEFAULT_ZERO
                )
                if isinstance(progress_data_elif, dict)
                else const.DEFAULT_ZERO
            )

            percent = (
                (progress / target * 100)
                if target > const.DEFAULT_ZERO
                else const.DEFAULT_ZERO
            )

        elif ach_type == const.ACHIEVEMENT_TYPE_DAILY_MIN:
            # Use Phase 7.5 cache API for temporal stats (not storage)
            cache_stats = self.coordinator.statistics_manager.get_stats(
                self._assignee_id
            )
            daily = cache_stats.get(
                const.PRES_ASSIGNEE_CHORES_APPROVED_TODAY, const.DEFAULT_ZERO
            )

            percent = (
                (daily / target * 100)
                if target > const.DEFAULT_ZERO
                else const.DEFAULT_ZERO
            )

        else:
            percent = const.DEFAULT_ZERO

        return min(100, round(percent, const.DATA_FLOAT_PRECISION))

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes for the achievement progress."""
        achievement: AchievementData = cast(
            "AchievementData",
            self.coordinator.achievements_data.get(self._achievement_id, {}),
        )
        target = achievement.get(const.DATA_ACHIEVEMENT_TARGET_VALUE, 1)
        progress_data: AchievementProgress = achievement.get(
            const.DATA_ACHIEVEMENT_PROGRESS, {}
        ).get(self._assignee_id, {})
        raw_progress = const.DEFAULT_ZERO

        awarded = (
            progress_data.get(const.DATA_ACHIEVEMENT_AWARDED, False)
            if isinstance(progress_data, dict)
            else False
        )

        if achievement.get(const.DATA_ACHIEVEMENT_TYPE) == const.ACHIEVEMENT_TYPE_TOTAL:
            current_value = (
                progress_data.get(
                    const.DATA_ACHIEVEMENT_CURRENT_VALUE, const.DEFAULT_ZERO
                )
                if isinstance(progress_data, dict)
                else const.DEFAULT_ZERO
            )
            raw_progress = (
                int(current_value)
                if isinstance(current_value, (int, float, str))
                else const.DEFAULT_ZERO
            )

        elif (
            achievement.get(const.DATA_ACHIEVEMENT_TYPE)
            == const.ACHIEVEMENT_TYPE_STREAK
        ):
            raw_progress = (
                progress_data.get(
                    const.DATA_ACHIEVEMENT_CURRENT_STREAK, const.DEFAULT_ZERO
                )
                if isinstance(progress_data, dict)
                else const.DEFAULT_ZERO
            )

        elif (
            achievement.get(const.DATA_ACHIEVEMENT_TYPE)
            == const.ACHIEVEMENT_TYPE_DAILY_MIN
        ):
            # Use Phase 7.5 cache API for temporal stats (not storage)
            cache_stats = self.coordinator.statistics_manager.get_stats(
                self._assignee_id
            )
            raw_progress = cache_stats.get(
                const.PRES_ASSIGNEE_CHORES_APPROVED_TODAY, const.DEFAULT_ZERO
            )

        associated_chore = const.SENTINEL_EMPTY
        selected_chore_id = achievement.get(const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID)
        if selected_chore_id:
            associated_chore = (
                cast(
                    "ChoreData", self.coordinator.chores_data.get(selected_chore_id, {})
                ).get(const.DATA_CHORE_NAME)
                or const.SENTINEL_EMPTY
            )

        assigned_assignees_ids = achievement.get(
            const.DATA_ACHIEVEMENT_ASSIGNED_ASSIGNEES, []
        )
        assigned_assignees_names = [
            name
            for k_id in assigned_assignees_ids
            if (
                name := get_item_name_or_log_error(
                    "assignee",
                    k_id,
                    self.coordinator.assignees_data.get(k_id, {}),
                    const.DATA_USER_NAME,
                )
            )
        ]

        stored_labels = achievement.get(const.DATA_ACHIEVEMENT_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label)
            for label in cast("list", stored_labels)
        ]

        return {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_ACHIEVEMENT_PROGRESS,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_ACHIEVEMENT_NAME: self._achievement_name,
            const.ATTR_DESCRIPTION: achievement.get(
                const.DATA_ACHIEVEMENT_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_ASSIGNED_ASSIGNEES: assigned_assignees_names,
            const.ATTR_TYPE: achievement.get(const.DATA_ACHIEVEMENT_TYPE),
            const.ATTR_ASSOCIATED_CHORE: associated_chore,
            const.ATTR_CRITERIA: achievement.get(
                const.DATA_ACHIEVEMENT_CRITERIA, const.SENTINEL_EMPTY
            ),
            const.ATTR_TARGET_VALUE: target,
            const.ATTR_REWARD_POINTS: achievement.get(
                const.DATA_ACHIEVEMENT_REWARD_POINTS
            ),
            const.ATTR_RAW_PROGRESS: raw_progress,
            const.ATTR_AWARDED: awarded,
            const.ATTR_LABELS: friendly_labels,
        }

    @property
    def icon(self) -> str | None:
        """Return the icon for the achievement."""
        achievement: AchievementData = cast(
            "AchievementData",
            self.coordinator.achievements_data.get(self._achievement_id, {}),
        )
        return achievement.get(const.DATA_ACHIEVEMENT_ICON) or None


# ------------------------------------------------------------------------------------------
class AssigneeChallengeProgressSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Sensor representing a assignee's progress toward a specific challenge.

    Tracks challenge progress as a percentage (0-100) for individual assignee/challenge
    combinations. Supports two challenge types: TOTAL_WITHIN_WINDOW (simple count
    toward target) and DAILY_MIN (required daily minimums summed across date range).
    Includes comprehensive metadata such as start/end dates, target values, reward
    points, associated chore, and award status.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHALLENGE_PROGRESS_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        challenge_id: str,
        challenge_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            challenge_id: Unique identifier for the challenge.
            challenge_name: Display name of the challenge.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._challenge_id = challenge_id
        self._challenge_name = challenge_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{challenge_id}{const.SENSOR_KC_UID_SUFFIX_CHALLENGE_PROGRESS_SENSOR}"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_SENSOR_ATTR_CHALLENGE_NAME: challenge_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{assignee_name}{const.SENSOR_KC_EID_MIDFIX_CHALLENGE_PROGRESS_SENSOR}{challenge_name}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> float:
        """Return the challenge progress percentage.

        Calculates percentage based on challenge type:
        - TOTAL_WITHIN_WINDOW: (count / target) * 100
        - DAILY_MIN: (sum_of_daily_counts / (required_daily * num_days)) * 100

        Returns:
            Progress percentage capped at 100.0, rounded to 1 decimal place.
        """
        challenge: ChallengeData = cast(
            "ChallengeData",
            self.coordinator.challenges_data.get(self._challenge_id, {}),
        )
        target = challenge.get(const.DATA_CHALLENGE_TARGET_VALUE, 1)
        challenge_type = challenge.get(const.DATA_CHALLENGE_TYPE)
        progress_data: ChallengeProgress = challenge.get(
            const.DATA_CHALLENGE_PROGRESS, {}
        ).get(self._assignee_id, {})

        if challenge_type == const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW:
            raw_progress = (
                progress_data.get(const.DATA_CHALLENGE_COUNT, const.DEFAULT_ZERO)
                if isinstance(progress_data, dict)
                else const.DEFAULT_ZERO
            )

        elif challenge_type == const.CHALLENGE_TYPE_DAILY_MIN:
            if isinstance(progress_data, dict):
                daily_counts = progress_data.get(const.DATA_CHALLENGE_DAILY_COUNTS, {})
                raw_progress = sum(daily_counts.values())

                start_date = dt_util.parse_datetime(
                    challenge.get(const.DATA_CHALLENGE_START_DATE) or ""
                )
                end_date = dt_util.parse_datetime(
                    challenge.get(const.DATA_CHALLENGE_END_DATE) or ""
                )

                if start_date and end_date:
                    num_days = (end_date.date() - start_date.date()).days + 1

                else:
                    num_days = 1
                required_daily = challenge.get(const.DATA_CHALLENGE_REQUIRED_DAILY, 1)
                target = required_daily * num_days

            else:
                raw_progress = const.DEFAULT_ZERO

        else:
            raw_progress = const.DEFAULT_ZERO

        percent = (
            (raw_progress / target * 100)
            if target > const.DEFAULT_ZERO
            else const.DEFAULT_ZERO
        )

        return min(100, round(percent, const.DATA_FLOAT_PRECISION))

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes for the challenge progress."""
        challenge: ChallengeData = cast(
            "ChallengeData",
            self.coordinator.challenges_data.get(self._challenge_id, {}),
        )
        target = challenge.get(const.DATA_CHALLENGE_TARGET_VALUE, 1)
        challenge_type = challenge.get(const.DATA_CHALLENGE_TYPE)
        progress_data: ChallengeProgress = challenge.get(
            const.DATA_CHALLENGE_PROGRESS, {}
        ).get(self._assignee_id, {})
        awarded = (
            progress_data.get(const.DATA_CHALLENGE_AWARDED, False)
            if isinstance(progress_data, dict)
            else False
        )

        if challenge_type == const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW:
            raw_progress = (
                progress_data.get(const.DATA_CHALLENGE_COUNT, const.DEFAULT_ZERO)
                if isinstance(progress_data, dict)
                else const.DEFAULT_ZERO
            )
        elif challenge_type == const.CHALLENGE_TYPE_DAILY_MIN:
            if isinstance(progress_data, dict):
                daily_counts = progress_data.get(const.DATA_CHALLENGE_DAILY_COUNTS, {})
                raw_progress = sum(daily_counts.values())
            else:
                raw_progress = const.DEFAULT_ZERO
        else:
            raw_progress = const.DEFAULT_ZERO

        associated_chore = const.SENTINEL_EMPTY
        selected_chore_id = challenge.get(const.DATA_CHALLENGE_SELECTED_CHORE_ID)
        if selected_chore_id:
            associated_chore = (
                cast(
                    "ChoreData", self.coordinator.chores_data.get(selected_chore_id, {})
                ).get(const.DATA_CHORE_NAME)
                or const.SENTINEL_EMPTY
            )

        assigned_assignees_ids = challenge.get(
            const.DATA_CHALLENGE_ASSIGNED_ASSIGNEES, []
        )
        assigned_assignees_names = [
            name
            for k_id in assigned_assignees_ids
            if (
                name := get_item_name_or_log_error(
                    "assignee",
                    k_id,
                    self.coordinator.assignees_data.get(k_id, {}),
                    const.DATA_USER_NAME,
                )
            )
        ]

        stored_labels = challenge.get(const.DATA_CHALLENGE_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label)
            for label in cast("list", stored_labels)
        ]

        return {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_CHALLENGE_PROGRESS,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_CHALLENGE_NAME: self._challenge_name,
            const.ATTR_DESCRIPTION: challenge.get(
                const.DATA_CHALLENGE_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_ASSIGNED_ASSIGNEES: assigned_assignees_names,
            const.ATTR_TYPE: challenge_type,
            const.ATTR_ASSOCIATED_CHORE: associated_chore,
            const.ATTR_CRITERIA: challenge.get(
                const.DATA_CHALLENGE_CRITERIA, const.SENTINEL_EMPTY
            ),
            const.ATTR_TARGET_VALUE: target,
            const.ATTR_REWARD_POINTS: challenge.get(const.DATA_CHALLENGE_REWARD_POINTS),
            const.ATTR_START_DATE: challenge.get(const.DATA_CHALLENGE_START_DATE),
            const.ATTR_END_DATE: challenge.get(const.DATA_CHALLENGE_END_DATE),
            const.ATTR_RAW_PROGRESS: raw_progress,
            const.ATTR_AWARDED: awarded,
            const.ATTR_LABELS: friendly_labels,
        }

    @property
    def icon(self) -> str | None:
        """Return the icon for the challenge.

        Use the icon provided in the challenge data if set, else fallback to default.
        """
        challenge: ChallengeData = cast(
            "ChallengeData",
            self.coordinator.challenges_data.get(self._challenge_id, {}),
        )
        return challenge.get(const.DATA_CHALLENGE_ICON) or None


# ------------------------------------------------------------------------------------------
class SystemDashboardTranslationSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """System-level sensor providing dashboard UI translations for a specific language.

    Created once per language in use across all assignees and approvers. Provides the
    `ui_translations` dict attribute containing all 40+ localization keys for
    the ChoreOps dashboard. Multiple assignees using the same language share one
    translation sensor, reducing overall attribute storage.

    Entity ID format: sensor.kc_ui_dashboard_lang_{language_code}
    Example: sensor.kc_ui_dashboard_lang_en, sensor.kc_ui_dashboard_lang_es
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_DASHBOARD_TRANSLATION

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        language_code: str,
    ):
        """Initialize the translation sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            language_code: ISO language code (e.g., 'en', 'es', 'de').
        """
        super().__init__(coordinator)
        self._entry = entry
        self._language_code = language_code
        self._attr_unique_id = f"{entry.entry_id}_{language_code}{const.SENSOR_KC_UID_SUFFIX_DASHBOARD_LANG}"
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = (
        #     f"{const.SENSOR_KC_PREFIX}"
        #     f"{const.SENSOR_KC_EID_PREFIX_DASHBOARD_LANG}{language_code}"
        # )
        self._attr_translation_placeholders = {
            const.TRANS_KEY_ATTR_LANGUAGE: language_code,
        }
        self._attr_device_info = create_system_device_info(entry)

        # Translations cache - loaded async on entity add
        self._ui_translations: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        """Load translations when entity is added to hass."""
        await super().async_added_to_hass()
        self._ui_translations = await load_dashboard_translation(
            self.hass, self._language_code
        )

    @property
    def native_value(self) -> str:
        """Return the language code as the sensor state."""
        return self._language_code

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the ui_translations dict for dashboard consumption.

        Dashboard templates read this via:
        state_attr('sensor.kc_ui_dashboard_lang_en', 'ui_translations')
        """
        return {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_DASHBOARD_TRANSLATION,
            "ui_translations": self._ui_translations,
            const.TRANS_KEY_ATTR_LANGUAGE: self._language_code,
        }

    @property
    def icon(self) -> str | None:
        """Return None for icons.json fallback."""
        return None


# ------------------------------------------------------------------------------------------
class AssigneeDashboardHelperSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Aggregated dashboard helper sensor for a assignee.

    Provides a consolidated view of all assignee-related entities including chores,
    rewards, badges, bonuses, penalties, achievements, challenges, and point buttons.
    Serves pre-sorted and pre-filtered entity lists to optimize dashboard template
    rendering performance.

    Translations are delegated to system-level translation sensors
    (sensor.kc_ui_dashboard_lang_{code}). This sensor provides a `translation_sensor`
    attribute pointing to the appropriate translation sensor entity ID based on the
    assignee's configured dashboard language.

    This sensor is the single source of truth for the ChoreOps dashboard,
    eliminating expensive frontend list iterations and sorting operations.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_DASHBOARD_HELPER

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        points_label: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            points_label: Customizable label for points currency (e.g., 'Points', 'Stars').

        Note: Translation sensor entity ID is computed dynamically based on assignee's
        current dashboard language, allowing automatic updates when language changes.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._points_label = points_label
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_UI_DASHBOARD_HELPER}"
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # which enforces stricter entity ID validation (no uppercase, spaces, special chars)
        # self.entity_id = (
        #     f"{const.SENSOR_KC_PREFIX}{assignee_name}"
        #     f"{const.SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER}"
        # )
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name
        }
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    def _get_translation_sensor_eid(self) -> str | None:
        """Get the translation sensor entity ID for this assignee's current language.

        Dynamically computed based on assignee's dashboard_language setting.
        If the translation sensor doesn't exist yet (new language), triggers
        creation via coordinator.ensure_translation_sensor_exists().

        Returns:
            Entity ID of the translation sensor or None if not found in registry
        """
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )
        lang_code = assignee_info.get(
            const.DATA_ASSIGNEE_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
        )

        # Check if sensor exists; if not, schedule async creation
        if not self.coordinator.ui_manager.is_translation_sensor_created(lang_code):
            # Create new sensor asynchronously - entity will update on next cycle
            self.hass.add_job(
                self.coordinator.ui_manager.ensure_translation_sensor_exists(lang_code)
            )
            # Return None for now (sensor will exist after async creation completes)
            return None

        # Look up entity ID from registry
        return self.coordinator.ui_manager.get_translation_sensor_eid(lang_code)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        Checks if pending approvals changed to force attribute rebuild.
        Translation handling is now delegated to the system-level translation sensor.
        """
        # Check if pending approvals changed - forces attribute rebuild
        # Flags are reset in extra_state_attributes after rebuild
        if (
            self.coordinator.ui_manager.pending_chore_changed
            or self.coordinator.ui_manager.pending_reward_changed
        ):
            # Flag set - attributes will rebuild in next extra_state_attributes call
            pass

        super()._handle_coordinator_update()

    def _get_next_monday_7am_local(self) -> datetime:
        """Calculate the next Monday at 7:00 AM local time.

        Uses snap_to_weekday from schedule_engine to find next Monday.
        If currently Monday before 7am, returns today at 7am, otherwise next Monday.
        """
        now_local = dt_now_local()

        # Calculate days until the upcoming Monday (0 = Monday)
        # If today is Tuesday (1), (0-1)%7 = 6 days ahead.
        # If today is Monday (0), (0-0)%7 = 0 days ahead.
        days_ahead = (0 - now_local.weekday()) % 7

        # Set reference time to Today at 7:00 AM
        target = now_local.replace(hour=7, minute=0, second=0, microsecond=0)

        # Move forward to the correct day
        target += timedelta(days=days_ahead)

        # If the result is in the past (e.g., it's Monday 8:00 AM), add 1 week
        if target <= now_local:
            target += timedelta(weeks=1)

        return target

    def _calculate_chore_attributes(
        self,
        chore_id: str,
        chore_info: ChoreData,
        assignee_info: AssigneeData,
        chore_eid,
    ) -> dict | None:
        """Calculate minimal attributes for a single chore in dashboard helper.

        Returns a dictionary with only the essential chore attributes needed for
        dashboard list rendering and sorting. Additional attributes (due_date,
        can_claim, can_approve, timestamps, etc.) should be fetched from the
        chore status sensor via state_attr(chore.eid, 'attribute_name').

        Minimal fields (9 total as of Phase 4):
        - eid: entity_id (for fetching additional attributes from chore sensor)
        - name: chore name (for display)
        - status: pending/claimed/approved/overdue (for status coloring)
        - labels: list of label strings (for label filtering)
        - primary_group: today/this_week/other (for grouping)
        - is_today_am: boolean or None (for AM/PM sorting)
        - lock_reason: str | None (waiting/not_my_turn/missed, Phase 4 rotation support)
        - turn_assignee_name: str | None (current turn holder name for rotation chores)
        - available_at: str | None (ISO datetime when waiting chore becomes claimable)

        Uses get_chore_status_context() for single bulk fetch instead of
        multiple individual manager calls.

        Returns None if chore name is missing (data corruption).
        """
        chore_name = get_item_name_or_log_error(
            "chore", chore_id, chore_info, const.DATA_CHORE_NAME
        )
        if not chore_name:
            return None

        # Single bulk fetch for all status data
        ctx = self.coordinator.chore_manager.get_chore_status_context(
            self._assignee_id, chore_id
        )
        status = ctx[const.CHORE_CTX_STATE]
        due_date_str = ctx[const.CHORE_CTX_DUE_DATE]
        is_due = ctx[const.CHORE_CTX_IS_DUE]

        # Get chore labels (always a list, even if empty)
        chore_labels = chore_info.get(const.DATA_CHORE_LABELS, [])
        if not isinstance(chore_labels, list):
            chore_labels = []

        # Convert due date to local datetime for grouping calculations
        due_date_local_dt = None
        if due_date_str:
            due_date_utc = dt_to_utc(due_date_str)
            if due_date_utc:
                due_date_local_dt = dt_format(
                    due_date_utc, const.HELPER_RETURN_DATETIME_LOCAL
                )

        # Calculate is_today_am (only if due date exists and is today)
        is_today_am = None
        if due_date_local_dt and isinstance(due_date_local_dt, datetime):
            today_local = dt_today_local()
            if due_date_local_dt.date() == today_local and due_date_local_dt.hour < 12:
                is_today_am = True
            elif due_date_local_dt.date() == today_local:
                is_today_am = False

        # Calculate primary_group for dashboard grouping
        recurring_frequency = chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY) or ""
        primary_group = self._calculate_primary_group(
            status, is_due, due_date_local_dt, recurring_frequency
        )

        # Phase 4: Calculate rotation-aware attributes using ChoreEngine
        lock_reason = ctx.get(const.CHORE_CTX_LOCK_REASON)
        turn_assignee_name = None
        available_at = ctx.get(const.CHORE_CTX_AVAILABLE_AT)

        # For rotation chores, get current turn holder name
        if ChoreEngine.is_rotation_mode(chore_info):
            current_turn_assignee_id = chore_info.get(
                const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID
            )
            if current_turn_assignee_id:
                turn_assignee_info: Any = self.coordinator.assignees_data.get(
                    current_turn_assignee_id, {}
                )
                turn_assignee_name = turn_assignee_info.get(const.DATA_USER_NAME)

        # Return the 9 fields needed for Phase 4 dashboard rendering
        return {
            const.ATTR_EID: chore_eid,
            const.ATTR_NAME: chore_name,
            const.ATTR_STATUS: status,
            const.ATTR_CHORE_LABELS: chore_labels,
            const.ATTR_CHORE_PRIMARY_GROUP: primary_group,
            const.ATTR_CHORE_IS_TODAY_AM: is_today_am,
            const.ATTR_CHORE_LOCK_REASON: lock_reason,
            const.ATTR_CHORE_TURN_ASSIGNEE_NAME: turn_assignee_name,
            const.ATTR_CHORE_AVAILABLE_AT: available_at,
        }

    def _calculate_primary_group(
        self, status: str, is_due: bool, due_date_local, recurring_frequency: str
    ) -> str:
        """Calculate the primary group for a chore.

        Primary group is determined by the due date timing and due window status.
        This ensures a chore stays in the same group even when transitioning
        from pending → due → claimed → approved.

        Args:
            status: The derived display state (from context provider)
            is_due: Whether chore is in due window (from context provider)
            due_date_local: Local datetime or None
            recurring_frequency: Chore frequency string

        Returns: "today", "this_week", or "other"
        """
        # Overdue chores always go to today group (past due date)
        if status == const.CHORE_STATE_OVERDUE:
            return const.PRIMARY_GROUP_TODAY

        # If chore is in due window (regardless of actual due date), it goes to today
        if is_due:
            return const.PRIMARY_GROUP_TODAY

        # Check due date if available
        if due_date_local and isinstance(due_date_local, datetime):
            today_local = dt_today_local()

            # Past due dates -> today group (catches claimed/approved chores that were overdue)
            if due_date_local.date() < today_local:
                return const.PRIMARY_GROUP_TODAY

            # Due today -> today group
            if due_date_local.date() == today_local:
                return const.PRIMARY_GROUP_TODAY

            # Due before next Monday 7am -> this_week group
            next_monday_7am = self._get_next_monday_7am_local()
            if due_date_local < next_monday_7am:
                return const.PRIMARY_GROUP_THIS_WEEK

            # Due later -> other group
            return const.PRIMARY_GROUP_OTHER

        # No due date - check recurring frequency
        if recurring_frequency == const.FREQUENCY_DAILY:
            return const.PRIMARY_GROUP_TODAY
        if recurring_frequency == const.FREQUENCY_WEEKLY:
            return const.PRIMARY_GROUP_THIS_WEEK

        return const.PRIMARY_GROUP_OTHER

    @property
    def native_value(self) -> Any:
        """Return an overall summary string. Primary consumers should use attributes."""
        # Provide a short human-readable summary
        # Count chores by status using context provider for single bulk fetch per chore
        chores = []
        for chore_id, chore_info in self.coordinator.chores_data.items():
            if self._assignee_id not in chore_info.get(
                const.DATA_CHORE_ASSIGNED_ASSIGNEES, []
            ):
                continue
            chore_name = get_item_name_or_log_error(
                "chore", chore_id, chore_info, const.DATA_CHORE_NAME
            )
            if not chore_name:
                continue
            # Get status from context provider (single bulk fetch)
            ctx = self.coordinator.chore_manager.get_chore_status_context(
                self._assignee_id, chore_id
            )
            chores.append(
                {
                    "id": chore_id,
                    "name": chore_name,
                    "status": ctx[const.CHORE_CTX_STATE],
                }
            )

        # Rewards: list name and cost
        rewards = []
        for reward_id, reward_info in self.coordinator.rewards_data.items():
            reward_name = get_item_name_or_log_error(
                "reward", reward_id, reward_info, const.DATA_REWARD_NAME
            )
            if not reward_name:
                continue
            cost = reward_info.get(const.DATA_REWARD_COST, const.DEFAULT_REWARD_COST)
            rewards.append({"id": reward_id, "name": reward_name, "cost": cost})

        # Count badges, bonuses, penalties for this assignee
        # Badge applies if: no assignees assigned (applies to all) OR assignee is in assigned list
        badges_count = len(
            [
                b
                for b in self.coordinator.badges_data.values()
                if not b.get(const.DATA_BADGE_ASSIGNED_TO, [])
                or self._assignee_id in b.get(const.DATA_BADGE_ASSIGNED_TO, [])
            ]
        )
        bonuses_count = len(self.coordinator.bonuses_data)
        penalties_count = len(self.coordinator.penalties_data)

        # Count achievements and challenges assigned to this assignee
        achievements_count = len(
            [
                a
                for a in self.coordinator.achievements_data.values()
                if self._assignee_id
                in a.get(const.DATA_ACHIEVEMENT_ASSIGNED_ASSIGNEES, [])
            ]
        )
        challenges_count = len(
            [
                c
                for c in self.coordinator.challenges_data.values()
                if self._assignee_id
                in c.get(const.DATA_CHALLENGE_ASSIGNED_ASSIGNEES, [])
            ]
        )

        # Minimal native value summarizing counts
        return f"chores:{len(chores)} rewards:{len(rewards)} badges:{badges_count} bonuses:{bonuses_count} penalties:{penalties_count} achievements:{achievements_count} challenges:{challenges_count}"

    def _build_core_sensors(self, entity_registry) -> dict[str, str | None]:
        """Build core sensor entity IDs for dashboard use.

        Looks up entity IDs from the registry by unique ID to ensure correct
        entity references even if users have renamed entities.

        Args:
            entity_registry: Entity registry instance from hass.

        Returns:
            dict: {
                "points_eid": "sensor.kc_assignee_name_points" or None,
                "chores_eid": "sensor.kc_assignee_name_chores" or None,
                "badges_eid": "sensor.kc_assignee_name_badges" or None
            }
        """
        sensor_types = [
            (const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_SENSOR, "points_eid"),
            (const.SENSOR_KC_UID_SUFFIX_CHORES_SENSOR, "chores_eid"),
            (const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_BADGES_SENSOR, "badges_eid"),
        ]

        core_sensors = {}
        for suffix, key in sensor_types:
            unique_id = f"{self._entry.entry_id}_{self._assignee_id}{suffix}"
            try:
                entity_id = entity_registry.async_get_entity_id(
                    "sensor", const.DOMAIN, unique_id
                )
                core_sensors[key] = entity_id
            except (KeyError, ValueError, AttributeError):
                core_sensors[key] = None

        return core_sensors

    def _build_dashboard_helpers(self, entity_registry) -> dict[str, str | None]:
        """Build dashboard helper entity IDs for dashboard use.

        Looks up entity IDs from the registry by unique ID to ensure correct
        entity references even if users have renamed entities.

        Args:
            entity_registry: Entity registry instance from hass.

        Returns:
            dict: {
                "date_helper_eid": "datetime.kc_assignee_name_ui_dashboard_date_helper" or None,
                "chore_select_eid": "select.kc_assignee_name_ui_dashboard_chore_list_helper" or None
            }
        """
        # Datetime helper uses SUFFIX pattern: entry_id_assignee_id + SUFFIX
        datetime_unique_id = f"{self._entry.entry_id}_{self._assignee_id}{const.DATETIME_KC_UID_SUFFIX_DATE_HELPER}"

        # Select helper uses SUFFIX pattern: entry_id_assignee_id + SUFFIX
        select_unique_id = f"{self._entry.entry_id}_{self._assignee_id}{const.SELECT_KC_UID_SUFFIX_ASSIGNEE_DASHBOARD_HELPER_CHORES_SELECT}"

        dashboard_helpers = {}

        # Look up datetime helper
        try:
            entity_id = entity_registry.async_get_entity_id(
                "datetime", const.DOMAIN, datetime_unique_id
            )
            dashboard_helpers["date_helper_eid"] = entity_id
        except (KeyError, ValueError, AttributeError):
            dashboard_helpers["date_helper_eid"] = None

        # Look up select helper
        try:
            entity_id = entity_registry.async_get_entity_id(
                "select", const.DOMAIN, select_unique_id
            )
            dashboard_helpers["chore_select_eid"] = entity_id
        except (KeyError, ValueError, AttributeError):
            dashboard_helpers["chore_select_eid"] = None

        return dashboard_helpers

    def _build_pending_approvals(self, entity_registry) -> dict:
        """Build pending approvals data with button entity IDs.

        Returns:
            dict: {
                "chores": [
                    {
                        "chore_id": "uuid",
                        "chore_name": "Take out Trash",
                        "timestamp": "2024-01-15T10:30:00+00:00",
                        "approve_button_eid": "button.kc_assignee_a_chore_1_approve",
                        "disapprove_button_eid": "button.kc_assignee_a_chore_1_disapprove"
                    }
                ],
                "rewards": [...]
            }
        """
        pending_chores = []
        pending_rewards = []

        # Get all pending approvals from coordinator via public properties
        pending_chore_approvals = self.coordinator.chore_manager.pending_chore_approvals
        pending_reward_approvals = (
            self.coordinator.reward_manager.get_pending_approvals()
        )

        # Filter for this assignee's pending chores
        for approval in pending_chore_approvals:
            if approval.get(const.DATA_ASSIGNEE_ID) != self._assignee_id:
                continue

            chore_id = approval.get(const.DATA_CHORE_ID)
            if not chore_id:
                continue
            chore_info: ChoreData = cast(
                "ChoreData", self.coordinator.chores_data.get(chore_id, {})
            )
            chore_name = get_item_name_or_log_error(
                "chore", chore_id, chore_info, const.DATA_CHORE_NAME
            )
            if not chore_name:
                continue

            # Build button unique IDs and lookup entity IDs
            approve_uid = (
                f"{self._entry.entry_id}_{self._assignee_id}_{chore_id}"
                f"{const.BUTTON_KC_UID_SUFFIX_APPROVE}"
            )
            disapprove_uid = (
                f"{self._entry.entry_id}_{self._assignee_id}_{chore_id}"
                f"{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE}"
            )

            approve_eid = None
            disapprove_eid = None
            if entity_registry:
                approve_eid = entity_registry.async_get_entity_id(
                    "button", const.DOMAIN, approve_uid
                )
                disapprove_eid = entity_registry.async_get_entity_id(
                    "button", const.DOMAIN, disapprove_uid
                )

            pending_chores.append(
                {
                    "chore_id": chore_id,
                    "chore_name": chore_name,
                    "timestamp": approval.get(const.DATA_CHORE_TIMESTAMP),
                    "approve_button_eid": approve_eid,
                    "disapprove_button_eid": disapprove_eid,
                }
            )

        # Filter for this assignee's pending rewards
        for approval in pending_reward_approvals:
            if approval.get(const.DATA_ASSIGNEE_ID) != self._assignee_id:
                continue

            reward_id = approval.get(const.DATA_REWARD_ID)
            if not reward_id:
                continue
            reward_info: RewardData = cast(
                "RewardData", self.coordinator.rewards_data.get(reward_id, {})
            )
            reward_name = get_item_name_or_log_error(
                "reward", reward_id, reward_info, const.DATA_REWARD_NAME
            )
            if not reward_name:
                continue

            # Build button unique IDs and lookup entity IDs
            approve_uid = (
                f"{self._entry.entry_id}_{self._assignee_id}_{reward_id}"
                f"{const.BUTTON_KC_UID_SUFFIX_APPROVE_REWARD}"
            )
            disapprove_uid = (
                f"{self._entry.entry_id}_{self._assignee_id}_{reward_id}"
                f"{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE_REWARD}"
            )

            approve_eid = None
            disapprove_eid = None
            if entity_registry:
                approve_eid = entity_registry.async_get_entity_id(
                    "button", const.DOMAIN, approve_uid
                )
                disapprove_eid = entity_registry.async_get_entity_id(
                    "button", const.DOMAIN, disapprove_uid
                )

            pending_rewards.append(
                {
                    "reward_id": reward_id,
                    "reward_name": reward_name,
                    "timestamp": approval.get(const.DATA_REWARD_TIMESTAMP),
                    "approve_button_eid": approve_eid,
                    "disapprove_button_eid": disapprove_eid,
                }
            )

        return {"chores": pending_chores, "rewards": pending_rewards}

    @property
    def extra_state_attributes(self) -> dict:
        """Return detailed aggregated structure as attributes.

        Format:
        {
          "chores": [
            {"eid": "sensor.assignee_a_chore_1", "name": "Take out Trash", "status": "overdue"},
            ...
          ],
          "rewards": [
            {"eid": "sensor.assignee_a_reward_1", "name": "Ice Cream", "cost": "10 Points"},
            ...
          ],
        }
        """
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )

        try:
            entity_registry = async_get(self.hass)
        except (KeyError, ValueError, AttributeError):
            entity_registry = None

        gamification_enabled = should_create_gamification_entities(
            self.coordinator, self._assignee_id
        )
        chore_workflow_enabled = should_create_workflow_buttons(
            self.coordinator, self._assignee_id
        )

        chores_attr = []

        for chore_id, chore_info in self.coordinator.chores_data.items():
            if self._assignee_id not in chore_info.get(
                const.DATA_CHORE_ASSIGNED_ASSIGNEES, []
            ):
                continue

            # Get the ChoreStatusSensor entity_id
            chore_eid = None
            if entity_registry:
                unique_id = f"{self._entry.entry_id}_{self._assignee_id}_{chore_id}{const.SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR}"
                chore_eid = entity_registry.async_get_entity_id(
                    "sensor", const.DOMAIN, unique_id
                )

            # Use helper method to calculate all chore attributes
            chore_attrs = self._calculate_chore_attributes(
                chore_id, chore_info, assignee_info, chore_eid
            )
            if chore_attrs:  # Skip if name missing (data corruption)
                chores_attr.append(chore_attrs)

        # Sort chores by due date (ascending, earliest first)
        # Chores without due dates are placed at the end, sorted by entity_id
        chores_attr.sort(
            key=lambda c: (
                c.get(const.ATTR_CHORE_DUE_DATE) is None,  # None values go last
                c.get(const.ATTR_CHORE_DUE_DATE)
                or "",  # Sort by due_date (ISO format sorts correctly)
                c.get(const.ATTR_EID)
                or "",  # Then by entity_id for chores without due dates
            )
        )

        rewards_attr = []
        if gamification_enabled:
            for reward_id, reward_info in self.coordinator.rewards_data.items():
                reward_name = get_item_name_or_log_error(
                    "reward", reward_id, reward_info, const.DATA_REWARD_NAME
                )
                if not reward_name:
                    continue

                # Get the RewardStatusSensor entity_id
                reward_eid = None
                if entity_registry:
                    unique_id = f"{self._entry.entry_id}_{self._assignee_id}_{reward_id}{const.SENSOR_KC_UID_SUFFIX_REWARD_STATUS_SENSOR}"
                    reward_eid = entity_registry.async_get_entity_id(
                        "sensor", const.DOMAIN, unique_id
                    )

                # Get reward status from the sensor state
                reward_status = None
                if reward_eid:
                    state_obj = self.hass.states.get(reward_eid)
                    if state_obj:
                        reward_status = state_obj.state

                # Get reward labels (always a list, even if empty)
                reward_labels = reward_info.get(const.DATA_REWARD_LABELS, [])
                if not isinstance(reward_labels, list):
                    reward_labels = []

                # Get reward cost
                reward_cost = reward_info.get(const.DATA_REWARD_COST, 0)

                # Get claims and approvals counts using get_period_total
                reward_data_entry = assignee_info.get(
                    const.DATA_ASSIGNEE_REWARD_DATA, {}
                ).get(reward_id, {})
                periods = reward_data_entry.get(
                    const.DATA_ASSIGNEE_REWARD_DATA_PERIODS, {}
                )
                period_key_mapping = {
                    const.PERIOD_ALL_TIME: const.DATA_ASSIGNEE_REWARD_DATA_PERIODS_ALL_TIME
                }
                claims_count = self.coordinator.stats.get_period_total(
                    periods,
                    const.PERIOD_ALL_TIME,
                    const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_CLAIMED,
                    period_key_mapping=period_key_mapping,
                )
                approvals_count = self.coordinator.stats.get_period_total(
                    periods,
                    const.PERIOD_ALL_TIME,
                    const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_APPROVED,
                    period_key_mapping=period_key_mapping,
                )

                rewards_attr.append(
                    {
                        const.ATTR_EID: reward_eid,
                        const.ATTR_NAME: reward_name,
                        const.ATTR_STATUS: reward_status,
                        const.ATTR_LABELS: reward_labels,
                        const.ATTR_COST: reward_cost,
                        const.ATTR_CLAIMS: claims_count,
                        const.ATTR_APPROVALS: approvals_count,
                    }
                )

            # Sort rewards by name (alphabetically)
            rewards_attr.sort(key=lambda r: str(r.get(const.ATTR_NAME, "")).lower())

        # Badges assigned to this assignee - only build if gamification is enabled
        # Badge applies if: no assignees assigned (applies to all) OR assignee is in assigned list
        # Note: Cumulative badges return system-level badge sensor (no assignee-specific progress sensor)
        # Other badge types return assignee-specific progress sensors
        badges_attr = []
        if gamification_enabled:
            for badge_id, badge_info in self.coordinator.badges_data.items():
                assigned_to = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
                if assigned_to and self._assignee_id not in assigned_to:
                    continue
                badge_type = badge_info.get(const.DATA_BADGE_TYPE, const.SENTINEL_EMPTY)
                badge_name = get_item_name_or_log_error(
                    "badge", badge_id, badge_info, const.DATA_BADGE_NAME
                )
                if not badge_name:
                    continue

                # For cumulative badges, return the system-level badge sensor
                # For other types, return the assignee-specific progress sensor
                badge_eid = None
                if entity_registry:
                    if badge_type == const.BADGE_TYPE_CUMULATIVE:
                        # System badge sensor (no assignee_id in unique_id)
                        unique_id = f"{self._entry.entry_id}_{badge_id}{const.SENSOR_KC_UID_SUFFIX_BADGE_SENSOR}"
                        badge_eid = entity_registry.async_get_entity_id(
                            "sensor", const.DOMAIN, unique_id
                        )
                    else:
                        # Assignee-specific progress sensor
                        unique_id = f"{self._entry.entry_id}_{self._assignee_id}_{badge_id}{const.SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR}"
                        badge_eid = entity_registry.async_get_entity_id(
                            "sensor", const.DOMAIN, unique_id
                        )

                # Check if badge is earned (in badges_earned dict)
                badges_earned = assignee_info.get(const.DATA_ASSIGNEE_BADGES_EARNED, {})
                is_earned = badge_id in badges_earned
                badge_earned = (
                    badges_earned.get(badge_id, {})
                    if isinstance(badges_earned, dict)
                    else {}
                )
                periods = badge_earned.get(
                    const.DATA_ASSIGNEE_BADGES_EARNED_PERIODS, {}
                )
                period_key_mapping = {
                    const.PERIOD_ALL_TIME: const.DATA_ASSIGNEE_BADGES_EARNED_PERIODS_ALL_TIME
                }
                earned_count = self.coordinator.stats.get_period_total(
                    periods,
                    const.PERIOD_ALL_TIME,
                    const.DATA_ASSIGNEE_BADGES_EARNED_AWARD_COUNT,
                    period_key_mapping=period_key_mapping,
                )

                # Get badge status from assignee's badge progress (only for non-cumulative)
                badge_status = const.SENTINEL_NONE
                if badge_type != const.BADGE_TYPE_CUMULATIVE:
                    badge_progress = assignee_info.get(
                        const.DATA_ASSIGNEE_BADGE_PROGRESS, {}
                    ).get(badge_id, {})
                    badge_status = badge_progress.get(
                        const.DATA_ASSIGNEE_BADGE_PROGRESS_STATUS, const.SENTINEL_NONE
                    )
                    badges_attr.append(
                        {
                            const.ATTR_EID: badge_eid,
                            const.ATTR_NAME: badge_name,
                            const.ATTR_BADGE_TYPE: badge_type,
                            const.ATTR_STATUS: badge_status,
                            const.ATTR_BADGE_EARNED: is_earned,
                            const.ATTR_EARNED_COUNT: earned_count,
                        }
                    )
                else:
                    # Cumulative badge - no status
                    badges_attr.append(
                        {
                            const.ATTR_EID: badge_eid,
                            const.ATTR_NAME: badge_name,
                            const.ATTR_BADGE_TYPE: badge_type,
                            const.ATTR_BADGE_EARNED: is_earned,
                            const.ATTR_EARNED_COUNT: earned_count,
                        }
                    )

            # Sort badges by name (alphabetically)
            badges_attr.sort(key=lambda b: str(b.get(const.ATTR_NAME, "")).lower())

        # Bonuses for this assignee - only build if gamification is enabled
        bonuses_attr = []
        if gamification_enabled:
            for bonus_id, bonus_info in self.coordinator.bonuses_data.items():
                bonus_name = get_item_name_or_log_error(
                    "bonus", bonus_id, bonus_info, const.DATA_BONUS_NAME
                )
                if not bonus_name:
                    continue
                # Get ApproverBonusApplyButton entity_id
                bonus_eid = None
                if entity_registry:
                    unique_id = f"{self._entry.entry_id}_{self._assignee_id}_{bonus_id}{const.BUTTON_KC_UID_SUFFIX_APPROVER_BONUS_APPLY}"
                    bonus_eid = entity_registry.async_get_entity_id(
                        "button", const.DOMAIN, unique_id
                    )

                # Get bonus points
                bonus_points = bonus_info.get(const.DATA_BONUS_POINTS, 0)

                # Get applied count for this bonus for this assignee
                bonus_applies = assignee_info.get(const.DATA_ASSIGNEE_BONUS_APPLIES, {})
                bonus_entry = bonus_applies.get(bonus_id)
                if bonus_entry:
                    periods = bonus_entry.get(const.DATA_ASSIGNEE_BONUS_PERIODS, {})
                    applied_count = self.coordinator.stats.get_period_total(
                        periods,
                        const.PERIOD_ALL_TIME,
                        const.DATA_ASSIGNEE_BONUS_PERIOD_APPLIES,
                    )
                else:
                    applied_count = 0

                bonuses_attr.append(
                    {
                        const.ATTR_EID: bonus_eid,
                        const.ATTR_NAME: bonus_name,
                        const.ATTR_POINTS: bonus_points,
                        const.ATTR_APPLIED: applied_count,
                    }
                )

            # Sort bonuses by name (alphabetically)
            bonuses_attr.sort(key=lambda b: str(b.get(const.ATTR_NAME, "")).lower())
        # Bonuses for this assignee
        # Penalties for this assignee - only build if gamification is enabled
        penalties_attr = []
        if gamification_enabled:
            for penalty_id, penalty_info in self.coordinator.penalties_data.items():
                penalty_name = get_item_name_or_log_error(
                    "penalty", penalty_id, penalty_info, const.DATA_PENALTY_NAME
                )
                if not penalty_name:
                    continue
                # Get ApproverPenaltyApplyButton entity_id
                penalty_eid = None
                if entity_registry:
                    unique_id = f"{self._entry.entry_id}_{self._assignee_id}_{penalty_id}{const.BUTTON_KC_UID_SUFFIX_APPROVER_PENALTY_APPLY}"
                    penalty_eid = entity_registry.async_get_entity_id(
                        "button", const.DOMAIN, unique_id
                    )

                # Get penalty points (stored as positive, represents points removed)
                penalty_points = penalty_info.get(const.DATA_PENALTY_POINTS, 0)

                # Get applied count for this penalty for this assignee
                penalty_applies = assignee_info.get(
                    const.DATA_ASSIGNEE_PENALTY_APPLIES, {}
                )
                penalty_entry = penalty_applies.get(penalty_id)
                if penalty_entry:
                    periods = penalty_entry.get(const.DATA_ASSIGNEE_PENALTY_PERIODS, {})
                    applied_count = self.coordinator.stats.get_period_total(
                        periods,
                        const.PERIOD_ALL_TIME,
                        const.DATA_ASSIGNEE_PENALTY_PERIOD_APPLIES,
                    )
                else:
                    applied_count = 0

                penalties_attr.append(
                    {
                        const.ATTR_EID: penalty_eid,
                        const.ATTR_NAME: penalty_name,
                        const.ATTR_POINTS: penalty_points,
                        const.ATTR_APPLIED: applied_count,
                    }
                )

            # Sort penalties by name (alphabetically)
            penalties_attr.sort(key=lambda p: str(p.get(const.ATTR_NAME, "")).lower())
        # Penalties for this assignee
        # Achievements assigned to this assignee - only build if gamification is enabled
        achievements_attr = []
        if gamification_enabled:
            for (
                achievement_id,
                achievement_info,
            ) in self.coordinator.achievements_data.items():
                if self._assignee_id not in achievement_info.get(
                    const.DATA_ACHIEVEMENT_ASSIGNED_ASSIGNEES, []
                ):
                    continue
                achievement_name = get_item_name_or_log_error(
                    "achievement",
                    achievement_id,
                    achievement_info,
                    const.DATA_ACHIEVEMENT_NAME,
                )
                if not achievement_name:
                    continue
                # Get AssigneeAchievementProgressSensor entity_id
                achievement_eid = None
                if entity_registry:
                    unique_id = f"{self._entry.entry_id}_{self._assignee_id}_{achievement_id}{const.SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_PROGRESS_SENSOR}"
                    achievement_eid = entity_registry.async_get_entity_id(
                        "sensor", const.DOMAIN, unique_id
                    )
                achievements_attr.append(
                    {
                        const.ATTR_EID: achievement_eid,
                        const.ATTR_NAME: achievement_name,
                    }
                )

            # Sort achievements by name (alphabetically)
            achievements_attr.sort(key=lambda a: (a.get(const.ATTR_NAME) or "").lower())

        # Challenges assigned to this assignee - only build if gamification is enabled
        challenges_attr = []
        if gamification_enabled:
            for (
                challenge_id,
                challenge_info,
            ) in self.coordinator.challenges_data.items():
                if self._assignee_id not in challenge_info.get(
                    const.DATA_CHALLENGE_ASSIGNED_ASSIGNEES, []
                ):
                    continue
                challenge_name = get_item_name_or_log_error(
                    "challenge", challenge_id, challenge_info, const.DATA_CHALLENGE_NAME
                )
                if not challenge_name:
                    continue
                # Get AssigneeChallengeProgressSensor entity_id
                challenge_eid = None
                if entity_registry:
                    unique_id = f"{self._entry.entry_id}_{self._assignee_id}_{challenge_id}{const.SENSOR_KC_UID_SUFFIX_CHALLENGE_PROGRESS_SENSOR}"
                    challenge_eid = entity_registry.async_get_entity_id(
                        "sensor", const.DOMAIN, unique_id
                    )
                challenges_attr.append(
                    {
                        const.ATTR_EID: challenge_eid,
                        const.ATTR_NAME: challenge_name,
                    }
                )

            # Sort challenges by name (alphabetically)
            challenges_attr.sort(key=lambda c: (c.get(const.ATTR_NAME) or "").lower())

        # Point adjustment buttons for this assignee - only build if gamification is enabled
        points_buttons_attr = []
        if gamification_enabled and entity_registry:
            from .helpers.entity_helpers import get_points_adjustment_buttons

            buttons = get_points_adjustment_buttons(
                self.hass, self._entry.entry_id, self._assignee_id
            )
            # Remove delta key used internally for sorting
            points_buttons_attr = [
                {"eid": b["eid"], "name": b["name"]} for b in buttons
            ]

        # Get assignee's preferred dashboard language (default to English)
        assignee_info_lang: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )
        dashboard_language = assignee_info_lang.get(
            const.DATA_ASSIGNEE_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
        )

        # Build chores_by_label dictionary
        # Group chores by label, with entity IDs sorted by due date
        chores_by_label: dict[str, Any] = {}
        for chore in chores_attr:
            labels = chore.get(const.ATTR_CHORE_LABELS, [])
            chore_eid = chore.get(const.ATTR_EID)

            # Skip chores without entity IDs
            if not chore_eid:
                continue

            # Add this chore to each label group it belongs to
            for label in labels:
                if label not in chores_by_label:
                    chores_by_label[label] = []
                chores_by_label[label].append(chore)

        # Sort chores within each label by due date (ascending, earliest first)
        # Chores without due dates are placed at the end, sorted by entity_id
        for label, chore_list in chores_by_label.items():
            chore_list.sort(
                key=lambda c: (
                    c.get(const.ATTR_CHORE_DUE_DATE) is None,  # None values go last
                    c.get(const.ATTR_CHORE_DUE_DATE)
                    or "",  # Sort by due_date (ISO format sorts correctly)
                    c.get(const.ATTR_EID)
                    or "",  # Then by entity_id for chores without due dates
                )
            )
            # Convert to list of entity IDs only
            chores_by_label[label] = [c[const.ATTR_EID] for c in chore_list]

        # Sort labels alphabetically for consistent ordering
        chores_by_label = dict(sorted(chores_by_label.items()))

        # Build pending approvals data if flags indicate changes
        pending_approvals = self._build_pending_approvals(entity_registry)

        # Reset change flags after building attributes
        self.coordinator.ui_manager.reset_pending_change_flags()

        # Build core sensors dict (used by dashboard to avoid slug construction)
        core_sensors = self._build_core_sensors(entity_registry)

        # Build dashboard helpers dict (used by dashboard to avoid slug construction)
        dashboard_helpers = self._build_dashboard_helpers(entity_registry)

        return {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_DASHBOARD_HELPER,
            "chores": chores_attr,
            const.ATTR_CHORES_BY_LABEL: chores_by_label,
            "rewards": rewards_attr,
            "badges": badges_attr,
            "bonuses": bonuses_attr,
            "penalties": penalties_attr,
            "achievements": achievements_attr,
            "challenges": challenges_attr,
            "points_buttons": points_buttons_attr,
            "pending_approvals": pending_approvals,
            "core_sensors": core_sensors,
            "dashboard_helpers": dashboard_helpers,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_TRANSLATION_SENSOR: self._get_translation_sensor_eid(),
            "language": dashboard_language,
            "is_feature_gated_profile": is_user_feature_gated_profile(
                self.coordinator, self._assignee_id
            ),
            "gamification_enabled": gamification_enabled,
            "chore_workflow_enabled": chore_workflow_enabled,
        }

    @property
    def icon(self) -> str | None:
        """Return None for icons.json fallback."""
        return None
