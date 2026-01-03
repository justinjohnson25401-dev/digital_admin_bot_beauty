"""
Обработчики для подтверждения записи.
"""

import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states.booking import BookingState

logger = logging.getLogger(__name__)

router = Router()

async def show_confirmation(message: Message, state: FSMContext):
    """Отображает сводку по бронированию для подтверждения."""
    data = await state.get_data()
    booking_datetime = datetime.fromisoformat(data.get('booking_datetime'))
    
    summary_text = (
        f"<b>Подтвердите вашу запись:</b>\n\n"
        f"<b>Услуга:</b> {data.get('service_name')}\n"
        f"<b>Мастер:</b> {data.get('master_name', 'Любой')}\n"
        f"<b>Дата и время:</b> {booking_datetime.strftime('%d.%m.%Y в %H:%M')}\n"
        f"<b>Цена:</b> {data.get('price')}\n\n"
        f"<b>Ваши данные:</b>\n"
        f"<b>Имя:</b> {data.get('name')}\n"
        f"<b>Телефон:</b> {data.get('phone')}\n"
    )
    if data.get('comment'):
        summary_text += f"<b>Комментарий:</b> {data.get('comment')}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить и записаться", callback_data="confirm_booking")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")]
    ])
    
    await message.answer(summary_text, reply_markup=keyboard)
    await state.set_state(BookingState.confirmation)

@router.callback_query(BookingState.confirmation, F.data == "confirm_booking")
async def confirm_booking_callback(callback: CallbackQuery, state: FSMContext, db_manager, config: dict, admin_bot: Bot):
    """Сохраняет бронирование в БД, уведомляет пользователя и администратора."""
    user_id = callback.from_user.id
    data = await state.get_data()
    
    try:
        booking_id = db_manager.create_booking(
            user_id=user_id,
            service_id=data.get('service_id'),
            service_name=data.get('service_name'),
            master_id=data.get('master_id'),
            master_name=data.get('master_name'),
            booking_datetime=data.get('booking_datetime'),
            price=data.get('price'),
            comment=data.get('comment')
        )

        if not booking_id:
            raise ValueError("Booking creation returned no ID")

        logger.info(f"User {user_id} confirmed booking {booking_id}")

        # Форматируем сообщение об успехе
        success_template = config.get('messages', {}).get('success', "✅ Запись №{id} подтверждена!")
        booking_datetime = datetime.fromisoformat(data.get('booking_datetime'))
        
        format_data = {
            'id': booking_id,
            'date': booking_datetime.strftime('%d.%m.%Y'),
            'time': booking_datetime.strftime('%H:%M'),
            'address': config.get('contacts', {}).get('address', ''),
            'business_name': config.get('business_name', '')
        }
        
        success_message = success_template.format(**format_data)
        await callback.message.edit_text(success_message)

        # Уведомление администратора (если настроено)
        await notify_admin_on_booking(callback, data, booking_id, config, admin_bot)

    except ValueError:
        # Обработка ситуации, когда слот уже занят (race condition)
        logger.warning(f"User {user_id} tried to book an already taken slot.")
        error_msg = config.get('messages', {}).get('slot_taken', "К сожалению, это время уже занято.")
        await callback.message.edit_text(error_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Выбрать другое время", callback_data="back_to_time_selection")]
        ]))
    
    except Exception as e:
        # Обработка других непредвиденных ошибок
        logger.error(f"An unexpected error occurred during booking confirmation: {e}", exc_info=True)
        error_msg = config.get('messages', {}).get('error_generic', "❌ Произошла ошибка при записи.")
        await callback.message.edit_text(error_msg)

    finally:
        # Очищаем состояние только в случае успеха или полной отмены
        if 'booking_id' in locals() and booking_id:
            await state.clear()
        await callback.answer()

async def notify_admin_on_booking(callback: CallbackQuery, data: dict, booking_id: int, config: dict, admin_bot: Bot):
    """Отправляет уведомление администраторам о новой записи."""
    admin_ids = config.get('admin_ids', [])
    if not admin_ids:
        return

    notification_bot = admin_bot if admin_bot else callback.bot
    user = callback.from_user
    user_mention = f"@{user.username}" if user.username else user.full_name
    booking_datetime = datetime.fromisoformat(data.get('booking_datetime'))

    admin_text = (
        f"🔔 <b>НОВАЯ ЗАПИСЬ</b> 🔔\n\n"
        f"<b>Клиент:</b> {data.get('name')}, {user_mention} (ID: `{user.id}`)\n"
        f"<b>Телефон:</b> `{data.get('phone')}`\n\n"
        f"<b>Услуга:</b> {data.get('service_name')}\n"
        f"<b>Мастер:</b> {data.get('master_name', 'Любой')}\n"
        f"<b>Дата и время:</b> {booking_datetime.strftime('%d.%m.%Y в %H:%M')}\n"
    )
    if data.get('comment'):
        admin_text += f"<b>Комментарий:</b> {data.get('comment')}\n"
    
    try:
        for admin_id in admin_ids:
            await notification_bot.send_message(admin_id, admin_text)
    except Exception as e:
        logger.error(f"Failed to send booking notification to admin {admin_id}: {e}")


@router.callback_query(BookingState.confirmation, F.data == "cancel_booking_process")
async def cancel_booking_process_callback(callback: CallbackQuery, state: FSMContext, config: dict):
    """Отменяет процесс бронирования на этапе подтверждения."""
    await state.clear()
    cancel_message = config.get('messages', {}).get('booking_cancelled', "Запись отменена.")
    await callback.message.edit_text(cancel_message)
    await callback.answer()
