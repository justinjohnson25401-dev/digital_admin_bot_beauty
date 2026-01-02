
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
import logging
from datetime import datetime

from .keyboards import get_cancel_confirmation_keyboard, format_time
from utils.notify import get_client_history_text

logger = logging.getLogger(__name__)

router = Router()


async def notify_admin_about_cancellation(bot, admin_ids: list, order: dict, business_name: str, db_manager):
    """Уведомление администраторов об отмене"""
    formatted_time = format_time(order.get('booking_time', ''))

    message_text = (
        f"❌ Отмена записи в {business_name}\n\n"
        f"ID заявки: #{order['id']}\n"
        f"Услуга: {order['service_name']}\n"
        f"Дата: {order['booking_date']}\n"
        f"Время: {formatted_time}\n"
        f"Клиент: {order['client_name']}\n"
        f"Телефон: {order['phone']}\n"
    )

    history_text = get_client_history_text(db_manager, order['user_id'], order['id'])
    if history_text:
        message_text += f"\n{history_text}"

    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, message_text)
            logger.info(f"Cancellation notification sent to admin {admin_id}")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id} about cancellation: {e}")


@router.callback_query(F.data.startswith("cancel_order:"))
async def cancel_order_handler(callback: CallbackQuery, db_manager):
    """Запрос подтверждения отмены записи."""
    order_id = int(callback.data.split(":")[1])
    order = db_manager.get_order_by_id(order_id)

    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    try:
        date_obj = datetime.fromisoformat(order['booking_date'])
        date_formatted = date_obj.strftime('%d.%m.%Y')
    except (ValueError, TypeError):
        date_formatted = order['booking_date']

    time_formatted = format_time(order.get('booking_time', 'не указано'))
    
    text = (
        f"⚠️ Вы уверены, что хотите отменить запись?\n\n"
        f"📋 Услуга: {order['service_name']}\n"
        f"📅 Дата: {date_formatted}\n"
        f"🕐 Время: {time_formatted}\n\n"
        f"Это действие нельзя отменить."
    )

    keyboard = get_cancel_confirmation_keyboard(order_id)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_cancel:"))
async def confirm_cancel_order_handler(callback: CallbackQuery, config: dict, db_manager, messages: dict, admin_bot=None, scheduler=None):
    """Подтверждение и выполнение отмены записи."""
    order_id = int(callback.data.split(":")[1])
    order = db_manager.get_order_by_id(order_id)

    if not order or order['user_id'] != callback.from_user.id or order['status'] != 'active':
        await callback.answer("Заказ не найден или уже отменён.", show_alert=True)
        return

    success = db_manager.cancel_order(order_id)
    if not success:
        await callback.answer("Ошибка отмены заказа", show_alert=True)
        return

    if scheduler:
        try:
            scheduler.cancel_reminders(order_id)
        except Exception as e:
            logger.error(f"Error cancelling reminders: {e}")

    if config.get('features', {}).get('enable_admin_notify', True):
        notify_bot = admin_bot if admin_bot else callback.message.bot
        await notify_admin_about_cancellation(
            bot=notify_bot,
            admin_ids=config['admin_ids'],
            order=order,
            business_name=config['business_name'],
            db_manager=db_manager
        )
    
    formatted_time = format_time(order.get('booking_time', ''))
    cancel_msg = messages.get('booking_cancelled', 'Запись отменена.')
    await callback.message.edit_text(
        f"{cancel_msg}\n\n"
        f"Отменённая запись:\n"
        f"• {order['service_name']}\n"
        f"• {order['booking_date']} {formatted_time}"
    )

    logger.info(f"Order {order_id} cancelled by user {callback.from_user.id}")
    await callback.answer()
