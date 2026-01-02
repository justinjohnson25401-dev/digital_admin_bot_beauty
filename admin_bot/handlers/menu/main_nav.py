"""
Главная навигация: кнопки главного меню и кнопка Назад.
"""

from datetime import datetime

from aiogram import F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from admin_bot.keyboards import (
    get_admin_reply_keyboard, get_orders_reply_keyboard, get_services_reply_keyboard,
    get_staff_reply_keyboard, get_settings_reply_keyboard, get_clients_reply_keyboard,
)


async def _cancel_with_button(message: Message, state: FSMContext, text: str, callback_data: str):
    """Отмена с кнопкой возврата"""
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback_data)]])
    await message.answer("↩️ Действие отменено", reply_markup=keyboard)


async def reply_back_handler(message: Message, state: FSMContext, config: dict, db_manager):
    """Обработчик кнопки Назад"""
    from admin_bot.states import StaffEditorStates

    current_state = await state.get_state()

    if current_state:
        # Маппинг состояний на действия отмены
        cancel_map = {
            'PromotionStates': ("🎁 К акциям", "promotions_menu"),
            'ServiceEditStates': ("📋 К услугам", "admin_services"),
            'TextsEditorStates': ("📝 К текстам", "texts_menu"),
            'FAQEditorStates': ("📝 К текстам", "texts_menu"),
            'SettingsEditStates': ("⚙️ К настройкам", "admin_settings"),
            'BusinessSettingsStates': ("⚙️ К настройкам", "admin_settings"),
        }

        for state_name, (btn_text, callback) in cancel_map.items():
            if state_name in current_state:
                await _cancel_with_button(message, state, btn_text, callback)
                return

        if current_state == StaffEditorStates.enter_name.state:
            await _cancel_with_button(message, state, "👤 К персоналу", "staff_menu")
            return

        if 'ClosedDatesStates' in current_state:
            await _cancel_with_button(message, state, "👤 К персоналу", "staff_menu")
            return

    # По умолчанию - главное меню
    await state.clear()
    stats = db_manager.get_stats('today')
    planned = f"\n├ Планируемая: {stats.get('planned_revenue', 0)}₽" if stats.get('planned_revenue', 0) > 0 else ""
    text = (
        f"🎯 <b>Админ-панель \"{config.get('business_name', 'Ваш бизнес')}\"</b>\n\n"
        f"📅 Сегодня:\n├ Заказов: {stats['total_orders']}\n├ Выручка: {stats['total_revenue']}₽{planned}\n"
        f"└ Новых клиентов: {stats.get('new_clients', 0)}\n\nИспользуйте кнопки внизу для навигации."
    )
    await message.answer(text, reply_markup=get_admin_reply_keyboard())


async def reply_orders_handler(message: Message, state: FSMContext, config: dict, db_manager):
    """Обработчик кнопки Заказы"""
    await state.clear()
    stats = db_manager.get_stats('today')
    text = f"📅 <b>ЗАКАЗЫ</b>\n\n📊 Сегодня ({datetime.now().strftime('%d.%m.%Y')}):\n├ Заказов: {stats['total_orders']}\n└ Выручка: {stats['total_revenue']}₽\n\nИспользуйте кнопки внизу."
    await message.answer(text, reply_markup=get_orders_reply_keyboard())


async def reply_services_handler(message: Message, state: FSMContext, config_manager):
    """Обработчик кнопки Услуги"""
    await state.clear()
    config = config_manager.get_config()
    services, promotions = config.get('services', []), config.get('promotions', [])
    active_promos = len([p for p in promotions if p.get('active', True)])
    text = f"💼 <b>УСЛУГИ И АКЦИИ</b>\n\n📋 Услуг: {len(services)}\n🎁 Акций: {active_promos} активных\n\nИспользуйте кнопки внизу."
    await message.answer(text, reply_markup=get_services_reply_keyboard())


async def reply_staff_handler(message: Message, state: FSMContext, config: dict):
    """Обработчик кнопки Персонал"""
    await state.clear()
    staff = config.get('staff', {})
    is_enabled, masters = staff.get('enabled', False), staff.get('masters', [])
    status = "✅ Включена" if is_enabled else "❌ Отключена"
    text = f"👤 <b>УПРАВЛЕНИЕ ПЕРСОНАЛОМ</b>\n\nФункция персонала: <b>{status}</b>\n\n"
    if masters:
        text += f"Текущий состав ({len(masters)}):\n\n"
        for m in masters:
            text += f"👤 <b>{m['name']}</b> — {m.get('specialization') or m.get('role', 'Мастер')}\n   📋 Услуг: {len(m.get('services', []))}\n\n"
    else:
        text += "<i>Мастера не добавлены</i>\n\n"
    text += "Используйте кнопки внизу."

    toggle = "🔴 Выключить" if is_enabled else "🟢 Включить"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle, callback_data="toggle_staff")],
        [InlineKeyboardButton(text="🗑 Удалить мастера", callback_data="delete_master_list")],
    ])
    await message.answer(text, reply_markup=get_staff_reply_keyboard())
    await message.answer("Дополнительные действия:", reply_markup=keyboard)


async def reply_settings_handler(message: Message, state: FSMContext, config: dict):
    """Обработчик кнопки Настройки"""
    await state.clear()
    booking = config.get('booking', {})
    text = f"⚙️ <b>НАСТРОЙКИ</b>\n\n📍 Бизнес: {config.get('business_name', 'Не указано')}\n🕐 Часы: {int(booking.get('work_start', 10))}:00 - {int(booking.get('work_end', 20))}:00\n\nИспользуйте кнопки внизу."
    await message.answer(text, reply_markup=get_settings_reply_keyboard())


async def reply_clients_handler(message: Message, state: FSMContext, db_manager):
    """Обработчик кнопки Клиенты"""
    await state.clear()
    cursor = db_manager.connection.cursor()
    cursor.execute("""
        SELECT u.user_id, u.username, u.first_name, u.last_name, COUNT(o.id), COALESCE(SUM(o.price), 0), MAX(o.phone)
        FROM users u LEFT JOIN orders o ON u.user_id = o.user_id AND o.status = 'active'
        GROUP BY u.user_id ORDER BY COUNT(o.id) DESC LIMIT 20
    """)
    clients = cursor.fetchall()

    text = f"👥 <b>КЛИЕНТЫ</b>\n\nВсего: {len(clients)}\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    if not clients:
        text += "<i>Клиентов пока нет</i>"
    else:
        for uid, uname, fname, lname, cnt, spent, phone in clients:
            name = f"{fname or ''} {lname or ''}".strip() or "—"
            text += f"👤 <b>{name}</b>\n"
            if uname:
                text += f"   @{uname}\n"
            text += f"   📦 {cnt} заказов | 💰 {spent}₽\n"
            if phone:
                text += f"   📱 {phone}\n"
            text += "\n"
    await message.answer(text, reply_markup=get_clients_reply_keyboard())


def register_handlers(dp):
    """Регистрация обработчиков главной навигации"""
    dp.message.register(reply_back_handler, F.text == "◀️ Назад")
    dp.message.register(reply_orders_handler, F.text == "📅 Заказы")
    dp.message.register(reply_services_handler, F.text == "💼 Услуги")
    dp.message.register(reply_staff_handler, F.text == "👤 Персонал")
    dp.message.register(reply_settings_handler, F.text == "⚙️ Настройки")
    dp.message.register(reply_clients_handler, F.text == "👥 Клиенты")
