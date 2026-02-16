"""Test config flow error scenarios and edge cases.

Modern test coverage for error handling paths in KidsChores config flow,
converted from legacy test_config_flow_data_recovery.py patterns.
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from tests.helpers import DOMAIN


def create_temp_storage_file(storage_path: Path, content: str | dict[str, Any]) -> None:
    """Create a temporary storage file with given content."""
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, dict):
        storage_path.write_text(json.dumps(content), encoding="utf-8")
    else:
        storage_path.write_text(content, encoding="utf-8")


@pytest.fixture
def mock_storage_dir(tmp_path: Path) -> Path:
    """Create temporary .storage directory structure."""
    storage_dir = tmp_path / ".storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


@pytest.fixture
def storage_file(mock_storage_dir: Path) -> Path:
    """Path to the kidschores_data storage file."""
    return mock_storage_dir / "kidschores_data"


async def test_corrupt_json_validation(
    hass: HomeAssistant, mock_storage_dir: Path, storage_file: Path
) -> None:
    """Test config flow handles corrupt JSON gracefully."""
    # Test corrupt storage file detection
    create_temp_storage_file(storage_file, "{not valid json}")

    with patch.object(
        hass.config,
        "path",
        side_effect=lambda *args: str(mock_storage_dir.parent / Path(*args)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "data_recovery"

        # Try to use current - should abort with corrupt_file
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"backup_selection": "current_active"}
        )
        assert result.get("type") == FlowResultType.ABORT
        assert result.get("reason") == "corrupt_file"


async def test_invalid_data_structure(
    hass: HomeAssistant, mock_storage_dir: Path, storage_file: Path
) -> None:
    """Test config flow handles invalid data structure."""
    # Valid JSON but invalid structure
    invalid_structure = {"not": "kidschores_data"}
    create_temp_storage_file(storage_file, invalid_structure)

    with patch.object(
        hass.config,
        "path",
        side_effect=lambda *args: str(mock_storage_dir.parent / Path(*args)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"backup_selection": "current_active"}
        )
        assert result.get("type") == FlowResultType.ABORT
        assert result.get("reason") == "invalid_structure"


async def test_paste_json_flow_happy_path(
    hass: HomeAssistant, mock_storage_dir: Path
) -> None:
    """Test paste JSON flow works with valid data."""
    valid_data = {
        "version": 1,
        "minor_version": 1,
        "key": "kidschores_data",
        "data": {
            "meta": {"schema_version": 42},
            "kids": {"test_kid": {"name": "Test Kid", "points": 100}},
            "parents": {},
            "chores": {},
            "badges": {},
            "rewards": {},
            "penalties": {},
            "bonuses": {},
            "achievements": {},
            "challenges": {},
        },
    }

    with patch.object(
        hass.config,
        "path",
        side_effect=lambda *args: str(mock_storage_dir.parent / Path(*args)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Choose paste JSON option
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"backup_selection": "paste_json"}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "paste_json_input"

        # Submit valid JSON
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"json_data": json.dumps(valid_data)}
        )
        assert result.get("type") == FlowResultType.CREATE_ENTRY
        assert result.get("title") == "KidsChores"


async def test_paste_json_invalid_json(
    hass: HomeAssistant, mock_storage_dir: Path
) -> None:
    """Test paste JSON flow handles invalid JSON."""
    with patch.object(
        hass.config,
        "path",
        side_effect=lambda *args: str(mock_storage_dir.parent / Path(*args)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"backup_selection": "paste_json"}
        )

        # Submit invalid JSON
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"json_data": "{not valid json}"}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "paste_json_input"
        assert result.get("errors") == {"base": "invalid_json"}


async def test_paste_json_invalid_structure(
    hass: HomeAssistant, mock_storage_dir: Path
) -> None:
    """Test paste JSON flow handles invalid structure."""
    invalid_structure = {"not": "kidschores_data"}

    with patch.object(
        hass.config,
        "path",
        side_effect=lambda *args: str(mock_storage_dir.parent / Path(*args)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"backup_selection": "paste_json"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"json_data": json.dumps(invalid_structure)}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "paste_json_input"
        assert result.get("errors") == {"base": "invalid_structure"}


async def test_empty_input_handling(
    hass: HomeAssistant, mock_storage_dir: Path
) -> None:
    """Test paste JSON flow handles empty input."""
    with patch.object(
        hass.config,
        "path",
        side_effect=lambda *args: str(mock_storage_dir.parent / Path(*args)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"backup_selection": "paste_json"}
        )

        # Submit empty input
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"json_data": ""}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "paste_json_input"
        assert result.get("errors") == {"base": "empty_json"}


async def test_missing_storage_file_handling(
    hass: HomeAssistant, mock_storage_dir: Path
) -> None:
    """Test config flow handles missing storage file gracefully."""
    # No storage file exists - should still show data recovery but with limited options
    with patch.object(
        hass.config,
        "path",
        side_effect=lambda *args: str(mock_storage_dir.parent / Path(*args)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # Should show data recovery step but only with "start_fresh" option available
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "data_recovery"

        # Choose start fresh (should be only option when no storage exists)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"backup_selection": "start_fresh"}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "intro"


async def test_storage_file_detection(
    hass: HomeAssistant, mock_storage_dir: Path, storage_file: Path
) -> None:
    """Test data recovery step appears when storage file exists."""
    valid_storage = {
        "version": 1,
        "minor_version": 1,
        "key": "kidschores_data",
        "data": {"meta": {"schema_version": 42}, "kids": {}},
    }
    create_temp_storage_file(storage_file, valid_storage)

    with patch.object(
        hass.config,
        "path",
        side_effect=lambda *args: str(mock_storage_dir.parent / Path(*args)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # Should show data recovery step when storage exists
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "data_recovery"


async def test_diagnostic_format_handling(
    hass: HomeAssistant, mock_storage_dir: Path
) -> None:
    """Test paste JSON handles diagnostic export format."""
    # Diagnostic format has extra wrapper structure
    diagnostic_data = {
        "home_assistant": {"version": "2023.12.0"},
        "data": {
            "meta": {"schema_version": 42},
            "kids": {"test_kid": {"name": "Test", "points": 50}},
            "parents": {},
            "chores": {},
            "badges": {},
            "rewards": {},
            "penalties": {},
            "bonuses": {},
            "achievements": {},
            "challenges": {},
        },
    }

    with patch.object(
        hass.config,
        "path",
        side_effect=lambda *args: str(mock_storage_dir.parent / Path(*args)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"backup_selection": "paste_json"}
        )

        # Should handle diagnostic format and extract coordinator_data
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"json_data": json.dumps(diagnostic_data)}
        )
        assert result.get("type") == FlowResultType.CREATE_ENTRY
        assert result.get("title") == "KidsChores"
