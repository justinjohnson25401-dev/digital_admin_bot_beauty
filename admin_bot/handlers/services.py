"""
Обработчики для работы с услугами.
"""

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton


async def admin_services_menu_handler(callback: CallbackQuery, config_manager):
    """Меню фильтрации услуг"""
    config = config_manager.get_config()
    services = config.get('services', [])

    categories = {}
    for svc in services:
        cat = svc.get('category', 'Другое')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(svc)

    text = f"📋 <b>УСЛУГИ</b> ({len(services)})\n\nВыберите категорию для просмотра:"

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
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def admin_services_all_handler(callback: CallbackQuery, config_manager):
    """Показать все услуги"""
    from admin_handlers.services_editor import get_services_keyboard
    config = config_manager.get_config()
    services = config.get('services', [])

    text = f"📋 <b>ВСЕ УСЛУГИ</b> ({len(services)})\n\n"
    keyboard = get_services_keyboard(services)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def admin_services_by_category_handler(callback: CallbackQuery, config_manager):
    """Показать услуги по категории"""
    category = callback.data.replace("admin_services_cat:", "")
    config = config_manager.get_config()
    services = config.get('services', [])

    filtered = [s for s in services if s.get('category', 'Другое') == category]

    text = f"📁 <b>{category}</b> ({len(filtered)} услуг)\n\n"

    keyboard_rows = []
    for svc in filtered:
        dur = svc.get('duration', 0)
        dur_text = f" • {dur}мин" if dur else ""
        keyboard_rows.append([InlineKeyboardButton(
            text=f"✏️ {svc['name']} — {svc['price']}₽{dur_text}",
            callback_data=f"edit_service_{svc['id']}"
        )])

    keyboard_rows.append([InlineKeyboardButton(text="◀️ Все категории", callback_data="admin_services_menu")])
    keyboard_rows.append([InlineKeyboardButton(text="➕ Добавить услугу", callback_data="add_service_start")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


def register_handlers(dp):
    """Регистрация обработчиков услуг"""
    dp.callback_query.register(admin_services_all_handler, F.data == "admin_services_all")
    dp.callback_query.register(admin_services_by_category_handler, F.data.startswith("admin_services_cat:"))
    dp.callback_query.register(admin_services_menu_handler, F.data == "admin_services_menu")
