"""
Обработчики для выбора времени.
"""

import logging
from datetime import datetime, time, date, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from states.booking import BookingState
from .keyboards import get_time_slots_keyboard
from .contact import request_contact_info

logger = logging.getLogger(__name__)

router = Router()

async def show_time_slots(callback_or_message, state: FSMContext, config: dict, db_manager, selected_date: date):
    """Displays available time slots for the selected date."""
    data = await state.get_data()
    master_id = data.get('master_id')
    
    # Decide if we're editing a message or sending a new one
    message = callback_or_message if isinstance(callback_or_message, Message) else callback_or_message.message

    # Fetch busy slots from the database
    busy_slots = db_manager.get_busy_slots(selected_date.isoformat(), master_id)

    # Generate all possible time slots based on config
    work_hours_str = config.get('work_hours', {}).get(selected_date.strftime('%A').lower(), "09:00-18:00")
    start_work_str, end_work_str = work_hours_str.split('-')
    start_work_time = datetime.strptime(start_work_str, '%H:%M').time()
    end_work_time = datetime.strptime(end_work_str, '%H:%M').time()
    interval_minutes = config.get('booking_settings', {}).get('time_slot_interval', 30)

    all_slots = []
    current_time = datetime.combine(selected_date, start_work_time)
    end_datetime = datetime.combine(selected_date, end_work_time)

    while current_time < end_datetime:
        all_slots.append(current_time.strftime('%H:%M'))
        current_time += timedelta(minutes=interval_minutes)

    # Filter out busy slots
    available_slots = [slot for slot in all_slots if slot not in busy_slots]
    
    if not available_slots:
        await message.edit_text("На выбранную дату нет свободных слотов. Пожалуйста, выберите другую дату.")
        # Here you might want to send the calendar back
        # from .date import proceed_to_date_selection
        # await proceed_to_date_selection(callback_or_message, state, config, ...)
        return

    keyboard = get_time_slots_keyboard(available_slots)
    await message.edit_text(f"🕒 Выберите время на {selected_date.strftime('%d.%m.%Y')}:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_time)

@router.callback_query(BookingState.choosing_time, F.data.startswith("time:"))
async def time_selected(callback: CallbackQuery, state: FSMContext, db_manager):
    """Handles the selection of a time slot."""
    selected_time_str = callback.data.split(":", 1)[1]
    data = await state.get_data()
    booking_date = date.fromisoformat(data.get('booking_date'))
    
    # Combine date and time to create a full datetime object
    booking_datetime = datetime.combine(booking_date, time.fromisoformat(selected_time_str))
    
    await state.update_data(
        booking_datetime=booking_datetime.isoformat(),
        booking_time=selected_time_str  # Сохраняем время отдельно для save.py
    )
    logger.info(f"User {callback.from_user.id} selected time: {booking_datetime.isoformat()}")
    
    # Proceed to contact info request
    await request_contact_info(callback, state, db_manager)
    await callback.answer()