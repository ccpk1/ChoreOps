"""Single-path dashboard builder parity tests for prepared assets."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.choreops.helpers import (
    dashboard_builder as builder,
    dashboard_helpers as dh,
)


def _build_template_assets_with_shared_fragment() -> dict[str, str]:
    return {
        "templates/user-minimal-v1.yaml": (
            "button_card_templates:\n"
            "  << template_shared.row_v1 >>\n"
            "views:\n"
            "- title: << user.name >> Chores\n"
            "  path: << user.slug >>\n"
            "  sections: []\n"
        ),
        "templates/shared/row_v1.yaml": "choreops_chore_row_v1:\n  show_name: true\n",
    }


def _build_template_definition() -> dh.DashboardTemplateDefinition:
    return {
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
        "shared_fragments_required": ["row_v1"],
        "shared_fragments_optional": [],
    }


@pytest.mark.asyncio
async def test_create_dashboard_prepared_assets_match_release_applied_template_output() -> (
    None
):
    """Create path produces identical config for prepared and precomposed assets."""
    template_assets = _build_template_assets_with_shared_fragment()
    template_definition = _build_template_definition()
    composed_template = dh.compile_prepared_template_assets(
        template_assets,
        template_definitions=[template_definition],
    )["templates/user-minimal-v1.yaml"]

    async def run_create(
        *,
        prepared_assets: dict[str, Any] | None,
        fetched_template: str | None,
    ) -> dict[str, Any]:
        saved_configs: list[dict[str, Any]] = []

        async def _capture_save(
            _hass: Any, _url_path: str, config: dict[str, Any]
        ) -> None:
            saved_configs.append(config)

        fake_hass = SimpleNamespace(
            config=SimpleNamespace(recovery_mode=False),
            data={},
        )

        fetch_mock = AsyncMock(return_value=fetched_template)
        if prepared_assets is not None:
            fetch_mock = AsyncMock(
                side_effect=AssertionError(
                    "Prepared assets path should not fetch remote/local template"
                )
            )

        with (
            patch(
                "custom_components.choreops.helpers.dashboard_builder.dt_now_iso",
                return_value="2026-03-05T00:00:00+00:00",
            ),
            patch(
                "custom_components.choreops.helpers.dashboard_builder.normalize_template_id",
                side_effect=lambda template_id, *, admin_template: template_id,
            ),
            patch(
                "custom_components.choreops.helpers.dashboard_builder.get_template_source_path",
                return_value="templates/user-minimal-v1.yaml",
            ),
            patch(
                "custom_components.choreops.helpers.dashboard_builder.async_get_local_dashboard_release_version",
                AsyncMock(return_value="0.0.1-beta.3"),
            ),
            patch(
                "custom_components.choreops.helpers.dashboard_builder.async_check_dashboard_exists",
                AsyncMock(return_value=False),
            ),
            patch(
                "custom_components.choreops.helpers.dashboard_builder._create_dashboard_entry",
                AsyncMock(return_value=None),
            ),
            patch(
                "custom_components.choreops.helpers.dashboard_builder._save_dashboard_config",
                side_effect=_capture_save,
            ),
            patch(
                "custom_components.choreops.helpers.dashboard_builder.fetch_dashboard_template",
                fetch_mock,
            ),
        ):
            await builder.create_choreops_dashboard(
                fake_hass,
                integration_entry_id="entry-123",
                dashboard_name="Chores",
                assignee_names=["Zoe"],
                style="user-minimal-v1",
                include_admin=False,
                prepared_release_assets=prepared_assets,
            )

        assert len(saved_configs) == 1
        return saved_configs[0]

    prepared_output = await run_create(
        prepared_assets={
            "strict_pin": True,
            "template_definitions": [template_definition],
            "template_assets": template_assets,
        },
        fetched_template=None,
    )
    release_applied_output = await run_create(
        prepared_assets=None,
        fetched_template=composed_template,
    )

    assert prepared_output == release_applied_output


@pytest.mark.asyncio
async def test_update_dashboard_prepared_assets_match_release_applied_template_output() -> (
    None
):
    """Update path produces identical config for prepared and precomposed assets."""
    template_assets = _build_template_assets_with_shared_fragment()
    template_definition = _build_template_definition()
    composed_template = dh.compile_prepared_template_assets(
        template_assets,
        template_definitions=[template_definition],
    )["templates/user-minimal-v1.yaml"]

    class _FakeDashboard:
        def __init__(self) -> None:
            self.saved_configs: list[dict[str, Any]] = []

        async def async_load(self, _force: bool) -> dict[str, Any]:
            return {
                "views": [
                    {
                        "title": "Zoe Chores",
                        "path": "zoe",
                        "sections": [],
                    }
                ]
            }

        async def async_save(self, config: dict[str, Any]) -> None:
            self.saved_configs.append(config)

    async def run_update(
        *,
        prepared_assets: dict[str, Any] | None,
        fetched_template: str | None,
    ) -> dict[str, Any]:
        fake_dashboard = _FakeDashboard()
        fake_lovelace_data = SimpleNamespace(dashboards={"kcd-chores": fake_dashboard})
        workspace_path = "/workspaces/choreops"
        fake_hass = SimpleNamespace(
            data={builder.LOVELACE_DATA: fake_lovelace_data},
            config=SimpleNamespace(
                config_dir=workspace_path,
                path=lambda *_args: workspace_path,
            ),
            loop=asyncio.get_running_loop(),
        )

        fetch_mock = AsyncMock(return_value=fetched_template)
        if prepared_assets is not None:
            fetch_mock = AsyncMock(
                side_effect=AssertionError(
                    "Prepared assets path should not fetch remote/local template"
                )
            )

        with (
            patch(
                "custom_components.choreops.helpers.dashboard_builder.dt_now_iso",
                return_value="2026-03-05T00:00:00+00:00",
            ),
            patch(
                "custom_components.choreops.helpers.dashboard_builder.normalize_template_id",
                side_effect=lambda template_id, *, admin_template: template_id,
            ),
            patch(
                "custom_components.choreops.helpers.dashboard_builder.get_template_source_path",
                return_value="templates/user-minimal-v1.yaml",
            ),
            patch(
                "custom_components.choreops.helpers.dashboard_builder.async_get_local_dashboard_release_version",
                AsyncMock(return_value="0.0.1-beta.3"),
            ),
            patch(
                "custom_components.choreops.helpers.dashboard_builder.fetch_dashboard_template",
                fetch_mock,
            ),
        ):
            await builder.update_choreops_dashboard_views(
                fake_hass,
                integration_entry_id="entry-123",
                url_path="kcd-chores",
                assignee_names=["Zoe"],
                template_profile="user-minimal-v1",
                include_admin=False,
                prepared_release_assets=prepared_assets,
            )

        assert len(fake_dashboard.saved_configs) == 1
        return fake_dashboard.saved_configs[0]

    prepared_output = await run_update(
        prepared_assets={
            "strict_pin": True,
            "template_definitions": [template_definition],
            "template_assets": template_assets,
        },
        fetched_template=None,
    )
    release_applied_output = await run_update(
        prepared_assets=None,
        fetched_template=composed_template,
    )

    assert prepared_output == release_applied_output
