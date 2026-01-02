"""
Обработчики списка заказов и пагинации.
"""

from datetime import datetime

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton


async def admin_orders_handler(callback: CallbackQuery, config: dict, db_manager):
    """Заказы на сегодня"""
    await _admin_orders_render(callback, db_manager, config, period="today", page=0)


async def admin_orders_tomorrow_handler(callback: CallbackQuery, config: dict, db_manager):
    """Заказы на завтра"""
    await _admin_orders_render(callback, db_manager, config, period="tomorrow", page=0)


async def admin_orders_week_handler(callback: CallbackQuery, config: dict, db_manager):
    """Заказы на неделю"""
    await _admin_orders_render(callback, db_manager, config, period="week", page=0)


async def admin_orders_all_future_handler(callback: CallbackQuery, config: dict, db_manager):
    """Все будущие заказы"""
    await _admin_orders_render(callback, db_manager, config, period="all_future", page=0)


async def admin_orders_page_handler(callback: CallbackQuery, config: dict, db_manager):
    """Пагинация списка заказов"""
    try:
        _, period, page_str = callback.data.split(":", 2)
        page = max(0, int(page_str))
    except Exception:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        return

    await _admin_orders_render(callback, db_manager, config, period=period, page=page)


def _get_tz_modifier(config: dict) -> str:
    """Получить модификатор часового пояса для SQL"""
    tz_offset = config.get('timezone_offset_hours')
    if tz_offset is None:
        return "localtime"
    try:
        return f"{int(tz_offset):+d} hours"
    except Exception:
        return "localtime"


def _fmt_time(t: str) -> str:
    """Форматирование времени"""
    if not t:
        return "не указано"
    if ":" in t:
        return t
    try:
        return f"{int(t):02d}:00"
    except Exception:
        return t


async def _admin_orders_render(callback: CallbackQuery, db_manager, config: dict, period: str, page: int = 0):
    """Рендеринг списка заказов"""
    cursor = db_manager.connection.cursor()
    tz_modifier = _get_tz_modifier(config)
    page_size = 5
    offset = page * page_size

    def _count(sql: str, params: tuple) -> int:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return int(row[0] or 0) if row else 0

    # Определяем запрос по периоду
    if period == "today":
        title = "📋 <b>Заказы на сегодня</b>"
        where = "status = 'active' AND booking_date = date('now', ?)"
        params = (tz_modifier,)
    elif period == "tomorrow":
        title = "📋 <b>Заказы на завтра</b>"
        where = "status = 'active' AND booking_date = date('now', ?, '+1 day')"
        params = (tz_modifier,)
    elif period == "week":
        title = "📋 <b>Заказы на неделю</b>"
        where = "status = 'active' AND booking_date IS NOT NULL AND booking_date >= date('now', ?) AND booking_date <= date('now', ?, '+7 days')"
        params = (tz_modifier, tz_modifier)
    else:
        title = "📋 <b>Все будущие заказы</b>"
        where = "status = 'active' AND booking_date IS NOT NULL AND booking_date >= date('now', ?)"
        params = (tz_modifier,)

    total = _count(f"SELECT COUNT(*) FROM orders WHERE {where}", params)
    cursor.execute(
        f"SELECT id, service_name, booking_date, booking_time, client_name, phone, price FROM orders WHERE {where} ORDER BY booking_date, booking_time LIMIT ? OFFSET ?",
        params + (page_size, offset)
    )
    orders = cursor.fetchall()

    # Формируем текст
    if not orders:
        text = f"{title}\n\nНет заказов."
    else:
        text = f"{title}\n\nПоказано: {offset + 1}-{min(offset + len(orders), total)} из {total}\n\n"
        for order_id, service, date, time_str, name, phone, price in orders:
            try:
                date_fmt = datetime.fromisoformat(date).strftime('%d.%m.%Y')
            except Exception:
                date_fmt = date or "не указана"
            text += f"#{order_id} — {date_fmt} {_fmt_time(time_str)}\n└ {service} ({price}₽)\n\n"

    # Формируем клавиатуру
    keyboard_rows = [[InlineKeyboardButton(text=f"🔎 Подробнее #{row[0]}", callback_data=f"admin_order:{row[0]}:{period}:{page}")] for row in orders]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_orders_page:{period}:{page-1}"))
    if (offset + page_size) < total:
        nav.append(InlineKeyboardButton(text="➡️ Далее", callback_data=f"admin_orders_page:{period}:{page+1}"))
    if nav:
        keyboard_rows.append(nav)

    keyboard_rows.extend([
        [InlineKeyboardButton(text="📅 Сегодня", callback_data="admin_orders"), InlineKeyboardButton(text="📅 Завтра", callback_data="admin_orders_tomorrow")],
        [InlineKeyboardButton(text="📅 Эта неделя", callback_data="admin_orders_week"), InlineKeyboardButton(text="📆 Все будущие", callback_data="admin_orders_all_future")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data=f"admin_stats_period:{period}"), InlineKeyboardButton(text="📥 CSV", callback_data="admin_export_csv")],
    ])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows))
    await callback.answer()


def register_handlers(dp):
    """Регистрация обработчиков списка заказов"""
    dp.callback_query.register(admin_orders_handler, F.data == "admin_orders")
    dp.callback_query.register(admin_orders_tomorrow_handler, F.data == "admin_orders_tomorrow")
    dp.callback_query.register(admin_orders_week_handler, F.data == "admin_orders_week")
    dp.callback_query.register(admin_orders_all_future_handler, F.data == "admin_orders_all_future")
    dp.callback_query.register(admin_orders_page_handler, F.data.startswith("admin_orders_page:"))
