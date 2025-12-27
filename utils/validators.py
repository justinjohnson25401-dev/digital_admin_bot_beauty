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


# ==================== ВАЛИДАТОРЫ ДЛЯ АДМИН-ПАНЕЛИ ====================

def validate_price(price_str: str) -> tuple:
    """
    Валидация цены услуги.

    Возвращает: (is_valid, price_or_none)
    """
    try:
        price = int(str(price_str).strip())
        if price <= 0:
            return False, None
        if price > 1000000:
            return False, None
        return True, price
    except (ValueError, AttributeError, TypeError):
        return False, None


def validate_duration_strict(duration_str: str) -> tuple:
    """
    Валидация длительности услуги (строгий вариант).
    Допустимые значения: 15, 30, 45, 60, 90, 120, 180, 240 минут.

    Возвращает: (is_valid, duration_or_none)
    """
    allowed = [15, 30, 45, 60, 90, 120, 180, 240]

    try:
        duration = int(str(duration_str).strip())
        if duration in allowed:
            return True, duration
        return False, None
    except (ValueError, AttributeError, TypeError):
        return False, None


def validate_business_name(name: str) -> tuple:
    """
    Валидация названия бизнеса.
    От 3 до 50 символов.

    Возвращает: (is_valid, error_message)
    """
    if not name or not isinstance(name, str):
        return False, "Название должно быть непустой строкой"

    name = name.strip()

    if len(name) < 3:
        return False, "Название должно быть минимум 3 символа"

    if len(name) > 50:
        return False, "Название должно быть максимум 50 символов"

    return True, ""


def validate_work_hours(start: int, end: int) -> tuple:
    """
    Валидация рабочих часов.

    Возвращает: (is_valid, error_message)
    """
    if not isinstance(start, int) or not isinstance(end, int):
        return False, "Часы должны быть числами"

    if start < 0 or start >= 24:
        return False, "Начало работы должно быть от 0 до 23"

    if end <= 0 or end > 24:
        return False, "Конец работы должен быть от 1 до 24"

    if start >= end:
        return False, "Начало работы должно быть раньше конца"

    return True, ""


def validate_slot_duration(duration: int) -> tuple:
    """
    Валидация длительности слота бронирования.

    Возвращает: (is_valid, error_message)
    """
    allowed = [15, 30, 45, 60]

    if duration not in allowed:
        return False, f"Слот должен быть {', '.join(map(str, allowed))} минут"

    return True, ""


def validate_service_name(name: str) -> tuple:
    """
    Валидация названия услуги.

    Возвращает: (is_valid, error_message)
    """
    if not name or not isinstance(name, str):
        return False, "Название услуги не может быть пустым"

    name = name.strip()

    if len(name) < 2:
        return False, "Название услуги должно быть минимум 2 символа"

    if len(name) > 100:
        return False, "Название услуги должно быть максимум 100 символов"

    return True, ""


def validate_master_name(name: str) -> tuple:
    """
    Валидация имени мастера.

    Возвращает: (is_valid, error_message)
    """
    if not name or not isinstance(name, str):
        return False, "Имя не может быть пустым"

    name = name.strip()

    if len(name) < 2:
        return False, "Имя должно быть минимум 2 символа"

    if len(name) > 50:
        return False, "Имя должно быть максимум 50 символов"

    return True, ""


def validate_category_name(name: str) -> tuple:
    """
    Валидация названия категории.

    Возвращает: (is_valid, error_message)
    """
    if not name or not isinstance(name, str):
        return False, "Название категории не может быть пустым"

    name = name.strip()

    if len(name) < 2:
        return False, "Название категории должно быть минимум 2 символа"

    if len(name) > 50:
        return False, "Название категории должно быть максимум 50 символов"

    return True, ""


def validate_faq_button(text: str) -> tuple:
    """
    Валидация текста кнопки FAQ.

    Возвращает: (is_valid, error_message)
    """
    if not text or not isinstance(text, str):
        return False, "Текст кнопки не может быть пустым"

    text = text.strip()

    if len(text) < 2:
        return False, "Текст кнопки должен быть минимум 2 символа"

    if len(text) > 40:
        return False, "Текст кнопки должен быть максимум 40 символов"

    return True, ""


def validate_faq_answer(text: str) -> tuple:
    """
    Валидация ответа FAQ.

    Возвращает: (is_valid, error_message)
    """
    if not text or not isinstance(text, str):
        return False, "Ответ не может быть пустым"

    text = text.strip()

    if len(text) < 5:
        return False, "Ответ должен быть минимум 5 символов"

    if len(text) > 1000:
        return False, "Ответ должен быть максимум 1000 символов"

    return True, ""


def validate_message_text(text: str) -> tuple:
    """
    Валидация текста сообщения (welcome, success и т.д.).

    Возвращает: (is_valid, error_message)
    """
    if not text or not isinstance(text, str):
        return False, "Текст сообщения не может быть пустым"

    text = text.strip()

    if len(text) < 5:
        return False, "Текст должен быть минимум 5 символов"

    if len(text) > 1000:
        return False, "Текст должен быть максимум 1000 символов"

    return True, ""


def validate_date_format(date_str: str) -> tuple:
    """
    Валидация даты в формате YYYY-MM-DD.

    Возвращает: (is_valid, error_message)
    """
    import re
    from datetime import datetime

    if not date_str or not isinstance(date_str, str):
        return False, "Дата не может быть пустой"

    pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(pattern, date_str):
        return False, "Формат даты должен быть YYYY-MM-DD"

    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True, ""
    except ValueError:
        return False, "Некорректная дата"


def validate_time_slot(time_str: str) -> tuple:
    """
    Валидация времени слота в формате HH:MM.

    Возвращает: (is_valid, error_message)
    """
    import re

    if not time_str or not isinstance(time_str, str):
        return False, "Время не может быть пустым"

    pattern = r'^([01]?\d|2[0-3]):([0-5]\d)$'
    if not re.match(pattern, time_str):
        return False, "Формат времени должен быть HH:MM"

    return True, ""


def validate_master_role(role: str) -> tuple:
    """
    Валидация должности/специализации мастера.

    Возвращает: (is_valid, error_message)
    """
    if not role or not isinstance(role, str):
        return False, "Должность не может быть пустой"

    role = role.strip()

    if len(role) < 2:
        return False, "Должность должна быть минимум 2 символа"

    if len(role) > 50:
        return False, "Должность должна быть максимум 50 символов"

    return True, ""
