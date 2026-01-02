"""
Обработчик детальной карточки заказа.
"""

from datetime import datetime

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton


async def admin_order_detail_handler(callback: CallbackQuery, config: dict, db_manager):
    """Детальная карточка заказа"""
    try:
        _, order_id_str, period, page_str = callback.data.split(":", 3)
        order_id = int(order_id_str)
        page = int(page_str)
    except Exception:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        return

    order = db_manager.get_order_by_id(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    user_id = order.get('user_id')
    history = db_manager.get_user_bookings(user_id, active_only=False) if user_id else []
    visits = len(history)

    booking_date = order.get('booking_date')
    try:
        date_fmt = datetime.fromisoformat(booking_date).strftime('%d.%m.%Y') if booking_date else "не указана"
    except Exception:
        date_fmt = booking_date or "не указана"

    time_str = order.get('booking_time') or "не указано"
    comment = order.get('comment')
    comment_text = comment.strip() if isinstance(comment, str) and comment.strip() else "—"

    text = (
        f"🧾 <b>Заказ #{order_id}</b>\n\n"
        f"📅 Дата: {date_fmt}\n"
        f"🕐 Время: {time_str}\n"
        f"💇 Услуга: {order.get('service_name')}\n"
        f"💰 Цена: {order.get('price')}₽\n"
        f"👤 Клиент: {order.get('client_name')}\n"
        f"📞 Телефон: {order.get('phone')}\n"
        f"📝 Комментарий: {comment_text}\n\n"
        f"📚 История клиента: {visits} заказ(ов) всего\n"
    )

    if history:
        text += "\nПоследние записи:\n"
        for b in history[:5]:
            bd = b.get('booking_date') or ""
            bt = b.get('booking_time') or ""
            try:
                bd_fmt = datetime.fromisoformat(bd).strftime('%d.%m.%Y') if bd else ""
            except Exception:
                bd_fmt = bd
            text += f"• #{b.get('id')} — {bd_fmt} {bt} — {b.get('service_name')} ({b.get('price')}₽)\n"

    keyboard_rows = []
    if user_id:
        keyboard_rows.append([InlineKeyboardButton(
            text="📚 История клиента",
            callback_data=f"admin_client_history:{user_id}:0:{period}:{page}:{order_id}"
        )])
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад к списку", callback_data=f"admin_orders_page:{period}:{page}")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows))
    await callback.answer()


def register_handlers(dp):
    """Регистрация обработчика деталей заказа"""
    dp.callback_query.register(admin_order_detail_handler, F.data.startswith("admin_order:"))
