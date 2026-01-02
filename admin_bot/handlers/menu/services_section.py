"""
Обработчики раздела Услуги (нижняя клавиатура).
"""

from aiogram import F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext


async def reply_promotions_handler(message: Message, state: FSMContext, config: dict):
    """Управление акциями"""
    await state.clear()
    promotions = config.get('promotions', [])

    text = "🎁 <b>АКЦИИ</b>\n\n"
    if promotions:
        for promo in promotions:
            status = "✅" if promo.get('active', True) else "❌"
            text += f"{status} {promo.get('emoji', '🎁')} {promo.get('title', 'Без названия')}\n"
    else:
        text += "<i>Акций нет</i>\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить акцию", callback_data="promo_add")],
        [InlineKeyboardButton(text="📋 Управлять", callback_data="promotions_menu")],
    ])
    await message.answer(text, reply_markup=keyboard)


async def reply_services_list_handler(message: Message, config_manager):
    """Список услуг с фильтрацией по категориям"""
    config = config_manager.get_config()
    services = config.get('services', [])

    categories = {}
    for svc in services:
        cat = svc.get('category', 'Другое')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(svc)

    text = f"📋 <b>УСЛУГИ</b> ({len(services)})\n\n"

    keyboard_rows = []
    keyboard_rows.append([InlineKeyboardButton(text="📂 Все услуги", callback_data="admin_services_all")])

    for cat_name in categories.keys():
        count = len(categories[cat_name])
        keyboard_rows.append([InlineKeyboardButton(
            text=f"📁 {cat_name} ({count})",
            callback_data=f"admin_services_cat:{cat_name}"
        )])

    keyboard_rows.append([InlineKeyboardButton(text="➕ Добавить услугу", callback_data="add_service_start")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await message.answer(text + "Выберите категорию для просмотра:", reply_markup=keyboard)


async def reply_add_service_handler(message: Message, state: FSMContext):
    """Добавить услугу — переход к FSM"""
    from admin_handlers.services_editor import ServiceEditStates
    await state.set_state(ServiceEditStates.add_name)
    await message.answer("📝 Введите название новой услуги:")


def register_handlers(dp):
    """Регистрация обработчиков раздела Услуги"""
    dp.message.register(reply_promotions_handler, F.text == "🎁 Акции")
    dp.message.register(reply_services_list_handler, F.text == "📋 Список услуг")
    dp.message.register(reply_add_service_handler, F.text == "➕ Добавить")
