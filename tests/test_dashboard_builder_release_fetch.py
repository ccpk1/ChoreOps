"""Tests for dashboard template fetch fallback behavior."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.choreops.helpers import dashboard_builder as builder


@pytest.mark.asyncio
async def test_fetch_template_uses_fallback_release_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If first release candidate fails, second compatible candidate is used."""

    async def _mock_resolve(
        _hass: Any,
        pinned_release_tag: str | None = None,
        include_prereleases: bool = True,
    ) -> builder.DashboardReleaseSelection:
        _ = pinned_release_tag, include_prereleases
        return builder.DashboardReleaseSelection(
            selected_tag="0.5.4",
            fallback_tag="0.5.3",
            reason="pinned_release",
        )

    async def _mock_remote_fetch(_hass: Any, url: str) -> str:
        if "0.5.4" in url:
            raise builder.HomeAssistantError("404")
        return "remote-fallback-template"

    async def _mock_local_fetch(
        _hass: Any,
        template_id: str,
        source_path: str,
    ) -> str:
        _ = template_id, source_path
        return "local-template"

    monkeypatch.setattr(builder, "resolve_dashboard_release_selection", _mock_resolve)
    monkeypatch.setattr(builder, "_fetch_remote_template", _mock_remote_fetch)
    monkeypatch.setattr(builder, "_fetch_local_template", _mock_local_fetch)

    template = await builder.fetch_dashboard_template(MagicMock(), style="full")

    assert template == "remote-fallback-template"


@pytest.mark.asyncio
async def test_fetch_template_falls_back_to_local_when_remote_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remote release outage falls back to local bundled template."""

    async def _mock_resolve(
        _hass: Any,
        pinned_release_tag: str | None = None,
        include_prereleases: bool = True,
    ) -> builder.DashboardReleaseSelection:
        _ = pinned_release_tag, include_prereleases
        return builder.DashboardReleaseSelection(
            selected_tag=None,
            fallback_tag=None,
            reason="release_service_unavailable",
        )

    async def _mock_local_fetch(
        _hass: Any,
        template_id: str,
        source_path: str,
    ) -> str:
        _ = template_id, source_path
        return "local-template"

    monkeypatch.setattr(builder, "resolve_dashboard_release_selection", _mock_resolve)
    monkeypatch.setattr(builder, "_fetch_local_template", _mock_local_fetch)

    template = await builder.fetch_dashboard_template(MagicMock(), style="minimal")

    assert template == "local-template"


@pytest.mark.asyncio
async def test_fetch_template_raises_when_remote_and_local_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Template fetch raises DashboardTemplateError when all sources fail."""

    async def _mock_resolve(
        _hass: Any,
        pinned_release_tag: str | None = None,
        include_prereleases: bool = True,
    ) -> builder.DashboardReleaseSelection:
        _ = pinned_release_tag, include_prereleases
        return builder.DashboardReleaseSelection(
            selected_tag="0.5.4",
            fallback_tag=None,
            reason="latest_compatible",
        )

    async def _mock_remote_fetch(_hass: Any, url: str) -> str:
        _ = url
        raise builder.HomeAssistantError("404")

    async def _mock_local_fetch(
        _hass: Any,
        template_id: str,
        source_path: str,
    ) -> str:
        _ = template_id, source_path
        raise FileNotFoundError

    monkeypatch.setattr(builder, "resolve_dashboard_release_selection", _mock_resolve)
    monkeypatch.setattr(builder, "_fetch_remote_template", _mock_remote_fetch)
    monkeypatch.setattr(builder, "_fetch_local_template", _mock_local_fetch)

    with pytest.raises(builder.DashboardTemplateError):
        await builder.fetch_dashboard_template(MagicMock(), style="full")
