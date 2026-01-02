"""
Настройки бизнеса - редактирование названия, часов работы, слотов.
"""

from pathlib import Path
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from admin_bot.states import BusinessSettingsStates
from utils.config_editor import ConfigEditor
from utils.validators import validate_business_name, validate_work_hours, validate_slot_duration

router = Router()

# Корневая директория проекта
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_config_editor(config: dict) -> ConfigEditor:
    """Получить ConfigEditor с абсолютным путём к конфигу"""
    config_path = PROJECT_ROOT / "configs" / "client_lite.json"
    return ConfigEditor(str(config_path))


@router.callback_query(F.data == "business_settings")
async def show_business_settings(callback: CallbackQuery, config: dict):
    """Показать текущие настройки бизнеса"""

    booking = config.get('booking', {})

    text = f"""
⚙️ <b>НАСТРОЙКИ БИЗНЕСА</b>

Текущие данные:
━━━━━━━━━━━━━━━━━━━━━━
📍 <b>Название:</b> {config.get('business_name', 'Не указано')}
🕐 <b>Начало работы:</b> {int(booking.get('work_start', 10))}:00
🕑 <b>Конец работы:</b> {int(booking.get('work_end', 20))}:00
⏱ <b>Длительность слота:</b> {int(booking.get('slot_duration', 60))} минут
🌍 <b>Часовой пояс:</b> {config.get('timezone_city', 'Не указано')} (UTC{int(config.get('timezone_offset_hours', 3)):+d})
━━━━━━━━━━━━━━━━━━━━━━

Выберите что изменить:
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить название", callback_data="edit_business_name")],
        [InlineKeyboardButton(text="🕐 Изменить время начала", callback_data="edit_work_start")],
        [InlineKeyboardButton(text="🕑 Изменить время конца", callback_data="edit_work_end")],
        [InlineKeyboardButton(text="⏱ Изменить слот", callback_data="edit_slot_duration")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_settings")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# ==================== РЕДАКТИРОВАНИЕ НАЗВАНИЯ ====================

@router.callback_query(F.data == "edit_business_name")
async def edit_business_name_start(callback: CallbackQuery, state: FSMContext, config: dict):
    """Начать редактирование названия"""

    current_name = config.get('business_name', '')

    text = f"""
✏️ <b>ИЗМЕНЕНИЕ НАЗВАНИЯ</b>

Текущее название: <b>{current_name}</b>

Введите новое название салона (от 3 до 50 символов):
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="business_settings")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(BusinessSettingsStates.edit_name)
    await callback.answer()


@router.message(BusinessSettingsStates.edit_name)
async def save_business_name(message: Message, state: FSMContext, config: dict, config_manager):
    """Сохранить новое название"""

    name = message.text.strip()

    # Валидация
    is_valid, error = validate_business_name(name)

    if not is_valid:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="business_settings")],
        ])
        await message.answer(f"❌ {error}\n\nПопробуйте ещё раз:", reply_markup=keyboard)
        return

    # Сохранение через ConfigManager (обновляет и config)
    config_manager.update_business_name(name)
    config['business_name'] = name

    await message.answer(f"✅ Название обновлено: <b>{name}</b>")
    await state.clear()

    # Показать настройки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ К настройкам", callback_data="business_settings")],
    ])
    await message.answer("Выберите действие:", reply_markup=keyboard)


# ==================== РЕДАКТИРОВАНИЕ ВРЕМЕНИ НАЧАЛА ====================

