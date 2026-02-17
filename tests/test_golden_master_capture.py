"""Golden Master capture utility for Phase 5 Gamification testing.

This module provides utilities to:
1. Capture the current state of gamification data (badges, achievements, challenges)
2. Save as JSON fixture for regression testing
3. Compare new Engine output against the golden master

Usage:
    # Generate golden master (run once to capture baseline)
    pytest tests/test_golden_master_capture.py::test_capture_gamification_baseline -v

    # Verify Engine produces same output (after Phase 5 implementation)
    pytest tests/test_golden_master_capture.py::test_verify_against_golden_master -v
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from custom_components.choreops import const
from tests.helpers import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# =============================================================================
# CONSTANTS
# =============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN_MASTER_FILE = FIXTURES_DIR / "golden_master_gamification.json"


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def full_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load full scenario with badges, achievements, and challenges."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


# =============================================================================
# CAPTURE UTILITIES
# =============================================================================


def extract_gamification_data(coordinator: Any) -> dict[str, Any]:
    """Extract all gamification-related data from coordinator.

    Returns a structured dict containing:
    - badges_data: All badge definitions
    - achievements_data: All achievement definitions
    - challenges_data: All challenge definitions
    - per_kid_data: For each kid:
        - badge_progress: Progress toward each badge
        - badges_earned: Earned badge records
        - achievement_progress: Progress toward achievements
        - challenge_progress: Progress toward challenges
        - chore_stats: Stats that feed into gamification (streaks, totals)

    Args:
        coordinator: The KidsChoresCoordinator instance

    Returns:
        Dict with gamification snapshot
    """
    result: dict[str, Any] = {
        "metadata": {
            "capture_version": "1.0",
            "scenario": "scenario_full.yaml",
            "description": "Golden master for Phase 5 GamificationEngine regression testing",
        },
        "badges_data": {},
        "achievements_data": {},
        "challenges_data": {},
        "per_kid_data": {},
    }

    # Extract badge definitions
    for badge_id, badge_info in coordinator.badges_data.items():
        result["badges_data"][badge_id] = _sanitize_for_json(badge_info)

    # Extract achievement definitions
    for ach_id, ach_info in coordinator.achievements_data.items():
        result["achievements_data"][ach_id] = _sanitize_for_json(ach_info)

    # Extract challenge definitions
    for chal_id, chal_info in coordinator.challenges_data.items():
        result["challenges_data"][chal_id] = _sanitize_for_json(chal_info)

    # Extract per-kid gamification state
    for kid_id, kid_info in coordinator.kids_data.items():
        kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")

        kid_gamification: dict[str, Any] = {
            "kid_name": kid_name,
            "badge_progress": {},
            "badges_earned": {},
            "cumulative_badge_progress": {},
            "chore_stats": {},
        }

        # Badge progress
        badge_progress = kid_info.get(const.DATA_KID_BADGE_PROGRESS, {})
        for badge_id, progress in badge_progress.items():
            kid_gamification["badge_progress"][badge_id] = _sanitize_for_json(progress)

        # Badges earned
        badges_earned = kid_info.get(const.DATA_KID_BADGES_EARNED, {})
        for badge_id, earned_data in badges_earned.items():
            kid_gamification["badges_earned"][badge_id] = _sanitize_for_json(
                earned_data
            )

        # Cumulative badge progress (for badge tier maintenance)
        cumulative_progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
        kid_gamification["cumulative_badge_progress"] = _sanitize_for_json(
            cumulative_progress
        )

        # Chore stats (for achievement/challenge checking)
        # Extract per-chore data for this kid
        chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
        for chore_id, chore_info in chore_data.items():
            # Extract all chore info - sanitize to make JSON-safe
            kid_gamification["chore_stats"][chore_id] = _sanitize_for_json(chore_info)

        # Extract aggregate chore stats from chore_periods.all_time (v43+)
        chore_periods = kid_info.get(const.DATA_KID_CHORE_PERIODS, {})
        all_time_stats = chore_periods.get(
            const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
        )
        kid_gamification["aggregate_chore_stats"] = _sanitize_for_json(all_time_stats)

        result["per_kid_data"][kid_id] = kid_gamification

    return result


def _sanitize_for_json(data: Any) -> Any:
    """Convert data to JSON-serializable format.

    Handles:
    - datetime objects → ISO strings
    - sets → lists
    - non-serializable objects → str representation
    """
    if isinstance(data, dict):
        return {k: _sanitize_for_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_sanitize_for_json(item) for item in data]
    if isinstance(data, set):
        return sorted([_sanitize_for_json(item) for item in data])
    if hasattr(data, "isoformat"):
        return data.isoformat()
    try:
        json.dumps(data)
        return data
    except (TypeError, ValueError):
        return str(data)


def save_golden_master(data: dict[str, Any], filepath: Path | None = None) -> Path:
    """Save golden master data to JSON file.

    Args:
        data: The gamification data to save
        filepath: Optional custom path (defaults to GOLDEN_MASTER_FILE)

    Returns:
        Path to saved file
    """
    filepath = filepath or GOLDEN_MASTER_FILE
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with filepath.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)

    return filepath


def load_golden_master(filepath: Path | None = None) -> dict[str, Any]:
    """Load golden master data from JSON file.

    Args:
        filepath: Optional custom path (defaults to GOLDEN_MASTER_FILE)

    Returns:
        The loaded gamification data

    Raises:
        FileNotFoundError: If golden master doesn't exist
    """
    filepath = filepath or GOLDEN_MASTER_FILE

    if not filepath.exists():
        raise FileNotFoundError(
            f"Golden master not found at {filepath}. "
            "Run test_capture_gamification_baseline first."
        )

    with filepath.open("r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# TEST: CAPTURE BASELINE (Run once to generate golden master)
# =============================================================================


class TestGoldenMasterCapture:
    """Tests for capturing and using golden master gamification data."""

    @pytest.mark.asyncio
    async def test_capture_gamification_baseline(
        self,
        hass: HomeAssistant,
        full_scenario: SetupResult,
    ) -> None:
        """Capture baseline gamification state from scenario_full.

        This test:
        1. Loads scenario_full with badges, achievements, challenges
        2. Runs several claim/approve cycles to generate progress
        3. Captures the gamification state
        4. Saves as golden master JSON

        Run this ONCE to establish baseline, then use verify test.
        """
        coordinator = full_scenario.coordinator

        # Get kid and chore IDs for workflow
        zoe_id = full_scenario.kid_ids["Zoë"]
        max_id = full_scenario.kid_ids["Max!"]

        # Find some chores to complete
        chore_ids = list(coordinator.chores_data.keys())[:5]

        # Run claim/approve cycles to generate gamification progress
        for i, chore_id in enumerate(chore_ids):
            # Alternate between kids
            kid_id = zoe_id if i % 2 == 0 else max_id
            kid_name = "Zoë" if i % 2 == 0 else "Max!"

            # Check if kid is assigned to this chore
            assigned = coordinator.chores_data[chore_id].get(
                const.DATA_CHORE_ASSIGNED_KIDS, []
            )
            if kid_id not in assigned:
                continue

            # Claim the chore
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, kid_name)

            # Approve the chore
            await coordinator.chore_manager.approve_chore(
                "TestParent", kid_id, chore_id
            )

        # Now capture the gamification state
        gamification_data = extract_gamification_data(coordinator)

        # Verify we captured something meaningful
        assert gamification_data["badges_data"], "Should have badge definitions"
        assert gamification_data["achievements_data"], (
            "Should have achievement definitions"
        )
        assert gamification_data["challenges_data"], "Should have challenge definitions"
        assert gamification_data["per_kid_data"], "Should have per-kid data"

        # Check at least one kid has some progress (chore in approved state or points)
        has_progress = False
        for kid_id, kid_data in gamification_data["per_kid_data"].items():
            # Check chore_stats for any chores with "approved" state
            for chore_id, stats in kid_data.get("chore_stats", {}).items():
                if stats.get("state") == "approved" or stats.get("total_points", 0) > 0:
                    has_progress = True
                    break
            # Also check aggregate stats
            agg_stats = kid_data.get("aggregate_chore_stats", {})
            if agg_stats.get("approved_all_time", 0) > 0:
                has_progress = True
            if has_progress:
                break

        assert has_progress, "At least one kid should have chore progress"

        # Save the golden master
        saved_path = save_golden_master(gamification_data)
        assert saved_path.exists(), f"Golden master should be saved at {saved_path}"

        # Print summary for verification
        print(f"\n{'=' * 60}")
        print("GOLDEN MASTER CAPTURED")
        print(f"{'=' * 60}")
        print(f"Saved to: {saved_path}")
        print(f"Badges: {len(gamification_data['badges_data'])}")
        print(f"Achievements: {len(gamification_data['achievements_data'])}")
        print(f"Challenges: {len(gamification_data['challenges_data'])}")
        print(f"Kids: {len(gamification_data['per_kid_data'])}")

        for kid_id, kid_data in gamification_data["per_kid_data"].items():
            kid_name = kid_data["kid_name"]
            progress_count = len(kid_data.get("badge_progress", {}))
            earned_count = len(kid_data.get("badges_earned", {}))
            chores_with_stats = len(
                [
                    s
                    for s in kid_data.get("chore_stats", {}).values()
                    if s.get("state") == "approved" or s.get("total_points", 0) > 0
                ]
            )
            print(
                f"  - {kid_name}: {progress_count} badge progress, "
                f"{earned_count} earned, {chores_with_stats} chores completed"
            )

    @pytest.mark.asyncio
    async def test_verify_golden_master_exists(self) -> None:
        """Verify golden master file exists and is valid.

        Run after test_capture_gamification_baseline to verify the file.
        """
        try:
            data = load_golden_master()
        except FileNotFoundError:
            pytest.skip(
                "Golden master not yet captured. "
                "Run test_capture_gamification_baseline first."
            )

        # Validate structure
        assert "metadata" in data
        assert "badges_data" in data
        assert "achievements_data" in data
        assert "challenges_data" in data
        assert "per_kid_data" in data

        # Validate has content
        assert data["badges_data"], "Should have badge definitions"
        assert data["per_kid_data"], "Should have per-kid data"

        print(f"\n✅ Golden master is valid: {GOLDEN_MASTER_FILE}")

    @pytest.mark.asyncio
    async def test_extract_gamification_structure(
        self,
        hass: HomeAssistant,
        full_scenario: SetupResult,
    ) -> None:
        """Test that extraction produces expected structure.

        This is a quick validation test - doesn't save to file.
        """
        coordinator = full_scenario.coordinator

        data = extract_gamification_data(coordinator)

        # Verify top-level structure
        assert "metadata" in data
        assert "badges_data" in data
        assert "achievements_data" in data
        assert "challenges_data" in data
        assert "per_kid_data" in data

        # Verify badge structure
        for badge_id, badge_info in data["badges_data"].items():
            assert isinstance(badge_id, str)
            assert isinstance(badge_info, dict)

        # Verify kid data structure
        for kid_data in data["per_kid_data"].values():
            assert "kid_name" in kid_data
            assert "badge_progress" in kid_data
            assert "badges_earned" in kid_data
            assert "chore_stats" in kid_data


# =============================================================================
# VERIFICATION UTILITIES (For Phase 5 - placeholder)
# =============================================================================


def compare_gamification_output(
    actual: dict[str, Any],
    expected: dict[str, Any],
    ignore_keys: list[str] | None = None,
) -> list[str]:
    """Compare actual Engine output against golden master.

    Args:
        actual: Output from new GamificationEngine
        expected: Golden master data
        ignore_keys: Keys to ignore in comparison (e.g., timestamps)

    Returns:
        List of differences (empty if identical)
    """
    ignore_keys = ignore_keys or ["last_awarded", "last_awarded_date"]
    differences: list[str] = []

    def compare_dicts(path: str, a: Any, b: Any) -> None:
        if isinstance(a, dict) and isinstance(b, dict):
            all_keys = set(a.keys()) | set(b.keys())
            for key in all_keys:
                if key in ignore_keys:
                    continue
                new_path = f"{path}.{key}" if path else key
                if key not in a:
                    differences.append(f"Missing in actual: {new_path}")
                elif key not in b:
                    differences.append(f"Extra in actual: {new_path}")
                else:
                    compare_dicts(new_path, a[key], b[key])
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                differences.append(
                    f"List length mismatch at {path}: {len(a)} vs {len(b)}"
                )
            else:
                for i, (av, bv) in enumerate(zip(a, b, strict=False)):
                    compare_dicts(f"{path}[{i}]", av, bv)
        elif a != b:
            differences.append(f"Value mismatch at {path}: {a!r} vs {b!r}")

    compare_dicts("", actual, expected)
    return differences
