"""
Тесты для модуля logger (маскировка чувствительных данных)
"""
import pytest
from logger import SensitiveDataFilter


class TestSensitiveDataFilter:
    """Тесты маскировки чувствительных данных в логах"""

    def setup_method(self):
        """Создаём экземпляр фильтра перед каждым тестом"""
        self.filter = SensitiveDataFilter()

    def test_mask_bot_token(self):
        """Токены ботов маскируются"""
        text = "Using token: 1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ123456789"
        result = self.filter._mask_sensitive_data(text)

        assert "ABCdefGHI" not in result
        assert "***TOKEN_MASKED***" in result
        assert "1234567890:" in result  # Первая часть токена остаётся

    def test_mask_phone_russian_plus7(self):
        """Российские номера +7 маскируются"""
        text = "Клиент позвонил: +79991234567"
        result = self.filter._mask_sensitive_data(text)

        assert "+79991234567" not in result
        assert "+7999***4567" in result

    def test_mask_phone_russian_8(self):
        """Российские номера 8XXX маскируются"""
        text = "Телефон клиента: 89991234567"
        result = self.filter._mask_sensitive_data(text)

        assert "89991234567" not in result
        assert "8999***4567" in result

    def test_mask_email(self):
        """Email адреса маскируются"""
        text = "Email: user@example.com"
        result = self.filter._mask_sensitive_data(text)

        assert "user@example.com" not in result
        assert "***@example.com" in result

    def test_mask_multiple_phones(self):
        """Несколько телефонов маскируются"""
        text = "Первый: +79991111111, второй: +79992222222"
        result = self.filter._mask_sensitive_data(text)

        assert "+79991111111" not in result
        assert "+79992222222" not in result
        assert result.count("***") >= 2

    def test_no_mask_regular_text(self):
        """Обычный текст не изменяется"""
        text = "Обычное сообщение без чувствительных данных"
        result = self.filter._mask_sensitive_data(text)

        assert result == text

    def test_empty_text(self):
        """Пустой текст возвращается как есть"""
        assert self.filter._mask_sensitive_data("") == ""
        assert self.filter._mask_sensitive_data(None) is None

    def test_mask_combined_sensitive_data(self):
        """Комбинация чувствительных данных маскируется"""
        text = "User +79991234567 with email test@mail.com used bot 123456789:ABCdef_12345678901234567890123456789"
        result = self.filter._mask_sensitive_data(text)

        # Проверяем что все данные замаскированы
        assert "+79991234567" not in result
        assert "test@mail.com" not in result
        assert "ABCdef" not in result

        # Проверяем что маски присутствуют
        assert "***" in result
