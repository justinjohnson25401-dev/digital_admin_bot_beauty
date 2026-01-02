import re
from typing import Tuple, Optional


def is_valid_phone(phone: str) -> bool:
    """Проверяет, является ли строка валидным номером телефона."""
    if not phone or len(phone) < 10:
        return False
    return True


def clean_phone(phone: str) -> str:
    """Очищает номер телефона от лишних символов."""
    return re.sub(r"[^\d+]", "", phone)


def validate_russian_phone(phone: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует российский номер телефона.

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    cleaned = clean_phone(phone)

    if not cleaned:
        return False, "Номер телефона не может быть пустым"

    # Проверяем формат российского номера
    if cleaned.startswith('+7'):
        if len(cleaned) != 12:
            return False, "Номер в формате +7 должен содержать 12 символов"
    elif cleaned.startswith('8'):
        if len(cleaned) != 11:
            return False, "Номер в формате 8 должен содержать 11 цифр"
    elif cleaned.startswith('7'):
        if len(cleaned) != 11:
            return False, "Номер в формате 7 должен содержать 11 цифр"
    else:
        if len(cleaned) < 10:
            return False, "Номер телефона слишком короткий"

    return True, None


def validate_business_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует название бизнеса.

    Args:
        name: Название бизнеса

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not name:
        return False, "Название не может быть пустым"

    name = name.strip()

    if len(name) < 3:
        return False, "Название слишком короткое (минимум 3 символа)"

    if len(name) > 50:
        return False, "Название слишком длинное (максимум 50 символов)"

    # Проверяем на запрещённые символы
    forbidden_chars = ['<', '>', '{', '}', '[', ']', '|', '\\']
    for char in forbidden_chars:
        if char in name:
            return False, f"Название содержит запрещённый символ: {char}"

    return True, None


def validate_work_hours(start_hour: int, end_hour: int) -> Tuple[bool, Optional[str]]:
    """
    Валидирует часы работы.

    Args:
        start_hour: Час начала работы (0-23)
        end_hour: Час окончания работы (0-23)

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    try:
        start = int(start_hour)
        end = int(end_hour)
    except (ValueError, TypeError):
        return False, "Часы должны быть целыми числами"

    if start < 0 or start > 23:
        return False, "Час начала работы должен быть от 0 до 23"

    if end < 0 or end > 23:
        return False, "Час окончания работы должен быть от 0 до 23"

    if start >= end:
        return False, "Час начала должен быть меньше часа окончания"

    if end - start < 1:
        return False, "Рабочий день должен быть минимум 1 час"

    return True, None


def validate_slot_duration(duration: int) -> Tuple[bool, Optional[str]]:
    """
    Валидирует длительность слота.

    Args:
        duration: Длительность слота в минутах

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    try:
        dur = int(duration)
    except (ValueError, TypeError):
        return False, "Длительность должна быть целым числом"

    if dur < 15:
        return False, "Минимальная длительность слота — 15 минут"

    if dur > 480:
        return False, "Максимальная длительность слота — 480 минут (8 часов)"

    # Рекомендуем кратные 15 минутам
    if dur % 15 != 0:
        return False, "Рекомендуется указывать длительность кратную 15 минутам"

    return True, None


def validate_service_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует название услуги.

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not name:
        return False, "Название услуги не может быть пустым"

    name = name.strip()

    if len(name) < 2:
        return False, "Название слишком короткое (минимум 2 символа)"

    if len(name) > 100:
        return False, "Название слишком длинное (максимум 100 символов)"

    return True, None


def validate_price(price) -> Tuple[bool, Optional[str]]:
    """
    Валидирует цену услуги.

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    try:
        p = int(price)
    except (ValueError, TypeError):
        return False, "Цена должна быть целым числом"

    if p < 0:
        return False, "Цена не может быть отрицательной"

    if p > 1000000:
        return False, "Цена слишком высокая (максимум 1 000 000)"

    return True, None
