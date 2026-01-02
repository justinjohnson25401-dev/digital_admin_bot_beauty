"""
Добавление мастера (FSM).
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from admin_bot.states import StaffEditorStates
from utils.config_editor import ConfigEditor
from utils.validators import validate_master_name, validate_master_role
from .keyboards import _build_services_keyboard, _build_days_keyboard, _build_hours_keyboard

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == "add_master")
async def add_master_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление мастера"""

    text = """
➕ <b>ДОБАВЛЕНИЕ МАСТЕРА</b>

Шаг 1 из 4: Введите имя мастера (от 2 до 50 символов):

<i>Например: Анна, Мария Иванова</i>
"""

    await callback.message.edit_text(text)
    await state.set_state(StaffEditorStates.enter_name)
    await callback.answer()


@router.message(StaffEditorStates.enter_name)
async def add_master_name(message: Message, state: FSMContext):
    """Сохранить имя мастера"""

    name = message.text.strip()

    is_valid, error = validate_master_name(name)

    if not is_valid:
        await message.answer(f"❌ {error}\n\nПопробуйте ещё раз:")
        return

    await state.update_data(master_name=name)

    text = f"""
✅ Имя: <b>{name}</b>

Шаг 2 из 4: Введите должность/специализацию:

<i>Например: Парикмахер, Мастер маникюра, Косметолог</i>
"""

    await message.answer(text)
    await state.set_state(StaffEditorStates.enter_role)


@router.message(StaffEditorStates.enter_role)
async def add_master_role(message: Message, state: FSMContext, config: dict, config_manager):
    """Сохранить должность мастера"""

    role = message.text.strip()

    is_valid, error = validate_master_role(role)

    if not is_valid:
        await message.answer(f"❌ {error}\n\nПопробуйте ещё раз:")
        return

    await state.update_data(master_role=role)

    # Получаем список услуг
    services = config.get('services', [])

    if not services:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="staff_menu")],
        ])
        await message.answer(
            "❌ В системе нет услуг. Сначала добавьте услуги в разделе «Услуги».",
            reply_markup=keyboard
        )
        await state.clear()
        return

    data = await state.get_data()

    text = f"""
✅ Имя: <b>{data['master_name']}</b>
✅ Должность: <b>{role}</b>

Шаг 3 из 4: Выберите услуги, которые выполняет мастер.

Нажимайте на услуги для выбора, затем «Продолжить»:
"""

    # Инициализируем выбранные услуги
    await state.update_data(selected_services=[])

    keyboard = _build_services_keyboard(services, [])

    await message.answer(text, reply_markup=keyboard)
    await state.set_state(StaffEditorStates.choose_services)


@router.callback_query(F.data.startswith("select_service_"), StaffEditorStates.choose_services)
async def toggle_service_selection(callback: CallbackQuery, state: FSMContext, config: dict):
    """Переключить выбор услуги"""

    service_id = callback.data.replace("select_service_", "")

    data = await state.get_data()
    selected = data.get('selected_services', [])

    if service_id in selected:
        selected.remove(service_id)
    else:
        selected.append(service_id)

    await state.update_data(selected_services=selected)

    # Обновляем клавиатуру
    services = config.get('services', [])
    keyboard = _build_services_keyboard(services, selected)

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "services_done", StaffEditorStates.choose_services)
async def confirm_services(callback: CallbackQuery, state: FSMContext):
    """Услуги выбраны, переходим к выбору дней недели"""

    data = await state.get_data()
    selected = data.get('selected_services', [])

    if not selected:
        await callback.answer("❌ Выберите хотя бы одну услугу", show_alert=True)
        return

    # Инициализируем выбранные дни (по умолчанию Пн-Пт)
    default_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
    await state.update_data(selected_days=default_days)

    text = f"""
✅ Имя: <b>{data['master_name']}</b>
✅ Должность: <b>{data['master_role']}</b>
✅ Услуг выбрано: <b>{len(selected)}</b>

Шаг 4 из 5: Выберите рабочие дни мастера.

Нажимайте на дни для выбора/отмены:
"""

    keyboard = _build_days_keyboard(default_days)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(StaffEditorStates.choose_schedule_days)
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_day_"), StaffEditorStates.choose_schedule_days)
async def toggle_day_selection(callback: CallbackQuery, state: FSMContext):
    """Переключить выбор дня недели"""

    day_id = callback.data.replace("toggle_day_", "")

    data = await state.get_data()
    selected_days = data.get('selected_days', [])

    if day_id in selected_days:
        selected_days.remove(day_id)
    else:
        selected_days.append(day_id)

    await state.update_data(selected_days=selected_days)

    keyboard = _build_days_keyboard(selected_days)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "days_done", StaffEditorStates.choose_schedule_days)
