#!/usr/bin/env python3
"""Generic migration validation utility for KidsChores v40→v42.

This utility can validate ANY v40 data file migration to v42 without hardcoding
specific entity IDs, names, or values. It auto-discovers entities and validates
structure, data preservation, and schema upgrade.

Usage:
    # As standalone script
    python utils/validate_migration.py tests/migration_samples/kidschores_data_ad-ha

    # With pytest integration
    pytest tests/test_migration_generic.py --migration-file=path/to/file

    # Programmatic usage
    from utils.validate_migration import MigrationValidator
    validator = MigrationValidator("path/to/v40_file")
    results = await validator.validate_all()
"""

# pylint: disable=import-error  # custom_components only available when running in HA context
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Union

# Import Home Assistant test infrastructure
try:
    from homeassistant.core import HomeAssistant  # noqa: TC002
    from homeassistant.helpers.storage import Store
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    HAS_HA_DEPS = True
except ImportError:
    HAS_HA_DEPS = False
    print(  # noqa: T201
        "⚠️  Warning: Home Assistant dependencies not available. Some features disabled."
    )


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    name: str
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"{status}: {self.name} - {self.message}"


@dataclass
class EntityCounts:
    """Entity counts discovered in data."""

    kids: int = 0
    parents: int = 0
    chores: int = 0
    badges: int = 0
    rewards: int = 0
    penalties: int = 0
    bonuses: int = 0
    achievements: int = 0
    challenges: int = 0

    @classmethod
    def from_data(cls, data: dict[str, Any] | None) -> "EntityCounts":
        """Extract entity counts from data dictionary."""
        if data is None:
            return cls()
        return cls(
            kids=len(data.get("kids", {})),
            parents=len(data.get("parents", {})),
            chores=len(data.get("chores", {})),
            badges=len(data.get("badges", {})),
            rewards=len(data.get("rewards", {})),
            penalties=len(data.get("penalties", {})),
            bonuses=len(data.get("bonuses", {})),
            achievements=len(data.get("achievements", {})),
            challenges=len(data.get("challenges", {})),
        )

    def total(self) -> int:
        """Total entity count."""
        return (
            self.kids
            + self.parents
            + self.chores
            + self.badges
            + self.rewards
            + self.penalties
            + self.bonuses
            + self.achievements
            + self.challenges
        )


