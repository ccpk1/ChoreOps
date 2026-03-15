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
        normalized_user[const.DATA_USER_UI_PREFERENCES] = dict(
            user_data.get(const.DATA_USER_UI_PREFERENCES, {})
            if isinstance(user_data.get(const.DATA_USER_UI_PREFERENCES), dict)
            else {}
        )
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

    async def async_manage_ui_control(
        self,
        call_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create, update, or remove persisted UI control state."""
        action = str(call_data.get(const.SERVICE_FIELD_UI_CONTROL_ACTION, "")).strip()
        if action not in const.UI_CONTROL_ACTIONS:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_UI_CONTROL_INVALID_ACTION,
                translation_placeholders={"action": action or "<empty>"},
            )

        target = self._resolve_ui_control_target(call_data)
        key_path = self._validate_ui_control_key_path(
            action,
            str(call_data.get(const.SERVICE_FIELD_UI_CONTROL_KEY, "")),
        )

        if (
            action
            in (
                const.UI_CONTROL_ACTION_CREATE,
                const.UI_CONTROL_ACTION_UPDATE,
            )
            and const.SERVICE_FIELD_UI_CONTROL_VALUE not in call_data
        ):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_UI_CONTROL_VALUE_REQUIRED,
                translation_placeholders={"action": action},
            )

        target_bucket = target["bucket"]
        cleared_all = False
        if action == const.UI_CONTROL_ACTION_CREATE:
            self._set_ui_control_value(
                target_bucket,
                str(target["label"]),
                key_path,
                call_data.get(const.SERVICE_FIELD_UI_CONTROL_VALUE),
                create_only=True,
            )
        elif action == const.UI_CONTROL_ACTION_UPDATE:
            self._set_ui_control_value(
                target_bucket,
                str(target["label"]),
                key_path,
                call_data.get(const.SERVICE_FIELD_UI_CONTROL_VALUE),
                update_only=True,
            )
        elif key_path:
            self._clear_ui_control_value(target_bucket, str(target["label"]), key_path)
        else:
            self._clear_all_ui_control_values(target_bucket)
            cleared_all = True

        self.coordinator._persist_and_update()

        const.LOGGER.debug(
            "Managed ui_control for %s target %s with action %s and key %s",
            target["label"],
            target["target"],
            action,
            key_path or "<all>",
        )

        result = {
            const.SERVICE_FIELD_UI_CONTROL_TARGET: target["target"],
            const.SERVICE_FIELD_UI_CONTROL_ACTION: action,
            const.SERVICE_FIELD_UI_CONTROL_KEY: key_path,
            "cleared_all": cleared_all,
        }
        if user_id := target.get(const.SERVICE_FIELD_USER_ID):
            result[const.SERVICE_FIELD_USER_ID] = user_id
        if user_name := target.get(const.SERVICE_FIELD_USER_NAME):
            result[const.SERVICE_FIELD_USER_NAME] = user_name

        return result

    def _resolve_ui_control_target(
        self,
        call_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve the requested UI control persistence target."""
        target = str(
            call_data.get(
                const.SERVICE_FIELD_UI_CONTROL_TARGET,
                const.UI_CONTROL_TARGET_USER,
            )
        ).strip()

        if target not in const.UI_CONTROL_TARGETS:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_UI_CONTROL_INVALID_TARGET,
                translation_placeholders={"target": target or "<empty>"},
            )

        if target == const.UI_CONTROL_TARGET_SHARED_ADMIN:
            return self._resolve_ui_control_target_shared_admin(call_data)

        user_id, user_record = self._resolve_ui_control_target_user(call_data)
        return {
            "target": const.UI_CONTROL_TARGET_USER,
            const.SERVICE_FIELD_USER_ID: user_id,
            const.SERVICE_FIELD_USER_NAME: str(
                user_record.get(const.DATA_USER_NAME, user_id)
            ),
            "label": user_id,
            "bucket": self._get_ui_preferences_bucket(user_record),
        }

    def _resolve_ui_control_target_user(
        self,
        call_data: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        """Resolve one target user record from id and/or name."""
        provided_user_id = str(call_data.get(const.SERVICE_FIELD_USER_ID, "")).strip()
        provided_user_name = str(
            call_data.get(const.SERVICE_FIELD_USER_NAME, "")
        ).strip()

        if not provided_user_id and not provided_user_name:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_UI_CONTROL_TARGET_REQUIRED,
            )

        user_records = self._user_records()

        if provided_user_id:
            user_record = user_records.get(provided_user_id)
            if not isinstance(user_record, dict):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.ITEM_TYPE_USER,
                        "name": provided_user_id,
                    },
                )

            if provided_user_name:
                matched_user_id = self._find_user_id_by_name(provided_user_name)
                if matched_user_id and matched_user_id != provided_user_id:
                    const.LOGGER.warning(
                        "Manage UI control: user_id '%s' and user_name '%s' mismatch; using user_id",
                        provided_user_id,
                        provided_user_name,
                    )

            return provided_user_id, user_record

        matched_user_id = self._find_user_id_by_name(provided_user_name)
        if matched_user_id is None:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.ITEM_TYPE_USER,
                    "name": provided_user_name,
                },
            )

        return matched_user_id, user_records[matched_user_id]

    def _resolve_ui_control_target_shared_admin(
        self,
        call_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve the shared-admin UI control target and reject user context."""
        provided_user_id = str(call_data.get(const.SERVICE_FIELD_USER_ID, "")).strip()
        provided_user_name = str(
            call_data.get(const.SERVICE_FIELD_USER_NAME, "")
        ).strip()

        if provided_user_id or provided_user_name:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=(
                    const.TRANS_KEY_ERROR_UI_CONTROL_SHARED_ADMIN_CONTEXT_INVALID
                ),
            )

        return {
            "target": const.UI_CONTROL_TARGET_SHARED_ADMIN,
            "label": const.UI_CONTROL_TARGET_SHARED_ADMIN,
            "bucket": self._get_shared_admin_ui_control_bucket(),
        }

    def _find_user_id_by_name(self, user_name: str) -> str | None:
        """Return the user id for an exact user name match."""
        for user_id, user_record in self._user_records().items():
            if not isinstance(user_record, dict):
                continue
            if str(user_record.get(const.DATA_USER_NAME, "")).strip() == user_name:
                return user_id
        return None

    def _validate_ui_control_key_path(self, action: str, key_path: str) -> str:
        """Validate and normalize a slash-delimited UI control key path."""
        normalized_key_path = key_path.strip()
        if action == const.UI_CONTROL_ACTION_REMOVE and not normalized_key_path:
            return ""

        if not normalized_key_path:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_UI_CONTROL_INVALID_KEY,
                translation_placeholders={"key": key_path or "<empty>"},
            )

        if (
            "\\" in normalized_key_path
            or normalized_key_path.startswith(const.UI_CONTROL_KEY_PATH_DELIMITER)
            or normalized_key_path.endswith(const.UI_CONTROL_KEY_PATH_DELIMITER)
            or f"{const.UI_CONTROL_KEY_PATH_DELIMITER}{const.UI_CONTROL_KEY_PATH_DELIMITER}"
            in normalized_key_path
        ):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_UI_CONTROL_INVALID_KEY,
                translation_placeholders={"key": normalized_key_path},
            )

        segments = [
            segment.strip()
            for segment in normalized_key_path.split(
                const.UI_CONTROL_KEY_PATH_DELIMITER
            )
        ]
        if any(not segment for segment in segments):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_UI_CONTROL_INVALID_KEY,
                translation_placeholders={"key": normalized_key_path},
            )

        return const.UI_CONTROL_KEY_PATH_DELIMITER.join(segments)

    def _get_ui_preferences_bucket(self, user_record: dict[str, Any]) -> dict[str, Any]:
        """Return the mutable UI preferences bucket for a user."""
        ui_preferences = user_record.get(const.DATA_USER_UI_PREFERENCES)
        if isinstance(ui_preferences, dict):
            return ui_preferences

        user_record[const.DATA_USER_UI_PREFERENCES] = {}
        return user_record[const.DATA_USER_UI_PREFERENCES]

    def _get_shared_admin_ui_control_bucket(self) -> dict[str, Any]:
        """Return the mutable shared-admin UI control bucket."""
        data_meta = self.coordinator._data.get(const.DATA_META)
        if not isinstance(data_meta, dict):
            data_meta = {}
            self.coordinator._data[const.DATA_META] = data_meta

        shared_admin_ui_control = data_meta.get(const.DATA_META_SHARED_ADMIN_UI_CONTROL)
        if isinstance(shared_admin_ui_control, dict):
            return shared_admin_ui_control

        data_meta[const.DATA_META_SHARED_ADMIN_UI_CONTROL] = {}
        return data_meta[const.DATA_META_SHARED_ADMIN_UI_CONTROL]

    def _set_ui_control_value(
        self,
        ui_bucket: dict[str, Any],
        target_label: str,
        key_path: str,
        value: Any,
        *,
        create_only: bool = False,
        update_only: bool = False,
    ) -> None:
        """Set a UI control value at a nested key path."""
        if create_only and update_only:
            raise ValueError("create_only and update_only cannot both be true")

        segments = key_path.split(const.UI_CONTROL_KEY_PATH_DELIMITER)
        current = ui_bucket

        for segment in segments[:-1]:
            child = current.get(segment)
            if child is None:
                current[segment] = {}
                child = current[segment]

            if not isinstance(child, dict):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_UI_CONTROL_INVALID_KEY,
                    translation_placeholders={"key": key_path},
                )

            current = child

        leaf_key = segments[-1]
        leaf_exists = leaf_key in current

        if create_only and leaf_exists:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_UI_CONTROL_KEY_ALREADY_EXISTS,
                translation_placeholders={"key": key_path, "user_name": target_label},
            )

        current[leaf_key] = value

    def _clear_ui_control_value(
        self,
        ui_bucket: dict[str, Any],
        target_label: str,
        key_path: str,
    ) -> None:
        """Remove a nested UI control value and prune empty parent dicts."""
        segments = key_path.split(const.UI_CONTROL_KEY_PATH_DELIMITER)
        current = ui_bucket
        parents: list[tuple[dict[str, Any], str]] = []

        for segment in segments[:-1]:
            child = current.get(segment)
            if not isinstance(child, dict):
                return

            parents.append((current, segment))
            current = child

        leaf_key = segments[-1]
        if leaf_key not in current:
            return

        del current[leaf_key]

        for parent, segment in reversed(parents):
            child = parent.get(segment)
            if isinstance(child, dict) and not child:
                del parent[segment]

    def _clear_all_ui_control_values(self, ui_bucket: dict[str, Any]) -> None:
        """Clear all UI control values from one mutable bucket."""
        ui_bucket.clear()

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
