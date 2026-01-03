
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from states.booking import EditBookingState
from datetime import datetime
import logging

from .keyboards import (
    get_edit_menu_keyboard,
    get_reschedule_confirmation_keyboard,
    get_edit_service_keyboard,
    format_time
)
from handlers.booking.keyboards import get_dates_keyboard, get_time_slots_keyboard
from handlers.booking.calendar_utils import (
    generate_calendar_keyboard,
    handle_calendar_action
)
from utils.notify import send_order_change_to_admins

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.startswith("edit_booking:"))
async def edit_booking_menu_handler(callback: CallbackQuery, state: FSMContext, db_manager, config: dict):
    """Меню редактирования заказа"""
    order_id = int(callback.data.split(":")[1])
    order = db_manager.get_order_by_id(order_id)

    if not order or order['user_id'] != callback.from_user.id or order['status'] != 'active':
        await callback.answer("Заказ не найден или уже отменён.", show_alert=True)
        return

    await state.update_data(editing_order_id=order_id)
    await state.set_state(EditBookingState.choosing_action)

    try:
        date_obj = datetime.fromisoformat(order['booking_date'])
        formatted_date = date_obj.strftime('%d.%m.%Y')
    except (ValueError, TypeError):
        formatted_date = order['booking_date']

    await callback.message.edit_text(
        f"Редактирование заказа #{order_id}\n\n"
        f"Услуга: {order['service_name']}\n"
        f"Дата: {formatted_date}\n"
        f"Время: {format_time(order.get('booking_time', ''))}\n\n"
        f"Цена: {order['price']}₽\n\n"
        "Что хотите изменить?",
        reply_markup=get_edit_menu_keyboard(order_id)
    )
    await callback.answer()

# --- Обработка изменения даты и времени ---

@router.callback_query(EditBookingState.choosing_action, F.data.startswith("edit_datetime:"))
async def edit_datetime_start_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Выберите новую дату:",
        reply_markup=get_dates_keyboard()
    )
    await state.set_state(EditBookingState.choosing_date)
    await callback.answer()


@router.callback_query(EditBookingState.choosing_date, F.data.startswith(("quick_date:", "cal_date:")))
async def edit_date_selected_handler(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    """Обработка выбора готовой даты (сегодня/завтра) или из календаря"""
    booking_date = callback.data.split(":", 1)[1]
    await state.update_data(new_booking_date=booking_date)
    data = await state.get_data()
    order_id = data.get('editing_order_id')

    keyboard = get_time_slots_keyboard(config, db_manager, booking_date, exclude_order_id=order_id)
    
    try:
        date_obj = datetime.fromisoformat(booking_date)
        date_formatted = date_obj.strftime('%d.%m.%Y')
    except (ValueError, TypeError):
        date_formatted = booking_date

    await callback.message.edit_text(
        f"Дата: {date_formatted}\n\nВыберите новое время:",
        reply_markup=keyboard
    )
    await state.set_state(EditBookingState.choosing_time)
    await callback.answer()


# --- Обработка календаря при редактировании ---

@router.callback_query(EditBookingState.choosing_date, F.data.in_(["open_calendar", "cal_prev_month", "cal_next_month"]))
async def edit_calendar_handler(callback: CallbackQuery, state: FSMContext, config: dict):
    await handle_calendar_action(callback, state, config, "booking")


@router.callback_query(EditBookingState.choosing_date, F.data.in_(["date_closed", "cancel_calendar"]))
async def edit_calendar_action_handler(callback: CallbackQuery, state: FSMContext, config: dict):
    if callback.data == "date_closed":
        await callback.answer("❌ Эта дата недоступна", show_alert=True)
    elif callback.data == "cancel_calendar":
        await callback.message.edit_text("Выберите новую дату:", reply_markup=get_dates_keyboard(config=config))
        await callback.answer()

# --- Обработка выбора времени и подтверждения ---

@router.callback_query(EditBookingState.choosing_time, F.data == "slot_taken")
async def edit_slot_taken_handler(callback: CallbackQuery):
    await callback.answer("Это время уже занято", show_alert=True)


@router.callback_query(EditBookingState.choosing_time, F.data.startswith("time:"))
async def edit_time_selected_handler(callback: CallbackQuery, state: FSMContext, db_manager):
    """Выбор времени и переход к подтверждению."""
    booking_time = callback.data.split(":", 1)[1]
    data = await state.get_data()
    order_id = data.get('editing_order_id')
    new_booking_date = data.get('new_booking_date')

    if not db_manager.check_slot_availability_excluding(new_booking_date, booking_time, order_id):
        await callback.answer("Это время уже занято. Выберите другой слот.", show_alert=True)
        return

    await state.update_data(new_booking_time=booking_time)

    old_order = db_manager.get_order_by_id(order_id)

    try:
        old_date_obj = datetime.fromisoformat(old_order['booking_date'])
        old_date_formatted = old_date_obj.strftime('%d.%m.%Y')
    except (ValueError, TypeError):
        old_date_formatted = old_order['booking_date']

    try:
        new_date_obj = datetime.fromisoformat(new_booking_date)
        new_date_formatted = new_date_obj.strftime('%d.%m.%Y')
    except (ValueError, TypeError):
        new_date_formatted = new_booking_date


    await callback.message.edit_text(
        f"Подтверждение изменений\n\n"
        f"Было:\n├ Дата: {old_date_formatted}\n└ Время: {format_time(old_order.get('booking_time', ''))}\n\n"
        f"Будет:\n├ Дата: {new_date_formatted}\n└ Время: {format_time(booking_time)}\n\n"
        "Подтверждаете изменения?",
        reply_markup=get_reschedule_confirmation_keyboard()
    )
    await state.set_state(EditBookingState.confirmation)
    await callback.answer()


# --- Обработка изменения услуги ---

@router.callback_query(EditBookingState.choosing_action, F.data.startswith("edit_service_existing:"))
async def edit_service_start_handler(callback: CallbackQuery, state: FSMContext, config: dict):
    order_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "Выберите новую услугу:",
        reply_markup=get_edit_service_keyboard(config.get('services', []), order_id)
    )
    await state.set_state(EditBookingState.choosing_service)
    await callback.answer()


