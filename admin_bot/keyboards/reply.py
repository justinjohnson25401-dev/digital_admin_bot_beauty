"""
Reply-клавиатуры (постоянные кнопки внизу экрана).
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_admin_reply_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура админ-панели"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Заказы"), KeyboardButton(text="💼 Услуги")],
            [KeyboardButton(text="👤 Персонал"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="👥 Клиенты")],
        ],
        resize_keyboard=True
    )


def get_orders_reply_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура раздела Заказы"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="◀️ Назад")],
            [KeyboardButton(text="📅 Сегодня"), KeyboardButton(text="📅 Завтра")],
            [KeyboardButton(text="📅 Неделя"), KeyboardButton(text="📥 CSV")],
        ],
        resize_keyboard=True
    )


def get_services_reply_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура раздела Услуги (включает Акции)"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="◀️ Назад"), KeyboardButton(text="🎁 Акции")],
            [KeyboardButton(text="📋 Список услуг"), KeyboardButton(text="➕ Добавить")],
        ],
        resize_keyboard=True
    )


def get_staff_reply_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура раздела Персонал"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="◀️ Назад"), KeyboardButton(text="➕ Добавить мастера")],
            [KeyboardButton(text="✏️ Редактировать"), KeyboardButton(text="📅 Закрытые даты")],
        ],
        resize_keyboard=True
    )


def get_settings_reply_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура раздела Настройки (включает Помощь)"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="◀️ Назад"), KeyboardButton(text="❓ Помощь")],
            [KeyboardButton(text="⚙️ Бизнес"), KeyboardButton(text="📝 Тексты")],
            [KeyboardButton(text="🔔 Уведомления")],
        ],
        resize_keyboard=True
    )


def get_clients_reply_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура раздела Клиенты"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="◀️ Назад"), KeyboardButton(text="🔍 Поиск")],
        ],
        resize_keyboard=True
    )
