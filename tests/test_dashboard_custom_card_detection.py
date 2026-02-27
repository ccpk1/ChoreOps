"""Tests for dashboard custom card detection fallbacks."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from custom_components.choreops.helpers import dashboard_helpers as dh

if TYPE_CHECKING:
    from pathlib import Path


class _DummyHass:
    """Minimal hass-like object for helper tests."""

    def __init__(self, root_path: Path, data: dict[str, Any]) -> None:
        self._root_path = root_path
        self.data = data
        self.config = SimpleNamespace(path=self._path)

    def _path(self, relative_path: str) -> str:
        return str(self._root_path / relative_path)

    async def async_add_executor_job(self, func: Any, *args: Any) -> Any:
        return func(*args)


@pytest.mark.asyncio
async def test_check_custom_cards_installed_uses_filesystem_fallback(
    tmp_path: Path,
) -> None:
    """Filesystem fallback detects cards when lovelace resources are empty."""
    card_dir = tmp_path / "www" / "community" / "lovelace-mushroom"
    card_dir.mkdir(parents=True)
    (card_dir / "mushroom.js").write_text("// test", encoding="utf-8")

    hass = _DummyHass(tmp_path, data={})

    status = await dh.check_custom_cards_installed(hass)

    assert status["mushroom"] is True


@pytest.mark.asyncio
async def test_dependency_id_check_uses_filesystem_fallback(
    tmp_path: Path,
) -> None:
    """Dependency checker recognizes YAML-mode filesystem-installed cards."""
    card_dir = tmp_path / "www" / "community" / "auto-entities"
    card_dir.mkdir(parents=True)
    (card_dir / "auto-entities.js").write_text("// test", encoding="utf-8")

    hass = _DummyHass(tmp_path, data={})

    status = await dh.check_dashboard_dependency_ids_installed(
        hass,
        {"ha-card:auto-entities"},
    )

    assert status["ha-card:auto-entities"] is True
