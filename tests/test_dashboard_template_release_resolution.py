"""Tests for dashboard release resolution and compatibility filtering."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from packaging.version import Version
import pytest

from custom_components.choreops.helpers import dashboard_builder as builder


@pytest.mark.asyncio
async def test_discover_compatible_release_tags_filters_and_sorts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release discovery filters malformed/incompatible tags and sorts newest-first."""

    async def _mock_fetch_releases(_hass: Any) -> list[dict[str, Any]]:
        return [
            {"tag_name": "KCD_v0.5.4"},
            {"tag_name": "v0.5.6-beta1"},
            {"tag_name": "v0.5.5"},
            {"tag_name": "KCD_v0.5.0_beta3"},
            {"tag_name": "KCD_v0.5.5_beta1"},
            {"tag_name": "invalid_tag"},
            {"tag_name": "KCD_v0.4.9"},
        ]

    async def _mock_integration_version(_hass: Any) -> Version:
        return Version("0.5.2")

    monkeypatch.setattr(builder, "_fetch_dashboard_releases", _mock_fetch_releases)
    monkeypatch.setattr(
        builder,
        "_get_installed_integration_version",
        _mock_integration_version,
    )

    tags = await builder.discover_compatible_dashboard_release_tags(MagicMock())

    assert tags == [
        "v0.5.6-beta1",
        "v0.5.5",
        "KCD_v0.5.5_beta1",
        "KCD_v0.5.4",
        "KCD_v0.5.0_beta3",
    ]


@pytest.mark.asyncio
async def test_resolve_dashboard_release_selection_pinned_and_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pinned release resolves when available and falls back when unavailable."""

    async def _mock_discover(_hass: Any, include_prereleases: bool = True) -> list[str]:
        _ = include_prereleases
        return ["KCD_v0.5.4", "KCD_v0.5.3"]

    monkeypatch.setattr(
        builder,
        "discover_compatible_dashboard_release_tags",
        _mock_discover,
    )

    selected = await builder.resolve_dashboard_release_selection(
        MagicMock(),
        pinned_release_tag="KCD_v0.5.4",
    )
    assert selected.selected_tag == "KCD_v0.5.4"
    assert selected.reason == "pinned_release"

    fallback = await builder.resolve_dashboard_release_selection(
        MagicMock(),
        pinned_release_tag="KCD_v9.9.9",
    )
    assert fallback.selected_tag == "KCD_v0.5.4"
    assert fallback.reason == "pinned_unavailable_fallback_latest"


@pytest.mark.asyncio
async def test_resolve_dashboard_release_selection_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release resolver degrades gracefully when discovery fails."""

    async def _mock_discover(_hass: Any, include_prereleases: bool = True) -> list[str]:
        _ = include_prereleases
        raise TimeoutError

    monkeypatch.setattr(
        builder,
        "discover_compatible_dashboard_release_tags",
        _mock_discover,
    )

    result = await builder.resolve_dashboard_release_selection(MagicMock())

    assert result.selected_tag is None
    assert result.fallback_tag is None
    assert result.reason == "release_service_unavailable"
