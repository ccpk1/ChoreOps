"""Contract parity tests for the UI control surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from custom_components.choreops import const, services


def _normalized_schema_keys(schema: Any) -> set[str]:
    """Return normalized voluptuous field keys for one schema."""
    return {str(getattr(key, "schema", key)) for key in schema.schema}


def test_manage_ui_control_contracts_stay_aligned() -> None:
    """Service constants, schema, docs, and translations should not drift."""
    services_yaml_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "choreops"
        / "services.yaml"
    )
    with services_yaml_path.open(encoding="utf-8") as file_handle:
        services_yaml = yaml.safe_load(file_handle)

    translations_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "choreops"
        / "translations"
        / "en.json"
    )
    with translations_path.open(encoding="utf-8") as file_handle:
        translations = json.load(file_handle)

    documented_fields = services_yaml[const.SERVICE_MANAGE_UI_CONTROL]["fields"]
    translated_fields = translations["services"][const.SERVICE_MANAGE_UI_CONTROL][
        "fields"
    ]
    expected_schema_keys = {
        const.SERVICE_FIELD_CONFIG_ENTRY_ID,
        const.SERVICE_FIELD_CONFIG_ENTRY_TITLE,
        const.SERVICE_FIELD_USER_ID,
        const.SERVICE_FIELD_USER_NAME,
        const.SERVICE_FIELD_UI_CONTROL_TARGET,
        const.SERVICE_FIELD_UI_CONTROL_ACTION,
        const.SERVICE_FIELD_UI_CONTROL_KEY,
        const.SERVICE_FIELD_UI_CONTROL_VALUE,
    }

    assert _normalized_schema_keys(services.MANAGE_UI_CONTROL_SCHEMA) == (
        expected_schema_keys
    )
    assert set(documented_fields) == expected_schema_keys
    assert set(translated_fields) == expected_schema_keys
    assert documented_fields[const.SERVICE_FIELD_UI_CONTROL_ACTION]["selector"][
        "select"
    ]["options"] == list(const.UI_CONTROL_ACTIONS)
    assert documented_fields[const.SERVICE_FIELD_UI_CONTROL_TARGET]["selector"][
        "select"
    ]["options"] == list(const.UI_CONTROL_TARGETS)


def test_dashboard_helper_ui_control_attribute_contract_stays_translated() -> None:
    """Dashboard helper should keep the translated `ui_control` attribute label."""
    translations_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "choreops"
        / "translations"
        / "en.json"
    )
    with translations_path.open(encoding="utf-8") as file_handle:
        translations = json.load(file_handle)

    dashboard_helper_attributes = translations["entity"]["sensor"][
        "assignee_dashboard_helper_sensor"
    ]["state_attributes"]

    assert const.ATTR_UI_CONTROL in dashboard_helper_attributes
    assert dashboard_helper_attributes[const.ATTR_UI_CONTROL]["name"] == "UI Control"
