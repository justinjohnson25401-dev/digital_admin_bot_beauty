"""Валидаторы для ввода пользователей"""

import re


def is_valid_phone(phone: str) -> bool:
    """Проверка валидности номера телефона"""
    # Убираем все символы кроме цифр и +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    # Проверяем формат
    # Допустимые форматы:
    # +79991234567
    # 89991234567
    # 79991234567
    if cleaned.startswith('+'):
        return len(cleaned) == 12 and cleaned[1:].isdigit()
    elif cleaned.startswith('8'):
        return len(cleaned) == 11 and cleaned.isdigit()
    elif cleaned.startswith('7'):
        return len(cleaned) == 11 and cleaned.isdigit()
    else:
        return len(cleaned) == 10 and cleaned.isdigit()


def clean_phone(phone: str) -> str:
    """Очистка номера телефона от лишних символов"""
    return re.sub(r'[^\d+]', '', phone)


def is_valid_price(price_str: str) -> bool:
    """Проверка валидности цены"""
    try:
        price = int(price_str)
        return price > 0
    except (ValueError, TypeError):
        return False


def is_valid_duration(duration_str: str) -> bool:
    """Проверка валидности длительности услуги"""
    try:
        duration = int(duration_str)
        return 15 <= duration <= 240
    except (ValueError, TypeError):
        return False


def is_valid_time_format(time_str: str) -> tuple:
    """
    Проверка формата времени HH:MM-HH:MM
    Возвращает (is_valid, start_hour, end_hour) или (False, None, None)
    """
    pattern = r'^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})$'
    match = re.match(pattern, time_str)

    if not match:
        return (False, None, None)

    start_hour, start_min, end_hour, end_min = match.groups()
    start_hour, start_min, end_hour, end_min = int(start_hour), int(start_min), int(end_hour), int(end_min)

    # Валидация
    if start_hour >= 24 or end_hour >= 24 or start_min >= 60 or end_min >= 60:
        return (False, None, None)

    if start_hour >= end_hour:
        return (False, None, None)

    return (True, start_hour, end_hour)


# Новые валидаторы для unit-тестов

def validate_phone(phone: str) -> bool:
    """Алиас для is_valid_phone для совместимости с тестами"""
    if not phone:
        return False
    return is_valid_phone(phone)


def validate_name(name: str) -> bool:
    """
    Валидация имени клиента
    - Минимум 2 символа
    - Максимум 100 символов
    """
    if not name or not isinstance(name, str):
        return False

    name = name.strip()

    if len(name) < 2:
        return False

    if len(name) > 100:
        return False

    return True


def validate_comment(comment: str) -> bool:
    """
    Валидация комментария
    - Может быть пустым (опционально)
    - Максимум 500 символов
    """
    if comment is None or comment == "":
        return True  # Комментарий опционален

    if not isinstance(comment, str):
        return False

    if len(comment) > 500:
        return False

    return True
