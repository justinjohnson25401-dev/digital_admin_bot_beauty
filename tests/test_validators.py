"""
Тесты для модуля validators
"""
import pytest
from utils.validators import (
    is_valid_phone,
    clean_phone,
    validate_russian_phone,
    validate_business_name,
    validate_work_hours,
    validate_slot_duration,
    validate_service_name,
    validate_price
)


class TestPhoneValidation:
    """Тесты валидации телефонных номеров"""

    def test_valid_phone_russian_format(self):
        """Российский номер в формате +7 валиден"""
        assert is_valid_phone("+79991234567") == True

    def test_valid_phone_without_plus(self):
        """Номер без + валиден"""
        assert is_valid_phone("79991234567") == True

    def test_invalid_phone_too_short(self):
        """Слишком короткий номер невалиден"""
        assert is_valid_phone("123") == False

    def test_clean_phone_removes_spaces(self):
        """clean_phone удаляет пробелы"""
        assert clean_phone("+7 999 123 45 67") == "+79991234567"

    def test_clean_phone_removes_dashes(self):
        """clean_phone удаляет дефисы"""
        assert clean_phone("+7-999-123-45-67") == "+79991234567"

    def test_clean_phone_removes_parentheses(self):
        """clean_phone удаляет скобки"""
        assert clean_phone("+7(999)123-45-67") == "+79991234567"


class TestRussianPhoneValidation:
    """Тесты строгой валидации российских номеров"""

    def test_valid_plus7_format(self):
        """Номер +7XXXXXXXXXX валиден"""
        is_valid, error = validate_russian_phone("+79991234567")
        assert is_valid == True
        assert error is None

    def test_valid_8_format(self):
        """Номер 8XXXXXXXXXX валиден"""
        is_valid, error = validate_russian_phone("89991234567")
        assert is_valid == True
        assert error is None

    def test_invalid_empty(self):
        """Пустой номер невалиден"""
        is_valid, error = validate_russian_phone("")
        assert is_valid == False
        assert error is not None

    def test_invalid_short_plus7(self):
        """Короткий номер +7 невалиден"""
        is_valid, error = validate_russian_phone("+7999123")
        assert is_valid == False
        assert "12 символов" in error


class TestBusinessNameValidation:
    """Тесты валидации названия бизнеса"""

    def test_valid_name(self):
        """Корректное название проходит валидацию"""
        is_valid, error = validate_business_name("Салон Красоты")
        assert is_valid == True
        assert error is None

    def test_name_too_short(self):
        """Слишком короткое название"""
        is_valid, error = validate_business_name("AB")
        assert is_valid == False
        assert "короткое" in error

    def test_name_too_long(self):
        """Слишком длинное название"""
        is_valid, error = validate_business_name("A" * 60)
        assert is_valid == False
        assert "длинное" in error

    def test_name_empty(self):
        """Пустое название"""
        is_valid, error = validate_business_name("")
        assert is_valid == False

    def test_name_with_forbidden_chars(self):
        """Название с запрещёнными символами"""
        is_valid, error = validate_business_name("Salon <script>")
        assert is_valid == False
        assert "запрещённый" in error


class TestWorkHoursValidation:
    """Тесты валидации часов работы"""

    def test_valid_hours(self):
        """Корректные часы работы"""
        is_valid, error = validate_work_hours(10, 20)
        assert is_valid == True
        assert error is None

    def test_start_greater_than_end(self):
        """Начало позже конца"""
        is_valid, error = validate_work_hours(20, 10)
        assert is_valid == False
        assert "меньше" in error

    def test_start_equals_end(self):
        """Начало равно концу"""
        is_valid, error = validate_work_hours(10, 10)
        assert is_valid == False

    def test_invalid_start_hour(self):
        """Некорректный час начала"""
        is_valid, error = validate_work_hours(25, 20)
        assert is_valid == False
        assert "0 до 23" in error

    def test_invalid_end_hour(self):
        """Некорректный час конца"""
        is_valid, error = validate_work_hours(10, -1)
        assert is_valid == False


class TestSlotDurationValidation:
    """Тесты валидации длительности слота"""

    def test_valid_duration(self):
        """Корректная длительность"""
        is_valid, error = validate_slot_duration(60)
        assert is_valid == True
        assert error is None

    def test_duration_too_short(self):
        """Слишком короткий слот"""
        is_valid, error = validate_slot_duration(10)
        assert is_valid == False
        assert "15 минут" in error

    def test_duration_too_long(self):
        """Слишком длинный слот"""
        is_valid, error = validate_slot_duration(500)
        assert is_valid == False
        assert "480" in error

    def test_duration_not_multiple_of_15(self):
        """Длительность не кратна 15"""
        is_valid, error = validate_slot_duration(25)
        assert is_valid == False
        assert "кратную 15" in error

    def test_valid_durations(self):
        """Проверка различных валидных значений"""
        for duration in [15, 30, 45, 60, 90, 120]:
            is_valid, error = validate_slot_duration(duration)
            assert is_valid == True, f"Duration {duration} should be valid"


class TestServiceNameValidation:
    """Тесты валидации названия услуги"""

    def test_valid_service_name(self):
        """Корректное название услуги"""
        is_valid, error = validate_service_name("Стрижка")
        assert is_valid == True

    def test_service_name_too_short(self):
        """Слишком короткое название"""
        is_valid, error = validate_service_name("A")
        assert is_valid == False
        assert "короткое" in error

    def test_service_name_too_long(self):
        """Слишком длинное название"""
        is_valid, error = validate_service_name("A" * 150)
        assert is_valid == False
        assert "длинное" in error


class TestPriceValidation:
    """Тесты валидации цены"""

    def test_valid_price(self):
        """Корректная цена"""
        is_valid, error = validate_price(1500)
        assert is_valid == True

    def test_zero_price(self):
        """Нулевая цена валидна"""
        is_valid, error = validate_price(0)
        assert is_valid == True

    def test_negative_price(self):
        """Отрицательная цена"""
        is_valid, error = validate_price(-100)
        assert is_valid == False
        assert "отрицательной" in error

    def test_price_too_high(self):
        """Слишком высокая цена"""
        is_valid, error = validate_price(2000000)
        assert is_valid == False
        assert "высокая" in error

    def test_price_not_integer(self):
        """Нецелое значение цены"""
        is_valid, error = validate_price("abc")
        assert is_valid == False
        assert "целым числом" in error
