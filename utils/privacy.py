"""
Утилиты для защиты персональных данных в логах
"""
import re


def mask_phone(phone: str) -> str:
    """
    Маскирует номер телефона для логов

    Пример:
        +79991234567 -> +7999***4567
        89991234567 -> 8999***4567
    """
    if not phone or len(phone) < 8:
        return phone

    # Оставляем первые 4 и последние 4 цифры
    return phone[:4] + "***" + phone[-4:]


def mask_name(name: str) -> str:
    """
    Маскирует имя для логов

    Пример:
        Иван Петров -> И*** П***
        John -> J***
    """
    if not name:
        return name

    words = name.split()
    masked_words = []

    for word in words:
        if len(word) <= 1:
            masked_words.append(word)
        else:
            masked_words.append(word[0] + "***")

    return " ".join(masked_words)


def mask_personal_data(text: str) -> str:
    """
    Автоматически маскирует персональные данные в тексте

    - Номера телефонов
    - Email адреса
    - Потенциальные имена (капитализированные слова)
    """
    if not text:
        return text

    # Маскируем телефоны (российские форматы)
    text = re.sub(
        r'(\+?[78][\d]{3})[\d]{3}([\d]{4})',
        r'\1***\2',
        text
    )

    # Маскируем email
    text = re.sub(
        r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'***@\2',
        text
    )

    return text


def safe_log_order_creation(user_id: int, service_name: str, client_name: str,
                            phone: str, booking_date: str = None,
                            booking_time: str = None) -> str:
    """
    Создает безопасное сообщение лога для создания заказа
    """
    masked_name = mask_name(client_name)
    masked_phone = mask_phone(phone)

    log_msg = f"Order created: user_id={user_id}, service={service_name}, "
    log_msg += f"client={masked_name}, phone={masked_phone}"

    if booking_date and booking_time:
        log_msg += f", date={booking_date}, time={booking_time}"

    return log_msg
