"""
Unit-тесты для модуля privacy (маскировка персональных данных)
"""
import unittest
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.privacy import mask_phone, mask_name, mask_personal_data


class TestPrivacyMasking(unittest.TestCase):
    """Тесты для маскировки персональных данных"""

    def test_mask_phone_russian(self):
        """Тест маскировки российского номера телефона"""
        self.assertEqual(mask_phone("+79991234567"), "+799***4567")
        self.assertEqual(mask_phone("89991234567"), "8999***4567")

    def test_mask_phone_short(self):
        """Тест маскировки короткого номера (не маскируется)"""
        self.assertEqual(mask_phone("123"), "123")
        self.assertEqual(mask_phone(""), "")

    def test_mask_name_single(self):
        """Тест маскировки одного имени"""
        self.assertEqual(mask_name("Иван"), "И***")
        self.assertEqual(mask_name("John"), "J***")

    def test_mask_name_full(self):
        """Тест маскировки полного имени"""
        self.assertEqual(mask_name("Иван Петров"), "И*** П***")
        self.assertEqual(mask_name("John Doe"), "J*** D***")

    def test_mask_name_empty(self):
        """Тест маскировки пустого имени"""
        self.assertEqual(mask_name(""), "")
        self.assertEqual(mask_name(None), None)

    def test_mask_personal_data_phone(self):
        """Тест автоматической маскировки телефонов в тексте"""
        text = "Клиент +79991234567 записался"
        result = mask_personal_data(text)
        self.assertIn("+7999***4567", result)
        self.assertNotIn("+79991234567", result)

    def test_mask_personal_data_email(self):
        """Тест автоматической маскировки email"""
        text = "Email: test@example.com"
        result = mask_personal_data(text)
        self.assertIn("***@example.com", result)
        self.assertNotIn("test@", result)


class TestPhoneValidation(unittest.TestCase):
    """Тесты для валидации телефонов"""

    def test_valid_russian_phone(self):
        """Тест валидных российских номеров"""
        valid_phones = [
            "+79991234567",
            "89991234567",
            "+78001234567"
        ]
        for phone in valid_phones:
            masked = mask_phone(phone)
            # Проверяем что номер замаскирован
            self.assertIn("***", masked)
            # Проверяем что оригинальные цифры не все присутствуют
            self.assertNotEqual(masked, phone)


if __name__ == '__main__':
    unittest.main()
