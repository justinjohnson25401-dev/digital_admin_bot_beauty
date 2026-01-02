"""
Обработчики для работы с клиентами.
"""

from datetime import datetime

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton


async def admin_clients_handler(callback: CallbackQuery, config: dict, db_manager):
    """Обработчик базы клиентов"""
    cursor = db_manager.connection.cursor()
    cursor.execute("""
        SELECT COUNT(DISTINCT user_id) FROM orders
    """)
    total_clients = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT
            o.user_id,
            COUNT(o.id) as orders_count,
            u.username,
            u.first_name,
            u.last_name,
            (
                SELECT oo.phone
                FROM orders oo
                WHERE oo.user_id = o.user_id
                ORDER BY oo.created_at DESC
                LIMIT 1
            ) AS last_phone
        FROM orders o
        LEFT JOIN users u ON u.user_id = o.user_id
        GROUP BY o.user_id
        ORDER BY orders_count DESC
        LIMIT 10
        """
    )

    top_clients = cursor.fetchall()

    text = (
        f"👥 <b>База клиентов</b>\n\n"
        f"Всего клиентов: {total_clients}\n\n"
        f"🏆 Топ-10 клиентов:\n"
    )

    for i, (user_id, count, username, first_name, last_name, last_phone) in enumerate(top_clients, 1):
        full_name = " ".join([p for p in [first_name, last_name] if p])
        display_name = full_name or (f"@{username}" if username else f"ID {user_id}")

        text += f"{i}. {display_name} — {count} заказов\n"
        text += f"   ID: {user_id}\n"
        if username:
            text += f"   Username: @{username}\n"
            text += f"   Ссылка: https://t.me/{username}\n"
        if last_phone:
            text += f"   Телефон: {last_phone}\n"
        text += "\n"

    await callback.message.edit_text(text)
    await callback.answer()


async def admin_client_history_handler(callback: CallbackQuery, config: dict, db_manager):
    """Полная история клиента с пагинацией"""
    try:
        _, user_id_str, page_str, return_period, return_page_str, return_order_id_str = callback.data.split(":", 5)
        user_id = int(user_id_str)
        page = int(page_str)
        return_page = int(return_page_str)
        return_order_id = int(return_order_id_str)
    except Exception:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        return

    page_size = 5
    if page < 0:
        page = 0

    history = db_manager.get_user_bookings(user_id, active_only=False)
    total = len(history)
    offset = page * page_size
    items = history[offset: offset + page_size]

    text = f"📚 <b>История клиента</b>\n\nВсего заказов: {total}\n\n"
    if not items:
        text += "Нет данных для отображения."
    else:
        start_n = offset + 1
        end_n = min(offset + len(items), total)
        text += f"Показано: {start_n}-{end_n} из {total}\n\n"
        for b in items:
            bd = b.get('booking_date')
            bt = b.get('booking_time')
            try:
                bd_fmt = datetime.fromisoformat(bd).strftime('%d.%m.%Y') if bd else ""
            except Exception:
                bd_fmt = bd or ""
            comment = b.get('comment')
            comment_text = comment.strip() if isinstance(comment, str) and comment.strip() else "—"
            text += (
                f"#{b.get('id')} — {bd_fmt} {bt or ''}\n"
                f"├ {b.get('service_name')} ({b.get('price')}₽)\n"
                f"└ Комментарий: {comment_text}\n\n"
            )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"admin_client_history:{user_id}:{page-1}:{return_period}:{return_page}:{return_order_id}"
        ))
    if (offset + page_size) < total:
        nav.append(InlineKeyboardButton(
            text="➡️ Далее",
            callback_data=f"admin_client_history:{user_id}:{page+1}:{return_period}:{return_page}:{return_order_id}"
        ))

    keyboard_rows = []
    if nav:
        keyboard_rows.append(nav)
    keyboard_rows.append([
        InlineKeyboardButton(text="🔙 Назад к заказу", callback_data=f"admin_order:{return_order_id}:{return_period}:{return_page}")
    ])
    keyboard_rows.append([
        InlineKeyboardButton(text="🔙 Назад к списку", callback_data=f"admin_orders_page:{return_period}:{return_page}")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


def register_handlers(dp):
    """Регистрация обработчиков клиентов"""
    dp.callback_query.register(admin_clients_handler, F.data == "admin_clients")
    dp.callback_query.register(admin_client_history_handler, F.data.startswith("admin_client_history:"))
