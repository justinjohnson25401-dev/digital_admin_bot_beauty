"""
Inline-клавиатуры (кнопки под сообщениями).
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню админ-панели (компактное)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Заказы", callback_data="admin_orders"),
            InlineKeyboardButton(text="💼 Услуги", callback_data="admin_services")
        ],
        [
            InlineKeyboardButton(text="👤 Персонал", callback_data="staff_menu"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")
        ],
        [
            InlineKeyboardButton(text="👥 Клиенты", callback_data="admin_clients")
        ]
    ])
