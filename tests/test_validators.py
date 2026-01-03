"""
Тесты для валидаторов.
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.validators import is_valid_phone, clean_phone, validate_master_name, validate_master_role


class TestPhoneValidators:
    """Тесты для валидаторов телефонов."""

    def test_clean_phone_with_spaces(self):
        result = clean_phone("+7 900 123 45 67")
        assert " " not in result

    def test_clean_phone_with_dashes(self):
        result = clean_phone("+7-900-123-45-67")
        assert "-" not in result

    def test_clean_phone_with_parentheses(self):
        result = clean_phone("+7(900)123-45-67")
        assert "(" not in result
        assert ")" not in result

    def test_is_valid_phone_with_plus7(self):
        assert is_valid_phone("+79001234567") is True

    def test_is_valid_phone_with_8(self):
        assert is_valid_phone("89001234567") is True

    def test_is_valid_phone_short(self):
        assert is_valid_phone("123456") is False

    def test_is_valid_phone_empty(self):
        assert is_valid_phone("") is False


class TestMasterValidators:
    """Тесты для валидаторов мастеров."""

    def test_validate_master_name_valid(self):
        valid, error = validate_master_name("Анна")
        assert valid is True

    def test_validate_master_name_too_short(self):
        valid, error = validate_master_name("А")
        assert valid is False

    def test_validate_master_role_valid(self):
        valid, error = validate_master_role("Парикмахер")
        assert valid is True
