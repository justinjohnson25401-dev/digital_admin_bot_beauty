"""
Обработчики для выбора категории и старта процесса бронирования.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states.booking import BookingState
from .keyboards import get_categories_keyboard
from .service import show_services_list

logger = logging.getLogger(__name__)

router = Router()

async def start_booking_flow(callback_or_message: Message | CallbackQuery, state: FSMContext, config: dict):
    """Начинает процесс бронирования, показывая категории или сразу услуги."""
    categories = config.get('categories', [])
    message = callback_or_message if isinstance(callback_or_message, Message) else callback_or_message.message

    if categories:
        await message.answer(
            text=config.get('messages', {}).get('category_selection', "Выберите категорию:"),
            reply_markup=get_categories_keyboard(categories)
        )
        await state.set_state(BookingState.choosing_service)
    else:
        # Если категорий нет, сразу показываем услуги
        await show_services_list(callback_or_message, state, config)

@router.callback_query(BookingState.choosing_service, F.data.startswith("cat:"))
async def category_selected(callback: CallbackQuery, state: FSMContext, config: dict):
    """Обрабатывает выбор категории и показывает список услуг в ней."""
    category_name = callback.data.split(":")[1]
    await state.update_data(category_name=category_name)
    await show_services_list(callback, state, config, category_name)
    await callback.answer()
