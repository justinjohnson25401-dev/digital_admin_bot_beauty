"""
Выбор времени (слоты).
"""

import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from states.booking import BookingState
from .keyboards import get_time_slots_keyboard

logger = logging.getLogger(__name__)

router = Router()

async def show_time_slots(callback: CallbackQuery, state: FSMContext, config: dict, db_manager, selected_date):
    """Показывает доступные слоты времени."""
    data = await state.get_data()
    date_str = selected_date.isoformat()
    keyboard = get_time_slots_keyboard(config, db_manager, date_str, master_id=data.get('master_id'))
    
    date_label = "Сегодня" if selected_date == datetime.now().date() else selected_date.strftime('%d.%m.%Y')
    
    await callback.message.edit_text(
        f"📅 {date_label}\n\nВыберите время:",
        reply_markup=keyboard
    )
    await state.set_state(BookingState.choosing_time)

@router.callback_query(F.data == "slot_taken")
async def slot_taken_handler(callback: CallbackQuery):
    await callback.answer("Это время уже занято", show_alert=True)

@router.callback_query(BookingState.choosing_time, F.data.startswith("time:"))
async def time_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    """Обрабатывает выбор времени."""
    booking_time = callback.data.split(":", 1)[1]
    data = await state.get_data()
    try:
        slot_dt = datetime.combine(datetime.fromisoformat(data.get('booking_date')).date(), datetime.strptime(booking_time, "%H:%M").time())
    except Exception:
        await callback.answer("Некорректное время", show_alert=True)
        return
    if slot_dt <= datetime.now():
        await callback.answer("Это время уже прошло", show_alert=True)
        return

    await state.update_data(booking_time=booking_time)
    await callback.message.edit_text(f"📅 {datetime.fromisoformat(data.get('booking_date')).strftime('%d.%m.%Y')} в {booking_time}")
    
    from .contact import request_contact_info # Local import
    await request_contact_info(callback, state, db_manager)
    await callback.answer()
