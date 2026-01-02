"""
Обработчики выбора диапазона дат.
"""

from datetime import datetime

from aiogram import F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from admin_bot.states import AdminOrdersStates


async def admin_orders_custom_range_handler(callback: CallbackQuery, state: FSMContext):
    """Начать выбор диапазона дат"""
    await callback.message.edit_text(
        "📝 <b>Выбор диапазона дат</b>\n\n"
        "Введите дату <b>начала</b> периода в формате ДД.ММ.ГГГГ\n"
        "Например: 01.01.2025",
        parse_mode="HTML"
    )
    await state.set_state(AdminOrdersStates.input_date_from)
    await callback.answer()


def _parse_date(text: str):
    """Парсинг даты в различных форматах"""
    date_formats = ['%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']
    for fmt in date_formats:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


async def process_date_from(message: Message, state: FSMContext):
    """Обработка даты начала периода"""
    date_from = _parse_date(message.text)

    if not date_from:
        await message.answer("❌ Неверный формат даты.\n\nВведите дату в формате ДД.ММ.ГГГГ\nНапример: 01.01.2025")
        return

    await state.update_data(date_from=date_from.isoformat())
    await message.answer(
        f"✅ Начало периода: <b>{date_from.strftime('%d.%m.%Y')}</b>\n\n"
        "Теперь введите дату <b>конца</b> периода в формате ДД.ММ.ГГГГ\n"
        "Например: 31.01.2025",
        parse_mode="HTML"
    )
    await state.set_state(AdminOrdersStates.input_date_to)


async def process_date_to(message: Message, state: FSMContext, db_manager):
    """Обработка даты конца периода и показ заказов"""
    date_to = _parse_date(message.text)

    if not date_to:
        await message.answer("❌ Неверный формат даты.\n\nВведите дату в формате ДД.ММ.ГГГГ\nНапример: 31.01.2025")
        return

    data = await state.get_data()
    date_from = datetime.fromisoformat(data.get('date_from')).date()

    if date_to < date_from:
        await message.answer("❌ Дата конца не может быть раньше даты начала. Введите корректную дату:")
        return

    await state.clear()

    cursor = db_manager.connection.cursor()
    cursor.execute("""
        SELECT id, service_name, price, booking_date, booking_time, client_name
        FROM orders
        WHERE status = 'active' AND booking_date >= ? AND booking_date <= ?
        ORDER BY booking_date, booking_time
    """, (date_from.isoformat(), date_to.isoformat()))
    orders = cursor.fetchall()

    result_text = f"📋 <b>Заказы за период</b>\n📅 {date_from.strftime('%d.%m.%Y')} — {date_to.strftime('%d.%m.%Y')}\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if not orders:
        result_text += "<i>Заказов за этот период нет</i>"
    else:
        total_revenue = 0
        for order_id, service_name, price, booking_date, booking_time, client_name in orders:
            try:
                bd_fmt = datetime.fromisoformat(booking_date).strftime('%d.%m.%Y')
            except:
                bd_fmt = booking_date
            result_text += f"#{order_id} | {bd_fmt} {booking_time or ''}\n├ {service_name} — {price}₽\n└ {client_name}\n\n"
            total_revenue += price or 0

        result_text += f"━━━━━━━━━━━━━━━━━━━━━━\n📊 Всего: {len(orders)} заказов | 💰 {total_revenue}₽"

    await message.answer(result_text, parse_mode="HTML")


def register_handlers(dp):
    """Регистрация обработчиков диапазона дат"""
    dp.callback_query.register(admin_orders_custom_range_handler, F.data == "admin_orders_custom_range")
    dp.message.register(process_date_from, AdminOrdersStates.input_date_from)
    dp.message.register(process_date_to, AdminOrdersStates.input_date_to)
