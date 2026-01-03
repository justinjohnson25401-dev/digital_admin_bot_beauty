"""
Центральный маршрутизатор для навигации "Назад" в процессе бронирования.
Этот модуль устраняет циклические зависимости и сильную связанность.
"""

import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states.booking import BookingState

# Импортируем все функции, которые рендерят шаги бронирования
from .category import start_booking_flow
from .service import show_services_list
from .master import show_masters_for_service
from .date import proceed_to_date_selection
from .time import show_time_slots
from .contact import request_contact_info

logger = logging.getLogger(__name__)
router = Router()

async def get_service_from_data(config: dict, data: dict):
    """Вспомогательная функция для получения услуги из данных состояния."""
    service_id = data.get('service_id')
    return next((s for s in config.get('services', []) if s['id'] == service_id), None)

async def navigate_back(callback_or_message: Message | CallbackQuery, state: FSMContext, config: dict, db_manager):
    """
    Единая функция-маршрутизатор для навигации назад.
    Она определяет предыдущий шаг на основе текущего состояния FSM.
    """
    current_state = await state.get_state()
    data = await state.get_data()
    message = callback_or_message if isinstance(callback_or_message, Message) else callback_or_message.message

    # Карта состояний для навигации назад
    back_handlers = {
        BookingState.choosing_service: start_booking_flow,
        BookingState.choosing_master: lambda m, s, c, db: show_services_list(m, s, c, data.get('category_name')),
        BookingState.choosing_date: lambda m, s, c, db: show_masters_for_service(m, s, c, get_service_from_data(c, data)),
        BookingState.choosing_time: lambda m, s, c, db: proceed_to_date_selection(m, s, c, get_service_from_data(c, data)),
        BookingState.input_name: lambda m, s, c, db: show_time_slots(m, s, c, db, datetime.fromisoformat(data.get('booking_date')).date()),
        BookingState.input_phone: request_contact_info,
        BookingState.input_comment: request_contact_info,
        BookingState.confirmation: request_contact_info,
    }

    handler = back_handlers.get(current_state)

    if handler:
        # Адаптируем вызов в зависимости от того, требует ли лямбда get_service_from_data
        if "lambda" in repr(handler):
             # Если это лямбда, то она уже содержит нужные данные из state
            await handler(message, state, config, db_manager)
        else:
             await handler(message, state, config)
    else:
        # Если состояние не найдено, отменяем и выходим в главное меню
        # Прямой импорт заменен на получение из app-контекста
        from handlers.start import show_main_menu
        await state.clear()
        await show_main_menu(message, config)


# --- Обработчики для inline-кнопок "Назад" ---

@router.callback_query(F.data == "back_to_categories")
async def handle_back_to_categories(callback: CallbackQuery, state: FSMContext, config: dict):
    """Обработчик для кнопки 'Назад к категориям'."""
    await start_booking_flow(callback, state, config)
    await callback.answer()

@router.callback_query(F.data == "back_to_services")
async def handle_back_to_services(callback: CallbackQuery, state: FSMContext, config: dict):
    """Обработчик для кнопки 'Назад к услугам'."""
    data = await state.get_data()
    await show_services_list(callback, state, config, data.get('category_name'))
    await callback.answer()

@router.callback_query(F.data == "back_to_master_choice")
async def handle_back_to_master_choice(callback: CallbackQuery, state: FSMContext, config: dict):
    """Обработчик для кнопки 'Назад к выбору мастера'."""
    data = await state.get_data()
    service = await get_service_from_data(config, data)
    await show_masters_for_service(callback, state, config, service)
    await callback.answer()

@router.callback_query(F.data == "back_to_date_choice")
async def handle_back_to_date_choice(callback: CallbackQuery, state: FSMContext, config: dict):
    """Обработчик для кнопки 'Назад к выбору даты'."""
    data = await state.get_data()
    service = await get_service_from_data(config, data)
    await proceed_to_date_selection(callback, state, config, service)
    await callback.answer()
