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


# Паттерны для обнаружения опасного HTML/JS контента
_DANGEROUS_PATTERNS = [
    re.compile(r'<\s*script', re.IGNORECASE),
    re.compile(r'javascript\s*:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),  # onerror=, onclick=, etc.
    re.compile(r'<\s*iframe', re.IGNORECASE),
    re.compile(r'<\s*object', re.IGNORECASE),
    re.compile(r'<\s*embed', re.IGNORECASE),
    re.compile(r'<\s*form', re.IGNORECASE),
    re.compile(r'<\s*input', re.IGNORECASE),
    re.compile(r'data\s*:', re.IGNORECASE),
    re.compile(r'vbscript\s*:', re.IGNORECASE),
]


def _contains_dangerous_content(text: str) -> bool:
    """Проверяет, содержит ли текст опасный HTML/JS контент."""
    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(text):
            return True
    return False


def validate_message_text(text: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует текст сообщения для бота.

    Args:
        text: Текст сообщения

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not text:
        return False, "Текст сообщения не может быть пустым"

    text = text.strip()

    if len(text) < 3:
        return False, "Текст слишком короткий (минимум 3 символа)"

    if len(text) > 2000:
        return False, "Текст слишком длинный (максимум 2000 символов)"

    if _contains_dangerous_content(text):
        return False, "Текст содержит запрещённый HTML/JavaScript код"

    return True, None


def validate_faq_button(text: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует текст кнопки FAQ.

    Args:
        text: Текст кнопки

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not text:
        return False, "Текст кнопки не может быть пустым"

    text = text.strip()

    if len(text) < 1:
        return False, "Текст кнопки слишком короткий (минимум 1 символ)"

    if len(text) > 64:
        return False, "Текст кнопки слишком длинный (максимум 64 символа)"

    if '\n' in text or '\r' in text:
        return False, "Текст кнопки не должен содержать переносы строк"

    return True, None


def validate_faq_answer(text: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует текст ответа FAQ.

    Args:
        text: Текст ответа

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not text:
        return False, "Текст ответа не может быть пустым"

    text = text.strip()

    if len(text) < 3:
        return False, "Текст ответа слишком короткий (минимум 3 символа)"

    if len(text) > 2000:
        return False, "Текст ответа слишком длинный (максимум 2000 символов)"

    # Проверяем только на <script> и опасные атрибуты, многострочный текст разрешён
    if _contains_dangerous_content(text):
        return False, "Текст ответа содержит запрещённый HTML/JavaScript код"

    return True, None


# Паттерн для валидации имени мастера (буквы, пробелы, дефис)
_MASTER_NAME_PATTERN = re.compile(r'^[\w\s\-]+$', re.UNICODE)


def validate_master_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует имя мастера.

    Args:
        name: Имя мастера

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not name:
        return False, "Имя мастера не может быть пустым"

    name = name.strip()

    if len(name) < 2:
        return False, "Имя слишком короткое (минимум 2 символа)"

    if len(name) > 50:
        return False, "Имя слишком длинное (максимум 50 символов)"

    # Проверяем на допустимые символы (буквы, пробелы, дефис)
    if not _MASTER_NAME_PATTERN.match(name):
        return False, "Имя содержит недопустимые символы (разрешены буквы, пробелы и дефис)"

    return True, None


def validate_master_role(role: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует роль/специализацию мастера.

    Args:
        role: Роль мастера (может быть пустой)

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    # Пустая роль допустима
    if not role:
        return True, None

    role = role.strip()

    # После strip пустая строка тоже валидна
    if len(role) == 0:
        return True, None

    if len(role) < 2:
        return False, "Роль слишком короткая (минимум 2 символа)"

    if len(role) > 50:
        return False, "Роль слишком длинная (максимум 50 символов)"

    # Проверяем на опасный контент
    if _contains_dangerous_content(role):
        return False, "Роль содержит запрещённый HTML/JavaScript код"

    return True, None


def validate_date_format(date_str: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует формат даты (YYYY-MM-DD).

    Args:
        date_str: Строка с датой

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not date_str:
        return False, "Дата не может быть пустой"

    date_str = date_str.strip()

    from datetime import datetime

    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True, None
    except ValueError:
        return False, "Неверный формат даты (ожидается YYYY-MM-DD)"
