
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from datetime import datetime
from utils.db import DatabaseManager

logger = logging.getLogger(__name__)

def format_time(time_str: str) -> str:
    """Форматирует время в HH:MM формат"""
    if not time_str or ':' in time_str:
        return time_str or "не указано"
    try:
        return f"{int(time_str):02d}:00"
    except (ValueError, TypeError):
        return time_str

# НОВОЕ: Функция для получения истории клиента (ошибка #3)
def get_client_history_text(db_manager: DatabaseManager, user_id: int, current_order_id: int, limit: int = 5) -> str:
    """Получает текст с историей заказов клиента"""
    try:
        # Получаем все заказы клиента (не только активные)
        all_bookings = db_manager.bookings.get_user_bookings(user_id, active_only=False)
        
        if not all_bookings or len(all_bookings) <= 1:
            return ""  # Нет истории (первый заказ)
        
        history_text = "📜 История клиента:\n"
        
        count = 0
        for booking in all_bookings:
            if count >= limit:
                break
            
            # Форматируем дату
            try:
                date_obj = datetime.fromisoformat(booking['booking_date'])
                date_formatted = date_obj.strftime('%d.%m.%Y')
            except (ValueError, TypeError):
                date_formatted = booking['booking_date']
            
            # Форматируем время
            time_formatted = format_time(booking.get('booking_time', ''))
            
            # Статус эмодзи
            if booking['id'] == current_order_id:
                status_emoji = "🆕"
            elif booking['status'] == 'active':
                status_emoji = "✅"
            elif booking['status'] == 'cancelled':
                status_emoji = "❌"
            elif booking['status'] == 'completed':
                status_emoji = "✔️"
            else:
                status_emoji = "❓"
            
            history_text += f"  • Заказ #{booking['id']}: {booking['service_name']} ({date_formatted} {time_formatted}) {status_emoji}\n"
            count += 1
        
        # Добавляем комментарий текущего заказа, если есть
        current_booking = next((b for b in all_bookings if b['id'] == current_order_id), None)
        if current_booking and current_booking.get('comment'):
            history_text += f"\n💬 Комментарий:\n└ \"{current_booking['comment']}\"\n"
        
        return history_text
        
    except Exception as e:
        logger.error(f"Error getting client history: {e}")
        return ""

# ИЗМЕНЕНО: Добавлен параметр db_manager для истории клиента (ошибка #3, #7)
async def send_order_to_admins(bot: Bot, admin_ids: list, order_data: dict, business_name: str, db_manager: DatabaseManager =None):
    """Отправка уведомления о новом заказе администраторам"""
    message_text = (
        f"🔔 Новая заявка в {business_name}\n\n"
        f"ID заявки: #{order_data['order_id']}\n"
        f"Услуга: {order_data['service_name']}\n"
        f"Цена: {order_data['price']}₽\n"
    )

    # Мастер (если указан)
    if order_data.get('master_name'):
        message_text += f"Мастер: {order_data['master_name']}\n"

    # Дата и время записи
    if order_data.get('booking_date'):
        try:
            date_obj = datetime.fromisoformat(order_data['booking_date'])
            date_formatted = date_obj.strftime('%d.%m.%Y')
            message_text += f"Дата: {date_formatted}\n"
        except (ValueError, TypeError, KeyError):
            message_text += f"Дата: {order_data['booking_date']}\n"

    if order_data.get('booking_time'):
        formatted_time = format_time(order_data['booking_time'])
        message_text += f"Время: {formatted_time}\n"

    message_text += (
        f"\n📋 Контакты:\n"
        f"├ Клиент: {order_data['client_name']}\n"
        f"├ Телефон: {order_data['phone']}\n"
        f"└ Telegram: @{order_data.get('username', 'не указан')}\n"
    )

    # НОВОЕ: Добавляем историю клиента (ошибка #3)
    if db_manager and order_data.get('user_id'):
        history_text = get_client_history_text(db_manager, order_data['user_id'], order_data['order_id'])
        if history_text:
            message_text += f"\n{history_text}"

    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, message_text)
            logger.info(f"Order notification sent to admin {admin_id}")
        except TelegramAPIError as e:
            logger.error(f"Failed to send notification to admin {admin_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending notification to admin {admin_id}: {e}")

# ИЗМЕНЕНО: Добавлен параметр db_manager для истории клиента (ошибка #3, #7)
async def send_order_change_to_admins(bot: Bot, admin_ids: list, old_order: dict, new_order: dict, business_name: str, db_manager: DatabaseManager=None):
    """Отправляет уведомление администраторам об изменении заказа"""
    # Форматируем время
    old_time = format_time(old_order.get('booking_time', ''))
    new_time = format_time(new_order.get('booking_time', ''))

    # Форматируем даты
    old_date = old_order.get('booking_date', 'не указана')
    new_date = new_order.get('booking_date', 'не указана')

    try:
        old_date_obj = datetime.fromisoformat(old_date)
        old_date = old_date_obj.strftime('%d.%m.%Y')
    except (ValueError, TypeError):
        pass

    try:
        new_date_obj = datetime.fromisoformat(new_date)
        new_date = new_date_obj.strftime('%d.%m.%Y')
    except (ValueError, TypeError):
        pass

    message_text = (
        f"⚠️ Изменение заказа в {business_name}\n\n"
        f"ID: #{old_order['id']}\n\n"
        f"Было:\n"
        f"├ {old_order['service_name']}\n"
        f"├ {old_date}\n"
        f"└ {old_time}\n\n"
        f"Стало:\n"
        f"├ {new_order['service_name']}\n"
        f"├ {new_date}\n"
        f"└ {new_time}\n\n"
        f"📋 Контакты:\n"
        f"├ Клиент: {old_order['client_name']}\n"
        f"├ Телефон: {old_order['phone']}\n"
        f"└ Telegram: @{old_order.get('telegram_username', 'не указан')}\n"
    )

    # НОВОЕ: Добавляем историю клиента (ошибка #3)
    if db_manager and old_order.get('user_id'):
        history_text = get_client_history_text(db_manager, old_order['user_id'], old_order['id'])
        if history_text:
            message_text += f"\n{history_text}"

    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, message_text)
            logger.info(f"Order change notification sent to admin {admin_id}")
        except TelegramAPIError as e:
            logger.error(f"Failed to send change notification to admin {admin_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending change notification to admin {admin_id}: {e}")
