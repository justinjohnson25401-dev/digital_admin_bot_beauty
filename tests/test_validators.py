import pytest
from utils.validators import is_valid_phone, clean_phone

def test_valid_phone_russian_format():
    """Российский номер в формате +7 валиден"""
    assert is_valid_phone("+79991234567") == True

def test_valid_phone_without_plus():
    """Номер без + валиден"""
    assert is_valid_phone("79991234567") == True

def test_invalid_phone_too_short():
    """Слишком короткий номер невалиден"""
    assert is_valid_phone("123") == False

def test_clean_phone_removes_spaces():
    """clean_phone удаляет пробелы"""
    assert clean_phone("+7 999 123 45 67") == "+79991234567"

def test_clean_phone_removes_dashes():
    """clean_phone удаляет дефисы"""
    assert clean_phone("+7-999-123-45-67") == "+79991234567"