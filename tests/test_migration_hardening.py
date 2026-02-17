"""Tests for atomic migration hardening (#243).

Validates the 4-layer fallback cascade that prevents malformed data
after failed migrations:
1. Schema stamp fix (transitional version 42)
2. Atomic rollback (deepcopy + try/except)
3. Nuclear rebuild (build_*() with existing=)
4. Auto-restore from pre-migration backup

All cascade, fallback, and schema-44 logic lives in migration_pre_v50.py
(PreV50Migrator) and will be removed when v50 support is dropped.
"""

import copy
from datetime import UTC, datetime
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.choreops import const, migration_pre_v50 as mp50
from custom_components.choreops.store import KidsChoresStore

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def base_storage_data() -> dict[str, Any]:
    """Pre-migration storage data (schema < 43) with entity data."""
    return {
        const.DATA_META: {
            const.DATA_META_SCHEMA_VERSION: 41,
            const.DATA_META_LAST_MIGRATION_DATE: "2025-01-01T00:00:00+00:00",
            const.DATA_META_MIGRATIONS_APPLIED: [],
        },
        const.DATA_KIDS: {
            "kid-uuid-1": {
                const.DATA_KID_INTERNAL_ID: "kid-uuid-1",
                const.DATA_KID_NAME: "Alice",
                const.DATA_KID_POINTS: 150.0,
                const.DATA_KID_HA_USER_ID: "",
            },
        },
        const.DATA_CHORES: {
            "chore-uuid-1": {
                const.DATA_CHORE_INTERNAL_ID: "chore-uuid-1",
                const.DATA_CHORE_NAME: "Dishes",
                const.DATA_CHORE_DEFAULT_POINTS: 10.0,
                const.DATA_CHORE_ASSIGNED_KIDS: ["kid-uuid-1"],
            },
        },
        const.DATA_REWARDS: {},
        const.DATA_BADGES: {},
        const.DATA_PENALTIES: {},
        const.DATA_BONUSES: {},
        const.DATA_ACHIEVEMENTS: {},
        const.DATA_CHALLENGES: {},
        const.DATA_PARENTS: {},
        "pending_approvals": {"chores": {}, "rewards": {}},
    }


@pytest.fixture
def mock_coordinator(hass: HomeAssistant, base_storage_data: dict[str, Any]):
    """Create a mock coordinator with storage data."""
    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator._data = copy.deepcopy(base_storage_data)
    coordinator.config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        title="KidsChores",
        data={},
        options={},
    )
    coordinator.config_entry.add_to_hass(hass)

    # Mock store
    store = MagicMock(spec=KidsChoresStore)
    store.data = coordinator._data
    store.set_data = MagicMock()
    store.async_save = AsyncMock()
    coordinator.store = store

    return coordinator


@pytest.fixture
def migrator(mock_coordinator):
    """Create PreV50Migrator with mocked coordinator."""
    from custom_components.choreops.migration_pre_v50 import PreV50Migrator

    return PreV50Migrator(mock_coordinator)


@pytest.fixture
def system_manager(hass: HomeAssistant, mock_coordinator):
    """Create SystemManager with mocked coordinator."""
    from custom_components.choreops.managers.system_manager import SystemManager

    return SystemManager(hass, mock_coordinator)


# =============================================================================
# PHASE 1: Schema Stamp Fix
# =============================================================================


class TestSchemaStampFix:
    """Test transitional version stamp prevents premature schema=43."""

    def test_transitional_version_constant(self) -> None:
        """Verify SCHEMA_VERSION_TRANSITIONAL is 42."""
        assert const.SCHEMA_VERSION_TRANSITIONAL == 42

    def test_storage_only_version_constant(self) -> None:
        """Verify SCHEMA_VERSION_STORAGE_ONLY is 43."""
        assert const.SCHEMA_VERSION_STORAGE_ONLY == 43

    def test_beta4_version_constant(self) -> None:
        """Verify SCHEMA_VERSION_BETA4 is 44."""
        assert const.SCHEMA_VERSION_BETA4 == 44

    def test_version_ordering(self) -> None:
        """Verify version constants are in correct order."""
        assert (
            const.SCHEMA_VERSION_TRANSITIONAL
            < const.SCHEMA_VERSION_STORAGE_ONLY
            < const.SCHEMA_VERSION_BETA4
        )


