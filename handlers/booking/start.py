"""
Начало бронирования, выбор услуги.
"""

import logging
import time
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.booking import BookingState
from .keyboards import get_categories_keyboard, get_services_keyboard
from .utils import get_categories_from_services, get_services_by_category, get_masters_for_service, get_master_by_id

logger = logging.getLogger(__name__)

router = Router()

async def start_booking_flow(message: Message, state: FSMContext, config: dict):
    await state.clear()
    await state.update_data(fsm_started_at=time.time(), booking_confirmed=False)
    services = config.get('services', [])
    if not services:
        await message.answer("К сожалению, услуги временно недоступны.")
        return

    categories = get_categories_from_services(services)
    if len(categories) > 1:
        keyboard = get_categories_keyboard(categories)
        await message.answer("Выберите категорию услуг:", reply_markup=keyboard)
        await state.set_state(BookingState.choosing_category)
    else:
        await show_services_list(message, state, config, services)

@router.message(F.text == "📅 Записаться")
async def start_booking(message: Message, state: FSMContext, config: dict):
    logger.info(f"User {message.from_user.id} started booking")
    await start_booking_flow(message, state, config)

async def show_services_list(message: Message, state: FSMContext, config: dict, services: list):
    keyboard = get_services_keyboard(services)
    await message.answer("Выберите услугу:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_service)

@router.callback_query(BookingState.choosing_category, F.data.startswith("cat:"))
async def category_selected(callback: CallbackQuery, state: FSMContext, config: dict):
    category = callback.data.split(":", 1)[1]
    await state.update_data(selected_category=category)
    data = await state.get_data()
    all_services = config.get('services', [])
    services = all_services
    if data.get('booking_with_preselected_master'):
        master = get_master_by_id(config, data.get('master_id'))
        if master:
            services = [s for s in all_services if s.get('id') in master.get('services', [])]

    cat_services = get_services_by_category(services, category)
    keyboard = get_services_keyboard(cat_services, category)
    await callback.message.edit_text(f"📂 {category}\n\nВыберите услугу:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_service)
    await callback.answer()

@router.callback_query(BookingState.choosing_service, F.data.startswith("srv:"))
async def service_selected(callback: CallbackQuery, state: FSMContext, config: dict):
    service_id = callback.data.split(":")[1]
    selected_service = next((s for s in config.get('services', []) if s['id'] == service_id), None)
    if not selected_service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.update_data(service_id=service_id, service_name=selected_service['name'], price=selected_service['price'])
    data = await state.get_data()

    staff_enabled = config.get('staff', {}).get('enabled', False)
    masters = get_masters_for_service(config, service_id) if staff_enabled else []
    
    if data.get('booking_with_preselected_master'):
        from .date import proceed_to_date_selection_with_master
        await proceed_to_date_selection_with_master(callback, state, config, selected_service)
    elif masters:
        from .master import show_masters_for_service
        await show_masters_for_service(callback, state, config, selected_service)
    else:
        await state.update_data(master_id=None, master_name=None)
        from .date import proceed_to_date_selection
        await proceed_to_date_selection(callback, state, config, selected_service)
    await callback.answer()
