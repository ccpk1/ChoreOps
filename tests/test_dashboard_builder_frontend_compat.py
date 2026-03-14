"""Compatibility tests for dashboard frontend panel registration."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from custom_components.choreops.helpers import dashboard_builder as builder


def test_register_dashboard_panel_uses_show_in_sidebar_when_supported() -> None:
    """Pass through the new frontend keyword when the API supports it."""
    captured: dict[str, Any] = {}

    def _new_register_panel(
        hass: Any,
        component_name: str,
        sidebar_title: str | None = None,
        sidebar_icon: str | None = None,
        sidebar_default_visible: bool = True,
        frontend_url_path: str | None = None,
        config: dict[str, Any] | None = None,
        require_admin: bool = False,
        *,
        update: bool = False,
        config_panel_domain: str | None = None,
        show_in_sidebar: bool = True,
    ) -> None:
        captured.update(
            {
                "hass": hass,
                "component_name": component_name,
                "sidebar_title": sidebar_title,
                "sidebar_icon": sidebar_icon,
                "sidebar_default_visible": sidebar_default_visible,
                "frontend_url_path": frontend_url_path,
                "config": config,
                "require_admin": require_admin,
                "update": update,
                "config_panel_domain": config_panel_domain,
                "show_in_sidebar": show_in_sidebar,
            }
        )

    panel_kwargs = {
        "frontend_url_path": "kcd-chores",
        "require_admin": True,
        "show_in_sidebar": False,
        "sidebar_title": "Chores",
        "sidebar_icon": "mdi:clipboard-list",
        "config": {"mode": builder.MODE_STORAGE},
        "update": True,
    }

    with patch.object(builder, "async_register_built_in_panel", _new_register_panel):
        builder._register_dashboard_panel(object(), panel_kwargs)

    assert captured["frontend_url_path"] == "kcd-chores"
    assert captured["show_in_sidebar"] is False
    assert captured["sidebar_default_visible"] is True


def test_register_dashboard_panel_maps_sidebar_visibility_for_legacy_api() -> None:
    """Map sidebar visibility to the legacy frontend keyword when needed."""
    captured: dict[str, Any] = {}

    def _legacy_register_panel(
        hass: Any,
        component_name: str,
        sidebar_title: str | None = None,
        sidebar_icon: str | None = None,
        sidebar_default_visible: bool = True,
        frontend_url_path: str | None = None,
        config: dict[str, Any] | None = None,
        require_admin: bool = False,
        *,
        update: bool = False,
        config_panel_domain: str | None = None,
    ) -> None:
        captured.update(
            {
                "hass": hass,
                "component_name": component_name,
                "sidebar_title": sidebar_title,
                "sidebar_icon": sidebar_icon,
                "sidebar_default_visible": sidebar_default_visible,
                "frontend_url_path": frontend_url_path,
                "config": config,
                "require_admin": require_admin,
                "update": update,
                "config_panel_domain": config_panel_domain,
            }
        )

    panel_kwargs = {
        "frontend_url_path": "kcd-chores",
        "require_admin": False,
        "show_in_sidebar": False,
        "sidebar_title": "Chores",
        "sidebar_icon": "mdi:clipboard-list",
        "config": {"mode": builder.MODE_STORAGE},
        "update": False,
    }

    with patch.object(
        builder,
        "async_register_built_in_panel",
        _legacy_register_panel,
    ):
        builder._register_dashboard_panel(object(), panel_kwargs)

    assert captured["frontend_url_path"] == "kcd-chores"
    assert captured["sidebar_default_visible"] is False