# =============================================================================
# PHASE 2: Atomic Rollback
# =============================================================================


class TestAtomicRollback:
    """Test deepcopy + try/except protects data on migration failure."""

    async def test_migration_failure_restores_snapshot(
        self, hass: HomeAssistant, mock_coordinator
    ) -> None:
        """If run_all_migrations() fails, data reverts to pre-migration state."""
        from custom_components.choreops.migration_pre_v50 import PreV50Migrator

        original_data = copy.deepcopy(mock_coordinator._data)
        migrator = PreV50Migrator(mock_coordinator)

        # Make one migration phase raise an error
        with patch.object(
            migrator, "_migrate_datetime_wrapper", side_effect=RuntimeError("boom")
        ):
            with pytest.raises(RuntimeError, match="boom"):
                await migrator.run_all_migrations()

        # Data should be restored to original (rollback happened)
        assert mock_coordinator._data == original_data

    async def test_migration_success_stamps_schema_43(
        self, hass: HomeAssistant, mock_coordinator
    ) -> None:
        """Successful migration stamps SCHEMA_VERSION_STORAGE_ONLY (43)."""
        from custom_components.choreops.migration_pre_v50 import PreV50Migrator

        migrator = PreV50Migrator(mock_coordinator)

        # Patch all migration methods to no-op (avoid complex setup)
        migration_methods = [
            "_migrate_datetime_wrapper",
            "_migrate_stored_datetimes",
            "_migrate_chore_data",
            "_migrate_kid_data",
            "_migrate_legacy_kid_chore_data_and_streaks",
            "_migrate_badges",
            "_migrate_kid_legacy_badges_to_cumulative_progress",
            "_migrate_kid_legacy_badges_to_badges_earned",
            "_migrate_legacy_point_stats",
            "_migrate_independent_chores",
            "_migrate_per_kid_applicable_days",
            "_migrate_approval_reset_type",
            "_migrate_to_timestamp_tracking",
            "_migrate_reward_data_to_periods",
            "_initialize_data_from_config",
            "_add_chore_optional_fields",
            "_consolidate_point_stats",
            "_remove_legacy_fields",
            "_round_float_precision",
            "_cleanup_kid_chore_data_due_dates_v50",
            "_simplify_notification_config_v50",
            "remove_deprecated_button_entities",
            "remove_deprecated_sensor_entities",
            "_strip_temporal_stats",
            "_migrate_completed_metric",
            "_migrate_badge_award_count_to_periods",
            "_migrate_point_periods_v43",
            "_migrate_chore_periods_v43",
            "_migrate_reward_periods_v43",
            "_migrate_bonus_penalty_periods_v43",
        ]
        for method in migration_methods:
            setattr(migrator, method, MagicMock())

        await migrator.run_all_migrations()

        # Schema should be stamped at 43
        meta = mock_coordinator._data.get(const.DATA_META, {})
        assert meta[const.DATA_META_SCHEMA_VERSION] == const.SCHEMA_VERSION_STORAGE_ONLY

    async def test_failed_migration_does_not_stamp_schema(
        self, hass: HomeAssistant, mock_coordinator
    ) -> None:
        """Failed migration must NOT update schema version."""
        from custom_components.choreops.migration_pre_v50 import PreV50Migrator

        migrator = PreV50Migrator(mock_coordinator)

        # Fail on a late-stage migration
        with patch.object(
            migrator,
            "_migrate_bonus_penalty_periods_v43",
            side_effect=ValueError("late failure"),
        ):
            with pytest.raises(ValueError, match="late failure"):
                await migrator.run_all_migrations()

        # Schema should still be at original version (not 43)
        meta = mock_coordinator._data.get(const.DATA_META, {})
        assert meta[const.DATA_META_SCHEMA_VERSION] != const.SCHEMA_VERSION_STORAGE_ONLY


# =============================================================================
# PHASE 3: Nuclear Rebuild
# =============================================================================


