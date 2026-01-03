"""
Обработчики для выбора услуги.
"""
import logging
from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.booking import BookingState
from .keyboards import get_services_keyboard
from .master import show_masters_for_service

logger = logging.getLogger(__name__)

router = Router()

async def show_services_list(callback_or_message: Message | CallbackQuery, state: FSMContext, config: dict, category_name: str = None):
    """Показывает список услуг, опционально фильтруя по категории."""
    services = config.get('services', [])
    message = callback_or_message if isinstance(callback_or_message, Message) else callback_or_message.message

    if category_name:
        # Фильтруем услуги по выбранной категории
        services_in_category = [s for s in services if s.get('category') == category_name]
    else:
        # Показываем все услуги, если категории не используются
        services_in_category = services

    if not services_in_category:
        await message.answer("В этой категории нет доступных услуг. Попробуйте выбрать другую.")
        return

    await message.answer(
        text=config.get('messages', {}).get('service_selection', "Выберите услугу:"),
        reply_markup=get_services_keyboard(services_in_category, category_name)
    )
    await state.set_state(BookingState.choosing_master)
