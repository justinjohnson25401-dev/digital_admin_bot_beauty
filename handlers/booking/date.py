"""
Обработчики для выбора даты.
"""

import logging
from datetime import date, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from states.booking import BookingState
from .keyboards import get_calendar_keyboard
from .time import show_time_slots

logger = logging.getLogger(__name__)

router = Router()

async def proceed_to_date_selection(callback_or_message, state: FSMContext, config: dict, service: dict):
    """Displays the calendar for date selection."""
    today = date.today()
    
    # Decide if we're editing a message or sending a new one
    message = callback_or_message if isinstance(callback_or_message, Message) else callback_or_message.message

    keyboard = get_calendar_keyboard(year=today.year, month=today.month)
    await message.edit_text(f"📅 Выберите дату для услуги «{service['name']}»:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_date)

@router.callback_query(BookingState.choosing_date, F.data.startswith("calendar:"))
async def calendar_callback_handler(callback: CallbackQuery, state: FSMContext, db_manager, config: dict):
    """Handles calendar navigation and date selection."""
    action, year_str, month_str, day_str = callback.data.split(':')
    year, month, day = int(year_str), int(month_str), int(day_str)

    if action == "ignore":
        await callback.answer()
        return

    if action == "prev-month":
        prev_month_date = date(year, month, 1) - timedelta(days=1)
        keyboard = get_calendar_keyboard(year=prev_month_date.year, month=prev_month_date.month)
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()
        return

    if action == "next-month":
        next_month_date = date(year, month, 1) + timedelta(days=31)
        keyboard = get_calendar_keyboard(year=next_month_date.year, month=next_month_date.month)
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()
        return

    if action == "select-day":
        selected_date = date(year, month, day)
        today = date.today()
        if selected_date < today:
            await callback.answer("Нельзя выбрать прошедшую дату!", show_alert=True)
            return
        
        await state.update_data(booking_date=selected_date.isoformat())
        logger.info(f"User {callback.from_user.id} selected date: {selected_date.isoformat()}")
        
        # Proceed to time selection
        await show_time_slots(callback, state, config, db_manager, selected_date)
        await callback.answer()
