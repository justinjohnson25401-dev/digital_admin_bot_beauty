"""Редактор настроек для админ-бота"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging
import re

logger = logging.getLogger(__name__)

router = Router()


class SettingsEditStates(StatesGroup):
    """Состояния для редактирования настроек"""
    edit_business_name = State()
    edit_work_hours = State()
    edit_timezone_custom = State()


@router.callback_query(F.data == "admin_settings")
async def show_settings(callback: CallbackQuery, config_manager):
    """Показ настроек"""
    config = config_manager.get_config()
    
    business_name = config.get('business_name', 'Не указано')
    work_start = config.get('booking', {}).get('work_start', 10)
    work_end = config.get('booking', {}).get('work_end', 20)
    services_count = len(config.get('services', []))
    timezone_city = config.get('timezone_city', 'Авто (localtime)')
    timezone_offset = config.get('timezone_offset_hours')
    tz_text = timezone_city
    if timezone_offset is not None:
        tz_text = f"{timezone_city} (UTC{timezone_offset:+d})"

    text = (
        f"⚙️ <b>Настройки</b>\n\n"
        f"📝 Название: {business_name}\n"
        f"⏰ График: {work_start:02d}:00 - {work_end:02d}:00\n"
        f"📋 Услуг: {services_count}\n"
        f"🌍 Таймзона: {tz_text}\n"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Изменить название", callback_data="settings_edit_name"),
        ],
        [
            InlineKeyboardButton(text="⏰ Изменить график", callback_data="settings_edit_hours"),
        ],
        [
            InlineKeyboardButton(text="🌍 Таймзона", callback_data="settings_edit_timezone")
        ],
        [
            InlineKeyboardButton(text="📋 Управление услугами", callback_data="admin_services")
        ],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "settings_edit_timezone")
async def start_edit_timezone(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Москва (UTC+3)", callback_data="tz_set:Москва:3"),
            InlineKeyboardButton(text="Екатеринбург (UTC+5)", callback_data="tz_set:Екатеринбург:5"),
        ],
        [
            InlineKeyboardButton(text="Новосибирск (UTC+7)", callback_data="tz_set:Новосибирск:7"),
            InlineKeyboardButton(text="Калининград (UTC+2)", callback_data="tz_set:Калининград:2"),
        ],
        [InlineKeyboardButton(text="Другое (ввести вручную)", callback_data="tz_custom")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_settings")],
    ])

    await callback.message.edit_text(
        "🌍 <b>Таймзона</b>\n\n"
        "Выберите город (UTC offset) или введите вручную:",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tz_set:"))
async def set_timezone_preset(callback: CallbackQuery, config_manager):
    try:
        _, city, offset_str = callback.data.split(":", 2)
        offset = int(offset_str)
    except Exception:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        return

    success = config_manager.update_timezone(city=city, offset_hours=offset)
    if success:
        config_manager.reload_config()
        await callback.message.edit_text(f"✅ Таймзона установлена: {city} (UTC{offset:+d})")
        await callback.message.answer("Откройте настройки заново, чтобы увидеть обновления.")
    else:
        await callback.message.edit_text("❌ Ошибка при сохранении")

    await callback.answer()


@router.callback_query(F.data == "tz_custom")
async def start_timezone_custom(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsEditStates.edit_timezone_custom)
    await callback.message.edit_text(
        "Введите таймзону в формате:\n"
        "<code>Город,UTC+X</code>\n\n"
        "Примеры:\n"
        "<code>Екатеринбург,UTC+5</code>\n"
        "<code>Москва,UTC+3</code>\n"
        "<code>Самара,UTC+4</code>"
    )
    await callback.answer()


@router.message(SettingsEditStates.edit_timezone_custom)
async def process_timezone_custom(message: Message, state: FSMContext, config_manager):
    text = message.text.strip()

    m = re.match(r"^(.+),\s*UTC([+-]?\d{1,2})$", text, flags=re.IGNORECASE)
    if not m:
        await message.answer("❌ Неверный формат. Пример: <code>Екатеринбург,UTC+5</code>")
        return

    city = m.group(1).strip()
    offset = int(m.group(2))
    if offset < -12 or offset > 14:
        await message.answer("❌ Некорректный UTC offset. Допустимо от -12 до +14")
        return

    success = config_manager.update_timezone(city=city, offset_hours=offset)
    if success:
        config_manager.reload_config()
        await message.answer(f"✅ Таймзона установлена: {city} (UTC{offset:+d})")
    else:
        await message.answer("❌ Ошибка при сохранении")

    await state.clear()


# === РЕДАКТИРОВАНИЕ НАЗВАНИЯ БИЗНЕСА ===

@router.callback_query(F.data == "settings_edit_name")
async def start_edit_name(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования названия"""
    await state.set_state(SettingsEditStates.edit_business_name)

    await callback.message.edit_text(
        "📝 <b>Изменение названия бизнеса</b>\n\n"
        "Введите новое название:"
    )
    await callback.answer()


