"""Contract parity tests for overdue handling enums.

Guards against drift between:
- `const.OVERDUE_HANDLING_TYPE_OPTIONS` (single source)
- service validators in `services.py`
- service selector docs in `services.yaml` (create/update chore)
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


def test_overdue_handling_enum_parity() -> None:
    """Overdue handling options stay aligned across contracts and docs."""
    expected_values = [
        option["value"] for option in const.OVERDUE_HANDLING_TYPE_OPTIONS
    ]

    assert set(services._OVERDUE_HANDLING_VALUES) == set(expected_values)

    services_yaml_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "choreops"
        / "services.yaml"
    )
    with services_yaml_path.open(encoding="utf-8") as file_handle:
        services_yaml = yaml.safe_load(file_handle)

    create_options = services_yaml["create_chore"]["fields"]["overdue_handling"][
        "selector"
    ]["select"]["options"]
    update_options = services_yaml["update_chore"]["fields"]["overdue_handling"][
        "selector"
    ]["select"]["options"]

    assert set(create_options) == set(expected_values)
    assert set(update_options) == set(expected_values)

    translations_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "choreops"
        / "translations"
        / "en.json"
    )
    with translations_path.open(encoding="utf-8") as file_handle:
        translations = json.load(file_handle)

    overdue_map = _find_nested_mapping(translations, "overdue_handling_type")
    options_map = overdue_map.get("options")
    assert isinstance(options_map, dict)
    assert set(options_map.keys()) == set(expected_values)