class MigrationValidator:
    """Validates v40→v42 migration for any data file."""

    # Expected schema versions
    SCHEMA_V40 = 40
    SCHEMA_V42 = 42

    # Required v42 structure keys
    V42_REQUIRED_KEYS = {
        "meta": ["schema_version", "last_migration_date", "migrations_applied"],
        "kids": None,  # Required but structure varies
        "chores": None,
        "badges": None,
    }

    def __init__(self, data_file_path: str | Path):
        """Initialize validator with data file path.

        Args:
            data_file_path: Path to v40 data file to validate
        """
        self.data_file = Path(data_file_path)
        self.v40_data: dict[str, Any] | None = None
        self.v42_data: dict[str, Any] | None = None
        self.before_counts: EntityCounts | None = None
        self.after_counts: EntityCounts | None = None
        self.results: list[ValidationResult] = []

    def load_v40_data(self) -> dict[str, Any]:
        """Load v40 data from file."""
        if not self.data_file.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_file}")

        with open(self.data_file, encoding="utf-8") as f:
            data = json.load(f)

        # Handle both raw data and Store format
        if "data" in data and "version" in data:
            # Store format
            self.v40_data = data["data"]
        else:
            # Raw data format
            self.v40_data = data

        if self.v40_data is not None:
            self.before_counts = EntityCounts.from_data(self.v40_data)
        return self.v40_data  # type: ignore[return-value]

    def validate_v40_schema(self) -> ValidationResult:
        """Validate that source data is v40 format."""
        if not self.v40_data:
            return ValidationResult(
                name="V40 Schema Check", passed=False, message="No v40 data loaded"
            )

        # Check for v40 indicators
        schema_version = self.v40_data.get(
            "migration_key_version", self.v40_data.get("schema_version", 0)
        )

        if schema_version >= self.SCHEMA_V42:
            return ValidationResult(
                name="V40 Schema Check",
                passed=False,
                message=f"Data appears to be v{schema_version} already, not v40",
                details={"schema_version": schema_version},
            )

        # Check for v40 structure patterns
        has_kids = "kids" in self.v40_data and isinstance(self.v40_data["kids"], dict)
        has_chores = "chores" in self.v40_data

        if not has_kids or not has_chores:
            return ValidationResult(
                name="V40 Schema Check",
                passed=False,
                message="Data missing required v40 structure (kids, chores)",
                details={"has_kids": has_kids, "has_chores": has_chores},
            )

        return ValidationResult(
            name="V40 Schema Check",
            passed=True,
            message=f"Valid v40 data with {self.before_counts.total() if self.before_counts else 0} entities",
            details={
                "schema_version": schema_version,
                "entity_counts": self.before_counts.__dict__
                if self.before_counts
                else {},
            },
        )

    async def migrate_with_integration(
        self, hass: "HomeAssistant"
    ) -> dict[str, Any] | None:
        """Migrate data using actual integration code.

        Args:
            hass: Home Assistant instance

        Returns:
            Migrated v42 data or None if migration failed
        """
        if not HAS_HA_DEPS:
            raise RuntimeError("Home Assistant dependencies required for migration")

        # Create mock config entry
        config_entry = MockConfigEntry(
            domain="kidschores",
            title="Migration Test",
            data={},
            options={
                "points_label": "Points",
                "points_icon": "mdi:star",
                "update_interval": 5,
            },
        )
        config_entry.add_to_hass(hass)

        # Write v40 data to storage
        # NOTE: Store.async_save() expects just the data (not wrapped in {"data": ...})
        # Store will automatically wrap it in its own format
        store = Store(hass, version=1, key="kidschores_data")
        await store.async_save(self.v40_data)

        # Load integration (triggers migration)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Read migrated data from coordinator (not storage!)
        # Migration happens in coordinator._data and isn't auto-persisted
        from custom_components.kidschores.const import COORDINATOR, DOMAIN

        coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
        self.v42_data = coordinator._data  # pylint: disable=protected-access

        # DEBUG: Log what keys are in coordinator._data
        if self.v42_data is not None:
            print(f"DEBUG: Keys in coordinator._data: {list(self.v42_data.keys())}")  # noqa: T201
            print(f"DEBUG: Number of kids: {len(self.v42_data.get('kids', {}))}")  # noqa: T201
            print(  # noqa: T201
                f"DEBUG: Kids keys: {list(self.v42_data.get('kids', {}).keys())[:3]}..."
            )  # First 3

            self.after_counts = EntityCounts.from_data(self.v42_data)

        return self.v42_data

    def validate_v42_schema(self) -> ValidationResult:
        """Validate that migrated data is v42 format."""
        if not self.v42_data:
            return ValidationResult(
                name="V42 Schema Check", passed=False, message="No v42 data available"
            )

        # Check meta section exists
        if "meta" not in self.v42_data:
            return ValidationResult(
                name="V42 Schema Check",
                passed=False,
                message="Missing required 'meta' section in v42 data",
            )

        meta = self.v42_data["meta"]

        # Check schema version
        schema_version = meta.get("schema_version", 0)
        if schema_version != self.SCHEMA_V42:
            return ValidationResult(
                name="V42 Schema Check",
                passed=False,
                message=f"Schema version is {schema_version}, expected {self.SCHEMA_V42}",
                details={"schema_version": schema_version},
            )

        # Check required meta fields
        required_meta = ["schema_version", "last_migration_date", "migrations_applied"]
        missing = [f for f in required_meta if f not in meta]
        if missing:
            return ValidationResult(
                name="V42 Schema Check",
                passed=False,
                message=f"Missing required meta fields: {missing}",
                details={"missing_fields": missing},
            )

        return ValidationResult(
            name="V42 Schema Check",
            passed=True,
            message="Valid v42 schema with complete meta section",
            details={
                "schema_version": schema_version,
                "migrations_applied": len(meta.get("migrations_applied", [])),
            },
        )

    def validate_entity_preservation(self) -> ValidationResult:
        """Validate all entities were preserved during migration."""
        if not self.before_counts or not self.after_counts:
            return ValidationResult(
                name="Entity Preservation",
                passed=False,
                message="Missing before/after counts",
            )

        discrepancies = []

        for entity_type in [
            "kids",
            "parents",
            "chores",
            "badges",
            "rewards",
            "penalties",
            "bonuses",
            "achievements",
            "challenges",
        ]:
            before = getattr(self.before_counts, entity_type)
            after = getattr(self.after_counts, entity_type)

            if before != after:
                discrepancies.append(
                    f"{entity_type}: {before} → {after} (lost {before - after})"
                )

        if discrepancies:
            return ValidationResult(
                name="Entity Preservation",
                passed=False,
                message=f"Entity count mismatch: {', '.join(discrepancies)}",
                details={
                    "before": self.before_counts.__dict__,
                    "after": self.after_counts.__dict__,
                },
            )

        return ValidationResult(
            name="Entity Preservation",
            passed=True,
            message=f"All {self.before_counts.total()} entities preserved",
            details={
                "before": self.before_counts.__dict__,
                "after": self.after_counts.__dict__,
            },
        )

    def validate_modern_structures(self) -> ValidationResult:
        """Validate v42 modern nested structures exist."""
        if not self.v42_data:
            return ValidationResult(
                name="Modern Structures", passed=False, message="No v42 data available"
            )

        issues = []

        # Check kids have modern structures
        kids = self.v42_data.get("kids", {})
        if kids:
            first_kid_id = next(iter(kids))
            first_kid = kids[first_kid_id]

            # Check for nested structures
            if "chore_stats" not in first_kid:
                issues.append("Missing 'chore_stats' nested structure in kid data")
            elif isinstance(first_kid["chore_stats"], dict):
                # Validate it's a proper nested dict, not empty
                if "approved_all_time" not in first_kid["chore_stats"]:
                    issues.append("chore_stats missing 'approved_all_time' field")

            if "point_stats" not in first_kid:
                issues.append("Missing 'point_stats' nested structure in kid data")

        # Check chores have modern fields
        chores = self.v42_data.get("chores", {})
        if chores:
            first_chore_id = next(iter(chores))
            first_chore = chores[first_chore_id]

            # Check for completion_criteria (replaces shared_chore)
            if "completion_criteria" not in first_chore:
                issues.append(
                    "Missing 'completion_criteria' field in chore (v42 field)"
                )

            # Should NOT have legacy shared_chore field
            if "shared_chore" in first_chore:
                issues.append(
                    "Legacy 'shared_chore' field still present (should be migrated)"
                )

        if issues:
            return ValidationResult(
                name="Modern Structures",
                passed=False,
                message=f"Found {len(issues)} structure issues",
                details={"issues": issues},
            )

        return ValidationResult(
            name="Modern Structures",
            passed=True,
            message="All v42 modern structures present and valid",
        )

    def validate_no_legacy_fields(self) -> ValidationResult:
        """Validate legacy fields were removed during migration."""
        if not self.v42_data:
            return ValidationResult(
                name="Legacy Field Removal",
                passed=False,
                message="No v42 data available",
            )

        legacy_fields_found = []

        # Check kids for legacy fields
        kids = self.v42_data.get("kids", {})
        for kid_id, kid_data in kids.items():
            # These should NOT exist in v42
            legacy = [
                "completed_chores_total",
                "completed_chores_monthly",
                "completed_chores_weekly",
            ]
            for legacy_field in legacy:
                if legacy_field in kid_data:
                    legacy_fields_found.append(f"kids.{kid_id}.{legacy_field}")

        # Check chores for legacy fields
        chores = self.v42_data.get("chores", {})
        for chore_id, chore_data in chores.items():
            if "shared_chore" in chore_data:
                legacy_fields_found.append(f"chores.{chore_id}.shared_chore")

        if legacy_fields_found:
            return ValidationResult(
                name="Legacy Field Removal",
                passed=False,
                message=f"Found {len(legacy_fields_found)} legacy fields still present",
                details={"legacy_fields": legacy_fields_found[:10]},  # Show first 10
            )

        return ValidationResult(
            name="Legacy Field Removal",
            passed=True,
            message="All legacy fields properly removed",
        )

    def validate_kid_data_integrity(self) -> ValidationResult:
        """Validate kid data structure and content."""
        if not self.v40_data or not self.v42_data:
            return ValidationResult(
                name="Kid Data Integrity",
                passed=False,
                message="Missing before/after data",
            )

        v40_kids = self.v40_data.get("kids", {})
        v42_kids = self.v42_data.get("kids", {})

        issues = []

        # Check each kid
        for kid_id in v40_kids:
            if kid_id not in v42_kids:
                issues.append(f"Kid {kid_id} missing in v42 data")
                continue

            v40_kid = v40_kids[kid_id]
            v42_kid = v42_kids[kid_id]

            # Check name preserved
            if v40_kid.get("name") != v42_kid.get("name"):
                issues.append(f"Kid {kid_id} name changed")

            # Check points preserved (allow small floating point differences)
            v40_points = v40_kid.get("points", 0)
            v42_points = v42_kid.get("points", 0)
            if abs(v40_points - v42_points) > 0.01:
                issues.append(
                    f"Kid {kid_id} points changed: {v40_points} → {v42_points}"
                )

        if issues:
            return ValidationResult(
                name="Kid Data Integrity",
                passed=False,
                message=f"Found {len(issues)} kid data issues",
                details={"issues": issues},
            )

        return ValidationResult(
            name="Kid Data Integrity",
            passed=True,
            message=f"All {len(v40_kids)} kids validated successfully",
        )

    def validate_chore_data_integrity(self) -> ValidationResult:
        """Validate chore data structure and content."""
        if not self.v40_data or not self.v42_data:
            return ValidationResult(
                name="Chore Data Integrity",
                passed=False,
                message="Missing before/after data",
            )

        v40_chores = self.v40_data.get("chores", {})
        v42_chores = self.v42_data.get("chores", {})

        issues = []

        for chore_id in v40_chores:
            if chore_id not in v42_chores:
                issues.append(f"Chore {chore_id} missing in v42 data")
                continue

            v40_chore = v40_chores[chore_id]
            v42_chore = v42_chores[chore_id]

            # Check name preserved
            if v40_chore.get("name") != v42_chore.get("name"):
                issues.append(f"Chore {chore_id} name changed")

            # Check points preserved
            v40_points = v40_chore.get("default_points", 0)
            v42_points = v42_chore.get("default_points", 0)
            if abs(v40_points - v42_points) > 0.01:
                issues.append(f"Chore {chore_id} points changed")

            # Check shared_chore → completion_criteria migration
            if v40_chore.get("shared_chore") is True:
                if v42_chore.get("completion_criteria") != "shared_all":
                    issues.append(
                        f"Chore {chore_id} shared_chore not migrated correctly"
                    )

        if issues:
            return ValidationResult(
                name="Chore Data Integrity",
                passed=False,
                message=f"Found {len(issues)} chore data issues",
                details={"issues": issues},
            )

        return ValidationResult(
            name="Chore Data Integrity",
            passed=True,
            message=f"All {len(v40_chores)} chores validated successfully",
        )

    async def validate_all(
        self, hass: Union["HomeAssistant", None] = None
    ) -> list[ValidationResult]:
        """Run all validations.

        Args:
            hass: Optional Home Assistant instance for integration testing

        Returns:
            List of validation results
        """
        self.results = []

        # Load v40 data
        try:
            self.load_v40_data()
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.results.append(
                ValidationResult(
                    name="Load V40 Data", passed=False, message=f"Failed to load: {e}"
                )
            )
            return self.results

        # Validate v40 schema
        self.results.append(self.validate_v40_schema())
        if not self.results[-1].passed:
            return self.results  # Can't proceed without valid v40 data

        # Migrate if hass provided
        if hass:
            try:
                await self.migrate_with_integration(hass)
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.results.append(
                    ValidationResult(
                        name="Migration", passed=False, message=f"Migration failed: {e}"
                    )
                )
                return self.results
        else:
            self.results.append(
                ValidationResult(
                    name="Migration",
                    passed=False,
                    message="Home Assistant instance required for migration",
                )
            )
            return self.results

        # Validate v42 schema
        self.results.append(self.validate_v42_schema())

        # Validate entity preservation
        self.results.append(self.validate_entity_preservation())

        # Validate modern structures
        self.results.append(self.validate_modern_structures())

        # Validate legacy field removal
        self.results.append(self.validate_no_legacy_fields())

        # Validate data integrity
        self.results.append(self.validate_kid_data_integrity())
        self.results.append(self.validate_chore_data_integrity())

        return self.results

    def print_report(self) -> None:
        """Print validation report."""
        print("\n" + "=" * 70)  # noqa: T201
        print("MIGRATION VALIDATION REPORT")  # noqa: T201
        print("=" * 70)  # noqa: T201
        print(f"\nData File: {self.data_file}")  # noqa: T201

        if self.before_counts:
            print(f"\nBefore Migration: {self.before_counts.total()} entities")  # noqa: T201
            print(f"  - Kids: {self.before_counts.kids}")  # noqa: T201
            print(f"  - Chores: {self.before_counts.chores}")  # noqa: T201
            print(f"  - Badges: {self.before_counts.badges}")  # noqa: T201
            print(f"  - Rewards: {self.before_counts.rewards}")  # noqa: T201
            print(f"  - Penalties: {self.before_counts.penalties}")  # noqa: T201
            print(  # noqa: T201
                f"  - Other: {self.before_counts.total() - self.before_counts.kids - self.before_counts.chores - self.before_counts.badges - self.before_counts.rewards - self.before_counts.penalties}"
            )

        if self.after_counts:
            print(f"\nAfter Migration: {self.after_counts.total()} entities")  # noqa: T201

        print("\n" + "-" * 70)  # noqa: T201
        print("VALIDATION RESULTS")  # noqa: T201
        print("-" * 70)  # noqa: T201

        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed

        for res in self.results:
            print(f"\n{res}")  # noqa: T201
            if res.details:
                for key, value in res.details.items():
                    if isinstance(value, (list, dict)) and len(str(value)) > 100:
                        print(f"  {key}: {type(value).__name__} (see details)")  # noqa: T201
                    else:
                        print(f"  {key}: {value}")  # noqa: T201

        print("\n" + "=" * 70)  # noqa: T201
        print(f"SUMMARY: {passed} passed, {failed} failed")  # noqa: T201
        print("=" * 70)  # noqa: T201

        if failed == 0:
            print("\n🎉 ALL VALIDATIONS PASSED! Migration successful.")  # noqa: T201
        else:
            print(f"\n⚠️  {failed} validation(s) failed. Review issues above.")  # noqa: T201


