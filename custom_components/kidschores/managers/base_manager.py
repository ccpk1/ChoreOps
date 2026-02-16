"""Base manager class for KidsChores managers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .. import const
from ..helpers.entity_helpers import get_event_signal

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from ..coordinator import KidsChoresDataCoordinator


class BaseManager(ABC):
    """Base class for all KidsChores managers with scoped event support.

    Provides:
    - Instance-scoped event emitting (emit)
    - Instance-scoped event listening (listen)
    - Automatic cleanup via coordinator's config_entry.async_on_unload

    Data Persistence:
    - Use coordinator._persist_and_update() for user-visible state changes
      (workflow operations: claim, approve, timer-triggered state transitions)
    - Use coordinator._persist() alone for internal bookkeeping
      (notification metadata, system config cleanup)

    Subclasses must implement:
    - async_setup(): Subscribe to events, initialize state
    """

    def __init__(
        self, hass: HomeAssistant, coordinator: KidsChoresDataCoordinator
    ) -> None:
        """Initialize manager.

        Args:
            hass: Home Assistant instance
            coordinator: Parent coordinator managing this integration instance
        """
        self.hass = hass
        self.coordinator = coordinator
        self.entry_id = coordinator.config_entry.entry_id

    def emit(self, suffix: str, **payload: Any) -> None:
        """Emit instance-scoped event to other managers.

        Args:
            suffix: Signal suffix constant (e.g., const.SIGNAL_SUFFIX_POINTS_CHANGED)
            **payload: Event data dict passed to listeners (must be JSON-serializable)

        Example:
            self.emit(
                const.SIGNAL_SUFFIX_POINTS_CHANGED,
                kid_id=kid_id,
                old_balance=50.0,
                new_balance=60.0,
                delta=10.0,
                source="chore_approval"
            )
        """
        signal = get_event_signal(self.entry_id, suffix)
        const.LOGGER.debug(
            "Emitting event '%s' for instance %s with payload keys: %s",
            suffix,
            self.entry_id,
            list(payload.keys()),
        )
        # Pass payload as single dict argument (dispatcher only supports *args)
        async_dispatcher_send(self.hass, signal, payload)

    def listen(self, suffix: str, callback: Callable[..., Any]) -> None:
        """Subscribe to instance-scoped event with automatic cleanup.

        The subscription is automatically cleaned up when the config entry is unloaded.
        Supports both sync and async callbacks - HA dispatcher handles async via
        async_run_hass_job().

        Args:
            suffix: Signal suffix constant to listen for
            callback: Function called when event fires (receives payload dict as arg)
                      Can be sync (returns None) or async (returns Coroutine)

        Example:
            def _on_points_changed(self, payload: dict[str, Any]) -> None:
                kid_id = payload["kid_id"]
                new_balance = payload["new_balance"]
                self.recalculate_badges(kid_id)

            # In async_setup():
            self.listen(const.SIGNAL_SUFFIX_POINTS_CHANGED, self._on_points_changed)
        """
        signal = get_event_signal(self.entry_id, suffix)
        unsub = async_dispatcher_connect(self.hass, signal, callback)
        self.coordinator.config_entry.async_on_unload(unsub)
        const.LOGGER.debug(
            "Manager %s listening to event '%s' for instance %s",
            self.__class__.__name__,
            suffix,
            self.entry_id,
        )

    @abstractmethod
    async def async_setup(self) -> None:
        """Set up the manager (subscribe to events, initialize state).

        Called once during coordinator initialization.
        Subclasses should subscribe to events here using self.listen().
        """