class TestNuclearRebuild:
    """Test rebuild via build_*() preserves user definitions."""

    def test_rebuild_preserves_kid_points(self, migrator) -> None:
        """Nuclear rebuild preserves kid points value."""
        # Set up kid with points
        migrator.coordinator._data[const.DATA_KIDS] = {
            "kid-uuid-1": {
                const.DATA_KID_INTERNAL_ID: "kid-uuid-1",
                const.DATA_KID_NAME: "Alice",
                const.DATA_KID_POINTS: 250.5,
                const.DATA_KID_HA_USER_ID: "",
            },
        }

        result = migrator._attempt_nuclear_rebuild()
        assert result is True

        kid = migrator.coordinator._data[const.DATA_KIDS]["kid-uuid-1"]
        assert kid[const.DATA_KID_NAME] == "Alice"
        assert kid[const.DATA_KID_POINTS] == 250.5

    def test_rebuild_preserves_chore_assigned_kids(self, migrator) -> None:
        """Nuclear rebuild preserves chore assignments."""
        migrator.coordinator._data[const.DATA_CHORES] = {
            "chore-uuid-1": {
                const.DATA_CHORE_INTERNAL_ID: "chore-uuid-1",
                const.DATA_CHORE_NAME: "Dishes",
                const.DATA_CHORE_DEFAULT_POINTS: 10.0,
                const.DATA_CHORE_ASSIGNED_KIDS: ["kid-uuid-1", "kid-uuid-2"],
            },
        }

        result = migrator._attempt_nuclear_rebuild()
        assert result is True

        chore = migrator.coordinator._data[const.DATA_CHORES]["chore-uuid-1"]
        assert chore[const.DATA_CHORE_NAME] == "Dishes"
        assert "kid-uuid-1" in chore[const.DATA_CHORE_ASSIGNED_KIDS]
        assert "kid-uuid-2" in chore[const.DATA_CHORE_ASSIGNED_KIDS]

    def test_rebuild_stamps_schema_43(self, migrator) -> None:
        """Nuclear rebuild stamps SCHEMA_VERSION_STORAGE_ONLY."""
        result = migrator._attempt_nuclear_rebuild()
        assert result is True

        meta = migrator.coordinator._data.get(const.DATA_META, {})
        assert meta[const.DATA_META_SCHEMA_VERSION] == const.SCHEMA_VERSION_STORAGE_ONLY

    def test_rebuild_skips_bad_items(self, migrator) -> None:
        """Nuclear rebuild skips items that fail to build, continues others."""
        migrator.coordinator._data[const.DATA_KIDS] = {
            "good-kid": {
                const.DATA_KID_INTERNAL_ID: "good-kid",
                const.DATA_KID_NAME: "Alice",
                const.DATA_KID_POINTS: 100.0,
            },
            "bad-kid": {
                # Missing required name field — may cause build_kid() to fail
                const.DATA_KID_INTERNAL_ID: "bad-kid",
            },
        }

        # Even if one item fails, rebuild should succeed overall
        result = migrator._attempt_nuclear_rebuild()
        assert result is True

        # Good kid should be preserved
        assert "good-kid" in migrator.coordinator._data[const.DATA_KIDS]

    def test_wipe_all_kc_entities(self, migrator) -> None:
        """Entity wipe removes all KC entities from registry."""
        # Mock entity registry
        mock_entry = MagicMock()
        mock_entry.entity_id = "sensor.kc_alice_points"
        mock_entry2 = MagicMock()
        mock_entry2.entity_id = "button.kc_alice_claim_dishes"

        with (
            patch(
                "custom_components.choreops.migration_pre_v50.er.async_get"
            ) as mock_er_get,
            patch(
                "custom_components.choreops.migration_pre_v50.er.async_entries_for_config_entry",
                return_value=[mock_entry, mock_entry2],
            ),
        ):
            mock_registry = MagicMock()
            mock_er_get.return_value = mock_registry

            count = migrator._wipe_all_kc_entities()

        assert count == 2
        assert mock_registry.async_remove.call_count == 2


# =============================================================================
# PHASE 4: Auto-Restore
# =============================================================================


