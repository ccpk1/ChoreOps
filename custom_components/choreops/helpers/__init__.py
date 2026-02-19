# File: helpers/__init__.py
"""Home Assistant-bound helper functions for KidsChores.

This module contains functions that REQUIRE Home Assistant dependencies.
These helpers interact with the HA entity registry, device registry, auth,
and other HA-specific systems.

NOTE: Functions that need `hass` object belong here, NOT in utils/.

Submodules:
    - entity_helpers: Entity registry queries, unique_id parsing, cleanup
    - auth_helpers: User authorization checks
    - device_helpers: DeviceInfo construction
    - flow_helpers: Config/options flow helpers and validators
    - backup_helpers: Backup/restore utilities
    - translation_helpers: Translation file loading and caching

Usage:
    from . import entity_helpers
    from .auth_helpers import is_user_authorized_for_action
    from . import flow_helpers as fh
    from . import translation_helpers as th
"""

from . import (
    auth_helpers,
    backup_helpers,
    device_helpers,
    entity_helpers,
    flow_helpers,
    report_helpers,
    translation_helpers,
)

__all__ = [
    "auth_helpers",
    "backup_helpers",
    "device_helpers",
    "entity_helpers",
    "flow_helpers",
    "report_helpers",
    "translation_helpers",
]
