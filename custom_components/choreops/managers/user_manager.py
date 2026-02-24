"""User manager for ChoreOps integration.

Handles CRUD operations for Assignees and Approvers with proper event signaling.
Includes shadow assignee management for approver chore assignment feature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .. import const, data_builders as db
from ..helpers.entity_helpers import remove_entities_by_item_id
from .base_manager import BaseManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..coordinator import ChoreOpsDataCoordinator


class UserManager(BaseManager):
    """Manages Assignee and Approver CRUD operations.

    Provides centralized methods for:
    - Assignee create/update/delete with reference cleanup
    - Approver create/update/delete with shadow assignee management
    - Shadow assignee creation/unlinking for approver chore assignment

    All mutations emit appropriate signals for cross-manager coordination.
    """

    def __init__(
        self, hass: HomeAssistant, coordinator: ChoreOpsDataCoordinator
    ) -> None:
        """Initialize user manager.

        Args:
            hass: Home Assistant instance
            coordinator: Approver coordinator managing this integration instance
        """
        super().__init__(hass, coordinator)

    @property
    def _data(self) -> dict[str, Any]:
        """Access coordinator's data dict dynamically.

        This must be a property to always get the current data dict,
        as coordinator._data may be reassigned during updates.
        """
        return self.coordinator._data

    def _assignee_records(self) -> dict[str, Any]:
        """Return mutable assignee/user record bucket with users-first precedence."""
        users = self._data.get(const.DATA_USERS)
        if isinstance(users, dict) and users:
            return users

        assignees = self._data.get(const.DATA_USERS)
        if isinstance(assignees, dict) and assignees:
            return assignees

        if isinstance(users, dict):
            return users

        if isinstance(assignees, dict):
            return assignees

        self._data[const.DATA_USERS] = {}
        return self._data[const.DATA_USERS]

    def _approver_records(self) -> dict[str, Any]:
        """Return mutable approver-role records backed by canonical users bucket."""
        return self._user_records()

    def _user_records(self) -> dict[str, Any]:
        """Return mutable canonical user record bucket."""
        users = self._data.get(const.DATA_USERS)
        if isinstance(users, dict):
            return users

        self._data[const.DATA_USERS] = {}
        return self._data[const.DATA_USERS]

    async def async_setup(self) -> None:
        """Set up the user manager.

        Subscribes to cross-domain events for cleanup coordination.
        """
        # Listen for assignee deletion to clean approver associations
        self.listen(const.SIGNAL_SUFFIX_USER_DELETED, self._on_assignee_deleted)
        const.LOGGER.debug("UserManager async_setup complete")

    def _on_assignee_deleted(self, payload: dict[str, Any]) -> None:
        """Remove deleted assignee from approver associated_assignees lists.

        Follows Platinum Architecture (Choreography): UserManager reacts
        to KID_DELETED signal and cleans its own domain data (approver refs).

        Args:
            payload: Event data containing assignee_id
        """
        if payload.get("user_role") != const.ROLE_ASSIGNEE:
            return

        assignee_id = payload.get("user_id", "")
        if not assignee_id:
            return

        # Clean own domain: remove deleted assignee from approver associated_assignees
        approvers_data = self._approver_records()
        cleaned = False
        for approver_info in approvers_data.values():
            assoc_assignees = approver_info.get(
                const.DATA_APPROVER_ASSOCIATED_USERS, []
            )
            if assignee_id in assoc_assignees:
                approver_info[const.DATA_APPROVER_ASSOCIATED_USERS] = [
                    k for k in assoc_assignees if k != assignee_id
                ]
                const.LOGGER.debug(
                    "Removed deleted assignee %s from approver '%s' associated_assignees",
                    assignee_id,
                    approver_info.get(const.DATA_USER_NAME),
                )
                cleaned = True

        if cleaned:
            self.coordinator._persist()
            const.LOGGER.debug(
                "UserManager: Cleaned approver associations for deleted assignee %s",
                assignee_id,
            )

    # -------------------------------------------------------------------------
    # KID CRUD OPERATIONS
    # -------------------------------------------------------------------------

    def create_assignee(
        self,
        user_input: dict[str, Any],
        *,
        internal_id: str | None = None,
        prebuilt: bool = False,
        immediate_persist: bool = False,
    ) -> str:
        """Create a new assignee from user input or pre-built data.

        Args:
            user_input: Form input dict or pre-built AssigneeData if prebuilt=True
            internal_id: Optional UUID to use (for pre-built data scenarios)
            prebuilt: If True, user_input is already a complete AssigneeData dict
            immediate_persist: If True, persist immediately (use for config flow operations)

        Returns:
            The internal_id of the created assignee

        Raises:
            HomeAssistantError: If assignee creation fails
        """
        if prebuilt:
            assignee_data = dict(user_input)
            assignee_id = str(assignee_data[const.DATA_USER_INTERNAL_ID])
        else:
            assignee_data = dict(db.build_user_assignment_profile(user_input))
            assignee_id = str(assignee_data[const.DATA_USER_INTERNAL_ID])

        # Override internal_id if provided
        if internal_id:
            assignee_data[const.DATA_USER_INTERNAL_ID] = internal_id
            assignee_id = internal_id

        # Ensure assignees dict exists and store assignee data
        assignee_records = self._assignee_records()
        assignee_records[assignee_id] = assignee_data
        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        assignee_name = assignee_data.get(const.DATA_USER_NAME, assignee_id)
        const.LOGGER.info("Created assignee '%s' (ID: %s)", assignee_name, assignee_id)

        # Emit assignee created event
        self.emit(
            const.SIGNAL_SUFFIX_USER_CREATED,
            user_id=assignee_id,
            user_name=assignee_name,
            user_role=const.ROLE_ASSIGNEE,
        )

        return assignee_id

    def update_assignee(
        self,
        assignee_id: str,
        updates: dict[str, Any],
        *,
        immediate_persist: bool = False,
    ) -> None:
        """Update an existing assignee with new values.

        Args:
            assignee_id: Internal ID of the assignee to update
            updates: Dict of field updates to merge into assignee data
            immediate_persist: If True, persist immediately (use for config flow operations)

        Raises:
            HomeAssistantError: If assignee not found
        """
        assignee_records = self._assignee_records()
        if assignee_id not in assignee_records:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_ASSIGNEE,
                    "name": assignee_id,
                },
            )

        # Merge updates into existing assignee data
        assignee_records[assignee_id].update(updates)
        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        assignee_name = assignee_records[assignee_id].get(
            const.DATA_USER_NAME, assignee_id
        )
        const.LOGGER.info("Updated assignee '%s' (ID: %s)", assignee_name, assignee_id)

        # Emit assignee updated event
        self.emit(
            const.SIGNAL_SUFFIX_USER_UPDATED,
            user_id=assignee_id,
            user_name=assignee_name,
            user_role=const.ROLE_ASSIGNEE,
        )

    def delete_assignee(
        self, assignee_id: str, *, immediate_persist: bool = False
    ) -> None:
        """Delete assignee from storage and cleanup references.

        Args:
            assignee_id: Internal ID of the assignee to delete
            immediate_persist: If True, persist immediately (use for config flow operations)

        Raises:
            HomeAssistantError: If assignee not found
        """
        assignee_records = self._assignee_records()
        if assignee_id not in assignee_records:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_ASSIGNEE,
                    "name": assignee_id,
                },
            )

        assignee_info = assignee_records[assignee_id]
        assignee_name = assignee_info.get(const.DATA_USER_NAME, assignee_id)

        # Normal assignee deletion continues below
        del assignee_records[assignee_id]

        # Remove HA entities for this assignee
        remove_entities_by_item_id(
            self.hass,
            self.coordinator.config_entry.entry_id,
            assignee_id,
        )

        # Remove device from device registry
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(
            identifiers={(const.DOMAIN, assignee_id)}
        )
        if device:
            device_registry.async_remove_device(device.id)
            const.LOGGER.debug(
                "Removed device from registry for assignee ID: %s", assignee_id
            )

        # Note: Cleanup is now handled by signal listeners in each Manager:
        # - ChoreManager._on_assignee_deleted() removes assignee from chore assignments
        # - GamificationManager._on_assignee_deleted() removes achievement/challenge refs
        # - UserManager._on_assignee_deleted() removes approver associations
        # - UIManager._on_user_deleted() removes unused translation sensors

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self.coordinator._persist(immediate=immediate_persist)

        # Emit assignee deleted event AFTER persist so managers see consistent state
        self.emit(
            const.SIGNAL_SUFFIX_USER_DELETED,
            user_id=assignee_id,
            user_name=assignee_name,
            user_role=const.ROLE_ASSIGNEE,
            was_shadow=False,
        )

        self.coordinator.async_update_listeners()
        const.LOGGER.info("Deleted assignee '%s' (ID: %s)", assignee_name, assignee_id)

    # -------------------------------------------------------------------------
    # PARENT CRUD OPERATIONS
    # -------------------------------------------------------------------------

    def create_approver(
        self,
        user_input: dict[str, Any],
        *,
        internal_id: str | None = None,
        prebuilt: bool = False,
        immediate_persist: bool = False,
    ) -> str:
        """Create a new approver from user input or pre-built data.


        Args:
            user_input: Form input dict or pre-built ApproverData if prebuilt=True
            internal_id: Optional UUID to use (for pre-built data scenarios)
            prebuilt: If True, user_input is already a complete ApproverData dict
            immediate_persist: If True, persist immediately (use for config flow operations)

        Returns:
            The internal_id of the created approver

        Raises:
            HomeAssistantError: If approver creation fails
        """
        if prebuilt:
            approver_data = dict(user_input)
            approver_id = str(approver_data[const.DATA_USER_INTERNAL_ID])
        else:
            approver_data = dict(db.build_user_profile(user_input))
            approver_id = str(approver_data[const.DATA_USER_INTERNAL_ID])

        # Override internal_id if provided
        if internal_id:
            approver_data[const.DATA_USER_INTERNAL_ID] = internal_id
            approver_id = internal_id

        approver_name = str(approver_data.get(const.DATA_USER_NAME, approver_id))

        # Ensure approvers dict exists and store approver data
        approver_records = self._approver_records()
        user_records = self._user_records()
        can_be_assigned = bool(
            approver_data.get(const.DATA_USER_CAN_BE_ASSIGNED, False)
        )
        approver_records[approver_id] = approver_data
        user_records[approver_id] = {
            **dict(approver_data),
            const.DATA_USER_CAN_BE_ASSIGNED: can_be_assigned,
        }

        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        const.LOGGER.info("Created approver '%s' (ID: %s)", approver_name, approver_id)

        # Emit approver created event
        self.emit(
            const.SIGNAL_SUFFIX_USER_CREATED,
            user_id=approver_id,
            user_name=approver_name,
            user_role=const.ROLE_APPROVER,
            shadow_assignee_id=None,
        )

        return approver_id

    def update_approver(
        self,
        approver_id: str,
        updates: dict[str, Any],
        *,
        immediate_persist: bool = False,
    ) -> None:
        """Update an existing approver with new values.


        Args:
            approver_id: Internal ID of the approver to update
            updates: Dict of field updates to merge into approver data
            immediate_persist: If True, persist immediately (use for config flow operations)

        Raises:
            HomeAssistantError: If approver not found
        """
        approver_records = self._approver_records()
        user_records = self._user_records()
        if approver_id not in approver_records:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_APPROVER,
                    "name": approver_id,
                },
            )

        # Merge updates into existing approver data
        approver_records[approver_id].update(updates)
        can_be_assigned = bool(
            approver_records[approver_id].get(const.DATA_USER_CAN_BE_ASSIGNED, False)
        )
        existing_user = user_records.get(approver_id)
        if isinstance(existing_user, dict):
            existing_user.update(updates)
            existing_user[const.DATA_USER_CAN_BE_ASSIGNED] = can_be_assigned
        else:
            user_records[approver_id] = {
                **dict(approver_records[approver_id]),
                const.DATA_USER_CAN_BE_ASSIGNED: can_be_assigned,
            }

        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        approver_name = approver_records[approver_id].get(
            const.DATA_USER_NAME, approver_id
        )
        const.LOGGER.info("Updated approver '%s' (ID: %s)", approver_name, approver_id)

        # Emit approver updated event
        self.emit(
            const.SIGNAL_SUFFIX_USER_UPDATED,
            user_id=approver_id,
            user_name=approver_name,
            user_role=const.ROLE_APPROVER,
        )

    def delete_approver(
        self, approver_id: str, *, immediate_persist: bool = False
    ) -> None:
        """Delete approver from storage.


        Args:
            approver_id: Internal ID of the approver to delete
            immediate_persist: If True, persist immediately (use for config flow operations)

        Raises:
            HomeAssistantError: If approver not found
        """
        approver_records = self._approver_records()
        user_records = self._user_records()
        if approver_id not in approver_records:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_APPROVER,
                    "name": approver_id,
                },
            )

        approver_data = approver_records[approver_id]
        approver_name = approver_data.get(const.DATA_USER_NAME, approver_id)

        del approver_records[approver_id]
        user_records.pop(approver_id, None)

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self.coordinator._persist(immediate=immediate_persist)

        # Emit approver deleted event - UIManager listens to clean up translation sensors
        # (Platinum Architecture: signal-first, no cross-manager writes)
        self.emit(
            const.SIGNAL_SUFFIX_USER_DELETED,
            user_id=approver_id,
            user_name=approver_name,
            user_role=const.ROLE_APPROVER,
        )

        self.coordinator.async_update_listeners()
        const.LOGGER.info("Deleted approver '%s' (ID: %s)", approver_name, approver_id)

    def create_user(
        self,
        user_input: dict[str, Any],
        *,
        internal_id: str | None = None,
        prebuilt: bool = False,
        immediate_persist: bool = False,
    ) -> str:
        """Create a role-based user record using the approver-model implementation."""
        return self.create_approver(
            user_input,
            internal_id=internal_id,
            prebuilt=prebuilt,
            immediate_persist=immediate_persist,
        )

    def update_user(
        self,
        user_id: str,
        updates: dict[str, Any],
        *,
        immediate_persist: bool = False,
    ) -> None:
        """Update a role-based user record using the approver-model implementation."""
        self.update_approver(user_id, updates, immediate_persist=immediate_persist)

    def delete_user(self, user_id: str, *, immediate_persist: bool = False) -> None:
        """Delete a role-based user record using the approver-model implementation."""
        self.delete_approver(user_id, immediate_persist=immediate_persist)

    async def unlink_shadow(self, shadow_assignee_id: str) -> None:
        """Reject legacy unlink requests; link behavior is migration-only."""
        const.LOGGER.warning(
            "Ignoring legacy shadow unlink request for assignee ID: %s",
            shadow_assignee_id,
        )
        raise ServiceValidationError(
            translation_domain=const.DOMAIN,
            translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
            translation_placeholders={
                "entity_type": const.LABEL_ASSIGNEE,
                "name": shadow_assignee_id,
            },
        )
