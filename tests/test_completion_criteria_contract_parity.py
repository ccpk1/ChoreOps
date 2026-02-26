"""Contract parity tests for completion criteria enums.

Guards against drift between:
- `const.COMPLETION_CRITERIA_OPTIONS` (single source)
- service validators in `services.py`
- service selector docs in `services.yaml` for create only
- translation options map in `translations/en.json`

Update service intentionally excludes `completion_criteria` for now.
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


def test_completion_criteria_enum_parity() -> None:
    """Completion criteria options stay aligned across contracts and docs."""
    expected_values = [option["value"] for option in const.COMPLETION_CRITERIA_OPTIONS]

    assert expected_values == services._COMPLETION_CRITERIA_VALUES

    services_yaml_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "choreops"
        / "services.yaml"
    )
    with services_yaml_path.open(encoding="utf-8") as file_handle:
        services_yaml = yaml.safe_load(file_handle)

    create_options = services_yaml["create_chore"]["fields"]["completion_criteria"][
        "selector"
    ]["select"]["options"]
    assert create_options == expected_values

    update_fields = services_yaml["update_chore"]["fields"]
    assert "completion_criteria" not in update_fields

    translations_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "choreops"
        / "translations"
        / "en.json"
    )
    with translations_path.open(encoding="utf-8") as file_handle:
        translations = json.load(file_handle)

    completion_map = _find_nested_mapping(translations, "completion_criteria")
    options_map = completion_map.get("options")
    assert isinstance(options_map, dict)
    assert set(options_map.keys()) == set(expected_values)
