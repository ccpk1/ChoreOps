"""Storage key helpers for entry-scoped persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import const

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


def get_entry_storage_key(entry_id: str) -> str:
    """Return the canonical storage key for a config entry."""
    return f"{const.STORAGE_KEY}_{entry_id}"


def get_entry_storage_key_from_entry(config_entry: ConfigEntry) -> str:
    """Return canonical storage key for a config entry object."""
    return get_entry_storage_key(config_entry.entry_id)
