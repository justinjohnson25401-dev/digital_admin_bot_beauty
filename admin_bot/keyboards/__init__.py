"""
Клавиатуры админ-бота.
"""

from .reply import (
    get_admin_reply_keyboard,
    get_orders_reply_keyboard,
    get_services_reply_keyboard,
    get_staff_reply_keyboard,
    get_settings_reply_keyboard,
    get_clients_reply_keyboard,
)
from .inline import get_main_menu_keyboard

__all__ = [
    'get_admin_reply_keyboard',
    'get_orders_reply_keyboard',
    'get_services_reply_keyboard',
    'get_staff_reply_keyboard',
    'get_settings_reply_keyboard',
    'get_clients_reply_keyboard',
    'get_main_menu_keyboard',
]
