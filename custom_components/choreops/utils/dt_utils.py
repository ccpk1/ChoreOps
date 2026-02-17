# File: utils/dt_utils.py
"""Date and time utilities for KidsChores.

Pure Python date/time functions with ZERO Home Assistant dependencies.
All functions here can be unit tested without Home Assistant mocking.

⚠️ DIRECTIVE 1 - UTILS PURITY: NO `homeassistant.*` imports allowed.
   Uses standard library: datetime, zoneinfo, dateutil.

Functions:
    - dt_today_local: Get today's date in local timezone
    - dt_today_iso: Get today's date as ISO string
    - dt_now_local: Get current datetime in local timezone
    - dt_now_iso: Get current datetime as ISO string
    - dt_to_utc: Parse and convert to UTC
    - dt_parse_duration: Parse human-readable duration strings
    - dt_format_duration: Format timedelta to human-readable string
    - dt_time_until: Calculate time remaining until target
    - dt_parse_date: Parse date strings
    - dt_format_short: Format datetime for notifications
    - dt_format: Format datetime to various output types
    - dt_parse: Normalize datetime inputs
    - dt_add_interval: Add time intervals to dates
    - dt_next_schedule: Calculate next scheduled occurrence
    - parse_daily_multi_times: Parse pipe-separated time strings
    - validate_daily_multi_times: Validate daily multi-time format
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
import logging
import re
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

# Third-party date utilities (no HA dependency)
from dateutil.relativedelta import relativedelta

if TYPE_CHECKING:
    from datetime import tzinfo

# Module-level logger (no HA dependency)
_LOGGER = logging.getLogger(__name__)

# ==============================================================================
# Constants (local copies to avoid circular imports)
# These mirror const.py values but are defined locally for purity.
# ==============================================================================

# Default timezone - can be overridden by caller
DEFAULT_TIME_ZONE: ZoneInfo = ZoneInfo("UTC")

# Time unit constants
TIME_UNIT_MINUTES = "minutes"
TIME_UNIT_HOURS = "hours"
TIME_UNIT_DAYS = "days"
TIME_UNIT_WEEKS = "weeks"
TIME_UNIT_MONTHS = "months"
TIME_UNIT_QUARTERS = "quarters"
TIME_UNIT_YEARS = "years"

# Frequency constants
FREQUENCY_DAILY = "daily"
FREQUENCY_WEEKLY = "weekly"
FREQUENCY_BIWEEKLY = "biweekly"
FREQUENCY_MONTHLY = "monthly"
FREQUENCY_QUARTERLY = "quarterly"
FREQUENCY_YEARLY = "yearly"
FREQUENCY_DAILY_MULTI = "daily_multi"
FREQUENCY_CUSTOM_1_WEEK = "custom_1_week"
FREQUENCY_CUSTOM_1_MONTH = "custom_1_month"
FREQUENCY_CUSTOM_1_YEAR = "custom_1_year"

# Period-end constants
PERIOD_DAY_END = "day_end"
PERIOD_WEEK_END = "week_end"
PERIOD_MONTH_END = "month_end"
PERIOD_QUARTER_END = "quarter_end"
PERIOD_YEAR_END = "year_end"

# Return type constants
HELPER_RETURN_DATETIME = "datetime"
HELPER_RETURN_DATETIME_UTC = "datetime_utc"
HELPER_RETURN_DATETIME_LOCAL = "datetime_local"
HELPER_RETURN_DATE = "date"
HELPER_RETURN_ISO_DATETIME = "iso_datetime"
HELPER_RETURN_ISO_DATE = "iso_date"
HELPER_RETURN_SELECTOR_DATETIME = "selector_datetime"

# Display constant
DISPLAY_UNKNOWN = "Unknown"

# Safety limit for date calculations
MAX_DATE_CALCULATION_ITERATIONS = 100

# Float precision for rounding
DATA_FLOAT_PRECISION = 2


# ==============================================================================
# Timezone Configuration
# ==============================================================================


def set_default_timezone(tz: ZoneInfo) -> None:
    """Set the default timezone for all dt_utils functions.

    Call this during integration setup to configure the user's timezone.

    Args:
        tz: ZoneInfo object representing the default timezone
    """
    global DEFAULT_TIME_ZONE  # noqa: PLW0603
    DEFAULT_TIME_ZONE = tz


def get_default_timezone() -> ZoneInfo:
    """Get the current default timezone.

    Returns:
        The configured default timezone (ZoneInfo object)
    """
    return DEFAULT_TIME_ZONE


# ==============================================================================
# Current Date/Time Functions
# ==============================================================================


def dt_today_local(tz: ZoneInfo | None = None) -> date:
    """Return today's date in local timezone as a `datetime.date`.

    Args:
        tz: Optional timezone override. Uses DEFAULT_TIME_ZONE if not provided.

    Returns:
        Today's date in the specified timezone.

    Example:
        datetime.date(2025, 4, 7)
    """
    tz_info = tz or DEFAULT_TIME_ZONE
    return datetime.now(tz_info).date()


def dt_today_iso(tz: ZoneInfo | None = None) -> str:
    """Return today's date in local timezone as ISO string (YYYY-MM-DD).

    Args:
        tz: Optional timezone override. Uses DEFAULT_TIME_ZONE if not provided.

    Returns:
        Today's date as ISO string.

    Example:
        "2025-04-07"
    """
    return dt_today_local(tz).isoformat()


def dt_now_local(tz: ZoneInfo | None = None) -> datetime:
    """Return the current datetime in local timezone (timezone-aware).

    Args:
        tz: Optional timezone override. Uses DEFAULT_TIME_ZONE if not provided.

    Returns:
        Current datetime in the specified timezone.

    Example:
        datetime.datetime(2025, 4, 7, 14, 30, tzinfo=...)
    """
    tz_info = tz or DEFAULT_TIME_ZONE
    return datetime.now(tz_info)


def dt_now_iso(tz: ZoneInfo | None = None) -> str:
    """Return the current local datetime as an ISO 8601 string.

    Args:
        tz: Optional timezone override. Uses DEFAULT_TIME_ZONE if not provided.

    Returns:
        Current datetime as ISO string.

    Example:
        "2025-04-07T14:30:00-05:00"
    """
    return dt_now_local(tz).isoformat()


def dt_now_utc() -> datetime:
    """Return the current datetime in UTC (timezone-aware).

    Returns:
        Current UTC datetime.
    """
    return datetime.now(UTC)


# ==============================================================================
# Timezone Conversion
# ==============================================================================


def as_utc(dt_obj: datetime) -> datetime:
    """Convert a datetime to UTC timezone.

    Args:
        dt_obj: Datetime object (must be timezone-aware)

    Returns:
        Datetime in UTC timezone
    """
    if dt_obj.tzinfo is None:
        # Assume it's in default timezone if naive
        dt_obj = dt_obj.replace(tzinfo=DEFAULT_TIME_ZONE)
    return dt_obj.astimezone(UTC)


def as_local(dt_obj: datetime, tz: ZoneInfo | None = None) -> datetime:
    """Convert a datetime to local timezone.

    Args:
        dt_obj: Datetime object (must be timezone-aware)
        tz: Optional timezone override. Uses DEFAULT_TIME_ZONE if not provided.

    Returns:
        Datetime in local timezone
    """
    tz_info = tz or DEFAULT_TIME_ZONE
    if dt_obj.tzinfo is None:
        # Assume it's in UTC if naive
        dt_obj = dt_obj.replace(tzinfo=UTC)
    return dt_obj.astimezone(tz_info)


def start_of_local_day(dt_obj: datetime, tz: ZoneInfo | None = None) -> datetime:
    """Get the start of day (00:00:00) for a datetime in local timezone.

    DST-safe implementation that handles timezone transitions correctly.

    Args:
        dt_obj: Datetime object (can be in any timezone)
        tz: Optional timezone override. Uses DEFAULT_TIME_ZONE if not provided.

    Returns:
        Datetime at 00:00:00 in local timezone (timezone-aware)
    """
    tz_info = tz or DEFAULT_TIME_ZONE

    # Convert to local timezone first
    local_dt = as_local(dt_obj, tz_info)

    # Get start of day by replacing time components
    return local_dt.replace(hour=0, minute=0, second=0, microsecond=0)


# ==============================================================================
# Date/Time Parsing
# ==============================================================================


def dt_parse_date(date_str: str | None) -> date | None:
    """Safely parse a date string into a `datetime.date`.

    Accepts formats:
    - "2025-04-07" (ISO format)
    - "04/07/2025" (US format)
    - "07/04/2025" (European format - attempted if US fails)

    Args:
        date_str: Date string to parse, or None

    Returns:
        datetime.date or None if parsing fails.
    """
    if not date_str or not isinstance(date_str, str):
        return None

    # Try ISO format first (most common)
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        pass

    # Try common formats
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    return None


def dt_parse(
    dt_input: str | date | datetime | None,
    default_tzinfo: tzinfo | None = None,
    return_type: str | None = HELPER_RETURN_DATETIME,
) -> datetime | date | str | None:
    """Normalize various datetime input formats to a consistent format.

    This function handles various input formats (string, date, datetime) and
    ensures proper timezone awareness. It can output in various formats based
    on the return_type parameter.

    Args:
        dt_input: String, date or datetime to normalize, or None
        default_tzinfo: Timezone to use if the input is naive
                        (defaults to DEFAULT_TIME_ZONE if None)
        return_type: Format for the returned value:
            - HELPER_RETURN_DATETIME: returns a datetime object (default)
            - HELPER_RETURN_DATETIME_UTC: returns a datetime object in UTC
            - HELPER_RETURN_DATETIME_LOCAL: returns a datetime object in local tz
            - HELPER_RETURN_DATE: returns a date object
            - HELPER_RETURN_ISO_DATETIME: returns an ISO-formatted datetime string
            - HELPER_RETURN_ISO_DATE: returns an ISO-formatted date string
            - HELPER_RETURN_SELECTOR_DATETIME: returns local timezone string
              formatted for HA DateTimeSelector ("%Y-%m-%d %H:%M:%S")

    Returns:
        Normalized datetime, date, or string based on return_type, or None if
        the input could not be parsed.

    Example:
        >>> dt_parse("2025-04-15")
        datetime.datetime(2025, 4, 15, 0, 0, tzinfo=ZoneInfo('America/New_York'))

        >>> dt_parse("2025-04-15", return_type=HELPER_RETURN_ISO_DATETIME)
        '2025-04-15T00:00:00-04:00'
    """
    # Handle empty input
    if not dt_input:
        return None

    # Set default timezone if not specified
    tz_info = default_tzinfo or DEFAULT_TIME_ZONE

    # Initialize result variable
    result: datetime | None = None

    # Handle string inputs
    if isinstance(dt_input, str):
        try:
            # Try ISO format parsing
            result = datetime.fromisoformat(dt_input)
        except ValueError:
            # If datetime parsing fails, try to parse as a date
            parsed_date = dt_parse_date(dt_input)
            if parsed_date:
                # Convert date to datetime for consistent handling
                result = datetime.combine(parsed_date, datetime.min.time())
            else:
                return None

    # Handle date objects
    elif isinstance(dt_input, date) and not isinstance(dt_input, datetime):
        result = datetime.combine(dt_input, datetime.min.time())

    # Handle datetime objects
    elif isinstance(dt_input, datetime):
        result = dt_input

    else:
        # Unsupported input type
        return None

    # Ensure timezone awareness
    if result.tzinfo is None:
        result = result.replace(tzinfo=tz_info)

    # Return in the requested format
    return dt_format(result, return_type)


def dt_to_utc(dt_str: str | None) -> datetime | None:
    """Parse a datetime string, apply timezone if naive, and convert to UTC.

    Args:
        dt_str: Datetime string to parse, or None

    Returns:
        UTC-aware datetime object, or None if parsing fails.

    Example:
        "2025-04-07T14:30:00" → datetime.datetime(2025, 4, 7, 19, 30, tzinfo=UTC)
    """
    if not dt_str:
        return None

    result = dt_parse(
        dt_str,
        default_tzinfo=DEFAULT_TIME_ZONE,
        return_type=HELPER_RETURN_DATETIME_UTC,
    )
    return cast("datetime | None", result)


# ==============================================================================
# Date/Time Formatting
# ==============================================================================


def dt_format(
    dt_obj: datetime,
    return_type: str | None = HELPER_RETURN_DATETIME,
) -> datetime | date | str:
    """Format a datetime object according to the specified return_type.

    Args:
        dt_obj: The datetime object to format
        return_type: The desired return format:
            - HELPER_RETURN_DATETIME: returns the datetime object unchanged
            - HELPER_RETURN_DATETIME_UTC: returns in UTC timezone
            - HELPER_RETURN_DATETIME_LOCAL: returns in local timezone
            - HELPER_RETURN_DATE: returns the date portion as a date object
            - HELPER_RETURN_ISO_DATETIME: returns an ISO-formatted datetime string
            - HELPER_RETURN_ISO_DATE: returns an ISO-formatted date string
            - HELPER_RETURN_SELECTOR_DATETIME: returns local timezone string
              formatted for HA DateTimeSelector ("%Y-%m-%d %H:%M:%S")

    Returns:
        The formatted date/time value
    """
    if return_type == HELPER_RETURN_DATETIME:
        return dt_obj
    if return_type == HELPER_RETURN_DATETIME_UTC:
        return as_utc(dt_obj)
    if return_type == HELPER_RETURN_DATETIME_LOCAL:
        return as_local(dt_obj)
    if return_type == HELPER_RETURN_DATE:
        return dt_obj.date()
    if return_type == HELPER_RETURN_ISO_DATETIME:
        return dt_obj.isoformat()
    if return_type == HELPER_RETURN_ISO_DATE:
        return dt_obj.date().isoformat()
    if return_type == HELPER_RETURN_SELECTOR_DATETIME:
        # For HA DateTimeSelector: local timezone, "%Y-%m-%d %H:%M:%S" format
        return as_local(dt_obj).strftime("%Y-%m-%d %H:%M:%S")
    # Default fallback
    return dt_obj


def dt_format_short(
    dt_obj: datetime | None,
    language: str = "en",
    include_time: bool = True,
) -> str:
    """Format a datetime object into a user-friendly short format.

    Converts to local timezone and formats as:
    - "Jan 16, 3:00 PM" (English with time)
    - "Jan 16" (English without time)

    Args:
        dt_obj: The datetime object to format (UTC or timezone-aware)
        language: Language code for localization (default: "en")
        include_time: Whether to include time component (default: True)

    Returns:
        Formatted string, or "Unknown" if dt_obj is None.
    """
    if dt_obj is None:
        return DISPLAY_UNKNOWN

    # Convert to local timezone
    local_dt = as_local(dt_obj)

    # Format based on language and time inclusion
    if include_time:
        if language in ("en", "en-US", "en-GB"):
            return local_dt.strftime("%b %d, %I:%M %p").replace(" 0", " ")
        # For other languages, use 24-hour format
        return local_dt.strftime("%b %d, %H:%M")

    # Date only: "Jan 16"
    return local_dt.strftime("%b %d")


# ==============================================================================
# Duration Parsing and Formatting
# ==============================================================================


def dt_parse_duration(
    duration_str: str | None,
    default_unit: str = TIME_UNIT_MINUTES,
) -> timedelta | None:
    """Parse a human-readable duration string into a timedelta.

    Supported formats:
    - "30" or "30m" → 30 minutes (default unit)
    - "1d" → 1 day
    - "6h" → 6 hours
    - "1d 6h 30m" → compound duration (1 day, 6 hours, 30 minutes)
    - "0" → None (disabled)
    - "" or None → None (disabled)

    Args:
        duration_str: Human-readable duration string (e.g., "1d 6h 30m")
        default_unit: Unit to assume if no suffix provided (default: minutes).
                      Must be one of: TIME_UNIT_MINUTES, TIME_UNIT_HOURS, TIME_UNIT_DAYS

    Returns:
        timedelta for valid durations, None for "0", empty, or invalid input.

    Examples:
        dt_parse_duration("30") → timedelta(minutes=30)
        dt_parse_duration("1d 6h") → timedelta(days=1, hours=6)
        dt_parse_duration("0") → None
    """
    if not duration_str or duration_str.strip() == "0":
        return None

    cleaned = duration_str.strip().lower()

    # Pattern: one or more digits followed by optional whitespace and optional unit
    pattern = r"(\d+)\s*([dhm])?"
    matches = re.findall(pattern, cleaned)

    if not matches:
        _LOGGER.warning(
            "Invalid duration format: %s - expected format like '30', '1d', '2h 30m'",
            duration_str,
        )
        return None

    total = timedelta()
    for value_str, unit in matches:
        num = int(value_str)
        if unit == "d":
            total += timedelta(days=num)
        elif unit == "h":
            total += timedelta(hours=num)
        elif unit == "m":
            total += timedelta(minutes=num)
        elif not unit:
            # No unit suffix - use default_unit
            if default_unit == TIME_UNIT_DAYS:
                total += timedelta(days=num)
            elif default_unit == TIME_UNIT_HOURS:
                total += timedelta(hours=num)
            else:  # Default to minutes
                total += timedelta(minutes=num)

    return total if total > timedelta() else None


def dt_format_duration(td: timedelta | None) -> str:
    """Format a timedelta into a human-readable duration string.

    Converts a timedelta object back to the compact string format
    used by dt_parse_duration.

    Args:
        td: timedelta object to format, or None

    Returns:
        Duration string like "1d 6h 30m", or "0" if None/zero.

    Examples:
        dt_format_duration(timedelta(days=1, hours=6)) → "1d 6h"
        dt_format_duration(timedelta(minutes=30)) → "30m"
        dt_format_duration(None) → "0"
    """
    if td is None or td <= timedelta():
        return "0"

    total_seconds = int(td.total_seconds())
    if total_seconds <= 0:
        return "0"

    days, remainder = divmod(total_seconds, 86400)  # 24 * 60 * 60
    hours, remainder = divmod(remainder, 3600)  # 60 * 60
    minutes = remainder // 60

    parts: list[str] = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")

    return " ".join(parts) if parts else "0"


def dt_time_until(target_dt: datetime | None) -> str | None:
    """Calculate human-readable time remaining until a target datetime.

    Uses UTC comparison to calculate time remaining and formats the
    result using dt_format_duration.

    Args:
        target_dt: Target datetime (should be UTC-aware), or None

    Returns:
        Formatted duration string (e.g., "2h 30m"), or None if:
        - target_dt is None
        - target_dt is in the past

    Examples:
        dt_time_until(utcnow() + timedelta(hours=2, minutes=30)) → "2h 30m"
        dt_time_until(utcnow() - timedelta(hours=1)) → None  # past
        dt_time_until(None) → None
    """
    if not target_dt:
        return None

    now = dt_now_utc()
    if now >= target_dt:
        # Already past target
        return None

    time_remaining = target_dt - now
    return dt_format_duration(time_remaining)


# ==============================================================================
# Daily Multi-Time Parsing
# ==============================================================================


def parse_daily_multi_times(
    times_str: str | None,
    reference_date: str | date | datetime | None = None,
    timezone_info: tzinfo | None = None,
) -> list[datetime]:
    """Parse pipe-separated time strings into timezone-aware datetime objects.

    Args:
        times_str: Pipe-separated times in HH:MM format (e.g., "08:00|12:00|18:00")
        reference_date: Date to combine with times (defaults to today)
        timezone_info: Timezone for the times (defaults to DEFAULT_TIME_ZONE)

    Returns:
        List of timezone-aware datetime objects sorted chronologically.
        Empty list if parsing fails or no valid times found.

    Example:
        >>> parse_daily_multi_times("08:00|17:00")
        [datetime(2026, 1, 14, 8, 0, tzinfo=...), datetime(2026, 1, 14, 17, 0, tzinfo=...)]
    """
    if not times_str or not isinstance(times_str, str):
        return []

    # Default to today's date if no reference provided
    if reference_date is None:
        base_date = dt_today_local()
    elif isinstance(reference_date, datetime):
        base_date = reference_date.date()
    elif isinstance(reference_date, date):
        base_date = reference_date
    else:
        # Try to parse string date
        parsed = dt_parse_date(reference_date)
        base_date = parsed or dt_today_local()

    # Default to system timezone if none provided
    tz_info = timezone_info or DEFAULT_TIME_ZONE

    result: list[datetime] = []
    for time_part in times_str.split("|"):
        time_part = time_part.strip()
        if not time_part:
            continue

        try:
            hour_str, minute_str = time_part.split(":")
            hour = int(hour_str)
            minute = int(minute_str)

            # Validate hour/minute ranges
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                _LOGGER.warning(
                    "Invalid time value in daily_multi_times: %s (out of range)",
                    time_part,
                )
                continue

            time_obj = time(hour, minute)

            # Combine date + time and apply timezone
            dt_local = datetime.combine(base_date, time_obj)
            dt_with_tz = dt_local.replace(tzinfo=tz_info)

            result.append(dt_with_tz)
        except (ValueError, AttributeError) as exc:
            _LOGGER.warning(
                "Invalid time format in daily_multi_times: %s (expected HH:MM): %s",
                time_part,
                exc,
            )
            continue

    return sorted(result)


def validate_daily_multi_times(
    times_str: str,
    error_key_required: str = "daily_multi_times_required",
    error_key_invalid: str = "daily_multi_times_invalid_format",
    error_key_too_few: str = "daily_multi_times_too_few",
    error_key_too_many: str = "daily_multi_times_too_many",
) -> tuple[bool, str | None]:
    """Validate pipe-separated time string format for DAILY_MULTI frequency.

    Args:
        times_str: Pipe-separated times in HH:MM format (e.g., "08:00|12:00|18:00")
        error_key_required: Error key if times_str is empty/missing
        error_key_invalid: Error key if format is invalid
        error_key_too_few: Error key if fewer than 2 times
        error_key_too_many: Error key if more than 6 times

    Returns:
        Tuple of (is_valid, error_key).
        If valid, returns (True, None).
        If invalid, returns (False, error_key).
    """
    if not times_str or not isinstance(times_str, str):
        return False, error_key_required

    times_str = times_str.strip()
    if not times_str:
        return False, error_key_required

    # Parse and validate each time slot
    valid_times: list[str] = []
    for time_part in times_str.split("|"):
        time_part = time_part.strip()
        if not time_part:
            continue

        # Check format: must be HH:MM
        if ":" not in time_part:
            return False, error_key_invalid

        try:
            hour_str, minute_str = time_part.split(":")
            hour = int(hour_str)
            minute = int(minute_str)

            # Validate ranges
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                return False, error_key_invalid

            valid_times.append(time_part)
        except (ValueError, AttributeError):
            return False, error_key_invalid

    # Check minimum (2 times required)
    if len(valid_times) < 2:
        return False, error_key_too_few

    # Check maximum (6 times allowed)
    if len(valid_times) > 6:
        return False, error_key_too_many

    return True, None


# ==============================================================================
# Interval Calculations
# ==============================================================================


def dt_add_interval(
    base_date: str | date | datetime,
    interval_unit: str,
    delta: int,
    end_of_period: str | None = None,
    require_future: bool = False,
    reference_datetime: str | date | datetime | None = None,
    return_type: str | None = HELPER_RETURN_DATETIME,
) -> str | date | datetime | None:
    """Add or subtract a time interval to a date/datetime.

    Args:
        base_date: ISO string, datetime.date, or datetime.datetime.
        interval_unit: One of the TIME_UNIT_* constants.
        delta: Number of time units to add.
        end_of_period: Optional string to adjust to end of period.
        require_future: If True, ensures result is after reference_datetime.
        reference_datetime: Reference datetime for require_future comparison.
        return_type: Output format (HELPER_RETURN_* constants).

    Returns:
        The calculated date/time in the requested format, or None on error.
    """
    if not base_date:
        _LOGGER.error("dt_add_interval: base_date is None")
        return None

    # Normalize base_date to datetime
    base_dt = dt_parse(
        base_date,
        default_tzinfo=DEFAULT_TIME_ZONE,
        return_type=HELPER_RETURN_DATETIME,
    )
    if base_dt is None:
        _LOGGER.error("dt_add_interval: Could not parse base_date")
        return None
    base_dt = cast("datetime", base_dt)

    # Prepare reference datetime
    ref_dt: datetime | None = None
    if reference_datetime:
        ref_parsed = dt_parse(
            reference_datetime,
            default_tzinfo=DEFAULT_TIME_ZONE,
            return_type=HELPER_RETURN_DATETIME,
        )
        if ref_parsed:
            ref_dt = as_utc(cast("datetime", ref_parsed))

    # Calculate the new datetime based on interval_unit
    result_dt = _add_interval_internal(
        base_dt=base_dt,
        interval_unit=interval_unit,
        delta=delta,
        end_of_period=end_of_period,
    )

    if result_dt is None:
        return None

    # Handle require_future
    if require_future and ref_dt:
        iteration_count = 0
        result_utc = as_utc(result_dt)
        ref_dt_utc = as_utc(ref_dt)

        while (
            result_utc <= ref_dt_utc
            and iteration_count < MAX_DATE_CALCULATION_ITERATIONS
        ):
            iteration_count += 1
            next_result = _add_interval_internal(
                base_dt=result_dt,
                interval_unit=interval_unit,
                delta=1,  # Add one more interval
                end_of_period=end_of_period,
            )
            if next_result is None:
                _LOGGER.warning(
                    "dt_add_interval: Early loop exit at iteration %d. next_result is None",
                    iteration_count,
                )
                break
            result_dt = next_result
            result_utc = as_utc(result_dt)

        if iteration_count >= MAX_DATE_CALCULATION_ITERATIONS:
            _LOGGER.warning(
                "dt_add_interval: Maximum iterations reached. base_date=%s, interval=%s",
                base_date,
                interval_unit,
            )

    return dt_format(result_dt, return_type)


def _add_interval_internal(
    base_dt: datetime,
    interval_unit: str,
    delta: int,
    end_of_period: str | None = None,
) -> datetime | None:
    """Internal helper for adding intervals without formatting.

    Args:
        base_dt: Base datetime (must be timezone-aware)
        interval_unit: Time unit constant
        delta: Number of units to add
        end_of_period: Optional period-end adjustment

    Returns:
        New datetime, or None on error
    """
    try:
        # Calculate new datetime based on interval unit
        if interval_unit == TIME_UNIT_MINUTES:
            result = base_dt + timedelta(minutes=delta)
        elif interval_unit == TIME_UNIT_HOURS:
            result = base_dt + timedelta(hours=delta)
        elif interval_unit == TIME_UNIT_DAYS:
            result = base_dt + timedelta(days=delta)
        elif interval_unit == TIME_UNIT_WEEKS:
            result = base_dt + timedelta(weeks=delta)
        elif interval_unit == TIME_UNIT_MONTHS:
            result = base_dt + relativedelta(months=delta)
        elif interval_unit == TIME_UNIT_QUARTERS:
            result = base_dt + relativedelta(months=delta * 3)
        elif interval_unit == TIME_UNIT_YEARS:
            result = base_dt + relativedelta(years=delta)
        else:
            _LOGGER.warning("Unknown interval_unit: %s", interval_unit)
            return None

        # Apply end-of-period adjustment if specified
        if end_of_period:
            result = _apply_end_of_period(result, end_of_period)

        return result
    except (ValueError, OverflowError) as exc:
        _LOGGER.error("Error adding interval: %s", exc)
        return None


def _apply_end_of_period(dt_obj: datetime, period: str) -> datetime:
    """Apply end-of-period adjustment to a datetime.

    Args:
        dt_obj: Datetime to adjust
        period: Period constant (PERIOD_DAY_END, etc.)

    Returns:
        Adjusted datetime
    """
    if period == PERIOD_DAY_END:
        return dt_obj.replace(hour=23, minute=59, second=0, microsecond=0)

    if period == PERIOD_WEEK_END:
        # Advance to Sunday
        days_until_sunday = (6 - dt_obj.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7  # Next Sunday if already Sunday
        result = dt_obj + timedelta(days=days_until_sunday)
        return result.replace(hour=23, minute=59, second=0, microsecond=0)

    if period == PERIOD_MONTH_END:
        # Go to first day of next month, then back one day
        next_month = dt_obj.replace(day=1) + relativedelta(months=1)
        last_day = next_month - timedelta(days=1)
        return last_day.replace(hour=23, minute=59, second=0, microsecond=0)

    if period == PERIOD_QUARTER_END:
        # Calculate quarter end (March 31, June 30, Sept 30, Dec 31)
        quarter = (dt_obj.month - 1) // 3
        quarter_end_month = (quarter + 1) * 3
        next_quarter = dt_obj.replace(month=quarter_end_month, day=1) + relativedelta(
            months=1
        )
        last_day = next_quarter - timedelta(days=1)
        return last_day.replace(hour=23, minute=59, second=0, microsecond=0)

    if period == PERIOD_YEAR_END:
        return dt_obj.replace(month=12, day=31, hour=23, minute=59, second=0)

    return dt_obj


def dt_next_schedule(
    base_date: str | date | datetime,
    interval_type: str,
    require_future: bool = True,
    reference_datetime: str | date | datetime | None = None,
    return_type: str | None = HELPER_RETURN_DATETIME,
) -> date | datetime | str | None:
    """Calculate the next scheduled datetime based on an interval type.

    IMPORTANT: This function ALWAYS advances by one interval from base_date first,
    then (if require_future=True) keeps advancing until the result is after reference.

    Supported interval types:
      - Daily: FREQUENCY_DAILY
      - Weekly: FREQUENCY_WEEKLY or FREQUENCY_CUSTOM_1_WEEK
      - Biweekly: FREQUENCY_BIWEEKLY
      - Monthly: FREQUENCY_MONTHLY or FREQUENCY_CUSTOM_1_MONTH
      - Quarterly: FREQUENCY_QUARTERLY
      - Yearly: FREQUENCY_YEARLY or FREQUENCY_CUSTOM_1_YEAR
      - Period-end types: PERIOD_DAY_END, PERIOD_WEEK_END, etc.

    Args:
        base_date: Starting date/datetime
        interval_type: Frequency constant
        require_future: If True, ensure result is after reference_datetime
        reference_datetime: Reference for require_future (defaults to now)
        return_type: Output format

    Returns:
        Next scheduled date/time in requested format, or None on error.

    Examples:
        dt_next_schedule("2025-04-07", FREQUENCY_MONTHLY) → datetime(2025, 5, 7)
        dt_next_schedule("2025-04-07", PERIOD_MONTH_END) → datetime(2025, 4, 30, 23, 59)
    """
    if not base_date:
        _LOGGER.error("dt_next_schedule: base_date is None")
        return None

    # Normalize base_date to datetime
    base_dt = dt_parse(
        base_date,
        default_tzinfo=DEFAULT_TIME_ZONE,
        return_type=HELPER_RETURN_DATETIME,
    )
    if base_dt is None:
        _LOGGER.error("dt_next_schedule: Could not parse base_date")
        return None
    base_dt = cast("datetime", base_dt)

    # Get reference datetime (default to now)
    ref_input = reference_datetime or dt_now_local()
    ref_dt = dt_parse(
        ref_input,
        default_tzinfo=DEFAULT_TIME_ZONE,
        return_type=HELPER_RETURN_DATETIME,
    )
    ref_dt = cast("datetime", ref_dt)
    ref_utc = as_utc(ref_dt)

    # Map interval_type to interval_unit and end_of_period
    interval_unit: str
    end_of_period: str | None = None
    delta = 1

    if interval_type in (FREQUENCY_DAILY, FREQUENCY_DAILY_MULTI):
        interval_unit = TIME_UNIT_DAYS
    elif interval_type in (FREQUENCY_WEEKLY, FREQUENCY_CUSTOM_1_WEEK):
        interval_unit = TIME_UNIT_WEEKS
    elif interval_type == FREQUENCY_BIWEEKLY:
        interval_unit = TIME_UNIT_WEEKS
        delta = 2
    elif interval_type in (FREQUENCY_MONTHLY, FREQUENCY_CUSTOM_1_MONTH):
        interval_unit = TIME_UNIT_MONTHS
    elif interval_type == FREQUENCY_QUARTERLY:
        interval_unit = TIME_UNIT_QUARTERS
    elif interval_type in (FREQUENCY_YEARLY, FREQUENCY_CUSTOM_1_YEAR):
        interval_unit = TIME_UNIT_YEARS
    elif interval_type == PERIOD_DAY_END:
        interval_unit = TIME_UNIT_DAYS
        end_of_period = PERIOD_DAY_END
    elif interval_type == PERIOD_WEEK_END:
        interval_unit = TIME_UNIT_WEEKS
        end_of_period = PERIOD_WEEK_END
    elif interval_type == PERIOD_MONTH_END:
        interval_unit = TIME_UNIT_MONTHS
        end_of_period = PERIOD_MONTH_END
    elif interval_type == PERIOD_QUARTER_END:
        interval_unit = TIME_UNIT_QUARTERS
        end_of_period = PERIOD_QUARTER_END
    elif interval_type == PERIOD_YEAR_END:
        interval_unit = TIME_UNIT_YEARS
        end_of_period = PERIOD_YEAR_END
    else:
        _LOGGER.warning("Unknown interval_type: %s", interval_type)
        return None

    # Always advance by one interval first
    result_dt = _add_interval_internal(
        base_dt=base_dt,
        interval_unit=interval_unit,
        delta=delta,
        end_of_period=end_of_period,
    )

    if result_dt is None:
        return None

    _LOGGER.debug(
        "dt_next_schedule: After first interval. base=%s, result=%s, interval=%s, delta=%d, require_future=%s",
        base_dt.isoformat() if base_dt else None,
        result_dt.isoformat() if result_dt else None,
        interval_type,
        delta,
        require_future,
    )

    # If require_future, keep advancing until result > reference
    if require_future:
        iteration_count = 0
        result_utc = as_utc(result_dt)

        _LOGGER.debug(
            "dt_next_schedule: Starting require_future loop. "
            "result_utc=%s, ref_utc=%s, result<=ref=%s",
            result_utc.isoformat(),
            ref_utc.isoformat(),
            result_utc <= ref_utc,
        )

        while (
            result_utc <= ref_utc and iteration_count < MAX_DATE_CALCULATION_ITERATIONS
        ):
            iteration_count += 1

            if iteration_count <= 3 or iteration_count % 10 == 0:
                _LOGGER.debug(
                    "dt_next_schedule: Loop iteration %d. result_utc=%s, ref_utc=%s, still_past=%s",
                    iteration_count,
                    result_utc.isoformat(),
                    ref_utc.isoformat(),
                    result_utc <= ref_utc,
                )

            next_result = _add_interval_internal(
                base_dt=result_dt,
                interval_unit=interval_unit,
                delta=delta,
                end_of_period=end_of_period,
            )
            if next_result is None or next_result == result_dt:
                _LOGGER.warning(
                    "dt_next_schedule: Early loop exit at iteration %d. "
                    "next_result=%s, result_dt=%s, equal=%s, none=%s",
                    iteration_count,
                    next_result.isoformat() if next_result else None,
                    result_dt.isoformat(),
                    next_result == result_dt if next_result else False,
                    next_result is None,
                )
                break
            result_dt = next_result
            result_utc = as_utc(result_dt)

        _LOGGER.debug(
            "dt_next_schedule: Loop completed. iterations=%d, final_result=%s, is_future=%s",
            iteration_count,
            result_dt.isoformat(),
            as_utc(result_dt) > ref_utc,
        )

        if iteration_count >= MAX_DATE_CALCULATION_ITERATIONS:
            _LOGGER.warning(
                "dt_next_schedule: Maximum iterations reached. base_date=%s, interval=%s",
                base_date,
                interval_type,
            )

    return dt_format(result_dt, return_type)
