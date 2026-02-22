"""Base entity classes for ChoreOps integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const
from .coordinator import ChoreOpsDataCoordinator


class ChoreOpsCoordinatorEntity(CoordinatorEntity[ChoreOpsDataCoordinator]):
    """Base entity class for ChoreOps sensors with typed coordinator access.

    This base class provides:
    - Typed coordinator property pattern eliminating duplication across 30+ entity classes
    - Explicit `available` property checking coordinator update success (Platinum requirement)
    - Unavailability logging pattern (`_unavailable_logged`) per HA guidelines
    """

    # Platinum requirement: Track unavailability logging state
    _unavailable_logged: bool = False

    @property
    def coordinator(self) -> ChoreOpsDataCoordinator:
        """Return typed coordinator.

        Uses object.__getattribute__ to access the private _coordinator attribute
        set by the base CoordinatorEntity class, providing strong typing for
        autocomplete and type checking throughout sensor implementations.
        """
        return object.__getattribute__(self, "_coordinator")

    @coordinator.setter
    def coordinator(self, value: ChoreOpsDataCoordinator) -> None:
        """Set coordinator with proper typing.

        Args:
            value: The ChoreOpsDataCoordinator instance to set.
        """
        object.__setattr__(self, "_coordinator", value)

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Checks coordinator's last_update_success status and logs state transitions.
        This follows Home Assistant Platinum quality guidelines for entity availability.
        """
        # Check coordinator update success (base availability)
        coordinator_available = self.coordinator.last_update_success

        if not coordinator_available:
            if not self._unavailable_logged:
                const.LOGGER.info(
                    "Entity %s unavailable: coordinator update failed",
                    self.entity_id,
                )
                self._unavailable_logged = True
            return False

        # Log recovery if previously unavailable
        if self._unavailable_logged:
            const.LOGGER.info("Entity %s available again", self.entity_id)
            self._unavailable_logged = False

        return True
