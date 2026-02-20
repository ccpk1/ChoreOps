# File: coordinator.py
"""Coordinator for the KidsChores integration.

Handles data synchronization, chore claiming and approval, badge tracking,
reward redemption, penalty application, and recurring chore handling.
Manages entities primarily using internal_id for consistency.

Architecture (v0.5.0+):
    - Coordinator = Routing layer (handles persistence, routes to Managers)
    - Managers = Stateful workflows (ChoreManager, EconomyManager, etc.)
    - Engines = Pure logic (ChoreEngine, EconomyEngine, etc.)
"""

import asyncio
from datetime import timedelta
import sys
import time
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const
from .engines.statistics_engine import StatisticsEngine
from .managers import (
    ChoreManager,
    EconomyManager,
    GamificationManager,
    NotificationManager,
    RewardManager,
    StatisticsManager,
    SystemManager,
    UIManager,
    UserManager,
)
from .store import KidsChoresStore
from .type_defs import (
    AchievementsCollection,
    BadgesCollection,
    BonusesCollection,
    ChallengesCollection,
    ChoresCollection,
    KidsCollection,
    ParentData,
    ParentsCollection,
    PenaltiesCollection,
    RewardsCollection,
    UserData,
    UsersCollection,
)

# Type alias for typed config entry access (modern HA pattern)
# Must be defined after imports but before class since it references the class
type KidsChoresConfigEntry = ConfigEntry["KidsChoresDataCoordinator"]


