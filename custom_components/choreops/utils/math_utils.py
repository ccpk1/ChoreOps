# File: utils/math_utils.py
"""Math and calculation utilities for ChoreOps.

Pure Python math functions with ZERO Home Assistant dependencies.
All functions here can be unit tested without Home Assistant mocking.

⚠️ DIRECTIVE 1 - UTILS PURITY: NO `homeassistant.*` imports allowed.

Functions:
    - round_points: Consistent rounding to configured precision
    - apply_multiplier: Multiplier arithmetic with proper rounding
    - calculate_percentage: Progress percentage calculations
    - parse_points_adjust_values: Parse pipe-separated point values (string input)
    - parse_points_adjust_values: Parse and normalize any adjustment value input
"""

from __future__ import annotations

import logging

# Module-level logger (no HA dependency)
_LOGGER = logging.getLogger(__name__)

# ==============================================================================
# Constants (local copies to avoid circular imports)
# ==============================================================================

# Default float precision for point rounding
DATA_FLOAT_PRECISION = 2


# ==============================================================================
# Point Arithmetic Functions (AMENDMENT - Phase 7.1.3)
# ==============================================================================


def round_points(value: float, precision: int = DATA_FLOAT_PRECISION) -> float:
    """Round a point value to the configured precision.

    Provides consistent rounding across the integration for all point-related
    calculations.

    Args:
        value: The float value to round
        precision: Number of decimal places (default: DATA_FLOAT_PRECISION)

    Returns:
        Rounded float value

    Examples:
        round_points(10.456) → 10.46
        round_points(10.454) → 10.45
        round_points(10.0) → 10.0
    """
    return round(value, precision)


def apply_multiplier(
    base: float,
    multiplier: float,
    precision: int = DATA_FLOAT_PRECISION,
) -> float:
    """Apply a multiplier to a base value with proper rounding.

    Used for streak multipliers, bonus multipliers, etc.

    Args:
        base: Base point value
        multiplier: Multiplier to apply (e.g., 1.5 for 50% bonus)
        precision: Number of decimal places for rounding

    Returns:
        Calculated value with proper rounding

    Examples:
        apply_multiplier(10, 1.5) → 15.0
        apply_multiplier(10, 1.333) → 13.33
        apply_multiplier(10, 0.5) → 5.0
    """
    return round_points(base * multiplier, precision)


def calculate_percentage(
    current: float,
    target: float,
    precision: int = DATA_FLOAT_PRECISION,
) -> float:
    """Calculate progress percentage with proper rounding.

    Args:
        current: Current progress value
        target: Target/total value
        precision: Number of decimal places for rounding

    Returns:
        Percentage (0-100) with proper rounding, or 0.0 if target is 0

    Examples:
        calculate_percentage(50, 100) → 50.0
        calculate_percentage(33, 100) → 33.0
        calculate_percentage(1, 3) → 33.33
        calculate_percentage(5, 0) → 0.0  # Division by zero protection
    """
    if target <= 0:
        return 0.0
    return round_points((current / target) * 100, precision)


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between minimum and maximum bounds.

    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Value clamped to [min_val, max_val] range

    Examples:
        clamp(150, 0, 100) → 100
        clamp(-10, 0, 100) → 0
        clamp(50, 0, 100) → 50
    """
    return max(min_val, min(value, max_val))


# ==============================================================================
# Point String Parsing
# ==============================================================================


def parse_points_adjust_values(raw_input: str | list | None = None) -> list[float]:
    """Parse adjustment delta values from any input type into normalized list of floats.

    Handles multiple input types:
    - None: Returns default adjustment values
    - list: Converts each element to float with precision rounding
    - str: Parses pipe-separated values with international decimal support

    All values are rounded to 2 decimal places for consistent unique_id generation.
    Handles international decimal separators (comma → period) for string input.

    Args:
        raw_input: Raw config value (list, str, or None)

    Returns:
        List of normalized float adjustment values, or defaults if invalid

    Examples:
        parse_points_adjust_values(None) → [1.0, -1.0, 2.0, -2.0, 10.0, -10.0]
        parse_points_adjust_values([1, 5, 10]) → [1.0, 5.0, 10.0]
        parse_points_adjust_values("2.5|5|10") → [2.5, 5.0, 10.0]
        parse_points_adjust_values("2,5|5|10") → [2.5, 5.0, 10.0]  # European format
        parse_points_adjust_values("invalid|10") → [10.0]  # Skips invalid
    """
    # Default fallback (hardcoded to avoid const import violation)
    default_values = [1.0, -1.0, 2.0, -2.0, 10.0, -10.0]
    precision = 2  # DATA_FLOAT_PRECISION hardcoded to avoid const import

    if not raw_input:
        return default_values

    # Handle list input
    if isinstance(raw_input, list):
        try:
            return [round(float(v), precision) for v in raw_input]
        except (ValueError, TypeError):
            _LOGGER.error(
                "Invalid adjustment values list: %s, using defaults", raw_input
            )
            return default_values

    # Handle string input (original pipe-separated logic)
    if isinstance(raw_input, str):
        values: list[float] = []
        for part in raw_input.split("|"):
            part = part.strip()
            if not part:
                continue

            try:
                # Handle European decimal separators (comma → period)
                value = round(float(part.replace(",", ".")), precision)
                values.append(value)
            except ValueError:
                _LOGGER.error("Invalid number '%s' in points adjust values", part)

        # Return parsed values or defaults if nothing valid
        return values or default_values

    # Unknown type
    _LOGGER.error(
        "Unexpected adjustment values type: %s, using defaults", type(raw_input)
    )
    return default_values