@router.message(SettingsEditStates.edit_business_name)
async def process_edit_name(message: Message, state: FSMContext, config_manager):
    """Обработка нового названия бизнеса"""
    new_name = message.text.strip()
    
    if len(new_name) < 2:
        await message.answer("❌ Название слишком короткое. Минимум 2 символа:")
        return
    
    success = config_manager.update_business_name(new_name)
    
    if success:
        await message.answer(f"✅ Название изменено на:\n<b>{new_name}</b>")
        config_manager.reload_config()
        
        # Показываем обновлённые настройки
        config = config_manager.get_config()
        work_start = config.get('booking', {}).get('work_start', 10)
        work_end = config.get('booking', {}).get('work_end', 20)
        slot_duration = config.get('booking', {}).get('slot_duration', 60)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К настройкам", callback_data="admin_settings")]
        ])
        
        await message.answer(
            f"⚙️ <b>Обновлённые настройки</b>\n\n"
            f"📝 Название: {new_name}\n"
            f"⏰ График: {work_start:02d}:00 - {work_end:02d}:00\n"
            f"🕐 Слот: {slot_duration} мин",
            reply_markup=keyboard
        )
    else:
        await message.answer("❌ Ошибка при сохранении")
    
    await state.clear()


# === РЕДАКТИРОВАНИЕ ГРАФИКА РАБОТЫ ===

@router.callback_query(F.data == "settings_edit_hours")
async def start_edit_hours(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования графика"""
    await state.set_state(SettingsEditStates.edit_work_hours)

    await callback.message.edit_text(
        "⏰ <b>Изменение графика работы</b>\n\n"
        "Введите новый график в формате:\n"
        "<code>ЧЧ:ММ-ЧЧ:ММ</code>\n\n"
        "Примеры:\n"
        "• <code>09:00-21:00</code>\n"
        "• <code>10:00-20:00</code>\n"
        "• <code>08:30-18:30</code>"
    )
    await callback.answer()


@router.message(SettingsEditStates.edit_work_hours)
async def process_edit_hours(message: Message, state: FSMContext, config_manager):
    """Обработка нового графика работы"""
    text = message.text.strip()
    
    # Проверяем формат HH:MM-HH:MM
    pattern = r'^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})$'
    match = re.match(pattern, text)
    
    if not match:
        await message.answer(
            "❌ Неверный формат!\n\n"
            "Используйте формат: <code>ЧЧ:ММ-ЧЧ:ММ</code>\n"
            "Например: <code>09:00-21:00</code>"
        )
        return
    
    start_hour, start_min, end_hour, end_min = match.groups()
    start_hour, start_min, end_hour, end_min = int(start_hour), int(start_min), int(end_hour), int(end_min)
    
    # Валидация
    if start_hour >= 24 or end_hour >= 24 or start_min >= 60 or end_min >= 60:
        await message.answer("❌ Некорректное время. Часы: 0-23, минуты: 0-59")
        return
    
    if start_hour >= end_hour:
        await message.answer("❌ Время начала должно быть раньше времени окончания")
        return
    
    # Пока что сохраняем только часы (упрощённо)
    success = config_manager.update_work_hours(start_hour, end_hour)
    
    if success:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К настройкам", callback_data="admin_settings")],
        ])
        await message.answer(
            f"✅ График изменён:\n"
            f"<b>{start_hour:02d}:{start_min:02d} - {end_hour:02d}:{end_min:02d}</b>",
            reply_markup=keyboard,
        )
        config_manager.reload_config()
    else:
        await message.answer("❌ Ошибка при сохранении")
    
    await state.clear()


