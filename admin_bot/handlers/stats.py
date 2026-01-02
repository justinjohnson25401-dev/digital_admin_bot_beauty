"""
Обработчики статистики.
"""

import logging
from datetime import datetime, timedelta

from aiogram import F
from aiogram.types import CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)


async def admin_stats_handler(callback: CallbackQuery, config: dict, db_manager):
    """Обработчик статистики"""
    stats_today = db_manager.get_stats('today')
    stats_week = db_manager.get_stats('week')
    stats_month = db_manager.get_stats('month')

    text = (
        f"📊 <b>Статистика</b>\n\n"
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

    await callback.message.edit_text(text)
    await callback.answer()


async def admin_stats_period_handler(callback: CallbackQuery, config: dict, db_manager):
    """Статистика за выбранный период"""
    try:
        _, period = callback.data.split(":", 1)
    except ValueError:
        period = "today"

    today = datetime.now().date()
    if period == "today":
        title = f"📊 Статистика за сегодня ({today.strftime('%d.%m.%Y')})"
        start_date, end_date = today.isoformat(), today.isoformat()
    elif period == "tomorrow":
        tomorrow = today + timedelta(days=1)
        title = f"📊 Статистика на завтра ({tomorrow.strftime('%d.%m.%Y')})"
        start_date, end_date = tomorrow.isoformat(), tomorrow.isoformat()
    elif period == "week":
        week_end = today + timedelta(days=7)
        title = f"📊 Статистика за неделю ({today.strftime('%d.%m')} - {week_end.strftime('%d.%m.%Y')})"
        start_date, end_date = today.isoformat(), week_end.isoformat()
    else:
        title = "📊 Статистика (все будущие заказы)"
        start_date, end_date = today.isoformat(), (today + timedelta(days=365)).isoformat()

    cursor = db_manager.connection.cursor()
    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(price), 0), COUNT(DISTINCT user_id)
        FROM orders WHERE booking_date >= ? AND booking_date <= ? AND status = 'active'
    """, (start_date, end_date))

    row = cursor.fetchone()
    total_orders, total_revenue, unique_clients = row[0] or 0, row[1] or 0, row[2] or 0
    avg_check = int(total_revenue / total_orders) if total_orders > 0 else 0

    text = f"{title}\n\n📦 Заказов: {total_orders}\n💰 Выручка: {total_revenue}₽\n📈 Средний чек: {avg_check}₽\n👥 Уникальных клиентов: {unique_clients}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к заказам", callback_data=f"admin_orders_page:{period}:0")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def admin_export_csv_handler(callback: CallbackQuery, config: dict, db_manager):
    """Экспорт заказов в CSV"""
    try:
        csv_data = db_manager.get_orders_csv(days=30)
        filename = f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        document = BufferedInputFile(csv_data, filename=filename)
        await callback.message.answer_document(document, caption="📥 Заказы за последние 30 дней")

        try:
            await callback.message.delete()
        except Exception:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К записям", callback_data="admin_orders")]])
            try:
                await callback.message.edit_text("✅ CSV файл отправлен выше 👆", reply_markup=keyboard)
            except Exception:
                pass

        await callback.answer("✅ Файл отправлен")
    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        await callback.answer("❌ Ошибка экспорта", show_alert=True)


def register_handlers(dp):
    """Регистрация обработчиков статистики"""
    dp.callback_query.register(admin_stats_handler, F.data == "admin_stats")
    dp.callback_query.register(admin_stats_period_handler, F.data.startswith("admin_stats_period:"))
    dp.callback_query.register(admin_export_csv_handler, F.data == "admin_export_csv")
