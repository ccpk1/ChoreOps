"""Test config flow with existing choreops_data file."""

# pylint: disable=redefined-outer-name  # Pytest fixture pattern

from collections.abc import Awaitable, Callable, Generator
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from custom_components.choreops import const, migration_pre_v50 as mp50
from tests.helpers import (
    CFOF_DATA_RECOVERY_INPUT_SELECTION,
    CONFIG_FLOW_STEP_DATA_RECOVERY,
    DOMAIN,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock async_setup_entry."""
    with patch(
        "custom_components.choreops.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def migrate_legacy_payload_to_users() -> Callable[
    [dict[str, object]], Awaitable[dict[str, object]]
]:
    """Return helper that applies schema45 user contract migration to payloads."""

    async def _apply(payload: dict[str, object]) -> dict[str, object]:
        data_payload = payload.get("data") if "data" in payload else payload
        assert isinstance(data_payload, dict)
        coordinator = SimpleNamespace(_data=copy.deepcopy(data_payload))
        await mp50.async_apply_schema45_user_contract(coordinator)
        migrated = coordinator._data
        assert isinstance(migrated, dict)
        return migrated

    return _apply


async def test_config_flow_use_existing_v40beta1(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    migrate_legacy_payload_to_users: Callable[
        [dict[str, object]], Awaitable[dict[str, object]]
    ],
) -> None:
    """Test config flow with existing v40beta1 choreops_data file (already wrapped format)."""
    # Place v40beta1 sample as active choreops_data file (already has wrapper)
    storage_path = Path(hass.config.path(".storage", "choreops_data"))
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
    assert result["title"] == const.CHOREOPS_TITLE
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

    # Verify schema45 users contract from legacy payload via real migration hook
    migrated_data = await migrate_legacy_payload_to_users(stored_data)
    assert const.DATA_USERS in migrated_data
    assert isinstance(migrated_data[const.DATA_USERS], dict)


async def test_config_flow_use_existing_v30(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    migrate_legacy_payload_to_users: Callable[
        [dict[str, object]], Awaitable[dict[str, object]]
    ],
) -> None:
    """Test config flow with existing v30 choreops_data file (raw format with legacy schema)."""
    # Place v30 sample as active choreops_data file (raw format, no version wrapper)
    storage_path = Path(hass.config.path(".storage", "choreops_data"))
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
    assert result["title"] == const.CHOREOPS_TITLE
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

    # Verify schema45 users contract from legacy payload via real migration hook
    migrated_data = await migrate_legacy_payload_to_users(stored_data)
    assert const.DATA_USERS in migrated_data
    assert isinstance(migrated_data[const.DATA_USERS], dict)


async def test_config_flow_use_existing_already_wrapped(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    migrate_legacy_payload_to_users: Callable[
        [dict[str, object]], Awaitable[dict[str, object]]
    ],
) -> None:
    """Test config flow with existing file that already has version wrapper."""
    # Place file with proper HA storage format
    storage_path = Path(hass.config.path(".storage", "choreops_data"))
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
    assert result["title"] == const.CHOREOPS_TITLE
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

    # Verify wrapped legacy payload still migrates cleanly to users contract
    migrated_data = await migrate_legacy_payload_to_users(stored_data)
    assert const.DATA_USERS in migrated_data