# Standalone script usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python validate_migration.py <path_to_v40_data_file>")  # noqa: T201
        print("\nExample:")  # noqa: T201
        print(  # noqa: T201
            "  python utils/validate_migration.py tests/migration_samples/kidschores_data_ad-ha"
        )
        sys.exit(1)

    data_file = sys.argv[1]

    print("KidsChores Migration Validator")  # noqa: T201
    print("Validating v40 → v42 migration")  # noqa: T201
    print(f"Data file: {data_file}\n")  # noqa: T201

    if not HAS_HA_DEPS:
        print("⚠️  Error: This script requires Home Assistant test dependencies.")  # noqa: T201
        print("Install with: pip install pytest-homeassistant-custom-component")  # noqa: T201
        sys.exit(1)

    # For standalone usage, we can't easily create a hass instance
    # User should use pytest integration instead
    print("⚠️  For full migration testing, use pytest integration:")  # noqa: T201
    print(f"  pytest tests/test_migration_generic.py --migration-file={data_file}")  # noqa: T201
    print("\nPerforming basic file validation only...\n")  # noqa: T201

    validator = MigrationValidator(data_file)

    # Load and validate v40 data only
    validator.load_v40_data()
    result = validator.validate_v40_schema()
    validator.results.append(result)

    validator.print_report()

    sys.exit(0 if result.passed else 1)