@router.callback_query(F.data == "edit_work_start")
async def edit_work_start(callback: CallbackQuery, state: FSMContext, config: dict):
    """Начать редактирование времени начала работы"""

    current = config.get('booking', {}).get('work_start', 10)

    text = f"""
🕐 <b>ВРЕМЯ НАЧАЛА РАБОТЫ</b>

Текущее время начала: <b>{current}:00</b>

Введите час начала работы (число от 0 до 23):
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="business_settings")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(BusinessSettingsStates.edit_work_start)
    await callback.answer()


@router.message(BusinessSettingsStates.edit_work_start)
async def save_work_start(message: Message, state: FSMContext, config: dict, config_manager):
    """Сохранить время начала"""

    try:
        start = int(message.text.strip())
    except ValueError:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="business_settings")],
        ])
        await message.answer("❌ Введите число от 0 до 23", reply_markup=keyboard)
        return

    end = config.get('booking', {}).get('work_end', 20)

    is_valid, error = validate_work_hours(start, end)

    if not is_valid:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="business_settings")],
        ])
        await message.answer(f"❌ {error}", reply_markup=keyboard)
        return

    # Сохранение
    config_manager.update_work_hours(start, end)
    config['booking']['work_start'] = start

    await message.answer(f"✅ Время начала обновлено: <b>{start}:00</b>")
    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ К настройкам", callback_data="business_settings")],
    ])
    await message.answer("Выберите действие:", reply_markup=keyboard)


# ==================== РЕДАКТИРОВАНИЕ ВРЕМЕНИ КОНЦА ====================

@router.callback_query(F.data == "edit_work_end")
async def edit_work_end(callback: CallbackQuery, state: FSMContext, config: dict):
    """Начать редактирование времени конца работы"""

    current = config.get('booking', {}).get('work_end', 20)

    text = f"""
🕑 <b>ВРЕМЯ КОНЦА РАБОТЫ</b>

Текущее время конца: <b>{current}:00</b>

Введите час конца работы (число от 1 до 24):
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="business_settings")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(BusinessSettingsStates.edit_work_end)
    await callback.answer()


@router.message(BusinessSettingsStates.edit_work_end)
async def save_work_end(message: Message, state: FSMContext, config: dict, config_manager):
    """Сохранить время конца"""

    try:
        end = int(message.text.strip())
    except ValueError:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="business_settings")],
        ])
        await message.answer("❌ Введите число от 1 до 24", reply_markup=keyboard)
        return

    start = config.get('booking', {}).get('work_start', 10)

    is_valid, error = validate_work_hours(start, end)

    if not is_valid:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="business_settings")],
        ])
        await message.answer(f"❌ {error}", reply_markup=keyboard)
        return

    # Сохранение
    config_manager.update_work_hours(start, end)
    config['booking']['work_end'] = end

    await message.answer(f"✅ Время конца обновлено: <b>{end}:00</b>")
    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ К настройкам", callback_data="business_settings")],
    ])
    await message.answer("Выберите действие:", reply_markup=keyboard)


# ==================== РЕДАКТИРОВАНИЕ СЛОТА ====================

@router.callback_query(F.data == "edit_slot_duration")
async def edit_slot_duration(callback: CallbackQuery, config: dict):
    """Выбрать длительность слота"""

    current = config.get('booking', {}).get('slot_duration', 60)

    text = f"""
⏱ <b>ДЛИТЕЛЬНОСТЬ СЛОТА</b>

Текущая длительность: <b>{current} минут</b>

Выберите новую длительность слота:
"""

    # Отметим текущий выбор
    def mark(duration: int) -> str:
        return f"✓ {duration} минут" if duration == current else f"{duration} минут"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=mark(15), callback_data="slot_duration_15")],
        [InlineKeyboardButton(text=mark(30), callback_data="slot_duration_30")],
        [InlineKeyboardButton(text=mark(45), callback_data="slot_duration_45")],
        [InlineKeyboardButton(text=mark(60), callback_data="slot_duration_60")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="business_settings")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("slot_duration_"))
async def save_slot_duration(callback: CallbackQuery, config: dict, config_manager):
    """Сохранить длительность слота"""

    try:
        duration = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    is_valid, error = validate_slot_duration(duration)

    if not is_valid:
        await callback.answer(f"❌ {error}", show_alert=True)
        return

    # Сохранение
    config_manager.update_slot_duration(duration)
    config['booking']['slot_duration'] = duration

    await callback.answer(f"✅ Слот установлен: {duration} минут")

    # Обновить меню
    await show_business_settings(callback, config)