class TestAutoRestore:
    """Test auto-restore from pre-migration backup."""

    async def test_auto_restore_finds_pre_migration_backup(
        self, hass: HomeAssistant, migrator, tmp_path
    ) -> None:
        """Auto-restore finds and applies pre-migration backup."""
        backup_data = {
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: 41,
            },
            const.DATA_KIDS: {"kid-1": {"name": "Alice"}},
            const.DATA_CHORES: {},
            const.DATA_REWARDS: {},
            const.DATA_BADGES: {},
        }

        # Write a real backup file
        storage_dir = tmp_path / ".storage"
        storage_dir.mkdir()
        backup_filename = "kidschores_data_2025-01-01_00-00-00_pre-migration"
        backup_file = storage_dir / backup_filename
        backup_file.write_text(json.dumps(backup_data))

        # Make hass.config.path() resolve to tmp_path
        hass.config.config_dir = str(tmp_path)

        with (
            patch(
                "custom_components.choreops.migration_pre_v50.bh.discover_backups",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "filename": backup_filename,
                        "tag": const.BACKUP_TAG_PRE_MIGRATION,
                        "timestamp": None,
                        "age_hours": 1.0,
                        "size_bytes": 1000,
                    },
                ],
            ),
            patch(
                "custom_components.choreops.migration_pre_v50.bh.validate_backup_json",
                return_value=True,
            ),
        ):
            result = await migrator._attempt_auto_restore()

        assert result is True
        # Data should be restored to backup content
        assert migrator.coordinator._data == backup_data

    async def test_auto_restore_returns_false_when_no_backup(
        self, hass: HomeAssistant, migrator
    ) -> None:
        """Auto-restore returns False when no pre-migration backup exists."""
        with patch(
            "custom_components.choreops.migration_pre_v50.bh.discover_backups",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await migrator._attempt_auto_restore()

        assert result is False

    async def test_auto_restore_returns_false_on_discover_error(
        self, hass: HomeAssistant, migrator
    ) -> None:
        """Auto-restore returns False if backup discovery fails."""
        with patch(
            "custom_components.choreops.migration_pre_v50.bh.discover_backups",
            new_callable=AsyncMock,
            side_effect=OSError("disk error"),
        ):
            result = await migrator._attempt_auto_restore()

        assert result is False

    async def test_auto_restore_skips_non_pre_migration_backups(
        self, hass: HomeAssistant, migrator
    ) -> None:
        """Auto-restore only uses pre-migration tagged backups."""
        with patch(
            "custom_components.choreops.migration_pre_v50.bh.discover_backups",
            new_callable=AsyncMock,
            return_value=[
                {
                    "filename": "kidschores_data_2025-01-01_00-00-00_recovery",
                    "tag": "recovery",
                    "timestamp": None,
                    "age_hours": 0.5,
                    "size_bytes": 500,
                },
            ],
        ):
            result = await migrator._attempt_auto_restore()

        assert result is False


# =============================================================================
# PHASE 6: Schema 44 Gate
# =============================================================================


class TestSchema44Gate:
    """Test schema 44 migration gate."""

    def test_schema_44_stamps_version(self, migrator) -> None:
        """Schema 44 migration stamps SCHEMA_VERSION_BETA4."""
        # Set up as schema 43 (pre-condition for schema 44)
        migrator.coordinator._data[const.DATA_META] = {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_STORAGE_ONLY,
            const.DATA_META_MIGRATIONS_APPLIED: ["config_to_storage"],
        }

        migrator._migrate_to_schema_44()

        meta = migrator.coordinator._data[const.DATA_META]
        assert meta[const.DATA_META_SCHEMA_VERSION] == const.SCHEMA_VERSION_BETA4

    def test_schema_44_preserves_existing_migrations(self, migrator) -> None:
        """Schema 44 appends to existing migrations list."""
        migrator.coordinator._data[const.DATA_META] = {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_STORAGE_ONLY,
            const.DATA_META_MIGRATIONS_APPLIED: ["config_to_storage", "some_phase"],
        }

        migrator._migrate_to_schema_44()

        meta = migrator.coordinator._data[const.DATA_META]
        applied = meta[const.DATA_META_MIGRATIONS_APPLIED]
        assert "config_to_storage" in applied
        assert "some_phase" in applied
        assert "schema_44_beta4" in applied

    def test_schema_44_removes_legacy_kid_chore_badge_refs(self, migrator) -> None:
        """Schema 44 removes legacy badge_refs from kid chore records."""
        migrator.coordinator._data[const.DATA_META] = {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_STORAGE_ONLY,
            const.DATA_META_MIGRATIONS_APPLIED: ["config_to_storage"],
        }

        kids = migrator.coordinator._data.setdefault(const.DATA_KIDS, {})
        kids["kid-uuid-1"][const.DATA_KID_CHORE_DATA] = {
            "chore-uuid-1": {
                const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                const.DATA_KID_CHORE_DATA_BADGE_REFS: ["badge-a", "badge-b"],
            },
            "chore-uuid-2": {
                const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
            },
        }

        migrator._migrate_to_schema_44()

        kid_chore_data = kids["kid-uuid-1"][const.DATA_KID_CHORE_DATA]
        assert (
            const.DATA_KID_CHORE_DATA_BADGE_REFS not in kid_chore_data["chore-uuid-1"]
        )
        assert (
            const.DATA_KID_CHORE_DATA_BADGE_REFS not in kid_chore_data["chore-uuid-2"]
        )


# =============================================================================
# FULL CASCADE INTEGRATION
# =============================================================================


class TestFullCascade:
    """Test the full fallback cascade in run_full_pre_v50_cascade()."""

    async def test_cascade_normal_migration_success(
        self, hass: HomeAssistant, migrator
    ) -> None:
        """Normal migration succeeds → no fallback needed."""
        with patch.object(
            migrator, "run_all_migrations", new_callable=AsyncMock
        ) as mock_migrate:
            await migrator.run_full_pre_v50_cascade(current_version=41)

        mock_migrate.assert_called_once()

    async def test_cascade_migration_fails_rebuild_succeeds(
        self, hass: HomeAssistant, migrator
    ) -> None:
        """Migration fails → nuclear rebuild succeeds → entities wiped."""
        with (
            patch.object(
                migrator,
                "run_all_migrations",
                new_callable=AsyncMock,
                side_effect=RuntimeError("migration failed"),
            ),
            patch.object(
                migrator,
                "_attempt_nuclear_rebuild",
                return_value=True,
            ) as mock_rebuild,
            patch.object(
                migrator,
                "_wipe_all_kc_entities",
                return_value=5,
            ) as mock_wipe,
        ):
            await migrator.run_full_pre_v50_cascade(current_version=41)

        mock_rebuild.assert_called_once()
        mock_wipe.assert_called_once()

    async def test_cascade_rebuild_fails_restore_succeeds(
        self, hass: HomeAssistant, migrator
    ) -> None:
        """Migration + rebuild fail → auto-restore succeeds."""
        with (
            patch.object(
                migrator,
                "run_all_migrations",
                new_callable=AsyncMock,
                side_effect=RuntimeError("migration failed"),
            ),
            patch.object(
                migrator,
                "_attempt_nuclear_rebuild",
                return_value=False,
            ),
            patch.object(
                migrator,
                "_attempt_auto_restore",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_restore,
        ):
            await migrator.run_full_pre_v50_cascade(current_version=41)

        mock_restore.assert_called_once()

    async def test_cascade_all_fail_raises_config_entry_not_ready(
        self, hass: HomeAssistant, migrator
    ) -> None:
        """All layers fail → ConfigEntryNotReady raised."""
        with (
            patch.object(
                migrator,
                "run_all_migrations",
                new_callable=AsyncMock,
                side_effect=RuntimeError("migration failed"),
            ),
            patch.object(
                migrator,
                "_attempt_nuclear_rebuild",
                return_value=False,
            ),
            patch.object(
                migrator,
                "_attempt_auto_restore",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            with pytest.raises(ConfigEntryNotReady):
                await migrator.run_full_pre_v50_cascade(current_version=41)

    async def test_schema_43_skips_pre_v50_runs_44(
        self, hass: HomeAssistant, migrator
    ) -> None:
        """Schema 43 data skips pre-v50 migrations, runs schema 44 gate."""
        migrator.coordinator._data[const.DATA_META] = {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_STORAGE_ONLY,
            const.DATA_META_MIGRATIONS_APPLIED: [],
        }

        with patch.object(migrator, "_migrate_to_schema_44") as mock_44:
            await migrator.run_full_pre_v50_cascade(
                current_version=const.SCHEMA_VERSION_STORAGE_ONLY
            )

        mock_44.assert_called_once()

    async def test_schema_44_skips_everything(
        self, hass: HomeAssistant, migrator
    ) -> None:
        """Schema 44 data skips all migrations."""
        migrator.coordinator._data[const.DATA_META] = {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
            const.DATA_META_MIGRATIONS_APPLIED: [],
        }

        with (
            patch.object(
                migrator, "_run_migration_with_fallback", new_callable=AsyncMock
            ) as mock_fallback,
            patch.object(migrator, "_migrate_to_schema_44") as mock_44,
        ):
            await migrator.run_full_pre_v50_cascade(
                current_version=const.SCHEMA_VERSION_BETA4
            )

        mock_fallback.assert_not_called()
        mock_44.assert_not_called()

    async def test_premature_stamp_detected_and_downgraded(
        self, hass: HomeAssistant, migrator
    ) -> None:
        """Schema 43 with migration_performed present triggers re-migration (#243).

        The v0.5.0b3 bug stamped schema 43 before structural migrations ran.
        Detection: schema >= 43 AND root-level 'migration_performed' key exists.
        Fix: downgrade to 42 so the structural pipeline re-runs.
        """
        # Simulate premature-stamp state: schema 43 but legacy key still present
        migrator.coordinator._data[const.DATA_META] = {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_STORAGE_ONLY,
            const.DATA_META_MIGRATIONS_APPLIED: ["config_to_storage"],
        }
        migrator.coordinator._data[mp50.LEGACY_MIGRATION_PERFORMED_KEY] = True

        with patch.object(
            migrator,
            "_run_migration_with_fallback",
            new_callable=AsyncMock,
        ) as mock_fallback:
            await migrator.run_full_pre_v50_cascade(
                current_version=const.SCHEMA_VERSION_STORAGE_ONLY
            )

        # Must have triggered fallback cascade (downgraded to 42 < 43)
        mock_fallback.assert_called_once()
        # Meta version should have been downgraded to transitional
        meta = migrator.coordinator._data[const.DATA_META]
        assert meta[const.DATA_META_SCHEMA_VERSION] == const.SCHEMA_VERSION_TRANSITIONAL

    async def test_premature_stamp_schema_44_also_detected(
        self, hass: HomeAssistant, migrator
    ) -> None:
        """Schema 44 with migration_performed also triggers re-migration (#243).

        If schema was prematurely stamped 43 then bumped to 44 by the gate,
        but migration_performed is still present → same fix applies.
        """
        migrator.coordinator._data[const.DATA_META] = {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
            const.DATA_META_MIGRATIONS_APPLIED: [
                "config_to_storage",
                "schema_44_beta4",
            ],
        }
        migrator.coordinator._data[mp50.LEGACY_MIGRATION_PERFORMED_KEY] = True

        with patch.object(
            migrator,
            "_run_migration_with_fallback",
            new_callable=AsyncMock,
        ) as mock_fallback:
            await migrator.run_full_pre_v50_cascade(
                current_version=const.SCHEMA_VERSION_BETA4
            )

        mock_fallback.assert_called_once()

    async def test_ensure_data_integrity_delegates_to_migrator(
        self, hass: HomeAssistant, system_manager
    ) -> None:
        """SystemManager.ensure_data_integrity delegates to PreV50Migrator."""
        with (
            patch(
                "custom_components.choreops.migration_pre_v50.PreV50Migrator.run_full_pre_v50_cascade",
                new_callable=AsyncMock,
            ) as mock_cascade,
            patch.object(
                system_manager, "run_startup_safety_net", new_callable=AsyncMock
            ),
            patch.object(system_manager, "emit"),
        ):
            await system_manager.ensure_data_integrity(current_version=41)

        mock_cascade.assert_called_once_with(41)

    async def test_ensure_data_integrity_skips_migrator_for_v44(
        self, hass: HomeAssistant, system_manager
    ) -> None:
        """SystemManager skips migration for schema 44 without legacy keys."""
        system_manager.coordinator._data[const.DATA_META] = {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
            const.DATA_META_MIGRATIONS_APPLIED: [],
        }
        # No migration_performed key → no need for migration

        with (
            patch(
                "custom_components.choreops.migration_pre_v50.PreV50Migrator",
            ) as mock_migrator_cls,
            patch.object(
                system_manager, "run_startup_safety_net", new_callable=AsyncMock
            ),
            patch.object(system_manager, "emit"),
        ):
            await system_manager.ensure_data_integrity(
                current_version=const.SCHEMA_VERSION_BETA4
            )

        mock_migrator_cls.assert_not_called()


class TestSystemManagerMidnightCatchup:
    """Test startup midnight catch-up reliability behavior."""

    async def test_async_setup_runs_startup_midnight_catchup(
        self, system_manager
    ) -> None:
        """SystemManager async_setup should trigger catch-up check."""
        with (
            patch(
                "custom_components.choreops.managers.system_manager.async_track_time_change"
            ),
            patch.object(
                system_manager,
                "_run_startup_midnight_catchup",
                new_callable=AsyncMock,
            ) as mock_catchup,
        ):
            await system_manager.async_setup()

        mock_catchup.assert_called_once()

    async def test_startup_midnight_catchup_emits_when_stale(
        self, system_manager
    ) -> None:
        """Catch-up emits rollover and stamps meta when last processed is stale."""
        system_manager.coordinator._data[const.DATA_META] = {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
            const.DATA_META_LAST_MIDNIGHT_PROCESSED: "2026-02-10T00:00:00+00:00",
        }

        fixed_now_local = datetime(2026, 2, 11, 12, 0, tzinfo=UTC)
        fixed_now_utc = datetime(2026, 2, 11, 12, 0, tzinfo=UTC)

        with (
            patch(
                "custom_components.choreops.managers.system_manager.dt_util.now",
                return_value=fixed_now_local,
            ),
            patch(
                "custom_components.choreops.managers.system_manager.dt_util.utcnow",
                return_value=fixed_now_utc,
            ),
            patch.object(system_manager, "emit") as mock_emit,
            patch.object(system_manager.coordinator, "_persist") as mock_persist,
        ):
            await system_manager._run_startup_midnight_catchup()

        mock_emit.assert_called_once_with(
            const.SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER,
            catch_up=True,
        )
        mock_persist.assert_called_once()
        assert (
            system_manager.coordinator._data[const.DATA_META][
                const.DATA_META_LAST_MIDNIGHT_PROCESSED
            ]
            == fixed_now_utc.isoformat()
        )

    async def test_startup_midnight_catchup_skips_when_already_processed_today(
        self, system_manager
    ) -> None:
        """Catch-up does not emit when midnight was already processed today."""
        system_manager.coordinator._data[const.DATA_META] = {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
            const.DATA_META_LAST_MIDNIGHT_PROCESSED: "2026-02-11T00:00:00+00:00",
        }

        fixed_now_local = datetime(2026, 2, 11, 12, 0, tzinfo=UTC)

        with (
            patch(
                "custom_components.choreops.managers.system_manager.dt_util.now",
                return_value=fixed_now_local,
            ),
            patch.object(system_manager, "emit") as mock_emit,
            patch.object(system_manager.coordinator, "_persist") as mock_persist,
        ):
            await system_manager._run_startup_midnight_catchup()

        mock_emit.assert_not_called()
        mock_persist.assert_not_called()

    async def test_startup_midnight_catchup_treats_invalid_timestamp_as_stale(
        self, system_manager
    ) -> None:
        """Invalid meta timestamp should safely trigger catch-up."""
        system_manager.coordinator._data[const.DATA_META] = {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
            const.DATA_META_LAST_MIDNIGHT_PROCESSED: "not-a-datetime",
        }

        fixed_now_local = datetime(2026, 2, 11, 12, 0, tzinfo=UTC)
        fixed_now_utc = datetime(2026, 2, 11, 12, 0, tzinfo=UTC)

        with (
            patch(
                "custom_components.choreops.managers.system_manager.dt_util.now",
                return_value=fixed_now_local,
            ),
            patch(
                "custom_components.choreops.managers.system_manager.dt_util.utcnow",
                return_value=fixed_now_utc,
            ),
            patch.object(system_manager, "emit") as mock_emit,
            patch.object(system_manager.coordinator, "_persist") as mock_persist,
        ):
            await system_manager._run_startup_midnight_catchup()

        mock_emit.assert_called_once_with(
            const.SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER,
            catch_up=True,
        )
        mock_persist.assert_called_once()