@router.callback_query(EditBookingState.choosing_service, F.data.startswith("new_service:"))
async def edit_service_selected_handler(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    service_id = callback.data.split(":", 1)[1]
    selected_service = next((s for s in config.get('services', []) if s['id'] == service_id), None)

    if not selected_service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.update_data(
        new_service_id=selected_service['id'],
        new_service_name=selected_service['name'],
        new_price=selected_service['price']
    )

    data = await state.get_data()
    order_id = data.get('editing_order_id')
    old_order = db_manager.get_order_by_id(order_id)

    await callback.message.edit_text(
        f"Подтверждение изменений\n\n"
        f"Было: {old_order['service_name']} — {old_order['price']}₽\n"
        f"Будет: {selected_service['name']} — {selected_service['price']}₽\n\n"
        "Подтверждаете изменения?",
        reply_markup=get_reschedule_confirmation_keyboard()
    )
    await state.set_state(EditBookingState.confirmation)
    await callback.answer()


# --- Финальное подтверждение --- 

@router.callback_query(EditBookingState.confirmation, F.data == "confirm_edit")
async def confirm_order_edit_handler(callback: CallbackQuery, state: FSMContext, config: dict, db_manager, scheduler=None, admin_bot=None):
    """Финальное подтверждение всех изменений."""
    data = await state.get_data()
    order_id = data.get('editing_order_id')
    old_order = db_manager.get_order_by_id(order_id)
    
    updates = {
        key: data[f'new_{key}'] for key in ('booking_date', 'booking_time', 'service_id', 'service_name', 'price') if f'new_{key}' in data
    }

    if not db_manager.update_order(order_id, **updates):
        await callback.message.edit_text("❌ Ошибка изменения заказа")
        await state.clear()
        await callback.answer()
        return

    new_order = db_manager.get_order_by_id(order_id)
    
    # Обновление запланированных напоминаний
    if scheduler and ('booking_date' in updates or 'booking_time' in updates):
        try:
            scheduler.cancel_reminders(order_id)
            scheduler.schedule_reminders(order_id, **new_order)
        except Exception as e:
            logger.error(f"Error rescheduling reminders: {e}")

    # Уведомление админов
    if config.get('features', {}).get('enable_admin_notify', True):
        notify_bot = admin_bot or callback.message.bot
        await send_order_change_to_admins(
            bot=notify_bot,
            admin_ids=config['admin_ids'],
            old_order=old_order, new_order=new_order,
            business_name=config['business_name'],
            db_manager=db_manager
        )

    await callback.message.edit_text("✅ Заказ успешно изменён!")
    await state.clear()
    await callback.answer()
    
    # Показываем обновленный список записей
    from .view import show_my_bookings_handler # Круговой импорт, но для простоты оставим
    await show_my_bookings_handler(callback.message, db_manager, state, config)
