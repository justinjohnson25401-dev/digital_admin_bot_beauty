"""
Обработчик для просмотра и управления записями пользователя.
"""

import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

mybookings_router = Router()


@mybookings_router.message(F.text == "📋 Мои записи")
async def show_my_bookings(message: Message, state: FSMContext, db_manager):
    await state.clear() # Сбрасываем состояние на всякий случай
    user_id = message.from_user.id
    bookings = db_manager.get_user_bookings(user_id)

    now = datetime.now()
    upcoming_bookings = sorted([b for b in bookings if datetime.fromisoformat(b['booking_datetime']) > now], key=lambda b: b['booking_datetime'])
    past_bookings = sorted([b for b in bookings if datetime.fromisoformat(b['booking_datetime']) <= now], key=lambda b: b['booking_datetime'], reverse=True)

    if not upcoming_bookings and not past_bookings:
        await message.answer("У вас еще нет записей.")
        return

    text = "<b>📋 Мои записи</b>\n\n"
    keyboard_buttons = []

    if upcoming_bookings:
        text += "<b>Актуальные:</b>\n"
        for b in upcoming_bookings:
            dt = datetime.fromisoformat(b['booking_datetime'])
            text += f"• {dt.strftime('%d.%m.%Y в %H:%M')} - {b['service_name']}\n"
            keyboard_buttons.append([InlineKeyboardButton(text=f"Отменить запись на {dt.strftime('%d.%m %H:%M')}", callback_data=f"cancel_booking:{b['id']}")])
        text += "\n"

    if past_bookings:
        text += "<b>Прошедшие:</b>\n"
        for b in past_bookings[:5]: # Показываем последние 5
            dt = datetime.fromisoformat(b['booking_datetime'])
            text += f"• {dt.strftime('%d.%m.%Y в %H:%M')} - {b['service_name']}\n"
        text += "\n"
        
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main_menu_from_bookings")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons))

@mybookings_router.callback_query(F.data.startswith("cancel_booking:"))
async def confirm_cancel_booking(callback: CallbackQuery, state: FSMContext):
    booking_id = callback.data.split(":")[1]
    await state.update_data(booking_to_cancel=booking_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, отменить", callback_data="confirm_cancel")],
        [InlineKeyboardButton(text="Нет, оставить", callback_data="keep_booking")]
    ])
    await callback.message.edit_text("Вы уверены, что хотите отменить эту запись?", reply_markup=keyboard)
    await callback.answer()

@mybookings_router.callback_query(F.data == "confirm_cancel")
async def process_cancel_booking(callback: CallbackQuery, state: FSMContext, db_manager, config: dict, admin_bot: Bot):
    data = await state.get_data()
    booking_id = data.get('booking_to_cancel')
    if not booking_id:
        await callback.answer("Ошибка: не найдена запись для отмены.", show_alert=True)
        return

    booking = db_manager.get_booking_by_id(booking_id)
    success = db_manager.cancel_booking(booking_id)

    if success:
        await callback.message.edit_text("✅ Запись успешно отменена.")
        
        admin_chat_id = config.get('notifications', {}).get('admin_chat_id')
        notification_bot = admin_bot if admin_bot else callback.bot

        if admin_chat_id and booking:
            try:
                user = callback.from_user
                user_mention = f"@{user.username}" if user.username else user.full_name
                dt = datetime.fromisoformat(booking['booking_datetime'])
                
                text = (
                    f"‼️ <b>ОТМЕНА ЗАПИСИ</b> ‼️\n\n"
                    f"Пользователь {user_mention} (ID: `{user.id}`) отменил свою запись.\n\n"
                    f"<b>Услуга:</b> {booking['service_name']}\n"
                    f"<b>Мастер:</b> {booking.get('master_name', 'Любой')}\n"
                    f"<b>Дата и время:</b> {dt.strftime('%d.%m.%Y в %H:%M')}"
                )
                
                await notification_bot.send_message(admin_chat_id, text)
            except Exception as e:
                logger.error(f"Failed to send cancellation notification to admin: {e}")
    else:
        await callback.message.edit_text("❌ Не удалось отменить запись. Пожалуйста, свяжитесь с нами.")

    await state.clear()
    await callback.answer()

@mybookings_router.callback_query(F.data == "keep_booking")
async def keep_booking_after_prompt(callback: CallbackQuery, state: FSMContext, db_manager):
    await callback.message.delete() # Удаляем сообщение с подтверждением
    await show_my_bookings(callback.message, state, db_manager) # Показываем список записей снова
    await callback.answer()
    
@mybookings_router.callback_query(F.data == "back_to_main_menu_from_bookings")
async def back_to_main_menu_from_bookings(callback: CallbackQuery, state: FSMContext, config: dict):
    """Возврат в главное меню через inline-кнопку из my_bookings"""
    from handlers.start import get_main_keyboard
    await state.clear()
    business_name = config.get('business_name', 'наш бизнес')
    await callback.message.answer(f"🏠 Главное меню «{business_name}»", reply_markup=get_main_keyboard())
    await callback.answer()