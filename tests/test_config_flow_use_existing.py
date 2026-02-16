"""Test config flow with existing kidschores_data file."""

# pylint: disable=redefined-outer-name  # Pytest fixture pattern

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from tests.helpers import (
    CFOF_DATA_RECOVERY_INPUT_SELECTION,
    CONFIG_FLOW_STEP_DATA_RECOVERY,
    DOMAIN,
)


@pytest.fixture
def mock_setup_entry() -> AsyncMock:
    """Mock async_setup_entry."""
    with patch(
        "custom_components.kidschores.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


async def test_config_flow_use_existing_v40beta1(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test config flow with existing v40beta1 kidschores_data file (already wrapped format)."""
    # Place v40beta1 sample as active kidschores_data file (already has wrapper)
    storage_path = Path(hass.config.path(".storage", "kidschores_data"))
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    # Load v40beta1 sample (already in wrapped format)
    sample_path = (
        Path(__file__).parent / "migration_samples" / "kidschores_data_40beta1"
    )
    v40beta1_data = json.loads(sample_path.read_text())

    # Write wrapped data (v40beta1 already has wrapper)
    await hass.async_add_executor_job(
        storage_path.write_text,
        json.dumps(v40beta1_data, indent=2),
        "utf-8",
    )

    # Start config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == CONFIG_FLOW_STEP_DATA_RECOVERY

    # Select "use current active file"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CFOF_DATA_RECOVERY_INPUT_SELECTION: "current_active",
        },
    )

    # Should create entry successfully
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "KidsChores"
    assert result["data"] == {}

    # Verify setup was called
    assert len(mock_setup_entry.mock_calls) == 1

    # Verify storage file still has proper version wrapper (unchanged)
    stored_data_str = await hass.async_add_executor_job(
        storage_path.read_text,
        "utf-8",
    )
    stored_data = json.loads(stored_data_str)
    assert "version" in stored_data
    assert "data" in stored_data
    assert stored_data["version"] == 1

    # Verify the actual data is preserved
    assert "kids" in stored_data["data"]
    assert len(stored_data["data"]["kids"]) > 0


async def test_config_flow_use_existing_v30(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test config flow with existing v30 kidschores_data file (raw format with legacy schema)."""
    # Place v30 sample as active kidschores_data file (raw format, no version wrapper)
    storage_path = Path(hass.config.path(".storage", "kidschores_data"))
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    # Load v30 sample (raw data format with storage_version: 0)
    sample_path = Path(__file__).parent / "migration_samples" / "kidschores_data_30"
    v30_data = json.loads(sample_path.read_text())

    # Write raw data (no version wrapper) - simulates old installation
    await hass.async_add_executor_job(
        storage_path.write_text,
        json.dumps(v30_data, indent=2),
        "utf-8",
    )

    # Start config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == CONFIG_FLOW_STEP_DATA_RECOVERY

    # Select "use current active file"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CFOF_DATA_RECOVERY_INPUT_SELECTION: "current_active",
        },
    )

    # Should create entry successfully
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "KidsChores"
    assert result["data"] == {}

    # Verify setup was called
    assert len(mock_setup_entry.mock_calls) == 1

    # Verify storage file now has proper version wrapper
    stored_data_str = await hass.async_add_executor_job(
        storage_path.read_text,
        "utf-8",
    )
    stored_data = json.loads(stored_data_str)
    assert "version" in stored_data
    assert "data" in stored_data
    assert stored_data["version"] == 1


async def test_config_flow_use_existing_already_wrapped(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test config flow with existing file that already has version wrapper."""
    # Place file with proper HA storage format
    storage_path = Path(hass.config.path(".storage", "kidschores_data"))
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    # Load v40beta1 sample (already in wrapped format)
    sample_path = (
        Path(__file__).parent / "migration_samples" / "kidschores_data_40beta1"
    )
    wrapped_data = json.loads(sample_path.read_text())

    # Write the already-wrapped data
    await hass.async_add_executor_job(
        storage_path.write_text,
        json.dumps(wrapped_data, indent=2),
        "utf-8",
    )

    # Start config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == CONFIG_FLOW_STEP_DATA_RECOVERY

    # Select "use current active file"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CFOF_DATA_RECOVERY_INPUT_SELECTION: "current_active",
        },
    )

    # Should create entry successfully
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "KidsChores"
    assert result["data"] == {}

    # Verify setup was called
    assert len(mock_setup_entry.mock_calls) == 1

    # Verify storage file still has proper format (unchanged)
    stored_data_str = await hass.async_add_executor_job(
        storage_path.read_text,
        "utf-8",
    )
    stored_data = json.loads(stored_data_str)
    assert stored_data == wrapped_data
