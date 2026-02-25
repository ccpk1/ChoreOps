"""User manager for ChoreOps integration.

Handles canonical user CRUD operations with proper event signaling.
Includes assignment-participant association cleanup for deleted users.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .. import const, data_builders as db
from ..helpers.device_helpers import get_assignee_device_identifier
from ..helpers.entity_helpers import remove_entities_by_item_id
from .base_manager import BaseManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..coordinator import ChoreOpsDataCoordinator
    from ..type_defs import AssigneeData, UserData


class UserManager(BaseManager):
    """Manages canonical user CRUD operations.

    Storage is user-only (`DATA_USERS`). Capability flags define runtime behavior
    for assignment, workflow, gamification, approval, and management.
    """

    def __init__(
        self, hass: HomeAssistant, coordinator: ChoreOpsDataCoordinator
    ) -> None:
        """Initialize user manager.

        Args:
            hass: Home Assistant instance
            coordinator: Data coordinator managing this integration instance
        """
        super().__init__(hass, coordinator)

    @property
    def _data(self) -> dict[str, Any]:
        """Access coordinator's data dict dynamically.

        This must be a property to always get the current data dict,
        as coordinator._data may be reassigned during updates.
        """
        return self.coordinator._data

    def _user_records(self) -> dict[str, Any]:
        """Return mutable canonical user record bucket."""
        users = self._data.get(const.DATA_USERS)
        if isinstance(users, dict):
            return users

        self._data[const.DATA_USERS] = {}
        return self._data[const.DATA_USERS]

    async def async_setup(self) -> None:
        """Set up manager listeners."""
        self.listen(
            const.SIGNAL_SUFFIX_USER_DELETED,
            self._on_assignment_participant_deleted,
        )
        const.LOGGER.debug("UserManager async_setup complete")

    def _on_assignment_participant_deleted(self, payload: dict[str, Any]) -> None:
        """Remove deleted assignment participants from associated-user lists."""
        if not payload.get(const.DATA_USER_CAN_BE_ASSIGNED, False):
            return

        user_id = payload.get(const.DATA_USER_ID, "")
        if not user_id:
            return

        users_data = self._user_records()
        cleaned = False
        for user_info in users_data.values():
            assoc_user_ids = user_info.get(const.DATA_USER_ASSOCIATED_USER_IDS, [])
            if user_id in assoc_user_ids:
                user_info[const.DATA_USER_ASSOCIATED_USER_IDS] = [
                    associated_user_id
                    for associated_user_id in assoc_user_ids
                    if associated_user_id != user_id
                ]
                const.LOGGER.debug(
                    "Removed deleted assignment participant %s from user '%s' associated_user_ids",
                    user_id,
                    user_info.get(const.DATA_USER_NAME),
                )
                cleaned = True

        if cleaned:
            self.coordinator._persist()
            const.LOGGER.debug(
                "UserManager: Cleaned associated_user_ids for deleted assignment participant %s",
                user_id,
            )

    def _normalize_user_record(
        self,
        user_input: dict[str, Any],
        *,
        existing: dict[str, Any] | None = None,
        internal_id: str | None = None,
        prebuilt: bool = False,
    ) -> dict[str, Any]:
        """Build one canonical normalized user record."""
        if prebuilt:
            user_data = dict(user_input)
        else:
            user_data = dict(
                db.build_user_profile(
                    user_input,
                    existing=cast("UserData | None", existing),
                )
            )

        if internal_id:
            user_data[const.DATA_USER_INTERNAL_ID] = internal_id

        can_be_assigned = bool(user_data.get(const.DATA_USER_CAN_BE_ASSIGNED, False))
        if not can_be_assigned:
            return user_data

        assignment_seed = dict(existing) if isinstance(existing, dict) else {}
        assignment_seed.update(user_data)
        assignment_input = dict(assignment_seed)
        assignment_input.pop(const.CFOF_GLOBAL_INPUT_INTERNAL_ID, None)

        normalized_assignment = dict(
            db.build_user_assignment_profile(
                assignment_input,
                existing=cast("AssigneeData | None", assignment_seed or None),
            )
        )

        normalized_user = dict(normalized_assignment)
        normalized_user.update(user_data)
        normalized_user[const.DATA_USER_ASSOCIATED_USER_IDS] = list(
            user_data.get(const.DATA_USER_ASSOCIATED_USER_IDS, [])
        )
        normalized_user[const.DATA_USER_CAN_BE_ASSIGNED] = can_be_assigned
        normalized_user[const.DATA_USER_ENABLE_CHORE_WORKFLOW] = bool(
            user_data.get(const.DATA_USER_ENABLE_CHORE_WORKFLOW, False)
        )
        normalized_user[const.DATA_USER_ENABLE_GAMIFICATION] = bool(
            user_data.get(const.DATA_USER_ENABLE_GAMIFICATION, False)
        )
        normalized_user[const.DATA_USER_CAN_APPROVE] = bool(
            user_data.get(const.DATA_USER_CAN_APPROVE, False)
        )
        normalized_user[const.DATA_USER_CAN_MANAGE] = bool(
            user_data.get(const.DATA_USER_CAN_MANAGE, False)
        )
        return normalized_user

    def create_user(
        self,
        user_input: dict[str, Any],
        *,
        internal_id: str | None = None,
        prebuilt: bool = False,
        immediate_persist: bool = False,
    ) -> str:
        """Create a canonical user record."""
        user_record = self._normalize_user_record(
            user_input,
            internal_id=internal_id,
            prebuilt=prebuilt,
        )
        user_id = str(user_record[const.DATA_USER_INTERNAL_ID])

        user_records = self._user_records()
        user_records[user_id] = user_record

        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        user_name = str(user_record.get(const.DATA_USER_NAME, user_id))
        const.LOGGER.info("Created user '%s' (ID: %s)", user_name, user_id)

        self.emit(
            const.SIGNAL_SUFFIX_USER_CREATED,
            **{
                const.DATA_USER_ID: user_id,
                const.DATA_USER_NAME: user_name,
                const.DATA_USER_CAN_BE_ASSIGNED: bool(
                    user_record.get(const.DATA_USER_CAN_BE_ASSIGNED, False)
                ),
                const.DATA_USER_CAN_APPROVE: bool(
                    user_record.get(const.DATA_USER_CAN_APPROVE, False)
                ),
                const.DATA_USER_CAN_MANAGE: bool(
                    user_record.get(const.DATA_USER_CAN_MANAGE, False)
                ),
                const.DATA_USER_ENABLE_GAMIFICATION: bool(
                    user_record.get(const.DATA_USER_ENABLE_GAMIFICATION, False)
                ),
            },
        )
        return user_id

    def update_user(
        self,
        user_id: str,
        updates: dict[str, Any],
        *,
        immediate_persist: bool = False,
    ) -> None:
        """Update a canonical user record."""
        user_records = self._user_records()
        if user_id not in user_records:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.ITEM_TYPE_USER,
                    "name": user_id,
                },
            )

        existing = dict(user_records[user_id])
        merged_input = dict(existing)
        merged_input.update(updates)
        merged_input[const.DATA_USER_INTERNAL_ID] = user_id

        normalized_user = self._normalize_user_record(
            merged_input,
            existing=existing,
            internal_id=user_id,
        )
        user_records[user_id] = normalized_user

        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        user_name = str(normalized_user.get(const.DATA_USER_NAME, user_id))
        const.LOGGER.info("Updated user '%s' (ID: %s)", user_name, user_id)

        self.emit(
            const.SIGNAL_SUFFIX_USER_UPDATED,
            **{
                const.DATA_USER_ID: user_id,
                const.DATA_USER_NAME: user_name,
                const.DATA_USER_CAN_BE_ASSIGNED: bool(
                    normalized_user.get(const.DATA_USER_CAN_BE_ASSIGNED, False)
                ),
                const.DATA_USER_CAN_APPROVE: bool(
                    normalized_user.get(const.DATA_USER_CAN_APPROVE, False)
                ),
                const.DATA_USER_CAN_MANAGE: bool(
                    normalized_user.get(const.DATA_USER_CAN_MANAGE, False)
                ),
                const.DATA_USER_ENABLE_GAMIFICATION: bool(
                    normalized_user.get(const.DATA_USER_ENABLE_GAMIFICATION, False)
                ),
            },
        )

    def delete_user(self, user_id: str, *, immediate_persist: bool = False) -> None:
        """Delete a canonical user record and emit capability snapshot payload."""
        user_records = self._user_records()
        if user_id not in user_records:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.ITEM_TYPE_USER,
                    "name": user_id,
                },
            )

        user_record = dict(user_records[user_id])
        user_name = str(user_record.get(const.DATA_USER_NAME, user_id))
        can_be_assigned = bool(user_record.get(const.DATA_USER_CAN_BE_ASSIGNED, False))
        can_approve = bool(user_record.get(const.DATA_USER_CAN_APPROVE, False))
        can_manage = bool(user_record.get(const.DATA_USER_CAN_MANAGE, False))
        enable_gamification = bool(
            user_record.get(const.DATA_USER_ENABLE_GAMIFICATION, False)
        )

        del user_records[user_id]

        if can_be_assigned:
            remove_entities_by_item_id(
                self.hass,
                self.coordinator.config_entry.entry_id,
                user_id,
            )

            device_registry = dr.async_get(self.hass)
            device = device_registry.async_get_device(
                identifiers={
                    (
                        const.DOMAIN,
                        get_assignee_device_identifier(
                            self.coordinator.config_entry, user_id
                        ),
                    )
                }
            )
            if device:
                device_registry.async_remove_device(device.id)
                const.LOGGER.debug(
                    "Removed device from registry for assignment participant ID: %s",
                    user_id,
                )

        self.coordinator._persist(immediate=immediate_persist)

        self.emit(
            const.SIGNAL_SUFFIX_USER_DELETED,
            **{
                const.DATA_USER_ID: user_id,
                const.DATA_USER_NAME: user_name,
                const.DATA_USER_CAN_BE_ASSIGNED: can_be_assigned,
                const.DATA_USER_CAN_APPROVE: can_approve,
                const.DATA_USER_CAN_MANAGE: can_manage,
                const.DATA_USER_ENABLE_GAMIFICATION: enable_gamification,
            },
        )

        self.coordinator.async_update_listeners()
        const.LOGGER.info("Deleted user '%s' (ID: %s)", user_name, user_id)
