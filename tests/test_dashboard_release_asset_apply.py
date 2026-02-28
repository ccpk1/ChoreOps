"""Tests for applying prepared dashboard release assets to local disk."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.choreops.helpers import dashboard_helpers as dh

if TYPE_CHECKING:
    from pathlib import Path


def _build_prepared_assets() -> dh.DashboardReleaseAssets:
    """Return a minimal prepared release payload for disk apply tests."""
    return {
        "requested_release_selection": "0.5.4",
        "release_ref": "0.5.4",
        "resolution_reason": "explicit_release_selected",
        "execution_source": "remote_release",
        "strict_pin": True,
        "allow_local_fallback": False,
        "manifest_asset": '{"schema_version": 1, "release_version": "0.5.4", "templates": []}',
        "template_definitions": [],
        "template_assets": {
            "templates/user-minimal-v1.yaml": "views: []\n",
        },
        "translation_assets": {
            "translations/en_dashboard.json": '{"hello": "world"}',
        },
        "preference_assets": {
            "preferences/user-minimal-v1.md": "# Preferences\n",
        },
    }


def test_replace_managed_dashboard_assets_overwrites_dashboard_folders(
    tmp_path: Path,
) -> None:
    """Applying release assets replaces managed dashboard content on disk."""
    component_root = tmp_path / "custom_components" / "choreops"
    dashboards_root = component_root / "dashboards"
    (dashboards_root / "templates").mkdir(parents=True, exist_ok=True)
    (dashboards_root / "translations").mkdir(parents=True, exist_ok=True)
    (dashboards_root / "preferences").mkdir(parents=True, exist_ok=True)

    (dashboards_root / "templates" / "stale.yaml").write_text("old", encoding="utf-8")
    (dashboards_root / "translations" / "stale_dashboard.json").write_text(
        "{}", encoding="utf-8"
    )
    (dashboards_root / "preferences" / "stale.md").write_text("old", encoding="utf-8")

    dh._replace_managed_dashboard_assets_from_release(
        _build_prepared_assets(),
        component_root=component_root,
    )

    assert not (dashboards_root / "templates" / "stale.yaml").exists()
    assert not (dashboards_root / "translations" / "stale_dashboard.json").exists()
    assert not (dashboards_root / "preferences" / "stale.md").exists()

    assert (dashboards_root / "dashboard_registry.json").read_text(encoding="utf-8")
    assert (dashboards_root / "templates" / "user-minimal-v1.yaml").read_text(
        encoding="utf-8"
    ) == "views: []\n"
    assert (dashboards_root / "translations" / "en_dashboard.json").read_text(
        encoding="utf-8"
    ) == '{"hello": "world"}'
    assert (dashboards_root / "preferences" / "user-minimal-v1.md").read_text(
        encoding="utf-8"
    ) == "# Preferences\n"


def test_replace_managed_dashboard_assets_rejects_path_escape(tmp_path: Path) -> None:
    """Applying release assets fails when an asset path escapes dashboards root."""
    component_root = tmp_path / "custom_components" / "choreops"
    (component_root / "dashboards").mkdir(parents=True, exist_ok=True)

    payload = _build_prepared_assets()
    payload["template_assets"] = {
        "templates/../outside.yaml": "bad",
    }

    with pytest.raises(HomeAssistantError):
        dh._replace_managed_dashboard_assets_from_release(
            payload,
            component_root=component_root,
        )


@pytest.mark.asyncio
async def test_async_apply_release_assets_primes_manifest_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Applying release assets primes manifest cache for same-flow schema builds."""

    class _FakeHass:
        async def async_add_executor_job(self, func, *args):
            return func(*args)

    replace_mock = Mock()
    prime_mock = AsyncMock()
    clear_translation_cache_mock = Mock()

    def _replace_sync(*_args):
        return None

    def _clear_cache_sync() -> None:
        return None

    replace_mock.side_effect = _replace_sync
    clear_translation_cache_mock.side_effect = _clear_cache_sync

    monkeypatch.setattr(
        dh, "_replace_managed_dashboard_assets_from_release", replace_mock
    )
    monkeypatch.setattr(dh, "async_prime_manifest_template_definitions", prime_mock)
    monkeypatch.setattr(
        "custom_components.choreops.helpers.translation_helpers.clear_translation_cache",
        clear_translation_cache_mock,
    )

    await dh.async_apply_prepared_dashboard_release_assets(
        _FakeHass(), _build_prepared_assets()
    )

    assert replace_mock.call_count == 1
    assert prime_mock.await_count == 1
    assert clear_translation_cache_mock.call_count == 1
