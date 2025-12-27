from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard(faq_items: list | None = None) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📅 Записаться / Заказать")],
        [KeyboardButton(text="📋 Мои записи")],
        [KeyboardButton(text="❓ Часто задаваемые вопросы")],
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
