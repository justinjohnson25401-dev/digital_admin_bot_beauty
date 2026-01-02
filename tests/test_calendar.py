# -*- coding: utf-8 -*-
"""
Tests for calendar module (calendar keyboard generation)
"""
import pytest
from datetime import datetime, date, timedelta
from utils.calendar import generate_calendar_keyboard, MONTHS_RU


@pytest.fixture
def sample_config():
    """Test configuration"""
    return {
        "business_name": "Test Salon",
        "booking": {
            "work_start": 10,
            "work_end": 20,
            "slot_duration": 60
        },
        "staff": {
            "enabled": True,
            "masters": [
                {
                    "id": "master1",
                    "name": "Anna",
                    "active": True,
                    "services": ["service1"],
                    "closed_dates": [
                        {"date": "2026-01-05", "reason": "Day off"},
                        {"date": "2026-01-15", "reason": "Vacation"}
                    ]
                }
            ]
        }
    }


class TestCalendarGeneration:
    """Calendar generation tests"""

    def test_calendar_has_month_header(self, sample_config):
        """Calendar contains month header"""
        keyboard = generate_calendar_keyboard(2026, 1, config=sample_config)

        # First button should be header with month
        first_row = keyboard.inline_keyboard[0]
        assert len(first_row) == 1
        assert "2026" in first_row[0].text

    def test_calendar_has_weekday_row(self, sample_config):
        """Calendar contains weekday row"""
        keyboard = generate_calendar_keyboard(2026, 1, config=sample_config)

        # Second row - weekdays
        weekday_row = keyboard.inline_keyboard[1]
        assert len(weekday_row) == 7

    def test_calendar_navigation_buttons(self, sample_config):
        """Calendar has navigation buttons"""
        keyboard = generate_calendar_keyboard(2026, 6, config=sample_config)

        # Last row - navigation
        nav_row = keyboard.inline_keyboard[-1]
        assert len(nav_row) >= 2  # At least prev/next or cancel

    def test_calendar_closed_dates_marked(self, sample_config):
        """Closed dates for master are marked"""
        keyboard = generate_calendar_keyboard(
            2026, 1,
            config=sample_config,
            master_id="master1"
        )

        # Look for button with January 5 (closed date)
        found_closed = False
        for row in keyboard.inline_keyboard:
            for btn in row:
                if btn.callback_data == "cal_closed":
                    found_closed = True
                    break

        assert found_closed, "Closed dates should be marked"

    def test_calendar_today_highlighted(self, sample_config):
        """Today's date is highlighted"""
        today = datetime.now()
        keyboard = generate_calendar_keyboard(
            today.year,
            today.month,
            config=sample_config
        )

        # Calendar should be generated without errors
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) > 0

    def test_months_ru_dictionary(self):
        """Russian month names dictionary is correct"""
        assert len(MONTHS_RU) == 12
        assert 1 in MONTHS_RU
        assert 12 in MONTHS_RU


class TestCalendarModes:
    """Calendar mode tests"""

    def test_booking_mode_restricts_past_dates(self, sample_config):
        """In booking mode past dates are not available"""
        keyboard = generate_calendar_keyboard(
            2020, 1,  # Past month
            config=sample_config,
            mode="booking"
        )

        # All past month dates should be unavailable
        for row in keyboard.inline_keyboard[2:-1]:
            for btn in row:
                if btn.callback_data and btn.callback_data not in ["ignore", "cal_closed"]:
                    # Should not have available dates in 2020
                    assert "2020" not in btn.callback_data

    def test_admin_mode_allows_any_dates(self, sample_config):
        """In admin_view mode any dates are available"""
        keyboard = generate_calendar_keyboard(
            2025, 1,
            config=sample_config,
            mode="admin_view"
        )

        # In admin mode 2025 dates should be available
        found_date_button = False
        for row in keyboard.inline_keyboard[2:-1]:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("cal_date:"):
                    found_date_button = True
                    break

        assert found_date_button

    def test_date_range_mode_shows_apply_button(self, sample_config):
        """In date range mode Apply button is shown"""
        start_date = date(2026, 1, 10)
        end_date = date(2026, 1, 15)

        keyboard = generate_calendar_keyboard(
            2026, 1,
            config=sample_config,
            mode="date_range",
            range_start=start_date,
            range_end=end_date
        )

        # Last row should contain Apply button
        nav_row = keyboard.inline_keyboard[-1]
        # Check if apply button exists (has checkmark emoji)
        apply_found = any("apply" in btn.callback_data.lower() if btn.callback_data else False for btn in nav_row)

        assert apply_found, "Apply button should be in date_range mode"
