"""
Unit-тесты для модуля validators
"""
import unittest
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.validators import validate_phone, validate_name, validate_comment


class TestPhoneValidator(unittest.TestCase):
    """Тесты для валидации телефонов"""

    def test_valid_russian_phone(self):
        """Тест валидных российских номеров"""
        valid_phones = [
            "+79991234567",
            "89991234567",
            "+78001234567"
        ]
        for phone in valid_phones:
            self.assertTrue(validate_phone(phone), f"Phone {phone} should be valid")

    def test_invalid_phone_short(self):
        """Тест слишком короткого номера"""
        self.assertFalse(validate_phone("123"))
        self.assertFalse(validate_phone("+7999"))

    def test_invalid_phone_letters(self):
        """Тест номера с буквами"""
        self.assertFalse(validate_phone("+7999abc4567"))

    def test_empty_phone(self):
        """Тест пустого номера"""
        self.assertFalse(validate_phone(""))
        self.assertFalse(validate_phone(None))


class TestNameValidator(unittest.TestCase):
    """Тесты для валидации имен"""

    def test_valid_name(self):
        """Тест валидных имен"""
        valid_names = [
            "Иван",
            "Иван Петров",
            "John Doe",
            "Мария-Анна"
        ]
        for name in valid_names:
            self.assertTrue(validate_name(name), f"Name '{name}' should be valid")

    def test_invalid_name_too_short(self):
        """Тест слишком короткого имени"""
        self.assertFalse(validate_name("A"))
        self.assertFalse(validate_name("И"))

    def test_invalid_name_too_long(self):
        """Тест слишком длинного имени"""
        long_name = "А" * 101
        self.assertFalse(validate_name(long_name))

    def test_invalid_name_empty(self):
        """Тест пустого имени"""
        self.assertFalse(validate_name(""))
        self.assertFalse(validate_name(None))


class TestCommentValidator(unittest.TestCase):
    """Тесты для валидации комментариев"""

    def test_valid_comment(self):
        """Тест валидного комментария"""
        self.assertTrue(validate_comment("Прошу окно"))
        self.assertTrue(validate_comment(""))  # Пустой комментарий валиден

    def test_invalid_comment_too_long(self):
        """Тест слишком длинного комментария"""
        long_comment = "А" * 501
        self.assertFalse(validate_comment(long_comment))

    def test_valid_comment_max_length(self):
        """Тест комментария максимальной длины"""
        max_comment = "А" * 500
        self.assertTrue(validate_comment(max_comment))


if __name__ == '__main__':
    unittest.main()
