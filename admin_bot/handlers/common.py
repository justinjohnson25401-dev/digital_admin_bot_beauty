"""
Общие обработчики (помощь, главное меню, неизвестные сообщения).
"""

from aiogram import F
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from admin_bot.keyboards import get_main_menu_keyboard, get_admin_reply_keyboard


async def admin_help_handler(callback: CallbackQuery):
    """Обработчик помощи"""
    text = (
        "❓ <b>Помощь</b>\n\n"
        "<b>Кнопки меню:</b>\n"
        "📊 Статистика — просмотр статистики\n"
        "📅 Заказы — управление записями\n"
        "💼 Услуги — редактирование услуг\n"
        "👤 Персонал — управление мастерами\n"
        "⚙️ Настройки — настройки бизнеса\n\n"
        "<b>Команды:</b>\n"
        "/start — Главное меню\n\n"
        "<b>Навигация:</b>\n"
        "Используйте кнопки внизу экрана или inline-меню для доступа к разделам.\n\n"
        "По вопросам обращайтесь к разработчику: @Oroani"
    )

    await callback.message.edit_text(text)
    await callback.answer()


async def admin_main_handler(callback: CallbackQuery, config: dict, db_manager, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()

    business_name = config.get('business_name', 'Ваш бизнес')
    stats = db_manager.get_stats('today')

    planned_text = f"\n├ Планируемая: {stats.get('planned_revenue', 0)}₽" if stats.get('planned_revenue', 0) > 0 else ""
    text = (
        f"🎯 <b>Админ-панель \"{business_name}\"</b>\n\n"
        f"📅 Сегодня:\n"
        f"├ Заказов: {stats['total_orders']}\n"
        f"├ Выручка: {stats['total_revenue']}₽{planned_text}\n"
        f"└ Новых клиентов: {stats.get('new_clients', 0)}\n\n"
        "Выберите действие:"
    )

    keyboard = get_main_menu_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def unknown_message(message: Message):
    """Обработчик неизвестных сообщений"""
    await message.answer("Команда не распознана. Нажмите /start для открытия админ-меню.")


def register_handlers(dp):
    """Регистрация общих обработчиков"""
    dp.callback_query.register(admin_help_handler, F.data == "admin_help")
    dp.callback_query.register(admin_main_handler, F.data == "admin_main")
    dp.message.register(unknown_message, StateFilter(None), ~F.text.startswith("/"))
