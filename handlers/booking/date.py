"""
Выбор даты (календарь).
"""

import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from states.booking import BookingState
from .keyboards import get_dates_keyboard, get_time_slots_keyboard
from .utils import is_date_closed_for_master
from utils.calendar import generate_calendar_keyboard

logger = logging.getLogger(__name__)

router = Router()

async def proceed_to_date_selection(callback: CallbackQuery, state: FSMContext, config: dict, service: dict):
    data = await state.get_data()
    master_name = data.get('master_name')
    text = f"✅ {service['name']} — {service['price']}₽"
    if master_name:
        text += f"\n👤 Мастер: {master_name}"
    text += "\n\nВыберите дату:"

    if config.get('features', {}).get('enable_slot_booking', True):
        keyboard = get_dates_keyboard(config=config, master_id=data.get('master_id'))
        await callback.message.edit_text(text, reply_markup=keyboard)
        await state.set_state(BookingState.choosing_date)
    else:
        await callback.message.edit_text(text)
        from .contact import request_name_input # local import
        await request_name_input(callback.message, state)

async def proceed_to_date_selection_with_master(callback: CallbackQuery, state: FSMContext, config: dict, service: dict):
    await proceed_to_date_selection(callback, state, config, service)

@router.callback_query(BookingState.choosing_date, F.data.startswith("quick_date:"))
async def quick_date_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    date_str = callback.data.split(":", 1)[1]
    try:
        selected_date = datetime.fromisoformat(date_str).date()
    except Exception:
        await callback.answer("❌ Некорректная дата", show_alert=True)
        return

    if selected_date < datetime.now().date():
        await callback.answer("❌ Нельзя выбрать прошедшую дату", show_alert=True)
        return

    data = await state.get_data()
    is_closed, reason = is_date_closed_for_master(config, data.get('master_id'), selected_date)
    if is_closed:
        await callback.answer(f"❌ Мастер не работает в этот день{f' ({reason})' if reason else ''}", show_alert=True)
        return

    await state.update_data(booking_date=date_str)
    
    from .time import show_time_slots # Local import
    await show_time_slots(callback, state, config, db_manager, selected_date)
    await callback.answer()

@router.callback_query(F.data == "date_closed")
async def date_closed_handler(callback: CallbackQuery):
    await callback.answer("❌ Мастер не работает в этот день", show_alert=True)

@router.callback_query(BookingState.choosing_date, F.data == "open_calendar")
async def show_calendar(callback: CallbackQuery, state: FSMContext, config: dict):
    now = datetime.now()
    data = await state.get_data()
    master_id = data.get('master_id')
    await state.update_data(calendar_year=now.year, calendar_month=now.month, using_calendar=True)
    keyboard = generate_calendar_keyboard(year=now.year, month=now.month, config=config, master_id=master_id)
    await callback.message.edit_text("📅 Выберите дату в календаре:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(BookingState.choosing_date, F.data == "cal_prev_month")
async def calendar_prev_month(callback: CallbackQuery, state: FSMContext, config: dict):
    data = await state.get_data()
    year, month = data.get('calendar_year'), data.get('calendar_month')
    month -= 1
    if month < 1: month, year = 12, year - 1
    await state.update_data(calendar_year=year, calendar_month=month)
    keyboard = generate_calendar_keyboard(year=year, month=month, config=config, master_id=data.get('master_id'), mode="booking")
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(BookingState.choosing_date, F.data == "cal_next_month")
async def calendar_next_month(callback: CallbackQuery, state: FSMContext, config: dict):
    data = await state.get_data()
    year, month = data.get('calendar_year'), data.get('calendar_month')
    month += 1
    if month > 12: month, year = 1, year + 1
    await state.update_data(calendar_year=year, calendar_month=month)
    keyboard = generate_calendar_keyboard(year=year, month=month, config=config, master_id=data.get('master_id'), mode="booking")
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(BookingState.choosing_date, F.data.startswith("cal_date:"))
async def calendar_date_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    date_str = callback.data.split(":", 1)[1]
    try:
        selected_date = datetime.fromisoformat(date_str).date()
    except Exception:
        await callback.answer("❌ Некорректная дата", show_alert=True)
        return

    if selected_date < datetime.now().date():
        await callback.answer("❌ Нельзя выбрать прошедшую дату", show_alert=True)
        return

    data = await state.get_data()
    is_closed, reason = is_date_closed_for_master(config, data.get('master_id'), selected_date)
    if is_closed:
        await callback.answer(f"❌ Мастер не работает в этот день", show_alert=True)
        return

    await state.update_data(booking_date=date_str, using_calendar=False)
    
    from .time import show_time_slots # Local import
    await show_time_slots(callback, state, config, db_manager, selected_date)
    await callback.answer()

@router.callback_query(F.data == "cal_closed")
async def calendar_closed_handler(callback: CallbackQuery):
    await callback.answer("❌ Эта дата недоступна", show_alert=True)

@router.callback_query(F.data == "ignore")
async def calendar_ignore_handler(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data == "cancel_calendar")
async def calendar_cancel_handler(callback: CallbackQuery, state: FSMContext, config: dict):
    await state.update_data(using_calendar=False)
    data = await state.get_data()
    keyboard = get_dates_keyboard(config=config, master_id=data.get('master_id'))
    await callback.message.edit_text("Выберите дату:", reply_markup=keyboard)
    await callback.answer()
