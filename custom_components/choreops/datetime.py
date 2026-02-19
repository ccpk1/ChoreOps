# pyright: reportIncompatibleVariableOverride=false
# ^ Suppresses Pylance warnings about @property overriding @cached_property from base classes.
#   This is intentional: our entities compute dynamic values on each access,
#   so we use @property instead of @cached_property to avoid stale cached data.
"""DateTime platform for KidsChores integration.

Provides datetime helper entities for UI date/time selection in dashboards.
"""

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from . import const
from .coordinator import KidsChoresConfigEntry, KidsChoresDataCoordinator
from .helpers.device_helpers import create_kid_device_info_from_coordinator
from .helpers.entity_helpers import is_user_feature_gated_profile, should_create_entity

# Platinum requirement: Parallel Updates
# Set to 1 (serialized) for entities that modify state
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KidsChoresConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up KidsChores datetime entities."""
    coordinator: KidsChoresDataCoordinator = entry.runtime_data

    entities = []
    for kid_id, kid_info in coordinator.kids_data.items():
        # Use registry-based creation decision for future flexibility
        if should_create_entity(
            const.DATETIME_KC_UID_SUFFIX_DATE_HELPER,
            is_feature_gated_profile=is_user_feature_gated_profile(coordinator, kid_id),
        ):
            kid_name = kid_info.get(const.DATA_KID_NAME, f"Kid {kid_id}")
            entities.append(
                KidDashboardHelperDateTimePicker(coordinator, entry, kid_id, kid_name)
            )

    async_add_entities(entities)


class KidDashboardHelperDateTimePicker(DateTimeEntity, RestoreEntity):
    """DateTime helper entity for kid-specific date/time selection."""

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_DATETIME_DATE_HELPER

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: KidsChoresConfigEntry,
        kid_id: str,
        kid_name: str,
    ) -> None:
        """Initialize the datetime helper.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
        """
        self.coordinator = coordinator
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._attr_unique_id = (
            f"{entry.entry_id}_{kid_id}{const.DATETIME_KC_UID_SUFFIX_DATE_HELPER}"
        )
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name
        }
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

        # Default to tomorrow at noon
        default_time = dt_util.now() + timedelta(days=1)
        self._attr_native_value = default_time.replace(
            hour=12, minute=0, second=0, microsecond=0
        )

        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = (
        #     f"{const.DATETIME_KC_PREFIX}{kid_name}"
        #     f"{const.DATETIME_KC_EID_MIDFIX_UI_DASHBOARD}"
        #     f"{const.DATETIME_KC_EID_SUFFIX_DATE_HELPER}"
        # )

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass - restore previous state."""
        await super().async_added_to_hass()

        # Restore previous state if available
        if (last_state := await self.async_get_last_state()) and last_state.state:
            try:
                restored_datetime = dt_util.parse_datetime(last_state.state)
                if restored_datetime:
                    self._attr_native_value = restored_datetime
            except (ValueError, TypeError):
                # If restore fails, keep default value
                pass

    @property
    def native_value(self) -> datetime | None:
        """Return the current datetime value."""
        return self._attr_native_value

    def set_value(self, value: datetime) -> None:
        """Update the datetime value (sync version not used, but must be implemented)."""
        raise NotImplementedError("Use async_set_value instead")

    async def async_set_value(self, value: datetime) -> None:
        """Update the datetime value."""
        # Ensure timezone awareness
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt_util.get_default_time_zone())

        self._attr_native_value = value
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_DATETIME_DASHBOARD_HELPER,
            const.ATTR_KID_NAME: self._kid_name,
        }
