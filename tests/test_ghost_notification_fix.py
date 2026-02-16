"""Test notification placeholder handling and ghost notification prevention."""


# Helper function that mimics the logic of _format_notification_text
def format_notification_text(
    template: str, data: dict | None, json_key: str, text_type: str = "message"
) -> str | None:
    """Format notification text with placeholders, blocking on missing data."""
    try:
        return template.format(**(data or {}))
    except KeyError as err:
        # Simulate the logger.error call
        print(
            f"ERROR: Blocking notification '{json_key}' due to missing placeholder {err} in {text_type}."
        )
        return None


class TestGhostNotificationPrevention:
    """Test cases for preventing ghost notifications with missing placeholders."""

    def test_format_notification_text_success(self):
        """Test successful placeholder formatting."""
        template = "{kid_name}: {chore_name} is overdue! Due date was {due_date}."
        data = {
            "kid_name": "Alice",
            "chore_name": "Clean Room",
            "due_date": "2023-12-15",
        }
        result = format_notification_text(template, data, "test_key")
        expected = "Alice: Clean Room is overdue! Due date was 2023-12-15."
        assert result == expected

    def test_format_notification_text_missing_single_placeholder(self):
        """Test handling of single missing placeholder - should return None."""
        template = "{kid_name}: {chore_name} is overdue! Due date was {due_date}."
        data = {
            "kid_name": "Alice",
            "chore_name": "Clean Room",
            # missing "due_date"
        }
        result = format_notification_text(template, data, "test_key")
        assert result is None

    def test_format_notification_text_missing_multiple_placeholders(self):
        """Test handling of multiple missing placeholders - should return None."""
        template = "{kid_name}: {chore_name} is overdue! Due date was {due_date}."
        data = {
            "kid_name": "Alice"
            # missing both "chore_name" and "due_date"
        }
        result = format_notification_text(template, data, "test_key")
        assert result is None

    def test_format_notification_text_no_data(self):
        """Test handling when no data is provided - should return None."""
        template = "{kid_name}: {chore_name} is overdue! Due date was {due_date}."
        data = None
        result = format_notification_text(template, data, "test_key")
        assert result is None

    def test_format_notification_text_empty_data(self):
        """Test handling when empty data dict is provided - should return None."""
        template = "{kid_name}: {chore_name} is overdue! Due date was {due_date}."
        data = {}
        result = format_notification_text(template, data, "test_key")
        assert result is None

    def test_format_notification_text_fallback_for_extreme_case(self):
        """Test extreme case with many missing placeholders - should return None."""
        template = "Extreme case: {a} {b} {c} {d} {e} {f} {g} {h}"
        data = {"a": "1", "b": "2"}  # missing c, d, e, f, g, h
        result = format_notification_text(template, data, "test_key")
        assert result is None

    def test_format_notification_text_no_placeholder_needed(self):
        """Test template with no placeholders."""
        template = "No placeholders needed here"
        data = {"kid_name": "Alice"}  # data provided but not needed
        result = format_notification_text(template, data, "test_key")
        assert result == "No placeholders needed here"

    def test_chore_overdue_realistic_scenario(self):
        """Test realistic chore overdue scenario that caused the original issue."""
        # This is the real template that was causing ghost notifications
        template = "{kid_name}: {chore_name} is overdue!"
        # Simulate missing data that would cause the ghost notification
        data = {}  # completely empty - system bug caused this
        result = format_notification_text(template, data, "chore_overdue")
        # The fix: should return None instead of "{kid_name}: {chore_name} is overdue!"
        assert result is None
