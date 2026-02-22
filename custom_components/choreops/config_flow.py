# File: config_flow.py
"""Multi-step config flow for the ChoreOps integration, storing entities by internal_id.

Ensures that all add/edit/delete operations reference entities via internal_id for consistency.
"""

from typing import Any
import uuid

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.util import dt as dt_util
import voluptuous as vol

from . import const, data_builders as db, migration_pre_v50 as mp50
from .data_builders import EntityValidationError
from .helpers import backup_helpers as bh, flow_helpers as fh
from .options_flow import ChoreOpsOptionsFlowHandler


class ChoreOpsConfigFlow(config_entries.ConfigFlow, domain=const.DOMAIN):
    """Config Flow for ChoreOps with internal_id-based entity management."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._assignees_temp: dict[str, dict[str, Any]] = {}
        self._approvers_temp: dict[str, dict[str, Any]] = {}
        self._chores_temp: dict[str, dict[str, Any]] = {}
        self._badges_temp: dict[str, dict[str, Any]] = {}
        self._rewards_temp: dict[str, dict[str, Any]] = {}
        self._achievements_temp: dict[str, dict[str, Any]] = {}
        self._challenges_temp: dict[str, dict[str, Any]] = {}
        self._penalties_temp: dict[str, dict[str, Any]] = {}
        self._bonuses_temp: dict[str, dict[str, Any]] = {}

        self._assignee_count: int = 0
        self._approvers_count: int = 0
        self._chore_count: int = 0
        self._badge_count: int = 0
        self._reward_count: int = 0
        self._achievement_count: int = 0
        self._challenge_count: int = 0
        self._penalty_count: int = 0
        self._bonus_count: int = 0

        self._assignee_index: int = 0
        self._approvers_index: int = 0
        self._chore_index: int = 0
        self._badge_index: int = 0
        self._reward_index: int = 0
        self._achievement_index: int = 0
        self._challenge_index: int = 0
        self._penalty_index: int = 0
        self._bonus_index: int = 0
        self._legacy_split_user_counts: bool = False
        self._legacy_collecting_assignable_users: bool = False

    # --------------------------------------------------------------------------
    # INTRO
    # --------------------------------------------------------------------------

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Start the config flow with an intro step."""

        # Check if there's an existing ChoreOps entry
        if any(self._async_current_entries()):
            return self.async_abort(reason=const.TRANS_KEY_ERROR_SINGLE_INSTANCE)

        # Always show data recovery options first (even if no file exists)
        # This allows users to restore from backup, paste JSON, or start fresh
        return await self.async_step_data_recovery()

    async def async_step_intro(self, user_input: dict[str, Any] | None = None):
        """Intro / welcome step. Press Next to continue."""
        if user_input is not None:
            return await self.async_step_points_label()

        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_INTRO,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_QUICK_START
            },
        )

    # --------------------------------------------------------------------------
    # DATA RECOVERY
    # --------------------------------------------------------------------------

    async def async_step_data_recovery(self, user_input: dict[str, Any] | None = None):
        """Handle data recovery options when existing storage is found."""
        from pathlib import Path

        from .store import ChoreOpsStore

        # Note: We don't load translations because SelectSelector cannot
        # dynamically translate runtime-generated options (backup file lists).
        # Using emoji prefixes (📄) as language-neutral solution instead.

        errors: dict[str, str] = {}

        if user_input is not None:
            selection = user_input.get(const.CFOF_DATA_RECOVERY_INPUT_SELECTION)

            # Validate that selection is not empty
            if not selection:
                errors["base"] = const.CFOP_ERROR_INVALID_SELECTION
            elif selection == "start_fresh":
                return await self._handle_start_fresh()
            elif selection == "current_active":
                return await self._handle_use_current()
            elif selection == "migrate_from_assigneeschores":
                return await self._handle_migrate_from_assigneeschores()
            elif selection == "paste_json":
                return await self._handle_paste_json()
            else:
                # It's a backup selection with emoji prefix - extract the actual filename
                # Selection format: "📄 [Tag] filename.json (age)"
                # Using emoji prefix because backup files are dynamic and can't use SelectSelector translation
                emoji_prefix = "📄 "

                # Extract filename from the prefixed selection
                if selection.startswith(emoji_prefix):
                    # Remove the emoji prefix
                    display_part = selection[len(emoji_prefix) :].strip()
                    # Extract filename from format "[Tag] filename.json (age)"
                    if "] " in display_part and " (" in display_part:
                        # Get the part between "] " and " ("
                        start_idx = display_part.find("] ") + 2
                        end_idx = display_part.rfind(" (")
                        if start_idx < end_idx:
                            filename = display_part[start_idx:end_idx]
                            return await self._handle_restore_backup(filename)

                # Fallback: treat as raw filename (shouldn't happen with new format)
                return await self._handle_restore_backup(selection)

        # Build selection menu
        store = ChoreOpsStore(self.hass)
        storage_path = Path(store.get_storage_path())
        recovery_capabilities = await mp50.async_get_data_recovery_capabilities(
            self.hass
        )
        has_current_data_file = recovery_capabilities["has_current_active_file"]
        has_legacy_candidates = recovery_capabilities["has_legacy_candidates"]

        # Discover backups (pass None for store - not needed for discovery)
        backups = await bh.discover_backups(self.hass, None)

        # Build options list for SelectSelector (keeping original approach for fixed options)
        # Start with fixed options that get translated via translation_key
        options = []

        # Only show "use current" if file actually exists
        if has_current_data_file:
            options.append("current_active")

        if has_legacy_candidates:
            options.append("migrate_from_assigneeschores")

        options.append("start_fresh")

        # Add discovered backups with emoji prefix
        # Note: Using emoji (📄) instead of translated text because:
        # 1. Backup files are dynamically generated and can't use SelectSelector translation
        # 2. Static options (start_fresh, etc.) use SelectSelector translation system
        # 3. Emoji provides visual distinction without requiring translation API
        for backup in backups:
            age_str = bh.format_backup_age(backup["age_hours"])
            tag_display = backup["tag"].replace("-", " ").title()
            backup_display = f"[{tag_display}] {backup['filename']} ({age_str})"
            emoji_option = f"📄 {backup_display}"
            options.append(emoji_option)

        # Add paste JSON option
        options.append("paste_json")

        # Build schema using SelectSelector with translation_key (original working approach)
        from homeassistant.helpers import selector

        data_schema = vol.Schema(
            {
                vol.Required(
                    const.CFOF_DATA_RECOVERY_INPUT_SELECTION
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key=const.TRANS_KEY_CFOF_DATA_RECOVERY_SELECTION,
                        custom_value=True,  # Allow backup filenames with prefixes
                    )
                )
            }
        )

        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_DATA_RECOVERY,
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "storage_path": str(storage_path.parent),
                "backup_count": str(len(backups)),
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_BACKUP_RESTORE,
            },
        )

    async def _handle_start_fresh(self):
        """Handle 'Start Fresh' - backup existing and delete."""
        import os
        from pathlib import Path

        from .store import ChoreOpsStore

        try:
            store = ChoreOpsStore(self.hass)
            storage_path = Path(store.get_storage_path())

            # Create safety backup if file exists
            storage_file_exists = await self.hass.async_add_executor_job(
                storage_path.exists
            )
            if storage_file_exists:
                backup_name = await bh.create_timestamped_backup(
                    self.hass, store, const.BACKUP_TAG_RECOVERY
                )
                if backup_name:
                    const.LOGGER.info(
                        "Created safety backup before fresh start: %s", backup_name
                    )

                # Delete active file
                await self.hass.async_add_executor_job(os.remove, str(storage_path))
                const.LOGGER.info("Deleted active storage file for fresh start")

            # Continue to intro (standard setup)
            return await self.async_step_intro()

        except Exception as err:
            const.LOGGER.error("Fresh start failed: %s", err)
            return self.async_abort(reason=const.TRANS_KEY_CFOP_ERROR_UNKNOWN)

    async def _handle_use_current(self):
        """Handle 'Use Current Active' - validate and continue setup."""
        result = await mp50.async_prepare_current_active_storage(self.hass)
        if not result.get("prepared"):
            error_key = result.get("error")
            if error_key == "file_not_found":
                return self.async_abort(
                    reason=const.TRANS_KEY_CFOP_ERROR_FILE_NOT_FOUND
                )
            if error_key == "corrupt_file":
                return self.async_abort(reason=const.TRANS_KEY_CFOP_ERROR_CORRUPT_FILE)
            if error_key == "invalid_structure":
                return self.async_abort(
                    reason=const.TRANS_KEY_CFOP_ERROR_INVALID_STRUCTURE
                )
            return self.async_abort(reason=const.TRANS_KEY_CFOP_ERROR_UNKNOWN)

        # File is valid - create config entry immediately with existing data
        # No need to collect assignees/chores/points since they're already defined
        return self.async_create_entry(
            title=const.CHOREOPS_TITLE,
            data={},  # Empty - integration will load from storage file
        )

    async def _handle_migrate_from_assigneeschores(self):
        """Handle one-time migration from legacy ChoreOps artifacts."""
        try:
            result = await mp50.async_migrate_from_legacy_choreops_storage(self.hass)
            if not result.get("migrated"):
                error_key = result.get("error")
                if error_key == "no_legacy_source":
                    return self.async_abort(
                        reason=const.TRANS_KEY_CFOP_ERROR_FILE_NOT_FOUND
                    )
                if error_key in {"invalid_json", "invalid_structure"}:
                    return self.async_abort(
                        reason=const.TRANS_KEY_CFOP_ERROR_INVALID_STRUCTURE
                    )
                return self.async_abort(reason=const.TRANS_KEY_CFOP_ERROR_UNKNOWN)

            options = result.get("settings")
            if not isinstance(options, dict):
                options = {}

            return self.async_create_entry(
                title=const.CHOREOPS_TITLE,
                data={},
                options=options,
            )
        except Exception as err:
            const.LOGGER.error("Legacy migration failed: %s", err)
            return self.async_abort(reason=const.TRANS_KEY_CFOP_ERROR_UNKNOWN)

    async def _handle_restore_backup(self, backup_filename: str):
        """Handle restoring from a specific backup file."""
        import json
        from pathlib import Path
        import shutil

        from .store import ChoreOpsStore

        try:
            # Get storage path directly without creating storage manager yet
            store = ChoreOpsStore(self.hass)
            storage_path = Path(store.get_storage_path())
            backup_path = storage_path.parent / backup_filename

            backup_file_exists = await self.hass.async_add_executor_job(
                backup_path.exists
            )
            if not backup_file_exists:
                const.LOGGER.error("Backup file not found: %s", backup_filename)
                return self.async_abort(
                    reason=const.TRANS_KEY_CFOP_ERROR_FILE_NOT_FOUND
                )

            # Read and validate backup
            backup_data_str = await self.hass.async_add_executor_job(
                backup_path.read_text, "utf-8"
            )

            try:
                json.loads(backup_data_str)  # Validate parseable JSON
            except json.JSONDecodeError:
                const.LOGGER.error("Backup file has invalid JSON: %s", backup_filename)
                return self.async_abort(reason=const.TRANS_KEY_CFOP_ERROR_CORRUPT_FILE)

            # Validate structure
            if not bh.validate_backup_json(backup_data_str):
                const.LOGGER.error(
                    "Backup file missing required keys: %s", backup_filename
                )
                return self.async_abort(
                    reason=const.TRANS_KEY_CFOP_ERROR_INVALID_STRUCTURE
                )

            # Create safety backup of current file if it exists
            storage_file_exists = await self.hass.async_add_executor_job(
                storage_path.exists
            )
            if storage_file_exists:
                # Create storage manager only for safety backup creation
                # Note: config_entry not available yet in config flow, settings will be defaults
                safety_backup = await bh.create_timestamped_backup(
                    self.hass, store, const.BACKUP_TAG_RECOVERY, None
                )
                if safety_backup:
                    const.LOGGER.info(
                        "Created safety backup before restore: %s", safety_backup
                    )

            # Parse backup data
            backup_data = json.loads(backup_data_str)

            # Check if backup already has Home Assistant storage format
            if "version" in backup_data and "data" in backup_data:
                # Already in storage format - restore as-is
                await self.hass.async_add_executor_job(
                    shutil.copy2, str(backup_path), str(storage_path)
                )
            else:
                # Raw data format (like v30, v31, v40beta1 samples)
                # Load through storage manager to add proper wrapper
                store = ChoreOpsStore(self.hass)
                store.set_data(backup_data)
                await store.async_save()

            const.LOGGER.info("Restored backup: %s", backup_filename)

            # Extract and validate config_entry_settings if present
            options = {}
            if const.DATA_CONFIG_ENTRY_SETTINGS in backup_data:
                settings = backup_data[const.DATA_CONFIG_ENTRY_SETTINGS]
                validated = bh.validate_config_entry_settings(settings)

                if validated:
                    # Merge with defaults for any missing keys
                    options = {
                        key: validated.get(key, default)
                        for key, default in const.DEFAULT_SYSTEM_SETTINGS.items()
                    }
                    const.LOGGER.info(
                        "Restored %d system settings from backup", len(validated)
                    )
                else:
                    const.LOGGER.info(
                        "No valid system settings in backup, using defaults"
                    )
            else:
                const.LOGGER.info(
                    "Backup does not contain system settings, using defaults"
                )

            # Backup successfully restored - create config entry with settings
            # No need to collect assignees/chores/points since they were in the backup
            return self.async_create_entry(
                title=const.CHOREOPS_TITLE,
                data={},  # Empty - integration will load from restored storage file
                options=options,  # Apply restored settings (or defaults)
            )

        except Exception as err:
            const.LOGGER.error("Restore backup failed: %s", err)
            return self.async_abort(reason=const.TRANS_KEY_CFOP_ERROR_UNKNOWN)

    async def _handle_paste_json(self):
        """Handle pasting JSON data from diagnostics - show text input form."""
        return await self.async_step_paste_json_input()

    async def async_step_paste_json_input(
        self, user_input: dict[str, Any] | None = None
    ):
        """Allow user to paste JSON data from data file or diagnostics."""
        import json
        from pathlib import Path

        from .store import ChoreOpsStore

        errors: dict[str, str] = {}

        if user_input is not None:
            json_text = user_input.get(
                const.CFOF_DATA_RECOVERY_INPUT_JSON_DATA, ""
            ).strip()

            if not json_text:
                errors["base"] = const.CFOP_ERROR_EMPTY_JSON
            else:
                try:
                    # Parse JSON
                    pasted_data = json.loads(json_text)

                    # Validate structure
                    if not bh.validate_backup_json(json_text):
                        errors["base"] = const.CFOP_ERROR_INVALID_STRUCTURE
                    else:
                        # Determine data format and extract storage data
                        storage_data = pasted_data

                        # Handle diagnostic format (KC 4.0+ diagnostic exports)
                        if (
                            const.DATA_KEY_HOME_ASSISTANT in pasted_data
                            and const.DATA_KEY_DATA in pasted_data
                        ):
                            const.LOGGER.info("Processing diagnostic export format")
                            storage_data = pasted_data[const.DATA_KEY_DATA]
                        # Handle Store format (KC 3.0/3.1/4.0beta1)
                        elif (
                            const.DATA_KEY_VERSION in pasted_data
                            and const.DATA_KEY_DATA in pasted_data
                        ):
                            const.LOGGER.info("Processing Store format")
                            storage_data = pasted_data[const.DATA_KEY_DATA]
                        # Raw storage data format
                        else:
                            const.LOGGER.info("Processing raw storage format")
                            storage_data = pasted_data

                        # Always wrap in HA Store format for storage file
                        wrapped_data = {
                            const.DATA_KEY_VERSION: 1,
                            "minor_version": 1,
                            const.DATA_KEY_KEY: const.STORAGE_KEY,
                            const.DATA_KEY_DATA: storage_data,
                        }

                        # Write to storage file
                        storage_path = Path(ChoreOpsStore(self.hass).get_storage_path())

                        await self.hass.async_add_executor_job(
                            lambda: storage_path.parent.mkdir(
                                parents=True, exist_ok=True
                            )
                        )

                        # Write wrapped data to storage (directory created by HA/test fixtures)
                        await self.hass.async_add_executor_job(
                            storage_path.write_text,
                            json.dumps(wrapped_data, indent=2),
                            "utf-8",
                        )

                        const.LOGGER.info("Successfully imported JSON data to storage")

                        # Create config entry - integration will load from storage
                        return self.async_create_entry(
                            title=const.CHOREOPS_TITLE,
                            data={},
                        )

                except json.JSONDecodeError as err:
                    const.LOGGER.error("Invalid JSON pasted: %s", err)
                    errors["base"] = const.CFOP_ERROR_INVALID_JSON
                except Exception as err:
                    const.LOGGER.error("Failed to process pasted JSON: %s", err)
                    errors["base"] = const.CFOP_ERROR_UNKNOWN

        # Show form with text area
        data_schema = vol.Schema(
            {
                vol.Required(const.CFOF_DATA_RECOVERY_INPUT_JSON_DATA): str,
            }
        )

        return self.async_show_form(
            step_id="paste_json_input",
            data_schema=data_schema,
            errors=errors,
        )

    # --------------------------------------------------------------------------
    # POINTS
    # --------------------------------------------------------------------------

    async def async_step_points_label(self, user_input: dict[str, Any] | None = None):
        """Let the user define a custom label for points."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate inputs
            errors = fh.validate_points_inputs(user_input)

            if not errors:
                # Build and store points configuration
                points_data = fh.build_points_data(user_input)
                self._data.update(points_data)
                return await self.async_step_user_count()

        points_schema = fh.build_points_schema(
            default_label=const.DEFAULT_POINTS_LABEL,
            default_icon=const.DEFAULT_POINTS_ICON,
        )

        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_POINTS,
            data_schema=points_schema,
            errors=errors,
        )

    # --------------------------------------------------------------------------
    # ASSIGNEES (canonical)
    # --------------------------------------------------------------------------

    async def async_step_assignee_count(self, user_input: dict[str, Any] | None = None):
        """Ask how many assignee profiles to define for setup compatibility."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._assignee_count = int(
                    user_input[const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_COUNT]
                )
                if self._assignee_count < 0:
                    raise ValueError
                if self._assignee_count == 0:
                    return await self.async_step_chore_count()
                self._assignee_index = 0
                return await self.async_step_assignees()
            except ValueError:
                errors[const.CFOP_ERROR_BASE] = (
                    const.TRANS_KEY_CFOF_INVALID_ASSIGNEE_COUNT
                )

        schema = vol.Schema(
            {
                vol.Required(
                    const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_COUNT, default=1
                ): vol.Coerce(int)
            }
        )
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_ASSIGNEE_COUNT,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_assignees(self, user_input: dict[str, Any] | None = None):
        """Collect each assignee profile using internal_id as the primary key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = fh.validate_assignee_inputs(
                user_input,
                self._assignees_temp,
                self._approvers_temp,
            )

            if not errors:
                assignee_profile_data = dict(db.build_assignee_profile(user_input))
                internal_id = str(
                    assignee_profile_data[const.DATA_ASSIGNEE_INTERNAL_ID]
                )
                self._assignees_temp[internal_id] = assignee_profile_data

                assignee_name = str(assignee_profile_data[const.DATA_ASSIGNEE_NAME])
                const.LOGGER.debug(
                    "Added assignee profile: %s with ID: %s",
                    assignee_name,
                    internal_id,
                )

            self._assignee_index += 1
            if self._assignee_index >= self._assignee_count:
                return await self.async_step_user_count()
            return await self.async_step_assignees()

        users = await self.hass.auth.async_get_users()
        assignee_schema = await fh.build_assignee_schema(self.hass, users=users)
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_ASSIGNEES,
            data_schema=assignee_schema,
            errors=errors,
        )

    # --------------------------------------------------------------------------
    # USERS
    # --------------------------------------------------------------------------

    async def async_step_user_count(self, user_input: dict[str, Any] | None = None):
        """Ask how many users to define initially."""
        errors: dict[str, str] = {}
        if user_input is not None:
            count_input_key = const.CFOF_APPROVERS_INPUT_APPROVER_COUNT
            if const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_COUNT in user_input:
                count_input_key = const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_COUNT
                self._legacy_split_user_counts = True
                self._legacy_collecting_assignable_users = True
            elif (
                self._legacy_split_user_counts
                and self._legacy_collecting_assignable_users
                and const.CFOF_APPROVERS_INPUT_APPROVER_COUNT in user_input
            ):
                self._legacy_collecting_assignable_users = False

            try:
                self._approvers_count = int(user_input[count_input_key])
                if self._approvers_count < 0:
                    raise ValueError
                if self._approvers_count == 0:
                    if (
                        self._legacy_split_user_counts
                        and self._legacy_collecting_assignable_users
                    ):
                        self._legacy_collecting_assignable_users = False
                        return await self.async_step_user_count()
                    return await self.async_step_chore_count()
                self._approvers_index = 0
                return await self.async_step_users()
            except ValueError:
                if count_input_key == const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_COUNT:
                    errors[const.CFOP_ERROR_BASE] = (
                        const.TRANS_KEY_CFOF_INVALID_ASSIGNEE_COUNT
                    )
                else:
                    errors[const.CFOP_ERROR_BASE] = (
                        const.TRANS_KEY_CFOF_INVALID_APPROVER_COUNT
                    )

        schema = vol.Schema(
            {
                vol.Required(
                    const.CFOF_APPROVERS_INPUT_APPROVER_COUNT,
                    default=1,
                ): vol.Coerce(int)
            }
        )
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_USER_COUNT,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_users(self, user_input: dict[str, Any] | None = None):
        """Collect each user profile using internal_id as the primary key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            is_assignee_payload = (
                const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME in user_input
                and const.CFOF_APPROVERS_INPUT_ASSOCIATED_ASSIGNEES not in user_input
                and const.CFOF_APPROVERS_INPUT_CAN_APPROVE not in user_input
                and const.CFOF_APPROVERS_INPUT_CAN_MANAGE not in user_input
                and const.CFOF_APPROVERS_INPUT_ALLOW_CHORE_ASSIGNMENT not in user_input
            )
            is_assignee_payload = is_assignee_payload or (
                bool(user_input.get(const.CFOF_APPROVERS_INPUT_ALLOW_CHORE_ASSIGNMENT))
                and not bool(user_input.get(const.CFOF_APPROVERS_INPUT_CAN_APPROVE))
                and not bool(user_input.get(const.CFOF_APPROVERS_INPUT_CAN_MANAGE))
                and not user_input.get(
                    const.CFOF_APPROVERS_INPUT_ASSOCIATED_ASSIGNEES, []
                )
            )

            if is_assignee_payload:
                assignee_input = {
                    const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME: user_input.get(
                        const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME,
                        user_input.get(
                            const.CFOF_APPROVERS_INPUT_NAME,
                            const.SENTINEL_EMPTY,
                        ),
                    ),
                    const.CFOF_ASSIGNEES_INPUT_HA_USER: user_input.get(
                        const.CFOF_ASSIGNEES_INPUT_HA_USER,
                        user_input.get(
                            const.CFOF_APPROVERS_INPUT_HA_USER,
                            const.SENTINEL_EMPTY,
                        ),
                    ),
                    const.CFOF_ASSIGNEES_INPUT_DASHBOARD_LANGUAGE: user_input.get(
                        const.CFOF_ASSIGNEES_INPUT_DASHBOARD_LANGUAGE,
                        user_input.get(
                            const.CFOF_APPROVERS_INPUT_DASHBOARD_LANGUAGE,
                            const.DEFAULT_DASHBOARD_LANGUAGE,
                        ),
                    ),
                    const.CFOF_ASSIGNEES_INPUT_MOBILE_NOTIFY_SERVICE: user_input.get(
                        const.CFOF_ASSIGNEES_INPUT_MOBILE_NOTIFY_SERVICE,
                        user_input.get(
                            const.CFOF_APPROVERS_INPUT_MOBILE_NOTIFY_SERVICE,
                            const.SENTINEL_EMPTY,
                        ),
                    ),
                }
                errors = fh.validate_assignee_inputs(
                    assignee_input,
                    self._assignees_temp,
                    self._approvers_temp,
                )

                if not errors:
                    assignee_profile_data = dict(
                        db.build_assignee_profile(assignee_input)
                    )
                    internal_id = str(
                        assignee_profile_data[const.DATA_ASSIGNEE_INTERNAL_ID]
                    )
                    self._assignees_temp[internal_id] = assignee_profile_data
                    assignee_name = str(assignee_profile_data[const.DATA_ASSIGNEE_NAME])
                    const.LOGGER.debug(
                        "Added assignee profile: %s with ID: %s",
                        assignee_name,
                        internal_id,
                    )
            else:
                user_input = fh.normalize_user_form_input(user_input)

                errors = fh.validate_users_inputs(
                    user_input,
                    self._approvers_temp,
                    self._assignees_temp,
                )

                if not errors:
                    approver_data = dict(db.build_user_profile(user_input))
                    internal_id = str(approver_data[const.DATA_APPROVER_INTERNAL_ID])
                    approver_name = str(approver_data[const.DATA_APPROVER_NAME])

                    approver_data[const.DATA_APPROVER_LINKED_PROFILE_ID] = None

                    self._approvers_temp[internal_id] = approver_data
                    const.LOGGER.debug(
                        "Added user profile: %s with ID: %s",
                        approver_name,
                        internal_id,
                    )

            self._approvers_index += 1
            if self._approvers_index >= self._approvers_count:
                if (
                    self._legacy_split_user_counts
                    and self._legacy_collecting_assignable_users
                ):
                    self._legacy_collecting_assignable_users = False
                    return await self.async_step_user_count()
                return await self.async_step_chore_count()
            return await self.async_step_users()

        assignees_dict = {
            assignee_data[const.DATA_ASSIGNEE_NAME]: assignee_id
            for assignee_id, assignee_data in self._assignees_temp.items()
        }

        users = await self.hass.auth.async_get_users()
        user_schema = await fh.build_user_schema(
            self.hass, users=users, assignees_dict=assignees_dict
        )
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_USERS,
            data_schema=user_schema,
            errors=fh.map_user_form_errors(errors),
        )

    # --------------------------------------------------------------------------
    # CHORES
    # --------------------------------------------------------------------------
    async def async_step_chore_count(self, user_input: dict[str, Any] | None = None):
        """Ask how many chores to define."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._chore_count = int(user_input[const.CFOF_CHORES_INPUT_CHORE_COUNT])
                if self._chore_count < 0:
                    raise ValueError
                if self._chore_count == 0:
                    return await self.async_step_badge_count()
                self._chore_index = 0
                return await self.async_step_chores()
            except ValueError:
                errors[const.CFOP_ERROR_BASE] = const.TRANS_KEY_CFOF_INVALID_CHORE_COUNT

        schema = vol.Schema(
            {
                vol.Required(
                    const.CFOF_CHORES_INPUT_CHORE_COUNT, default=1
                ): vol.Coerce(int)
            }
        )
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_CHORE_COUNT,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_chores(self, user_input: dict[str, Any] | None = None):
        """Collect chore details using internal_id as the primary key.

        Store in self._chores_temp as a dict keyed by internal_id.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = fh.normalize_chore_form_input(user_input)

            # Build assignees_dict for name→UUID conversion
            assignees_dict = {
                assignee_data[const.DATA_ASSIGNEE_NAME]: assignee_id
                for assignee_id, assignee_data in self._assignees_temp.items()
            }

            # Validate chore input (returns errors dict and processed due_date)
            errors, due_date_str = fh.validate_chores_inputs(
                user_input, assignees_dict, self._chores_temp
            )
            errors = fh.map_chore_form_errors(errors)

            if errors:
                # Re-show the form with user's attempted values as suggestions
                # (preserves clearable-field behavior)
                suggested_values = fh.build_chore_section_suggested_values(user_input)
                chore_schema = fh.build_chore_schema(
                    assignees_dict,
                    frequency_options=const.CHORE_FREQUENCY_OPTIONS_CONFIG_FLOW,
                )
                chore_schema = self.add_suggested_values_to_schema(
                    chore_schema,
                    suggested_values,
                )
                chore_schema = vol.Schema(chore_schema.schema, extra=vol.ALLOW_EXTRA)
                return self.async_show_form(
                    step_id=const.CONFIG_FLOW_STEP_CHORES,
                    data_schema=chore_schema,
                    errors=errors,
                )

            # Transform CFOF_* → DATA_* keys
            transformed_data = fh.transform_chore_cfof_to_data(
                user_input, assignees_dict, due_date_str
            )

            # Build complete chore entity (generates internal_id)
            new_chore = db.build_chore(transformed_data)
            internal_id = new_chore[const.DATA_CHORE_INTERNAL_ID]

            # Store the chore (cast to dict for _chores_temp type compatibility)
            self._chores_temp[internal_id] = dict(new_chore)

            chore_name = new_chore[const.DATA_CHORE_NAME]
            const.LOGGER.debug(
                "DEBUG: Added Chore: %s with ID: %s", chore_name, internal_id
            )

            self._chore_index += 1
            if self._chore_index >= self._chore_count:
                return await self.async_step_badge_count()
            return await self.async_step_chores()

        # Use flow_helpers.build_chore_schema, passing the current assignees
        # Config flow uses restricted frequency options (excludes DAILY_MULTI)
        assignees_dict = {
            assignee_data[const.DATA_ASSIGNEE_NAME]: assignee_id
            for assignee_id, assignee_data in self._assignees_temp.items()
        }
        default_data: dict[str, Any] = {}
        chore_schema = fh.build_chore_schema(
            assignees_dict,
            default_data,
            frequency_options=const.CHORE_FREQUENCY_OPTIONS_CONFIG_FLOW,
        )
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_CHORES,
            data_schema=chore_schema,
            errors=errors,
        )

    # --------------------------------------------------------------------------
    # BADGES
    # --------------------------------------------------------------------------
    async def async_step_badge_count(self, user_input: dict[str, Any] | None = None):
        """Ask how many badges to define."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._badge_count = int(user_input[const.CFOF_BADGES_INPUT_BADGE_COUNT])
                if self._badge_count < 0:
                    raise ValueError
                if self._badge_count == 0:
                    return await self.async_step_reward_count()
                self._badge_index = 0
                return await self.async_step_badges()
            except ValueError:
                errors[const.CFOP_ERROR_BASE] = const.TRANS_KEY_CFOF_INVALID_BADGE_COUNT

        schema = vol.Schema(
            {
                vol.Required(
                    const.CFOF_BADGES_INPUT_BADGE_COUNT, default=0
                ): vol.Coerce(int)
            }
        )
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_BADGE_COUNT,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_badges(self, user_input: dict[str, Any] | None = None):
        """Collect badge details using internal_id as the primary key."""
        return await self.async_add_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_CUMULATIVE,
        )

    async def async_add_badge_common(
        self,
        user_input: dict[str, Any] | None = None,
        badge_type: str = const.BADGE_TYPE_CUMULATIVE,
        default_data: dict[str, Any] | None = None,
    ):
        """Handle adding a badge in the config flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # --- Validate Inputs ---
            errors = fh.validate_badge_common_inputs(
                user_input=user_input,
                internal_id=None,  # No internal_id yet for new badges
                existing_badges=self._badges_temp,
                badge_type=badge_type,
            )

            if not errors:
                # --- Build Data using data_builders ---
                updated_badge_data = db.build_badge(
                    user_input=user_input,
                    existing=None,
                    badge_type=badge_type,
                )

                # --- Save Data ---
                internal_id = updated_badge_data[const.DATA_BADGE_INTERNAL_ID]
                self._badges_temp[internal_id] = dict(updated_badge_data)

                const.LOGGER.debug(
                    "Added Badge '%s' with ID: %s. Data: %s",
                    updated_badge_data[const.DATA_BADGE_NAME],
                    internal_id,
                    updated_badge_data,
                )

                # Proceed to the next step or finish
                self._badge_index += 1
                if self._badge_index >= self._badge_count:
                    return await self.async_step_reward_count()
                return await self.async_step_badges()

        # --- Build Schema with Suggested Values ---
        schema_fields = fh.build_badge_common_schema(
            default=None,
            assignees_dict=self._assignees_temp,
            chores_dict=self._chores_temp,
            rewards_dict=self._rewards_temp,
            achievements_dict=self._achievements_temp,
            challenges_dict=self._challenges_temp,
            badge_type=badge_type,
        )
        data_schema = vol.Schema(schema_fields)

        # On validation error, preserve user's attempted input
        if user_input:
            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)

        # Determine step name dynamically
        step_name = const.CONFIG_FLOW_STEP_BADGES

        # Add documentation URL based on badge_type (same logic as options flow)
        doc_url_map = {
            const.BADGE_TYPE_CUMULATIVE: const.DOC_URL_BADGES_CUMULATIVE,
            const.BADGE_TYPE_PERIODIC: const.DOC_URL_BADGES_PERIODIC,
            const.BADGE_TYPE_ACHIEVEMENT_LINKED: const.DOC_URL_BADGES_OVERVIEW,
            const.BADGE_TYPE_CHALLENGE_LINKED: const.DOC_URL_BADGES_OVERVIEW,
            const.BADGE_TYPE_DAILY: const.DOC_URL_BADGES_OVERVIEW,
            const.BADGE_TYPE_SPECIAL_OCCASION: const.DOC_URL_BADGES_OVERVIEW,
        }

        return self.async_show_form(
            step_id=step_name,
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: doc_url_map.get(
                    badge_type, const.DOC_URL_BADGES_OVERVIEW
                )
            },
        )

    # --------------------------------------------------------------------------
    # REWARDS
    # --------------------------------------------------------------------------
    async def async_step_reward_count(self, user_input: dict[str, Any] | None = None):
        """Ask how many rewards to define."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._reward_count = int(
                    user_input[const.CFOF_REWARDS_INPUT_REWARD_COUNT]
                )
                if self._reward_count < 0:
                    raise ValueError
                if self._reward_count == 0:
                    return await self.async_step_penalty_count()
                self._reward_index = 0
                return await self.async_step_rewards()
            except ValueError:
                errors[const.CFOP_ERROR_BASE] = (
                    const.TRANS_KEY_CFOF_INVALID_REWARD_COUNT
                )

        schema = vol.Schema(
            {
                vol.Required(
                    const.CFOF_REWARDS_INPUT_REWARD_COUNT, default=0
                ): vol.Coerce(int)
            }
        )
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_REWARD_COUNT,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_rewards(self, user_input: dict[str, Any] | None = None):
        """Collect reward details using internal_id as the primary key.

        Store in self._rewards_temp as a dict keyed by internal_id.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = fh.validate_rewards_inputs(user_input, self._rewards_temp)
            if not errors:
                # Generate internal_id for new reward
                internal_id = str(uuid.uuid4())

                # CFOF_* keys now aligned with DATA_* keys - pass directly
                reward_data = dict(db.build_reward(user_input))
                self._rewards_temp[internal_id] = reward_data

                reward_name = reward_data[const.DATA_REWARD_NAME]
                const.LOGGER.debug(
                    "DEBUG: Added Reward: %s with ID: %s", reward_name, internal_id
                )

            self._reward_index += 1
            if self._reward_index >= self._reward_count:
                return await self.async_step_penalty_count()
            return await self.async_step_rewards()

        reward_schema = fh.build_reward_schema()
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_REWARDS,
            data_schema=reward_schema,
            errors=errors,
        )

    # --------------------------------------------------------------------------
    # PENALTIES
    # --------------------------------------------------------------------------
    async def async_step_penalty_count(self, user_input: dict[str, Any] | None = None):
        """Ask how many penalties to define."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._penalty_count = int(
                    user_input[const.CFOF_PENALTIES_INPUT_PENALTY_COUNT]
                )
                if self._penalty_count < 0:
                    raise ValueError
                if self._penalty_count == 0:
                    return await self.async_step_bonus_count()
                self._penalty_index = 0
                return await self.async_step_penalties()
            except ValueError:
                errors[const.CFOP_ERROR_BASE] = (
                    const.TRANS_KEY_CFOF_INVALID_PENALTY_COUNT
                )

        schema = vol.Schema(
            {
                vol.Required(
                    const.CFOF_PENALTIES_INPUT_PENALTY_COUNT, default=0
                ): vol.Coerce(int)
            }
        )
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_PENALTY_COUNT,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_penalties(self, user_input: dict[str, Any] | None = None):
        """Collect penalty details using internal_id as the primary key.

        Store in self._penalties_temp as a dict keyed by internal_id.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            # Validate inputs
            errors = fh.validate_penalties_inputs(user_input, self._penalties_temp)

            if not errors:
                # Transform form input keys to DATA_* keys for data_builders
                transformed_input = {
                    const.DATA_PENALTY_NAME: user_input.get(
                        const.CFOF_PENALTIES_INPUT_NAME, const.SENTINEL_EMPTY
                    ),
                    const.DATA_PENALTY_DESCRIPTION: user_input.get(
                        const.CFOF_PENALTIES_INPUT_DESCRIPTION, const.SENTINEL_EMPTY
                    ),
                    const.DATA_PENALTY_POINTS: user_input.get(
                        const.CFOF_PENALTIES_INPUT_POINTS, const.DEFAULT_PENALTY_POINTS
                    ),
                    const.DATA_PENALTY_ICON: user_input.get(
                        const.CFOF_PENALTIES_INPUT_ICON, const.SENTINEL_EMPTY
                    ),
                }
                # Build penalty data using unified helper
                penalty_data = db.build_bonus_or_penalty(transformed_input, "penalty")
                internal_id = penalty_data[const.DATA_PENALTY_INTERNAL_ID]
                self._penalties_temp[internal_id] = penalty_data

                penalty_name = user_input[const.CFOF_PENALTIES_INPUT_NAME].strip()
                const.LOGGER.debug(
                    "DEBUG: Added Penalty: %s with ID: %s", penalty_name, internal_id
                )

            self._penalty_index += 1
            if self._penalty_index >= self._penalty_count:
                return await self.async_step_bonus_count()
            return await self.async_step_penalties()

        penalty_schema = fh.build_penalty_schema()
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_PENALTIES,
            data_schema=penalty_schema,
            errors=errors,
        )

    # --------------------------------------------------------------------------
    # BONUSES
    # --------------------------------------------------------------------------
    async def async_step_bonus_count(self, user_input: dict[str, Any] | None = None):
        """Ask how many bonuses to define."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._bonus_count = int(
                    user_input[const.CFOF_BONUSES_INPUT_BONUS_COUNT]
                )
                if self._bonus_count < 0:
                    raise ValueError
                if self._bonus_count == 0:
                    return await self.async_step_achievement_count()
                self._bonus_index = 0
                return await self.async_step_bonuses()
            except ValueError:
                errors[const.CFOP_ERROR_BASE] = const.TRANS_KEY_CFOF_INVALID_BONUS_COUNT

        schema = vol.Schema(
            {
                vol.Required(
                    const.CFOF_BONUSES_INPUT_BONUS_COUNT, default=0
                ): vol.Coerce(int)
            }
        )
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_BONUS_COUNT,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_bonuses(self, user_input: dict[str, Any] | None = None):
        """Collect bonus details using internal_id as the primary key.

        Store in self._bonuses_temp as a dict keyed by internal_id.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            # Validate inputs
            errors = fh.validate_bonuses_inputs(user_input, self._bonuses_temp)

            if not errors:
                # Transform form input keys to DATA_* keys for data_builders
                transformed_input = {
                    const.DATA_BONUS_NAME: user_input.get(
                        const.CFOF_BONUSES_INPUT_NAME, const.SENTINEL_EMPTY
                    ),
                    const.DATA_BONUS_DESCRIPTION: user_input.get(
                        const.CFOF_BONUSES_INPUT_DESCRIPTION, const.SENTINEL_EMPTY
                    ),
                    const.DATA_BONUS_POINTS: user_input.get(
                        const.CFOF_BONUSES_INPUT_POINTS, const.DEFAULT_BONUS_POINTS
                    ),
                    const.DATA_BONUS_ICON: user_input.get(
                        const.CFOF_BONUSES_INPUT_ICON, const.SENTINEL_EMPTY
                    ),
                }
                # Build bonus data using unified helper
                bonus_data = db.build_bonus_or_penalty(transformed_input, "bonus")
                internal_id = bonus_data[const.DATA_BONUS_INTERNAL_ID]
                self._bonuses_temp[internal_id] = bonus_data

                bonus_name = user_input[const.CFOF_BONUSES_INPUT_NAME].strip()
                const.LOGGER.debug(
                    "DEBUG: Added Bonus '%s' with ID: %s", bonus_name, internal_id
                )

            self._bonus_index += 1
            if self._bonus_index >= self._bonus_count:
                return await self.async_step_achievement_count()
            return await self.async_step_bonuses()

        schema = fh.build_bonus_schema()
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_BONUSES, data_schema=schema, errors=errors
        )

    # --------------------------------------------------------------------------
    # ACHIEVEMENTS
    # --------------------------------------------------------------------------
    async def async_step_achievement_count(
        self, user_input: dict[str, Any] | None = None
    ):
        """Ask how many achievements to define initially."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._achievement_count = int(
                    user_input[const.CFOF_ACHIEVEMENTS_INPUT_ACHIEVEMENT_COUNT]
                )
                if self._achievement_count < 0:
                    raise ValueError
                if self._achievement_count == 0:
                    return await self.async_step_challenge_count()
                self._achievement_index = 0
                return await self.async_step_achievements()
            except ValueError:
                errors[const.CFOP_ERROR_BASE] = (
                    const.TRANS_KEY_CFOF_INVALID_ACHIEVEMENT_COUNT
                )
        schema = vol.Schema(
            {
                vol.Required(
                    const.CFOF_ACHIEVEMENTS_INPUT_ACHIEVEMENT_COUNT, default=0
                ): vol.Coerce(int)
            }
        )
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_achievements(self, user_input: dict[str, Any] | None = None):
        """Collect each achievement's details using internal_id as the key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Layer 2: UI validation (uniqueness + type-specific checks)
            errors = fh.validate_achievements_inputs(
                user_input, self._achievements_temp
            )

            if not errors:
                try:
                    # Config flow uses names directly (no name-to-ID mapping needed)
                    assignees_name_to_id = {
                        assignee_data[const.DATA_ASSIGNEE_NAME]: assignee_id
                        for assignee_id, assignee_data in self._assignees_temp.items()
                    }

                    # Layer 3: Convert CFOF_* to DATA_* keys
                    data_input = db.map_cfof_to_achievement_data(user_input)

                    # Convert assigned assignees from names to IDs
                    assigned_assignees_names = data_input.get(
                        const.DATA_ACHIEVEMENT_ASSIGNED_ASSIGNEES, []
                    )
                    if not isinstance(assigned_assignees_names, list):
                        assigned_assignees_names = (
                            [assigned_assignees_names]
                            if assigned_assignees_names
                            else []
                        )
                    data_input[const.DATA_ACHIEVEMENT_ASSIGNED_ASSIGNEES] = [
                        assignees_name_to_id.get(name, name)
                        for name in assigned_assignees_names
                    ]

                    # Build complete achievement structure
                    achievement = db.build_achievement(data_input)
                    internal_id = achievement[const.DATA_ACHIEVEMENT_INTERNAL_ID]
                    self._achievements_temp[internal_id] = dict(achievement)

                    achievement_name = user_input[
                        const.CFOF_ACHIEVEMENTS_INPUT_NAME
                    ].strip()
                    const.LOGGER.debug(
                        "DEBUG: Added Achievement '%s' with ID: %s",
                        achievement_name,
                        internal_id,
                    )

                except EntityValidationError as err:
                    errors[err.field] = err.translation_key

            if not errors:
                self._achievement_index += 1
                if self._achievement_index >= self._achievement_count:
                    return await self.async_step_challenge_count()
                return await self.async_step_achievements()

        assignees_dict = {
            assignee_data[const.DATA_ASSIGNEE_NAME]: assignee_id
            for assignee_id, assignee_data in self._assignees_temp.items()
        }
        all_chores = self._chores_temp
        achievement_schema = fh.build_achievement_schema(
            assignees_dict=assignees_dict, chores_dict=all_chores, default=None
        )
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_ACHIEVEMENTS,
            data_schema=achievement_schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_ACHIEVEMENTS_OVERVIEW
            },
        )

    # --------------------------------------------------------------------------
    # CHALLENGES
    # --------------------------------------------------------------------------
    async def async_step_challenge_count(
        self, user_input: dict[str, Any] | None = None
    ):
        """Ask how many challenges to define initially."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._challenge_count = int(
                    user_input[const.CFOF_CHALLENGES_INPUT_CHALLENGE_COUNT]
                )
                if self._challenge_count < 0:
                    raise ValueError
                if self._challenge_count == 0:
                    return await self.async_step_finish()
                self._challenge_index = 0
                return await self.async_step_challenges()
            except ValueError:
                errors[const.CFOP_ERROR_BASE] = (
                    const.TRANS_KEY_CFOF_INVALID_CHALLENGE_COUNT
                )
        schema = vol.Schema(
            {
                vol.Required(
                    const.CFOF_CHALLENGES_INPUT_CHALLENGE_COUNT, default=0
                ): vol.Coerce(int)
            }
        )
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_CHALLENGE_COUNT,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_challenges(self, user_input: dict[str, Any] | None = None):
        """Collect each challenge's details using internal_id as the key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Layer 2: UI validation (uniqueness + type-specific checks)
            errors = fh.validate_challenges_inputs(
                user_input,
                existing_challenges=self._challenges_temp,
                current_challenge_id=None,  # New challenge
            )

            if not errors:
                try:
                    # Config flow uses names directly (need name-to-ID mapping)
                    assignees_name_to_id = {
                        assignee_data[const.DATA_ASSIGNEE_NAME]: assignee_id
                        for assignee_id, assignee_data in self._assignees_temp.items()
                    }

                    # Layer 3: Convert CFOF_* to DATA_* keys
                    data_input = db.map_cfof_to_challenge_data(user_input)

                    # Convert assigned assignees from names to IDs
                    assigned_assignees_names = data_input.get(
                        const.DATA_CHALLENGE_ASSIGNED_ASSIGNEES, []
                    )
                    if not isinstance(assigned_assignees_names, list):
                        assigned_assignees_names = (
                            [assigned_assignees_names]
                            if assigned_assignees_names
                            else []
                        )
                    data_input[const.DATA_CHALLENGE_ASSIGNED_ASSIGNEES] = [
                        assignees_name_to_id.get(name, name)
                        for name in assigned_assignees_names
                    ]

                    # Additional config flow specific validation: dates must be in the future
                    start_date_str = data_input.get(const.DATA_CHALLENGE_START_DATE)
                    end_date_str = data_input.get(const.DATA_CHALLENGE_END_DATE)

                    start_dt = (
                        dt_util.parse_datetime(start_date_str)
                        if start_date_str
                        else None
                    )
                    end_dt = (
                        dt_util.parse_datetime(end_date_str) if end_date_str else None
                    )

                    if start_dt and start_dt < dt_util.utcnow():
                        errors = {
                            const.CFOP_ERROR_START_DATE: const.TRANS_KEY_CFOF_START_DATE_IN_PAST
                        }
                    elif end_dt and end_dt <= dt_util.utcnow():
                        errors = {
                            const.CFOP_ERROR_END_DATE: const.TRANS_KEY_CFOF_END_DATE_IN_PAST
                        }

                    if not errors:
                        # Build complete challenge structure
                        challenge = db.build_challenge(data_input)
                        internal_id = challenge[const.DATA_CHALLENGE_INTERNAL_ID]
                        self._challenges_temp[internal_id] = dict(challenge)

                        challenge_name = user_input[
                            const.CFOF_CHALLENGES_INPUT_NAME
                        ].strip()
                        const.LOGGER.debug(
                            "DEBUG: Added Challenge '%s' with ID: %s",
                            challenge_name,
                            internal_id,
                        )

                except EntityValidationError as err:
                    errors[err.field] = err.translation_key

            if not errors:
                self._challenge_index += 1
                if self._challenge_index >= self._challenge_count:
                    return await self.async_step_finish()
                return await self.async_step_challenges()

        assignees_dict = {
            assignee_data[const.DATA_ASSIGNEE_NAME]: assignee_id
            for assignee_id, assignee_data in self._assignees_temp.items()
        }
        all_chores = self._chores_temp
        default_data = user_input or None
        challenge_schema = fh.build_challenge_schema(
            assignees_dict=assignees_dict,
            chores_dict=all_chores,
            default=default_data,
        )
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_CHALLENGES,
            data_schema=challenge_schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_CHALLENGES_OVERVIEW
            },
        )

    # --------------------------------------------------------------------------
    # FINISH
    # --------------------------------------------------------------------------
    async def async_step_finish(self, user_input: dict[str, Any] | None = None):
        """Finalize summary and create the config entry."""
        if user_input is not None:
            return await self._create_entry()

        # Create a mapping from assignment-profile IDs to display names
        assignee_id_to_name = {
            assignee_id: data[const.DATA_ASSIGNEE_NAME]
            for assignee_id, data in self._assignees_temp.items()
        }

        # Enhance approver summary to include associated profile names
        approvers_summary = []
        for approver_record in self._approvers_temp.values():
            associated_assignees_names = [
                assignee_id_to_name.get(
                    assignee_id, const.TRANS_KEY_DISPLAY_UNKNOWN_ASSIGNEE
                )
                for assignee_id in approver_record.get(
                    const.DATA_APPROVER_ASSOCIATED_USERS, []
                )
            ]
            if associated_assignees_names:
                assignees_str = ", ".join(associated_assignees_names)
                approvers_summary.append(
                    f"{approver_record[const.DATA_APPROVER_NAME]} (Assignees: {assignees_str})"
                )
            else:
                approvers_summary.append(approver_record[const.DATA_APPROVER_NAME])

        assignees_names = (
            ", ".join(
                assignee_data[const.DATA_ASSIGNEE_NAME]
                for assignee_data in self._assignees_temp.values()
            )
            or const.SENTINEL_NONE_TEXT
        )
        approvers_names = ", ".join(approvers_summary) or const.SENTINEL_NONE_TEXT
        chores_names = (
            ", ".join(
                chore_data[const.DATA_CHORE_NAME]
                for chore_data in self._chores_temp.values()
            )
            or const.SENTINEL_NONE_TEXT
        )
        badges_names = (
            ", ".join(
                badge_data[const.DATA_BADGE_NAME]
                for badge_data in self._badges_temp.values()
            )
            or const.SENTINEL_NONE_TEXT
        )
        rewards_names = (
            ", ".join(
                reward_data[const.DATA_REWARD_NAME]
                for reward_data in self._rewards_temp.values()
            )
            or const.SENTINEL_NONE_TEXT
        )
        penalties_names = (
            ", ".join(
                penalty_data[const.DATA_PENALTY_NAME]
                for penalty_data in self._penalties_temp.values()
            )
            or const.SENTINEL_NONE_TEXT
        )
        bonuses_names = (
            ", ".join(
                bonus_data[const.DATA_BONUS_NAME]
                for bonus_data in self._bonuses_temp.values()
            )
            or const.SENTINEL_NONE_TEXT
        )
        achievements_names = (
            ", ".join(
                achievement_data[const.DATA_ACHIEVEMENT_NAME]
                for achievement_data in self._achievements_temp.values()
            )
            or const.SENTINEL_NONE_TEXT
        )
        challenges_names = (
            ", ".join(
                challenge_data[const.DATA_CHALLENGE_NAME]
                for challenge_data in self._challenges_temp.values()
            )
            or const.SENTINEL_NONE_TEXT
        )

        # Use TRANS_KEY constants that already contain English labels (e.g., "Assignees: ")
        summary = (
            f"{const.TRANS_KEY_CFOF_SUMMARY_ASSIGNEES}{assignees_names}\n\n"
            f"{const.TRANS_KEY_CFOF_SUMMARY_APPROVERS}{approvers_names}\n\n"
            f"{const.TRANS_KEY_CFOF_SUMMARY_CHORES}{chores_names}\n\n"
            f"{const.TRANS_KEY_CFOF_SUMMARY_BADGES}{badges_names}\n\n"
            f"{const.TRANS_KEY_CFOF_SUMMARY_REWARDS}{rewards_names}\n\n"
            f"{const.TRANS_KEY_CFOF_SUMMARY_PENALTIES}{penalties_names}\n\n"
            f"{const.TRANS_KEY_CFOF_SUMMARY_BONUSES}{bonuses_names}\n\n"
            f"{const.TRANS_KEY_CFOF_SUMMARY_ACHIEVEMENTS}{achievements_names}\n\n"
            f"{const.TRANS_KEY_CFOF_SUMMARY_CHALLENGES}{challenges_names}\n\n"
        )
        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_FINISH,
            data_schema=vol.Schema({}),
            description_placeholders={const.OPTIONS_FLOW_PLACEHOLDER_SUMMARY: summary},
        )

    async def _create_entry(self):
        """Finalize config entry with direct-to-storage entity data (KC 4.0+ architecture)."""
        from .store import ChoreOpsStore

        # Start with canonical structure from Store (SINGLE SOURCE OF TRUTH)
        storage_data = ChoreOpsStore.get_default_structure()

        # Populate with user-configured entities from config flow
        storage_data[const.DATA_ASSIGNEES] = self._assignees_temp
        approver_users = {
            approver_id: {
                **dict(approver_data),
                const.DATA_USER_CAN_BE_ASSIGNED: False,
            }
            for approver_id, approver_data in self._approvers_temp.items()
        }
        storage_data[const.DATA_USERS] = {
            **self._assignees_temp,
            **approver_users,
        }
        storage_data[const.DATA_CHORES] = self._chores_temp
        storage_data[const.DATA_BADGES] = self._badges_temp
        storage_data[const.DATA_REWARDS] = self._rewards_temp
        storage_data[const.DATA_PENALTIES] = self._penalties_temp
        storage_data[const.DATA_BONUSES] = self._bonuses_temp
        storage_data[const.DATA_ACHIEVEMENTS] = self._achievements_temp
        storage_data[const.DATA_CHALLENGES] = self._challenges_temp

        # Initialize storage manager and save entity data
        store = ChoreOpsStore(self.hass)
        store.set_data(storage_data)
        await store.async_save()

        const.LOGGER.info(
            "INFO: Config Flow saved storage with schema version %s (%d assignees, %d approvers, %d chores, %d badges, %d rewards, %d bonuses, %d penalties)",
            const.SCHEMA_VERSION_STORAGE_ONLY,
            len(self._assignees_temp),
            len(self._approvers_temp),
            len(self._chores_temp),
            len(self._badges_temp),
            len(self._rewards_temp),
            len(self._bonuses_temp),
            len(self._penalties_temp),
        )
        const.LOGGER.debug(
            "DEBUG: Config Flow - Assignees data: %s",
            {
                assignee_id: assignee_data.get(const.DATA_ASSIGNEE_NAME)
                for assignee_id, assignee_data in self._assignees_temp.items()
            },
        )

        # Config entry contains ONLY system settings (no entity data)
        entry_data: dict[str, Any] = {}  # Keep empty - standard HA pattern

        # Build all 9 system settings using consolidated helper function
        entry_options = fh.build_all_system_settings_data(self._data)

        const.LOGGER.debug(
            "Creating config entry with system settings only: %s",
            entry_options,
        )
        return self.async_create_entry(
            title=const.CHOREOPS_TITLE, data=entry_data, options=entry_options
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration (editing system settings via Configure button).

        This flow allows users to update all 9 system settings via the standard
        Home Assistant "Configure" button instead of navigating the options menu.
        Uses consolidated flow_helpers for validation and data building.
        """
        entry_id = self.context.get("entry_id")
        if not entry_id or not isinstance(entry_id, str):
            return self.async_abort(reason=const.CONFIG_FLOW_ABORT_RECONFIGURE_FAILED)

        config_entry = self.hass.config_entries.async_get_entry(entry_id)
        if not config_entry:
            return self.async_abort(reason=const.CONFIG_FLOW_ABORT_RECONFIGURE_FAILED)

        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate all 9 system settings using consolidated helper
            errors = fh.validate_all_system_settings(user_input)

            if not errors:
                # Build all 9 system settings using consolidated helper
                all_settings_data = fh.build_all_system_settings_data(user_input)

                # Update config entry options with all system settings
                updated_options = dict(config_entry.options)
                updated_options.update(all_settings_data)

                const.LOGGER.debug(
                    "Reconfiguring system settings: points_label=%s, update_interval=%s",
                    all_settings_data.get(const.CONF_POINTS_LABEL),
                    all_settings_data.get(const.CONF_UPDATE_INTERVAL),
                )

                # Update and reload integration
                self.hass.config_entries.async_update_entry(
                    config_entry, options=updated_options
                )
                await self.hass.config_entries.async_reload(config_entry.entry_id)

                return self.async_abort(
                    reason=const.CONFIG_FLOW_ABORT_RECONFIGURE_SUCCESSFUL
                )

        # Build the comprehensive schema with all 9 settings using current values
        all_settings_schema = fh.build_all_system_settings_schema(
            default_points_label=config_entry.options.get(
                const.CONF_POINTS_LABEL, const.DEFAULT_POINTS_LABEL
            ),
            default_points_icon=config_entry.options.get(
                const.CONF_POINTS_ICON, const.DEFAULT_POINTS_ICON
            ),
            default_update_interval=config_entry.options.get(
                const.CONF_UPDATE_INTERVAL, const.DEFAULT_UPDATE_INTERVAL
            ),
            default_calendar_show_period=config_entry.options.get(
                const.CONF_CALENDAR_SHOW_PERIOD, const.DEFAULT_CALENDAR_SHOW_PERIOD
            ),
            default_retention_daily=config_entry.options.get(
                const.CONF_RETENTION_DAILY, const.DEFAULT_RETENTION_DAILY
            ),
            default_retention_weekly=config_entry.options.get(
                const.CONF_RETENTION_WEEKLY, const.DEFAULT_RETENTION_WEEKLY
            ),
            default_retention_monthly=config_entry.options.get(
                const.CONF_RETENTION_MONTHLY, const.DEFAULT_RETENTION_MONTHLY
            ),
            default_retention_yearly=config_entry.options.get(
                const.CONF_RETENTION_YEARLY, const.DEFAULT_RETENTION_YEARLY
            ),
            default_points_adjust_values=config_entry.options.get(
                const.CONF_POINTS_ADJUST_VALUES, const.DEFAULT_POINTS_ADJUST_VALUES
            ),
        )

        return self.async_show_form(
            step_id=const.CONFIG_FLOW_STEP_RECONFIGURE,
            data_schema=all_settings_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the Options Flow."""
        return ChoreOpsOptionsFlowHandler(config_entry)
