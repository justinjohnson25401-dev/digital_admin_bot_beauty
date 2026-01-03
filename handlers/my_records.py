"""
Обработчики для раздела 'Мои записи'.
"""

import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

router = Router()

async def show_my_records(message: Message, db_manager, config: dict):
    """Отображает список активных записей пользователя."""
    user_id = message.from_user.id
    bookings = db_manager.get_user_bookings(user_id, active_only=True)

    if not bookings:
        await message.answer("У вас нет активных записей.")
        return

    text = "<b>📋 Ваши активные записи:</b>\n\n"
    keyboard_buttons = []

    for booking in bookings:
        booking_datetime = datetime.fromisoformat(booking['booking_datetime'])
        text += (
            f"<b>Запись №{booking['id']}</b>\n"
            f"Услуга: {booking['service_name']}\n"
            f"Мастер: {booking['master_name']}\n"
            f"Когда: {booking_datetime.strftime('%d.%m.%Y в %H:%M')}\n\n"
        )
        keyboard_buttons.append([InlineKeyboardButton(
            text=f"❌ Отменить запись №{booking['id']}", 
            callback_data=f"cancel_booking:{booking['id']}"
        )])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(text, reply_markup=reply_markup)

@router.callback_query(F.data.startswith("cancel_booking:"))
async def cancel_booking_callback(callback: CallbackQuery, db_manager, config: dict, admin_bot: Bot):
    """Обрабатывает отмену записи пользователем."""
    booking_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    # Проверяем, что пользователь отменяет свою запись
    booking = db_manager.get_booking_by_id(booking_id)
    if not booking or booking['user_id'] != user_id:
        await callback.answer("Это не ваша запись.", show_alert=True)
        return

    # Отменяем запись в БД
    if db_manager.cancel_booking(booking_id):
        logger.info(f"User {user_id} cancelled booking {booking_id}")
        success_message = config.get('messages', {}).get('booking_cancelled', "Запись отменена.")
        await callback.message.edit_text(success_message)
        
        # Опционально: уведомление администратора об отмене
        admin_ids = config.get('admin_ids', [])
        if admin_ids:
            booking_datetime = datetime.fromisoformat(booking['booking_datetime'])
            user_info = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.full_name
            admin_text = (
                f"🅾️ <b>ОТМЕНА ЗАПИСИ</b> 🅾️\n\n"
                f"Клиент {user_info} отменил запись №{booking_id}.\n"
                f"Услуга: {booking['service_name']}\n"
                f"Мастер: {booking['master_name']}\n"
                f"Время: {booking_datetime.strftime('%d.%m.%Y в %H:%M')}"
            )
            notification_bot = admin_bot if admin_bot else callback.bot
            for admin_id in admin_ids:
                try:
                    await notification_bot.send_message(admin_id, admin_text)
                except Exception as e:
                    logger.error(f"Failed to send cancellation notification to admin {admin_id}: {e}")

    else:
        error_message = config.get('messages', {}).get('error_generic', "Произошла ошибка.")
        await callback.message.answer(error_message)
    
    await callback.answer()
