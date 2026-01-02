"""
Обработчики раздела Клиенты (нижняя клавиатура).
"""

from aiogram import F
from aiogram.types import Message


async def reply_search_clients_handler(message: Message):
    """Поиск клиентов (заглушка)"""
    await message.answer("🔍 <b>Поиск клиентов</b>\n\n<i>Функция в разработке</i>")


def register_handlers(dp):
    """Регистрация обработчиков раздела Клиенты"""
    dp.message.register(reply_search_clients_handler, F.text == "🔍 Поиск")
