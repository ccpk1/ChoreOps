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


def test_replace_managed_dashboard_assets_preserves_shared_markers_in_templates(
    tmp_path: Path,
) -> None:
    """Template source markers are preserved when writing runtime templates."""
    component_root = tmp_path / "custom_components" / "choreops"
    dashboards_root = component_root / "dashboards"
    (dashboards_root / "templates").mkdir(parents=True, exist_ok=True)
    (dashboards_root / "translations").mkdir(parents=True, exist_ok=True)
    (dashboards_root / "preferences").mkdir(parents=True, exist_ok=True)

    payload = _build_prepared_assets()
    payload["template_assets"] = {
        "templates/user-minimal-v1.yaml": "start\n<< template_shared.row_v1 >>\nend\n",
        "templates/shared/row_v1.yaml": "row-content\n",
    }

    dh._replace_managed_dashboard_assets_from_release(
        payload, component_root=component_root
    )

    assert (dashboards_root / "templates" / "user-minimal-v1.yaml").read_text(
        encoding="utf-8"
    ) == "start\n<< template_shared.row_v1 >>\nend\n"
    assert (dashboards_root / "templates" / "shared" / "row_v1.yaml").read_text(
        encoding="utf-8"
    ) == "row-content\n"


def test_replace_managed_dashboard_assets_preserves_nested_shared_markers(
    tmp_path: Path,
) -> None:
    """Nested shared marker ids are preserved in runtime template source."""
    component_root = tmp_path / "custom_components" / "choreops"
    dashboards_root = component_root / "dashboards"
    (dashboards_root / "templates").mkdir(parents=True, exist_ok=True)
    (dashboards_root / "translations").mkdir(parents=True, exist_ok=True)
    (dashboards_root / "preferences").mkdir(parents=True, exist_ok=True)

    payload = _build_prepared_assets()
    payload["template_assets"] = {
        "templates/user-minimal-v1.yaml": (
            "start\n<< template_shared.rows/chore/action_v1 >>\nend\n"
        ),
        "templates/shared/rows/chore/action_v1.yaml": "nested-row-content\n",
    }

    dh._replace_managed_dashboard_assets_from_release(
        payload, component_root=component_root
    )

    assert (dashboards_root / "templates" / "user-minimal-v1.yaml").read_text(
        encoding="utf-8"
    ) == "start\n<< template_shared.rows/chore/action_v1 >>\nend\n"
    assert (
        dashboards_root / "templates" / "shared" / "rows" / "chore" / "action_v1.yaml"
    ).read_text(encoding="utf-8") == "nested-row-content\n"


def test_replace_managed_dashboard_assets_preserves_marker_line_indentation(
    tmp_path: Path,
) -> None:
    """Marker line indentation remains unchanged in persisted template source."""
    component_root = tmp_path / "custom_components" / "choreops"
    dashboards_root = component_root / "dashboards"
    (dashboards_root / "templates").mkdir(parents=True, exist_ok=True)
    (dashboards_root / "translations").mkdir(parents=True, exist_ok=True)
    (dashboards_root / "preferences").mkdir(parents=True, exist_ok=True)

    payload = _build_prepared_assets()
    payload["template_assets"] = {
        "templates/user-minimal-v1.yaml": (
            "button_card_templates:\n  << template_shared.row_v1 >>\nafter: true\n"
        ),
        "templates/shared/row_v1.yaml": "choreops_chore_row_v1:\n  key: value\n",
    }

    dh._replace_managed_dashboard_assets_from_release(
        payload, component_root=component_root
    )

    assert (dashboards_root / "templates" / "user-minimal-v1.yaml").read_text(
        encoding="utf-8"
    ) == ("button_card_templates:\n  << template_shared.row_v1 >>\nafter: true\n")


def test_replace_managed_dashboard_assets_fails_on_missing_shared_fragment(
    tmp_path: Path,
) -> None:
    """Missing shared fragments raise a HomeAssistantError during apply."""
    component_root = tmp_path / "custom_components" / "choreops"
    dashboards_root = component_root / "dashboards"
    (dashboards_root / "templates").mkdir(parents=True, exist_ok=True)
    (dashboards_root / "translations").mkdir(parents=True, exist_ok=True)
    (dashboards_root / "preferences").mkdir(parents=True, exist_ok=True)

    payload = _build_prepared_assets()
    payload["template_assets"] = {
        "templates/user-minimal-v1.yaml": "<< template_shared.missing_v1 >>\n",
    }

    with pytest.raises(HomeAssistantError):
        dh._replace_managed_dashboard_assets_from_release(
            payload,
            component_root=component_root,
        )


