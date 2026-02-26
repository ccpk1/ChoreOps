"""Contract parity tests for approval reset type enums.

Guards against drift between:
- `const.APPROVAL_RESET_TYPE_OPTIONS` (single source)
- service validators in `services.py`
- service selector docs in `services.yaml`
- translation options map in `translations/en.json`
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from custom_components.choreops import const, services


def _find_nested_mapping(root: dict[str, Any], key: str) -> dict[str, Any]:
    """Find first nested mapping by key in a nested dict/list structure."""
    queue: list[Any] = [root]
    while queue:
        current = queue.pop(0)
        if isinstance(current, dict):
            if key in current and isinstance(current[key], dict):
                return current[key]
            queue.extend(current.values())
        elif isinstance(current, list):
            queue.extend(current)
    raise KeyError(key)


def test_approval_reset_type_enum_parity() -> None:
    """Approval reset options stay aligned across constants, services, docs, and translations."""
    expected_values = [option["value"] for option in const.APPROVAL_RESET_TYPE_OPTIONS]

    # 1) Runtime service validator parity
    assert expected_values == services._APPROVAL_RESET_VALUES

    # 2) Service docs selector parity (create/update chore)
    services_yaml_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "choreops"
        / "services.yaml"
    )
    with services_yaml_path.open(encoding="utf-8") as file_handle:
        services_yaml = yaml.safe_load(file_handle)

    create_options = services_yaml["create_chore"]["fields"]["approval_reset_type"][
        "selector"
    ]["select"]["options"]
    update_options = services_yaml["update_chore"]["fields"]["approval_reset_type"][
        "selector"
    ]["select"]["options"]

    assert create_options == expected_values
    assert update_options == expected_values

    # 3) Translation options map parity
    translations_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "choreops"
        / "translations"
        / "en.json"
    )
    with translations_path.open(encoding="utf-8") as file_handle:
        translations = json.load(file_handle)

    approval_reset_map = _find_nested_mapping(translations, "approval_reset_type")
    options_map = approval_reset_map.get("options")
    assert isinstance(options_map, dict)
    assert list(options_map.keys()) == expected_values