class KidsChoresDataCoordinator(DataUpdateCoordinator):
    """Coordinator for KidsChores integration.

    Manages data primarily using internal_id for entities.

    Architecture (v0.5.0+):
        - Coordinator = Routing layer (calls Managers, handles persistence)
        - Managers = Stateful workflows (ChoreManager, EconomyManager, etc.)
        - Engines = Pure logic (ChoreEngine, EconomyEngine, etc.)
    """

    config_entry: ConfigEntry  # Override base class to enforce non-None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        store: KidsChoresStore,
    ):
        """Initialize the KidsChoresDataCoordinator."""
        update_interval_minutes = config_entry.options.get(
            const.CONF_UPDATE_INTERVAL, const.DEFAULT_UPDATE_INTERVAL
        )

        super().__init__(
            hass,
            const.LOGGER,
            name=f"{const.DOMAIN}{const.COORDINATOR_SUFFIX}",
            update_interval=timedelta(minutes=update_interval_minutes),
        )
        self.config_entry = config_entry
        self.store = store
        self._data: dict[str, Any] = {}

        # Test mode detection for reminder delays and persist debounce
        self._test_mode = "pytest" in sys.modules
        const.LOGGER.debug(
            "Coordinator initialized in %s mode",
            "TEST" if self._test_mode else "PRODUCTION",
        )

        # Debounced persist tracking (Phase 2 optimization)
        # Test mode uses 0 debounce to avoid 5-second waits in async_block_till_done()
        self._persist_task: asyncio.Task | None = None
        self._persist_debounce_seconds = 0 if self._test_mode else 5

        # System manager for reactive entity registry cleanup (v0.5.0+)
        # Listens to DELETED signals, runs startup safety net
        self.system_manager = SystemManager(hass, self)

        # Chore manager for chore workflow orchestration (v0.5.0+)
        # Signal-first: emits to EconomyManager for point transactions
        self.chore_manager = ChoreManager(hass, self)

        # Economy manager for point transactions and ledger (v0.5.0+)
        self.economy_manager = EconomyManager(hass, self)

        # User manager for Kid/Parent CRUD operations (v0.5.0+)
        # Phase 7.3b: Centralized create/update/delete with proper event signaling
        self.user_manager = UserManager(hass, self)

        # Reward manager for reward redemption lifecycle (v0.5.0+)
        # Signal-first: emits to EconomyManager for point withdrawals
        self.reward_manager = RewardManager(hass, self)

        # Gamification manager for badge/achievement/challenge evaluation (v0.5.x+)
        # Uses debounced evaluation triggered by coordinator events
        self.gamification_manager = GamificationManager(hass, self)

        # Statistics engine for unified period-based tracking (v0.5.0+)
        self.stats = StatisticsEngine()

        # Statistics manager for event-driven stats aggregation (v0.5.0+)
        # Listens to POINTS_CHANGED, CHORE_APPROVED, REWARD_APPROVED events
        self.statistics_manager = StatisticsManager(hass, self)

        # UI manager for translation sensors and dashboard features (v0.5.0+)
        # Phase 7.7: Extracted from Coordinator to achieve < 500 line target
        self.ui_manager = UIManager(hass, self)

        # Notification manager for all outgoing notifications (v0.5.0+)
        self.notification_manager = NotificationManager(hass, self)

    # -------------------------------------------------------------------------------------
    # Periodic + First Refresh
    # -------------------------------------------------------------------------------------

    async def _async_update_data(self):
        """Periodic update - emit pulse, managers react.

        Phase 3 Refactor: Instead of calling managers directly, emit a signal.
        Each manager subscribes to PERIODIC_UPDATE and performs its own maintenance.
        This decouples Coordinator from domain-specific logic.
        """
        try:
            # Emit periodic pulse - managers subscribe to perform maintenance:
            # - ChoreManager: check_overdue_chores, check_due_window_transitions, check_due_reminders
            from .helpers.entity_helpers import get_event_signal

            signal = get_event_signal(
                self.config_entry.entry_id, const.SIGNAL_SUFFIX_PERIODIC_UPDATE
            )
            async_dispatcher_send(self.hass, signal, {})

            # Notify entities of changes
            self.async_update_listeners()

            return self._data
        except Exception as err:
            raise UpdateFailed(f"Error updating KidsChores data: {err}") from err

    async def async_config_entry_first_refresh(self):
        """Load from storage and hand off to SystemManager for integrity.

        Baton Start Pattern (v0.5.0+):
        1. Physical Load (Infrastructure responsibility)
        2. Version Check (Read-only, for passing to SystemManager)
        3. BLOCKING Integrity Gate (SystemManager ensures clean data)
        4. Domain Initialization (Managers self-init via DATA_READY cascade)
        5. Finalize Infrastructure (persist result)
        """
        const.LOGGER.debug(
            "DEBUG: Coordinator first refresh - requesting data from storage manager"
        )

        # 1. Physical Load (Infrastructure responsibility)
        stored_data = self.store.data
        const.LOGGER.debug(
            "DEBUG: Coordinator received data from storage manager: %s entities",
            {
                "users": len(stored_data.get(const.DATA_USERS, {})),
                "chores": len(stored_data.get(const.DATA_CHORES, {})),
                "badges": len(stored_data.get(const.DATA_BADGES, {})),
                "schema_version": stored_data.get(const.DATA_META, {}).get(
                    const.DATA_META_SCHEMA_VERSION,
                    stored_data.get(const.DATA_SCHEMA_VERSION, "missing"),
                ),
            },
        )

        # Set data pointer (use stored data or fresh structure from Store)
        self._data = stored_data or self.store.get_default_structure()

        # 2. Version Check (Read-only, for passing to SystemManager)
        meta = self._data.get(const.DATA_META, {})
        current_version = meta.get(
            const.DATA_META_SCHEMA_VERSION,
            self._data.get(const.DATA_SCHEMA_VERSION, const.DEFAULT_ZERO),
        )

        # 3. BLOCKING Integrity Gate (The "Baton Pass")
        # Coordinator: "I have data, but don't know if it's correct for v50.
        # SystemManager, please fix it and don't return until it's safe."
        await self.system_manager.ensure_data_integrity(current_version=current_version)

        # 4. Domain Initialization (Managers self-init via DATA_READY cascade)
        # SystemManager.ensure_data_integrity() emits DATA_READY at the end, triggering:
        # - ChoreManager listens for DATA_READY → recalcs stats → emits CHORES_READY
        # - StatisticsManager listens for CHORES_READY → hydrates cache → emits STATS_READY
        # - GamificationManager listens for STATS_READY → updates badge refs → emits GAMIFICATION_READY
        # Coordinator no longer calls managers directly - cascade handles initialization order

        # Timer registrations moved to SystemManager.async_setup() (Phase 2.5)
        # SystemManager emits MIDNIGHT_ROLLOVER signal, domain managers subscribe:
        # - ChoreManager: process_recurring_chore_resets, check_overdue_chores
        # - UIManager: bump_past_datetime_helpers

        # 5. Finalize Infrastructure (persist result)
        self._persist(immediate=True)  # Startup persist should be immediate
        await super().async_config_entry_first_refresh()

    # -------------------------------------------------------------------------------------
    # Storage
    # -------------------------------------------------------------------------------------

    def _persist(self, immediate: bool = False):
        """Save coordinator data to persistent storage.

        Default behavior is debounced persistence (5-10 second delay) to batch multiple
        updates during approval sessions and reduce SD card wear on embedded devices.

        Args:
            immediate: If True, save immediately without debouncing. Use this for:
                      - Startup/migration persists (data integrity)
                      - Config flow operations (user expects immediate feedback)
                      - Unload operations (must complete before shutdown)
                      If False (default), schedule save with debouncing to batch updates.

        Philosophy:
            - Debounced=True (immediate=False) is the default because:
              1. Approval sessions often involve multiple rapid operations
              2. SD card/flash storage benefits from batched writes
              3. Any pending debounced write completes on next immediate write
              4. HA persists on clean shutdown, so only abrupt crashes lose last 5s
            - Use immediate=True only for critical paths where data integrity
              or user feedback timing is essential
        """
        # Thread safety: Schedule to event loop if called from worker thread
        # This can happen when dispatcher signals are fired from sync contexts
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None or loop != self.hass.loop:
            # Not in event loop thread - schedule to run in event loop
            self.hass.loop.call_soon_threadsafe(self._persist_impl, immediate)
            return

        self._persist_impl(immediate)

    def _persist_impl(self, immediate: bool = False) -> None:
        """Implementation of _persist - must be called from event loop thread."""
        # Treat 0 debounce (test mode) as immediate to avoid task overhead
        effective_immediate = immediate or self._persist_debounce_seconds == 0

        if effective_immediate:
            # Cancel any pending debounced save
            if self._persist_task and not self._persist_task.done():
                self._persist_task.cancel()
                self._persist_task = None

            # Immediate synchronous save
            perf_start = time.perf_counter()
            self.store.set_data(self._data)
            self.hass.add_job(self.store.async_save)
            perf_duration = time.perf_counter() - perf_start
            const.LOGGER.debug(
                "PERF: _persist(immediate=True) took %.3fs (queued async save)",
                perf_duration,
            )
        else:
            # Debounced save - cancel existing task and schedule new one
            if self._persist_task and not self._persist_task.done():
                self._persist_task.cancel()

            self._persist_task = self.hass.async_create_task(
                self._persist_debounced_impl()
            )

    async def _persist_debounced_impl(self):
        """Implementation of debounced persist with delay."""
        try:
            # Wait for debounce period
            await asyncio.sleep(self._persist_debounce_seconds)

            # PERF: Track storage write frequency
            perf_start = time.perf_counter()

            self.store.set_data(self._data)
            await self.store.async_save()

            perf_duration = time.perf_counter() - perf_start
            const.LOGGER.debug(
                "PERF: _persist_debounced_impl() took %.3fs (async save completed)",
                perf_duration,
            )
        except asyncio.CancelledError:
            # Task was cancelled, new save scheduled
            const.LOGGER.debug("Debounced persist cancelled (replaced by new save)")
            raise

    def _persist_and_update(self, immediate: bool = False) -> None:
        """Persist data AND update entity listeners to reflect state changes.

        Use this for ALL workflow operations that change user-visible state.
        Use _persist() alone only for internal bookkeeping (notification metadata,
        system config, cleanup operations).

        Name note: "update" refers to HA entity listener updates, NOT push
        notifications. See NotificationManager for push notification handling.

        Args:
            immediate: If True, persist immediately without debouncing.
                      If False (default), use debounced persistence.
                      See _persist() docstring for immediate=True use cases.

        Example:
            # Workflow operation that changes user-visible state
            async def claim_chore(self, chore_id: str) -> None:
                self._data[DATA_CHORES][chore_id]["state"] = "claimed"
                self.coordinator._persist_and_update()  # ✅ Persist + refresh entities
                self.emit(SIGNAL_SUFFIX_CHORE_CLAIMED, chore_id=chore_id)
        """
        self._persist(immediate=immediate)
        self.hass.loop.call_soon_threadsafe(self.async_update_listeners)

    # -------------------------------------------------------------------------------------
    # Properties for Easy Access
    # -------------------------------------------------------------------------------------

    @property
    def users_data(self) -> UsersCollection:
        """Return canonical users data for schema45+ runtime logic."""
        users = self._data.get(const.DATA_USERS, {})
        if isinstance(users, dict) and users:
            return {
                user_id: cast("UserData", user_data)
                for user_id, user_data in users.items()
                if isinstance(user_data, dict)
            }

        legacy_kids = self._data.get(const.DATA_KIDS, {})
        if not isinstance(legacy_kids, dict):
            return {}
        return {
            kid_id: cast("UserData", kid_data)
            for kid_id, kid_data in legacy_kids.items()
            if isinstance(kid_data, dict)
        }

    @property
    def users_for_management(self) -> UsersCollection:
        """Return records visible in the role-based Manage Users flow.

        Inclusion contract:
        - assignee-only users (`can_be_assigned=true`) are included
        - approver-only users (`can_approve=true`, `can_be_assigned=false`) are included
        - dual-role users are included
        - linked-profile users are included

        Phase 1 lock: this list is authoritative for user-management UX and must
        not be narrowed to a legacy parent-only bucket.
        """
        canonical_users = self._data.get(const.DATA_USERS)
        if isinstance(canonical_users, dict):
            merged_users: dict[str, object] = {
                user_id: dict(user_data)
                for user_id, user_data in canonical_users.items()
                if isinstance(user_data, dict)
            }
        else:
            merged_users = {}

            legacy_kids = self._data.get(const.DATA_KIDS, {})
            if isinstance(legacy_kids, dict):
                for user_id, user_data in legacy_kids.items():
                    if isinstance(user_data, dict):
                        existing_user = merged_users.get(user_id)
                        if isinstance(existing_user, dict):
                            merged_users[user_id] = {**existing_user, **user_data}
                        else:
                            merged_users[user_id] = dict(user_data)

        def _sort_key(item: tuple[str, object]) -> tuple[str, str]:
            user_id, user_data_raw = item
            user_data = user_data_raw if isinstance(user_data_raw, dict) else {}
            user_name = str(user_data.get(const.DATA_USER_NAME, "")).casefold()
            return (user_name, user_id)

        sorted_users: dict[str, object] = dict(
            sorted(merged_users.items(), key=_sort_key)
        )

        return cast("UsersCollection", sorted_users)

    @property
    def kids_data(self) -> KidsCollection:
        """Return kid-compatible data view.

        During schema45 migration window, `users` is canonical while much of
        runtime still consumes `kids_data`.
        """
        return {
            user_id: user_data
            for user_id, user_data in self.users_data.items()
            if isinstance(user_data, dict)
            and user_data.get(const.DATA_USER_CAN_BE_ASSIGNED, False)
        }

    @property
    def parents_data(self) -> ParentsCollection:
        """Return parent-compatible data view.

        Parent role records are derived from canonical `users`.
        """
        users = self.users_data
        if users:
            return {
                user_id: cast("ParentData", user_data)
                for user_id, user_data in users.items()
                if isinstance(user_data, dict)
                and (
                    user_data.get(const.DATA_USER_CAN_APPROVE, False)
                    or user_data.get(const.DATA_USER_CAN_MANAGE, False)
                    or const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT in user_data
                    or const.DATA_PARENT_ASSOCIATED_KIDS in user_data
                    or const.DATA_PARENT_LINKED_PROFILE_ID in user_data
                )
            }

        return {}

    @property
    def chores_data(self) -> ChoresCollection:
        """Return the chores data."""
        return self._data.get(const.DATA_CHORES, {})

    @property
    def badges_data(self) -> BadgesCollection:
        """Return the badges data."""
        return self._data.get(const.DATA_BADGES, {})

    @property
    def rewards_data(self) -> RewardsCollection:
        """Return the rewards data."""
        return self._data.get(const.DATA_REWARDS, {})

    @property
    def penalties_data(self) -> PenaltiesCollection:
        """Return the penalties data."""
        return self._data.get(const.DATA_PENALTIES, {})

    @property
    def achievements_data(self) -> AchievementsCollection:
        """Return the achievements data."""
        return self._data.get(const.DATA_ACHIEVEMENTS, {})

    @property
    def challenges_data(self) -> ChallengesCollection:
        """Return the challenges data."""
        return self._data.get(const.DATA_CHALLENGES, {})

    @property
    def bonuses_data(self) -> BonusesCollection:
        """Return the bonuses data."""
        return self._data.get(const.DATA_BONUSES, {})
