"""
Обработчики для подтверждения записи.
"""

import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states.booking import BookingState

logger = logging.getLogger(__name__)

router = Router()

async def show_confirmation(message: Message, state: FSMContext):
    """Отображает сводку по бронированию для подтверждения."""
    data = await state.get_data()
    booking_datetime = datetime.fromisoformat(data.get('booking_datetime'))
    
    summary_text = (
        f"<b>Подтвердите вашу запись:</b>\n\n"
        f"<b>Услуга:</b> {data.get('service_name')}\n"
        f"<b>Мастер:</b> {data.get('master_name', 'Любой')}\n"
        f"<b>Дата и время:</b> {booking_datetime.strftime('%d.%m.%Y в %H:%M')}\n"
        f"<b>Цена:</b> {data.get('price')}\n\n"
        f"<b>Ваши данные:</b>\n"
        f"<b>Имя:</b> {data.get('name')}\n"
        f"<b>Телефон:</b> {data.get('phone')}\n"
    )
    if data.get('comment'):
        summary_text += f"<b>Комментарий:</b> {data.get('comment')}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить и записаться", callback_data="confirm_booking")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")]
    ])
    
    await message.answer(summary_text, reply_markup=keyboard)
    await state.set_state(BookingState.confirmation)

# Обработчик confirm_booking находится в save.py (избегаем дублирования)


@router.callback_query(BookingState.confirmation, F.data == "cancel_booking_process")
async def cancel_booking_process_callback(callback: CallbackQuery, state: FSMContext, config: dict):
    """Отменяет процесс бронирования на этапе подтверждения."""
    await state.clear()
    cancel_message = config.get('messages', {}).get('booking_cancelled', "Запись отменена.")
    await callback.message.edit_text(cancel_message)
    await callback.answer()
