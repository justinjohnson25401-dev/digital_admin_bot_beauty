import re

def is_valid_phone(phone: str) -> bool:
    """Проверяет, является ли строка валидным номером телефона."""
    if not phone or len(phone) < 10:
        return False
    return True

def clean_phone(phone: str) -> str:
    """Очищает номер телефона от лишних символов."""
    return re.sub(r"[^\d+]", "", phone)