def test_replace_managed_dashboard_assets_fails_when_required_contract_fragment_missing(
    tmp_path: Path,
) -> None:
    """Release apply fails when shared contract requires a missing fragment asset."""
    component_root = tmp_path / "custom_components" / "choreops"
    dashboards_root = component_root / "dashboards"
    (dashboards_root / "templates").mkdir(parents=True, exist_ok=True)
    (dashboards_root / "translations").mkdir(parents=True, exist_ok=True)
    (dashboards_root / "preferences").mkdir(parents=True, exist_ok=True)

    payload = _build_prepared_assets()
    payload["template_definitions"] = [
        {
            "template_id": "user-minimal-v1",
            "source_path": "templates/user-minimal-v1.yaml",
            "source_type": "vendored",
            "source_ref": None,
            "audience": "user",
            "lifecycle_state": "active",
            "min_integration_version": "0.5.0",
            "max_integration_version": None,
            "maintainer": "ccpk1",
            "dependencies_required": [],
            "dependencies_recommended": [],
            "shared_contract_version": 1,
            "shared_fragments_required": ["rows/chore/action_v1"],
            "shared_fragments_optional": [],
        }
    ]
    payload["template_assets"] = {
        "templates/user-minimal-v1.yaml": "views: []\n",
    }

    with pytest.raises(HomeAssistantError, match="missing required shared fragment"):
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


@pytest.mark.asyncio
async def test_prepare_release_assets_fetches_required_shared_fragment_closure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release prepare includes required shared fragments from registry contract."""

    class _FakeHass:
        async def async_add_executor_job(self, func, *args):
            return func(*args)

    definitions: list[dh.DashboardTemplateDefinition] = [
        {
            "template_id": "user-chores-v1",
            "source_path": "templates/user-chores-v1.yaml",
            "source_type": "vendored",
            "source_ref": None,
            "audience": "user",
            "lifecycle_state": "active",
            "min_integration_version": "0.5.0",
            "max_integration_version": None,
            "maintainer": "ccpk1",
            "dependencies_required": [],
            "dependencies_recommended": [],
            "shared_contract_version": 1,
            "shared_fragments_required": ["button_card_template_user_chores_row_v1"],
            "shared_fragments_optional": [],
        }
    ]

    fetch_assets_mock = AsyncMock(
        side_effect=[
            {
                "templates/user-chores-v1.yaml": "main",
                "templates/shared/button_card_template_user_chores_row_v1.yaml": "frag",
            },
            {"translations/en_dashboard.json": "{}"},
            {},
        ]
    )

    monkeypatch.setattr(
        dh,
        "fetch_remote_manifest_template_definitions",
        AsyncMock(return_value=definitions),
    )
    monkeypatch.setattr(dh, "_fetch_release_assets_by_path", fetch_assets_mock)
    monkeypatch.setattr(
        "custom_components.choreops.helpers.translation_helpers.get_available_dashboard_languages",
        AsyncMock(return_value=["en"]),
    )
    monkeypatch.setattr(
        "custom_components.choreops.helpers.dashboard_builder.fetch_release_asset_text",
        AsyncMock(return_value='{"schema_version": 1, "templates": []}'),
    )

    prepared = await dh.async_prepare_dashboard_release_assets(
        _FakeHass(),
        release_selection="0.5.4",
        include_prereleases=False,
    )

    assert prepared["template_assets"]["templates/user-chores-v1.yaml"] == "main"
    assert (
        prepared["template_assets"][
            "templates/shared/button_card_template_user_chores_row_v1.yaml"
        ]
        == "frag"
    )
    fetched_template_paths = fetch_assets_mock.await_args_list[0].kwargs["source_paths"]
    assert sorted(fetched_template_paths) == [
        "templates/shared/button_card_template_user_chores_row_v1.yaml",
        "templates/user-chores-v1.yaml",
    ]
