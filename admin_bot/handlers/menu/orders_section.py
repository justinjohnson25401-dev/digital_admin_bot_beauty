"""
Обработчики раздела Заказы (нижняя клавиатура).
"""

from datetime import datetime, timedelta

from aiogram import F
from aiogram.types import Message, BufferedInputFile
from aiogram.fsm.context import FSMContext


async def reply_stats_handler(message: Message, state: FSMContext, config: dict, db_manager):
    """Подробная статистика"""
    stats_today = db_manager.get_stats('today')
    stats_week = db_manager.get_stats('week')
    stats_month = db_manager.get_stats('month')

    text = (
        f"📊 <b>СТАТИСТИКА</b>\n\n"
        f"📅 Сегодня ({datetime.now().strftime('%d.%m.%Y')}):\n"
        f"├ Заказов: {stats_today['total_orders']}\n"
        f"└ Выручка: {stats_today['total_revenue']}₽\n\n"
        f"📅 Эта неделя:\n"
        f"├ Заказов: {stats_week['total_orders']}\n"
        f"└ Выручка: {stats_week['total_revenue']}₽\n\n"
        f"📅 Этот месяц:\n"
        f"├ Заказов: {stats_month['total_orders']}\n"
        f"└ Выручка: {stats_month['total_revenue']}₽\n\n"
        f"🏆 Топ услуги (месяц):\n"
    )
    for i, (service, count) in enumerate(stats_month['top_services'][:5], 1):
        text += f"{i}. {service} ({count} шт.)\n"

    await message.answer(text)


async def reply_orders_today_handler(message: Message, db_manager, config: dict):
    """Заказы на сегодня"""
    tz_offset = config.get('timezone_offset_hours')
    tz_modifier = f"{int(tz_offset):+d} hours" if tz_offset else "localtime"

    cursor = db_manager.connection.cursor()
    cursor.execute("""
        SELECT id, service_name, booking_date, booking_time, client_name, phone, price
        FROM orders WHERE status = 'active' AND booking_date = date('now', ?)
        ORDER BY booking_time LIMIT 10
    """, (tz_modifier,))
    orders = cursor.fetchall()

    text = f"📅 <b>Заказы на сегодня</b> ({datetime.now().strftime('%d.%m.%Y')})\n\n"
    if not orders:
        text += "<i>Нет заказов</i>"
    else:
        for oid, service, date, time, name, phone, price in orders:
            text += f"#{oid} — {time or '?'}\n└ {service} ({price}₽) — {name}\n\n"

    await message.answer(text)


async def reply_orders_tomorrow_handler(message: Message, db_manager, config: dict):
    """Заказы на завтра"""
    tz_offset = config.get('timezone_offset_hours')
    tz_modifier = f"{int(tz_offset):+d} hours" if tz_offset else "localtime"

    cursor = db_manager.connection.cursor()
    cursor.execute("""
        SELECT id, service_name, booking_date, booking_time, client_name, phone, price
        FROM orders WHERE status = 'active' AND booking_date = date('now', ?, '+1 day')
        ORDER BY booking_time LIMIT 10
    """, (tz_modifier,))
    orders = cursor.fetchall()

    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
    text = f"📅 <b>Заказы на завтра</b> ({tomorrow})\n\n"
    if not orders:
        text += "<i>Нет заказов</i>"
    else:
        for oid, service, date, time, name, phone, price in orders:
            text += f"#{oid} — {time or '?'}\n└ {service} ({price}₽) — {name}\n\n"

    await message.answer(text)


async def reply_orders_week_handler(message: Message, db_manager, config: dict):
    """Заказы на неделю"""
    tz_offset = config.get('timezone_offset_hours')
    tz_modifier = f"{int(tz_offset):+d} hours" if tz_offset else "localtime"

    cursor = db_manager.connection.cursor()
    cursor.execute("""
        SELECT id, service_name, booking_date, booking_time, client_name, price
        FROM orders WHERE status = 'active'
          AND booking_date >= date('now', ?)
          AND booking_date <= date('now', ?, '+7 days')
        ORDER BY booking_date, booking_time LIMIT 15
    """, (tz_modifier, tz_modifier))
    orders = cursor.fetchall()

    text = f"📅 <b>Заказы на неделю</b>\n\n"
    if not orders:
        text += "<i>Нет заказов</i>"
    else:
        for oid, service, date, time, name, price in orders:
            try:
                date_fmt = datetime.fromisoformat(date).strftime('%d.%m')
            except:
                date_fmt = date
            text += f"#{oid} — {date_fmt} {time or ''}\n└ {service} ({price}₽)\n\n"

    await message.answer(text)


async def reply_csv_handler(message: Message, db_manager):
    """Выгрузить CSV"""
    try:
        csv_data = db_manager.get_orders_csv(days=30)
        filename = f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        document = BufferedInputFile(csv_data, filename=filename)
        await message.answer_document(document, caption="📥 Заказы за последние 30 дней")
    except Exception as e:
        await message.answer(f"❌ Ошибка экспорта: {e}")


def register_handlers(dp):
    """Регистрация обработчиков раздела Заказы"""
    dp.message.register(reply_stats_handler, F.text == "📊 Статистика")
    dp.message.register(reply_orders_today_handler, F.text == "📅 Сегодня")
    dp.message.register(reply_orders_tomorrow_handler, F.text == "📅 Завтра")
    dp.message.register(reply_orders_week_handler, F.text == "📅 Неделя")
    dp.message.register(reply_csv_handler, F.text == "📥 CSV")