async def confirm_schedule_days(callback: CallbackQuery, state: FSMContext, config: dict):
    """Дни выбраны, переходим к выбору времени работы"""

    data = await state.get_data()
    selected_days = data.get('selected_days', [])

    if not selected_days:
        await callback.answer("❌ Выберите хотя бы один день", show_alert=True)
        return

    # Форматируем выбранные дни
    days_short = {
        'monday': 'Пн', 'tuesday': 'Вт', 'wednesday': 'Ср',
        'thursday': 'Чт', 'friday': 'Пт', 'saturday': 'Сб', 'sunday': 'Вс'
    }
    days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    sorted_days = [d for d in days_order if d in selected_days]
    days_text = ', '.join([days_short[d] for d in sorted_days])

    # Получаем часы работы бизнеса из конфига
    booking = config.get('booking', {})
    business_start = int(booking.get('work_start', 10))
    business_end = int(booking.get('work_end', 20))

    text = f"""
✅ Имя: <b>{data['master_name']}</b>
✅ Должность: <b>{data['master_role']}</b>
✅ Услуг выбрано: <b>{len(data.get('selected_services', []))}</b>
✅ Дни: <b>{days_text}</b>

Шаг 5 из 5: Выберите время работы:

<i>💡 Часы работы бизнеса: {business_start:02d}:00 - {business_end:02d}:00</i>
"""

    keyboard = _build_hours_keyboard(business_start, business_end)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(StaffEditorStates.choose_schedule_hours)
    await callback.answer()


@router.callback_query(F.data.startswith("hours_"), StaffEditorStates.choose_schedule_hours)
async def choose_schedule_hours(callback: CallbackQuery, state: FSMContext, config: dict, config_manager):
    """Время выбрано, создаём мастера"""

    hours_data = callback.data.replace("hours_", "")
    start_hour, end_hour = hours_data.split("_")
    start_time = f"{start_hour}:00"
    end_time = f"{end_hour}:00"

    data = await state.get_data()
    selected_days = data.get('selected_days', [])

    # Создаём график
    schedule = {}
    all_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    for day in all_days:
        if day in selected_days:
            schedule[day] = {"working": True, "start": start_time, "end": end_time}
        else:
            schedule[day] = {"working": False}

    try:
        # Проверяем наличие всех необходимых данных
        if not data.get('master_name') or not data.get('master_role'):
            await callback.answer("❌ Ошибка: данные мастера не найдены. Начните заново.", show_alert=True)
            await state.clear()
            return

        if not data.get('selected_services'):
            await callback.answer("❌ Ошибка: услуги не выбраны. Начните заново.", show_alert=True)
            await state.clear()
            return

        master_data = {
            "name": data['master_name'],
            "specialization": data['master_role'],
            "role": data['master_role'],
            "photo_url": None,
            "services": data['selected_services'],
            "schedule": schedule,
            "closed_dates": []
        }

        # Сохраняем
        editor = ConfigEditor(config_manager.config_path)
        master_id = editor.add_master(master_data)

        if not master_id:
            raise ValueError("add_master вернул пустой ID")

        # Обновляем config в памяти
        if 'staff' not in config:
            config['staff'] = {'enabled': False, 'masters': []}

        master_data['id'] = master_id
        config['staff']['masters'].append(master_data)
        config_manager.config['staff'] = config['staff']

        # Форматируем выбранные дни
        days_short = {
            'monday': 'Пн', 'tuesday': 'Вт', 'wednesday': 'Ср',
            'thursday': 'Чт', 'friday': 'Пт', 'saturday': 'Сб', 'sunday': 'Вс'
        }
        days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        sorted_days = [d for d in days_order if d in selected_days]
        days_text = ', '.join([days_short[d] for d in sorted_days])

        text = f"""
✅ <b>МАСТЕР ДОБАВЛЕН!</b>

👤 <b>{data['master_name']}</b>
💼 {data['master_role']}
📋 Услуг: {len(data['selected_services'])}
📅 График: {days_text}, {start_time}-{end_time}

<i>ID мастера: {master_id}</i>
"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 К персоналу", callback_data="staff_menu")],
        ])

        await callback.message.edit_text(text, reply_markup=keyboard)
        logger.info(f"Master {master_id} ({data['master_name']}) added by admin {callback.from_user.id}")

    except Exception as e:
        logger.error(f"Error adding master: {e}", exc_info=True)

        error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="add_master")],
            [InlineKeyboardButton(text="👤 К персоналу", callback_data="staff_menu")],
        ])

        await callback.message.edit_text(
            f"❌ <b>Ошибка при добавлении мастера</b>\n\n"
            f"Произошла системная ошибка. Пожалуйста, попробуйте ещё раз.\n\n"
            f"<i>Техническая информация: {str(e)[:100]}</i>",
            reply_markup=error_keyboard
        )

    await state.clear()
    await callback.answer()
