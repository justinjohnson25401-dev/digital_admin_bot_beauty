"""
Сохранение в БД и уведомления.
"""

import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from states.booking import BookingState
from utils.notify import send_order_to_admins
from .keyboards import get_time_slots_keyboard

logger = logging.getLogger(__name__)

router = Router()

@router.callback_query(BookingState.confirmation, F.data == "confirm_booking")
async def confirm_booking_and_save(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    data = await state.get_data()
    if data.get('booking_confirmed'):
        await callback.answer("Запись уже создана", show_alert=True)
        return

    await state.update_data(booking_confirmed=True)

    try:
        order_id = await save_booking_to_db(data, callback.from_user.id, db_manager)
        db_manager.add_user(user_id=callback.from_user.id, username=callback.from_user.username, first_name=callback.from_user.first_name, last_name=callback.from_user.last_name)
        logger.info(f"Booking confirmed: order_id={order_id}, user_id={callback.from_user.id}")

        await send_success_message(callback, state, config, db_manager, order_id)
        await send_admin_notification(callback, config, data, order_id, db_manager)

        await state.clear()
        await callback.answer("✅ Запись создана!")

    except ValueError as e:
        logger.warning(f"Slot already taken for user {callback.from_user.id}: {e}")
        await state.update_data(booking_confirmed=False)
        await callback.answer("❌ К сожалению, это время уже занято. Выберите другое.", show_alert=True)
        await return_to_time_selection(callback, state, config, db_manager)
    except Exception as e:
        logger.exception(f"Error creating booking for user {callback.from_user.id}: {e}")
        await state.update_data(booking_confirmed=False)
        await callback.answer("❌ Произошла ошибка. Попробуйте ещё раз.", show_alert=True)
        await state.clear()

async def save_booking_to_db(data: dict, user_id: int, db_manager) -> int:
    return db_manager.add_order(
        user_id=user_id,
        service_id=data.get('service_id'),
        service_name=data.get('service_name'),
        price=data.get('price'),
        client_name=data.get('client_name'),
        phone=data.get('phone'),
        comment=data.get('comment'),
        booking_date=data.get('booking_date'),
        booking_time=data.get('booking_time'),
        master_id=data.get('master_id')
    )

async def send_success_message(callback: CallbackQuery, state: FSMContext, config: dict, db_manager, order_id: int):
    data = await state.get_data()
    try:
        date_formatted = datetime.fromisoformat(data.get('booking_date')).strftime('%d.%m.%Y')
    except Exception:
        date_formatted = data.get('booking_date')

    success_text = config.get('messages', {}).get('success', "✅ Запись #{id} успешно создана!").format(id=order_id, date=date_formatted, time=data.get('booking_time'))
    master_text = f"\n👤 Мастер: {data.get('master_name')}" if data.get('master_name') else ""
    await callback.message.edit_text(f"{success_text}\n\n📅 {date_formatted} в {data.get('booking_time')}\n💇 {data.get('service_name')} — {data.get('price')}₽{master_text}\n\nЖдём вас! 💫")
    
    from handlers.start import get_main_keyboard
    user_bookings = db_manager.get_user_bookings(callback.from_user.id, active_only=True)
    if user_bookings:
        profile_text = "📋 <b>ВАШИ ЗАПИСИ</b>\n" + "━"*20 + "\n\n"
        buttons = []
        for booking in user_bookings:
            # ... (formatting logic for each booking) ...
            buttons.append([InlineKeyboardButton(text=f"✏️ Изменить запись #{booking['id']}", callback_data=f"edit_booking:{booking['id']}")])
            buttons.append([InlineKeyboardButton(text=f"🗑 Отменить запись #{booking['id']}", callback_data=f"cancel_order:{booking['id']}")])
        await callback.message.answer(profile_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.message.answer("🏠 Главное меню", reply_markup=get_main_keyboard())

async def send_admin_notification(callback: CallbackQuery, config: dict, data: dict, order_id: int, db_manager):
    try:
        await send_order_to_admins(
            bot=callback.message.bot,
            admin_ids=config.get('admin_ids', []),
            order_data={
                'order_id': order_id,
                'user_id': callback.from_user.id,
                'service_name': data.get('service_name'),
                'price': data.get('price'),
                'booking_date': data.get('booking_date'),
                'booking_time': data.get('booking_time'),
                'client_name': data.get('client_name'),
                'phone': data.get('phone'),
                'username': callback.from_user.username,
                'master_name': data.get('master_name')
            },
            business_name=config.get('business_name', ''),
            db_manager=db_manager
        )
    except Exception as e:
        logger.error(f"Failed to notify admins: {e}")

async def return_to_time_selection(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    data = await state.get_data()
    keyboard = get_time_slots_keyboard(config, db_manager, data.get('booking_date'), master_id=data.get('master_id'))
    await callback.message.edit_text(f"📅 {data.get('booking_date')}\n\n⚠️ Выбранное время занято. Выберите другое:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_time)
