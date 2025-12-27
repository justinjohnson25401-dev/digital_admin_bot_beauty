"""
Настройка уведомлений - управление feature flags.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


# Описания feature flags
FEATURE_LABELS = {
    'enable_admin_notify': {
        'name': '🔔 Уведомления админу',
        'description': 'Отправлять уведомления о новых записях и отменах'
    },
    'require_phone': {
        'name': '📞 Требовать телефон',
        'description': 'Запрашивать номер телефона при записи'
    },
    'ask_comment': {
        'name': '💬 Запрашивать комментарий',
        'description': 'Предлагать оставить комментарий к записи'
    },
    'enable_slot_booking': {
        'name': '📅 Бронирование слотов',
        'description': 'Проверять доступность временных слотов'
    }
}


@router.callback_query(F.data == "notifications_menu")
async def show_notifications_menu(callback: CallbackQuery, config: dict):
    """Главное меню настройки уведомлений"""

    features = config.get('features', {})

    text = """
🔔 <b>НАСТРОЙКА УВЕДОМЛЕНИЙ И ФУНКЦИЙ</b>

Управляйте поведением бота:
"""

    # Формируем список с текущими статусами
    for key, info in FEATURE_LABELS.items():
        is_enabled = features.get(key, True)
        status = "✅" if is_enabled else "❌"
        text += f"\n{status} <b>{info['name']}</b>\n"
        text += f"   <i>{info['description']}</i>\n"

    text += "\nНажмите на функцию для переключения:"

    keyboard_rows = []

    for key, info in FEATURE_LABELS.items():
        is_enabled = features.get(key, True)
        status = "✅" if is_enabled else "❌"
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"{status} {info['name']}",
                callback_data=f"toggle_feature_{key}"
            )
        ])

    keyboard_rows.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_feature_"))
async def toggle_feature(callback: CallbackQuery, config: dict, config_manager):
    """Переключить feature flag"""

    feature_key = callback.data.replace("toggle_feature_", "")

    if feature_key not in FEATURE_LABELS:
        await callback.answer("❌ Неизвестная функция", show_alert=True)
        return

    # Получаем текущее значение
    features = config.get('features', {})
    current_value = features.get(feature_key, True)
    new_value = not current_value

    # Сохранение
    if 'features' not in config:
        config['features'] = {}

    config['features'][feature_key] = new_value
    config_manager.config['features'] = config['features']
    config_manager.save_config()

    # Уведомление
    info = FEATURE_LABELS[feature_key]
    status = "включена ✅" if new_value else "выключена ❌"
    await callback.answer(f"{info['name']}: {status}")

    # Обновить меню
    await show_notifications_menu(callback, config)
