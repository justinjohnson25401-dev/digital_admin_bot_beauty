"""
Управление персоналом - мастера, графики, закрытые даты.
"""

import logging
from pathlib import Path
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta

from admin_bot.states import StaffEditorStates, ClosedDatesStates
from utils.config_editor import ConfigEditor
from utils.staff_manager import StaffManager
from utils.validators import validate_master_name, validate_master_role, validate_date_format

logger = logging.getLogger(__name__)

router = Router()

# Корневая директория проекта (parent of admin_handlers/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_config_editor(config: dict) -> ConfigEditor:
    """Получить ConfigEditor с абсолютным путём к конфигу"""
    # setup.py всегда создаёт configs/client_lite.json
    config_path = PROJECT_ROOT / "configs" / "client_lite.json"
    return ConfigEditor(str(config_path))


@router.callback_query(F.data == "staff_menu")
async def show_staff_menu(callback: CallbackQuery, config: dict, state: FSMContext):
    """Главное меню управления персоналом"""
    # Очищаем FSM state при возврате в меню
    await state.clear()

    staff_data = config.get('staff', {})
    is_enabled = staff_data.get('enabled', False)
    masters = staff_data.get('masters', [])

    status = "✅ Включена" if is_enabled else "❌ Отключена"

    text = f"""
👤 <b>УПРАВЛЕНИЕ ПЕРСОНАЛОМ</b>

Функция персонала: <b>{status}</b>

"""

    if masters:
        text += f"Текущий состав ({len(masters)}):\n\n"
        for master in masters:
            services_count = len(master.get('services', []))
            text += f"👤 <b>{master['name']}</b> — {master.get('specialization') or master.get('role', 'Мастер')}\n"
            text += f"   📋 Услуг: {services_count}\n\n"
    else:
        text += "<i>Мастера не добавлены</i>\n\n"

    text += "Выберите действие:"

    toggle_text = "🔴 Выключить персонал" if is_enabled else "🟢 Включить персонал"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data="toggle_staff")],
        [InlineKeyboardButton(text="➕ Добавить мастера", callback_data="add_master")],
        [InlineKeyboardButton(text="✏️ Редактировать мастера", callback_data="edit_master_list")],
        [InlineKeyboardButton(text="📅 Закрытые даты", callback_data="closed_dates_menu")],
        [InlineKeyboardButton(text="🗑 Удалить мастера", callback_data="delete_master_list")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "toggle_staff")
async def toggle_staff_feature(callback: CallbackQuery, config: dict, config_manager, state: FSMContext):
    """Включить/выключить функцию персонала"""

    editor = get_config_editor(config)
    current = config.get('staff', {}).get('enabled', False)

    editor.toggle_staff_feature(not current)

    # Обновляем config в памяти
    if 'staff' not in config:
        config['staff'] = {'enabled': False, 'masters': []}
    config['staff']['enabled'] = not current

    # Обновляем config_manager
    config_manager.config['staff'] = config['staff']

    status = "✅ Включена" if not current else "❌ Отключена"
    await callback.answer(f"Функция персонала: {status}")

    await show_staff_menu(callback, config, state)


# ==================== ДОБАВЛЕНИЕ МАСТЕРА ====================

@router.callback_query(F.data == "add_master")
async def add_master_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление мастера"""

    text = """
➕ <b>ДОБАВЛЕНИЕ МАСТЕРА</b>

Шаг 1 из 4: Введите имя мастера (от 2 до 50 символов):

<i>Например: Анна, Мария Иванова</i>
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="staff_menu")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(StaffEditorStates.enter_name)
    await callback.answer()


@router.message(StaffEditorStates.enter_name)
async def add_master_name(message: Message, state: FSMContext):
    """Сохранить имя мастера"""

    name = message.text.strip()

    is_valid, error = validate_master_name(name)

    if not is_valid:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="staff_menu")],
        ])
        await message.answer(f"❌ {error}\n\nПопробуйте ещё раз:", reply_markup=keyboard)
        return

    await state.update_data(master_name=name)

    text = f"""
✅ Имя: <b>{name}</b>

Шаг 2 из 4: Введите должность/специализацию:

<i>Например: Парикмахер, Мастер маникюра, Косметолог</i>
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="staff_menu")],
    ])

    await message.answer(text, reply_markup=keyboard)
    await state.set_state(StaffEditorStates.enter_role)


@router.message(StaffEditorStates.enter_role)
async def add_master_role(message: Message, state: FSMContext, config: dict):
    """Сохранить должность мастера"""

    role = message.text.strip()

    is_valid, error = validate_master_role(role)

    if not is_valid:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="staff_menu")],
        ])
        await message.answer(f"❌ {error}\n\nПопробуйте ещё раз:", reply_markup=keyboard)
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

    keyboard_rows = []
    for service in services:
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"☐ {service['name']} ({service['price']}₽)",
                callback_data=f"select_service_{service['id']}"
            )
        ])

    keyboard_rows.append([InlineKeyboardButton(text="✅ Продолжить", callback_data="services_done")])
    keyboard_rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="staff_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

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

    keyboard_rows = []
    for service in services:
        is_selected = service['id'] in selected
        mark = "☑" if is_selected else "☐"
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"{mark} {service['name']} ({service['price']}₽)",
                callback_data=f"select_service_{service['id']}"
            )
        ])

    keyboard_rows.append([InlineKeyboardButton(text="✅ Продолжить", callback_data="services_done")])
    keyboard_rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="staff_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "services_done", StaffEditorStates.choose_services)
async def services_selected(callback: CallbackQuery, state: FSMContext):
    """Услуги выбраны, переходим к графику"""

    data = await state.get_data()
    selected = data.get('selected_services', [])

    if not selected:
        await callback.answer("❌ Выберите хотя бы одну услугу", show_alert=True)
        return

    text = f"""
✅ Имя: <b>{data['master_name']}</b>
✅ Должность: <b>{data['master_role']}</b>
✅ Услуг выбрано: <b>{len(selected)}</b>

Шаг 4 из 4: Выберите график работы:
"""

    templates = StaffManager.get_schedule_templates()

    keyboard_rows = []
    for template_id, description in templates.items():
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"📅 {description}",
                callback_data=f"template_{template_id}"
            )
        ])

    keyboard_rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="staff_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(StaffEditorStates.choose_schedule_template)
    await callback.answer()


@router.callback_query(F.data.startswith("template_"), StaffEditorStates.choose_schedule_template)
async def apply_schedule_template(callback: CallbackQuery, state: FSMContext, config: dict, config_manager):
    """Применить шаблон графика и сохранить мастера с обработкой ошибок"""

    template_id = callback.data.replace("template_", "")

    try:
        schedule = StaffManager.create_default_schedule(template_id)

        data = await state.get_data()

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
            "specialization": data['master_role'],  # Основное поле
            "role": data['master_role'],  # Для обратной совместимости
            "photo_url": None,
            "services": data['selected_services'],
            "schedule": schedule,
            "closed_dates": []
        }

        # Сохраняем с обработкой ошибок
        editor = get_config_editor(config)
        master_id = editor.add_master(master_data)

        if not master_id:
            raise ValueError("add_master вернул пустой ID")

        # Обновляем config в памяти
        if 'staff' not in config:
            config['staff'] = {'enabled': False, 'masters': []}

        master_data['id'] = master_id
        config['staff']['masters'].append(master_data)
        config_manager.config['staff'] = config['staff']

        templates = StaffManager.get_schedule_templates()
        schedule_desc = templates.get(template_id, template_id)

        text = f"""
✅ <b>МАСТЕР ДОБАВЛЕН!</b>

👤 <b>{data['master_name']}</b>
💼 {data['master_role']}
📋 Услуг: {len(data['selected_services'])}
📅 График: {schedule_desc}

<i>ID мастера: {master_id}</i>
"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 К персоналу", callback_data="staff_menu")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")],
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


# ==================== РЕДАКТИРОВАНИЕ МАСТЕРА ====================

@router.callback_query(F.data == "edit_master_list")
async def edit_master_list(callback: CallbackQuery, config: dict):
    """Список мастеров для редактирования"""

    masters = config.get('staff', {}).get('masters', [])

    if not masters:
        await callback.answer("Нет мастеров для редактирования", show_alert=True)
        return

    text = "✏️ <b>РЕДАКТИРОВАНИЕ МАСТЕРА</b>\n\nВыберите мастера:"

    keyboard_rows = []
    for master in masters:
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"👤 {master['name']} — {master.get('specialization') or master.get('role', 'Мастер')}",
                callback_data=f"edit_master_{master['id']}"
            )
        ])

    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="staff_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(
    F.data.startswith("edit_master_")
    & ~F.data.startswith("edit_master_list")
    & ~F.data.startswith("edit_master_name_")
    & ~F.data.startswith("edit_master_role_")
    & ~F.data.startswith("edit_master_services_")
    & ~F.data.startswith("edit_master_schedule_")
)
async def edit_master_show(callback: CallbackQuery, config: dict):
    """Показать информацию о мастере для редактирования"""

    master_id = callback.data.replace("edit_master_", "")

    masters = config.get('staff', {}).get('masters', [])
    master = next((m for m in masters if m['id'] == master_id), None)

    if not master:
        await callback.answer("❌ Мастер не найден", show_alert=True)
        return

    staff_manager = StaffManager(config)
    services_names = staff_manager.get_master_services_names(master)
    schedule_summary = staff_manager.get_schedule_summary(master)

    text = f"""
✏️ <b>РЕДАКТИРОВАНИЕ: {master['name']}</b>

👤 <b>Имя:</b> {master['name']}
💼 <b>Должность:</b> {master.get('specialization') or master.get('role', 'Не указана')}
📋 <b>Услуги:</b> {', '.join(services_names) if services_names else 'Не выбраны'}
📅 <b>График:</b> {schedule_summary}

Что изменить?
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить имя", callback_data=f"edit_master_name_{master_id}")],
        [InlineKeyboardButton(text="✏️ Изменить должность", callback_data=f"edit_master_role_{master_id}")],
        [InlineKeyboardButton(text="📋 Изменить услуги", callback_data=f"edit_master_services_{master_id}")],
        [InlineKeyboardButton(text="📅 Изменить график", callback_data=f"edit_master_schedule_{master_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="edit_master_list")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("edit_master_name_"))
async def edit_master_name_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование имени мастера"""

    master_id = callback.data.replace("edit_master_name_", "")

    text = "✏️ Введите новое имя мастера:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_master_{master_id}")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(StaffEditorStates.edit_name)
    await state.update_data(editing_master_id=master_id)
    await callback.answer()


@router.message(StaffEditorStates.edit_name)
async def edit_master_name_save(message: Message, state: FSMContext, config: dict, config_manager):
    """Сохранить новое имя мастера"""

    data = await state.get_data()
    master_id = data.get('editing_master_id')
    new_name = message.text.strip()

    is_valid, error = validate_master_name(new_name)

    if not is_valid:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_master_{master_id}")],
        ])
        await message.answer(f"❌ {error}\n\nПопробуйте ещё раз:", reply_markup=keyboard)
        return

    # Сохраняем
    editor = get_config_editor(config)
    editor.update_master(master_id, {'name': new_name})

    # Обновляем в памяти
    for master in config.get('staff', {}).get('masters', []):
        if master['id'] == master_id:
            master['name'] = new_name
            break

    config_manager.config['staff'] = config['staff']

    await message.answer(f"✅ Имя обновлено: <b>{new_name}</b>")
    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 К персоналу", callback_data="staff_menu")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")],
    ])
    await message.answer("Выберите действие:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("edit_master_role_"))
async def edit_master_role_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование должности мастера"""

    master_id = callback.data.replace("edit_master_role_", "")

    text = "✏️ Введите новую должность/специализацию:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_master_{master_id}")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(StaffEditorStates.edit_role)
    await state.update_data(editing_master_id=master_id)
    await callback.answer()


@router.message(StaffEditorStates.edit_role)
async def edit_master_role_save(message: Message, state: FSMContext, config: dict, config_manager):
    """Сохранить новую должность мастера"""

    data = await state.get_data()
    master_id = data.get('editing_master_id')
    new_role = message.text.strip()

    is_valid, error = validate_master_role(new_role)

    if not is_valid:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_master_{master_id}")],
        ])
        await message.answer(f"❌ {error}\n\nПопробуйте ещё раз:", reply_markup=keyboard)
        return

    # Сохраняем оба поля для совместимости
    editor = get_config_editor(config)
    editor.update_master(master_id, {'specialization': new_role, 'role': new_role})

    # Обновляем в памяти
    for master in config.get('staff', {}).get('masters', []):
        if master['id'] == master_id:
            master['specialization'] = new_role
            master['role'] = new_role
            break

    config_manager.config['staff'] = config['staff']

    await message.answer(f"✅ Должность обновлена: <b>{new_role}</b>")
    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 К персоналу", callback_data="staff_menu")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")],
    ])
    await message.answer("Выберите действие:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("edit_master_services_"))
async def edit_master_services_start(callback: CallbackQuery, state: FSMContext, config: dict):
    """Начать редактирование услуг мастера"""

    master_id = callback.data.replace("edit_master_services_", "")

    masters = config.get('staff', {}).get('masters', [])
    master = next((m for m in masters if m['id'] == master_id), None)

    if not master:
        await callback.answer("❌ Мастер не найден", show_alert=True)
        return

    services = config.get('services', [])
    if not services:
        await callback.answer("❌ В системе нет услуг", show_alert=True)
        return

    await state.update_data(editing_master_id=master_id, editing_services=list(master.get('services', [])))

    current_services = master.get('services', [])

    keyboard_rows = []
    for service in services:
        is_selected = service['id'] in current_services
        mark = "☑" if is_selected else "☐"
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"{mark} {service['name']} ({service['price']}₽)",
                callback_data=f"toggle_master_service_{service['id']}"
            )
        ])

    keyboard_rows.append([InlineKeyboardButton(text="✅ Сохранить", callback_data="save_master_services")])
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"edit_master_{master_id}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    text = f"""
✏️ <b>РЕДАКТИРОВАНИЕ УСЛУГ: {master['name']}</b>

Выберите услуги, которые выполняет мастер.
Нажимайте на услуги для выбора/отмены:
"""

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(StaffEditorStates.edit_services)
    await callback.answer()


@router.callback_query(StaffEditorStates.edit_services, F.data.startswith("toggle_master_service_"))
async def toggle_master_service(callback: CallbackQuery, state: FSMContext, config: dict):
    """Переключить выбор услуги для мастера"""

    service_id = callback.data.replace("toggle_master_service_", "")

    data = await state.get_data()
    selected = data.get('editing_services', [])
    master_id = data.get('editing_master_id')

    if service_id in selected:
        selected.remove(service_id)
    else:
        selected.append(service_id)

    await state.update_data(editing_services=selected)

    # Обновляем клавиатуру
    services = config.get('services', [])

    keyboard_rows = []
    for service in services:
        is_selected = service['id'] in selected
        mark = "☑" if is_selected else "☐"
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"{mark} {service['name']} ({service['price']}₽)",
                callback_data=f"toggle_master_service_{service['id']}"
            )
        ])

    keyboard_rows.append([InlineKeyboardButton(text="✅ Сохранить", callback_data="save_master_services")])
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"edit_master_{master_id}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(StaffEditorStates.edit_services, F.data == "save_master_services")
async def save_master_services(callback: CallbackQuery, state: FSMContext, config: dict, config_manager):
    """Сохранить изменённые услуги мастера"""

    data = await state.get_data()
    selected = data.get('editing_services', [])
    master_id = data.get('editing_master_id')

    if not selected:
        await callback.answer("❌ Выберите хотя бы одну услугу", show_alert=True)
        return

    # Сохраняем
    editor = get_config_editor(config)
    editor.update_master(master_id, {'services': selected})

    # Обновляем в памяти
    for master in config.get('staff', {}).get('masters', []):
        if master['id'] == master_id:
            master['services'] = selected
            break

    config_manager.config['staff'] = config['staff']

    await callback.answer(f"✅ Услуги обновлены ({len(selected)} шт.)")
    await state.clear()

    # Возвращаемся к мастеру
    await edit_master_show(callback, config)


@router.callback_query(F.data.startswith("edit_master_schedule_"))
async def edit_master_schedule(callback: CallbackQuery, config: dict):
    """Изменить график мастера"""

    master_id = callback.data.replace("edit_master_schedule_", "")

    text = "📅 <b>ИЗМЕНЕНИЕ ГРАФИКА</b>\n\nВыберите новый шаблон графика:"

    templates = StaffManager.get_schedule_templates()

    keyboard_rows = []
    for template_id, description in templates.items():
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"📅 {description}",
                callback_data=f"apply_schedule_{master_id}_{template_id}"
            )
        ])

    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"edit_master_{master_id}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("apply_schedule_"))
async def apply_new_schedule(callback: CallbackQuery, config: dict, config_manager):
    """Применить новый шаблон графика"""

    parts = callback.data.replace("apply_schedule_", "").split("_", 1)
    if len(parts) != 2:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    master_id, template_id = parts

    schedule = StaffManager.create_default_schedule(template_id)

    # Сохраняем
    editor = get_config_editor(config)
    editor.update_master(master_id, {'schedule': schedule})

    # Обновляем в памяти
    for master in config.get('staff', {}).get('masters', []):
        if master['id'] == master_id:
            master['schedule'] = schedule
            break

    config_manager.config['staff'] = config['staff']

    templates = StaffManager.get_schedule_templates()
    schedule_desc = templates.get(template_id, template_id)

    await callback.answer(f"✅ График обновлён: {schedule_desc}")

    # Возвращаемся к мастеру
    await edit_master_show(callback, config)


# ==================== УДАЛЕНИЕ МАСТЕРА ====================

@router.callback_query(F.data == "delete_master_list")
async def delete_master_list(callback: CallbackQuery, config: dict):
    """Список мастеров для удаления"""

    masters = config.get('staff', {}).get('masters', [])

    if not masters:
        await callback.answer("Нет мастеров для удаления", show_alert=True)
        return

    text = "🗑 <b>УДАЛЕНИЕ МАСТЕРА</b>\n\nВыберите мастера для удаления:"

    keyboard_rows = []
    for master in masters:
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"🗑 {master['name']} — {master.get('specialization') or master.get('role', 'Мастер')}",
                callback_data=f"delete_master_{master['id']}"
            )
        ])

    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="staff_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("delete_master_") & ~F.data.startswith("delete_master_list"))
async def delete_master_confirm(callback: CallbackQuery, config: dict, db_manager):
    """Подтверждение удаления мастера с проверкой активных записей"""

    master_id = callback.data.replace("delete_master_", "")

    masters = config.get('staff', {}).get('masters', [])
    master = next((m for m in masters if m['id'] == master_id), None)

    if not master:
        await callback.answer("❌ Мастер не найден", show_alert=True)
        return

    # НОВОЕ: Проверяем активные записи у мастера
    active_orders_count = 0
    try:
        cursor = db_manager.connection.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM orders
            WHERE master_id = ? AND status = 'active'
            AND (booking_date IS NULL OR booking_date >= date('now'))
        """, (master_id,))
        active_orders_count = cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error checking active orders for master {master_id}: {e}")

    warning_text = ""
    if active_orders_count > 0:
        warning_text = f"\n⚠️ <b>ВНИМАНИЕ:</b> У мастера {active_orders_count} активных записей!\nОни останутся в системе, но мастер не будет отображаться.\n"

    text = f"""
⚠️ <b>УДАЛЕНИЕ МАСТЕРА</b>

Вы уверены, что хотите удалить мастера?

👤 <b>{master['name']}</b>
💼 {master.get('specialization') or master.get('role', 'Мастер')}
{warning_text}
<i>Это действие нельзя отменить!</i>
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_master_{master_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="delete_master_list"),
        ],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_master_"))
async def delete_master_execute(callback: CallbackQuery, config: dict, config_manager, state: FSMContext):
    """Выполнить удаление мастера с обработкой ошибок"""

    master_id = callback.data.replace("confirm_delete_master_", "")

    # Находим мастера для имени
    masters = config.get('staff', {}).get('masters', [])
    master = next((m for m in masters if m['id'] == master_id), None)
    master_name = master['name'] if master else 'Неизвестный'

    try:
        # Удаляем из конфига
        editor = get_config_editor(config)
        success = editor.delete_master(master_id)

        if not success:
            await callback.answer("❌ Не удалось удалить мастера", show_alert=True)
            return

        # Обновляем в памяти
        config['staff']['masters'] = [m for m in masters if m['id'] != master_id]
        config_manager.config['staff'] = config['staff']

        await callback.answer(f"✅ Мастер \"{master_name}\" удалён!")
        logger.info(f"Master {master_id} ({master_name}) deleted by admin {callback.from_user.id}")

    except Exception as e:
        logger.error(f"Error deleting master {master_id}: {e}")
        await callback.answer(
            f"❌ Ошибка при удалении мастера: {str(e)[:50]}",
            show_alert=True
        )
        return

    await show_staff_menu(callback, config, state)


# ==================== ЗАКРЫТЫЕ ДАТЫ ====================

@router.callback_query(F.data == "closed_dates_menu")
async def closed_dates_menu(callback: CallbackQuery, config: dict):
    """Меню управления закрытыми датами"""

    masters = config.get('staff', {}).get('masters', [])

    if not masters:
        await callback.answer("Сначала добавьте мастеров", show_alert=True)
        return

    text = """
📅 <b>ЗАКРЫТЫЕ ДАТЫ</b>

Здесь вы можете закрыть определённые даты для мастеров (отпуск, больничный и т.д.)

Выберите мастера:
"""

    keyboard_rows = []
    for master in masters:
        closed_count = len(master.get('closed_dates', []))
        badge = f" ({closed_count})" if closed_count > 0 else ""
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"👤 {master['name']}{badge}",
                callback_data=f"closed_dates_{master['id']}"
            )
        ])

    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="staff_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("closed_dates_") & ~F.data.startswith("closed_dates_menu"))
async def show_master_closed_dates(callback: CallbackQuery, config: dict):
    """Показать закрытые даты мастера"""

    master_id = callback.data.replace("closed_dates_", "")

    masters = config.get('staff', {}).get('masters', [])
    master = next((m for m in masters if m['id'] == master_id), None)

    if not master:
        await callback.answer("❌ Мастер не найден", show_alert=True)
        return

    staff_manager = StaffManager(config)
    closed_text = staff_manager.format_closed_dates(master, limit=10)

    text = f"""
📅 <b>ЗАКРЫТЫЕ ДАТЫ: {master['name']}</b>

{closed_text}

Выберите действие:
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить закрытую дату", callback_data=f"add_closed_{master_id}")],
        [InlineKeyboardButton(text="🗑 Удалить закрытую дату", callback_data=f"remove_closed_list_{master_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="closed_dates_menu")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("add_closed_"))
async def add_closed_date_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление закрытой даты"""

    master_id = callback.data.replace("add_closed_", "")

    # Показываем ближайшие 14 дней
    today = datetime.now().date()
    dates = []
    for i in range(14):
        d = today + timedelta(days=i)
        dates.append(d)

    keyboard_rows = []
    row = []
    for d in dates:
        day_name = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][d.weekday()]
        btn_text = f"{d.day:02d}.{d.month:02d} {day_name}"
        row.append(InlineKeyboardButton(
            text=btn_text,
            callback_data=f"select_closed_date_{master_id}_{d.isoformat()}"
        ))
        if len(row) == 3:
            keyboard_rows.append(row)
            row = []

    if row:
        keyboard_rows.append(row)

    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"closed_dates_{master_id}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    text = "📅 <b>ДОБАВЛЕНИЕ ЗАКРЫТОЙ ДАТЫ</b>\n\nВыберите дату:"

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("select_closed_date_"))
async def select_closed_date(callback: CallbackQuery, state: FSMContext):
    """Выбрана дата для закрытия"""

    # Используем rsplit для корректной обработки master_id с подчёркиваниями
    # Формат: select_closed_date_{master_id}_{YYYY-MM-DD}
    remaining = callback.data.replace("select_closed_date_", "")

    # Разделяем справа по последнему подчёркиванию перед датой
    parts = remaining.rsplit("_", 1)
    if len(parts) != 2:
        await callback.answer("❌ Ошибка формата данных", show_alert=True)
        return

    master_id, date_str = parts

    # Проверяем формат даты
    try:
        date_obj = datetime.fromisoformat(date_str).date()
    except ValueError:
        await callback.answer("❌ Некорректная дата", show_alert=True)
        return

    await state.update_data(closing_master_id=master_id, closing_date=date_str)
    date_display = date_obj.strftime('%d.%m.%Y')

    text = f"""
📅 Дата: <b>{date_display}</b>

Введите причину закрытия (необязательно):

<i>Например: Отпуск, Больничный, Выходной</i>

Или нажмите «Пропустить» для сохранения без причины.
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"save_closed_no_reason_{master_id}_{date_str}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"closed_dates_{master_id}")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(ClosedDatesStates.enter_reason)
    await callback.answer()


@router.message(ClosedDatesStates.enter_reason)
async def save_closed_with_reason(message: Message, state: FSMContext, config: dict, config_manager):
    """Сохранить закрытую дату с причиной"""

    data = await state.get_data()
    master_id = data.get('closing_master_id')
    date_str = data.get('closing_date')
    reason = message.text.strip()[:100]  # Ограничение 100 символов

    # Сохраняем
    editor = get_config_editor(config)
    editor.add_closed_date(master_id, date_str, reason)

    # Обновляем в памяти
    for master in config.get('staff', {}).get('masters', []):
        if master['id'] == master_id:
            if 'closed_dates' not in master:
                master['closed_dates'] = []
            master['closed_dates'].append({'date': date_str, 'reason': reason})
            break

    config_manager.config['staff'] = config['staff']

    date_obj = datetime.fromisoformat(date_str).date()
    date_display = date_obj.strftime('%d.%m.%Y')

    await message.answer(f"✅ Дата {date_display} закрыта: <b>{reason}</b>")
    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 К закрытым датам", callback_data=f"closed_dates_{master_id}")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")],
    ])
    await message.answer("Выберите действие:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("save_closed_no_reason_"))
async def save_closed_no_reason(callback: CallbackQuery, state: FSMContext, config: dict, config_manager):
    """Сохранить закрытую дату без причины"""

    parts = callback.data.replace("save_closed_no_reason_", "").split("_", 1)
    if len(parts) != 2:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    master_id, date_str = parts

    # Сохраняем
    editor = get_config_editor(config)
    editor.add_closed_date(master_id, date_str, "")

    # Обновляем в памяти
    for master in config.get('staff', {}).get('masters', []):
        if master['id'] == master_id:
            if 'closed_dates' not in master:
                master['closed_dates'] = []
            master['closed_dates'].append({'date': date_str, 'reason': ''})
            break

    config_manager.config['staff'] = config['staff']

    date_obj = datetime.fromisoformat(date_str).date()
    date_display = date_obj.strftime('%d.%m.%Y')

    await callback.answer(f"✅ Дата {date_display} закрыта")
    await state.clear()

    # Возвращаемся к закрытым датам
    await show_master_closed_dates(callback, config)


@router.callback_query(F.data.startswith("remove_closed_list_"))
async def remove_closed_list(callback: CallbackQuery, config: dict):
    """Список закрытых дат для удаления"""

    master_id = callback.data.replace("remove_closed_list_", "")

    masters = config.get('staff', {}).get('masters', [])
    master = next((m for m in masters if m['id'] == master_id), None)

    if not master:
        await callback.answer("❌ Мастер не найден", show_alert=True)
        return

    closed_dates = master.get('closed_dates', [])

    if not closed_dates:
        await callback.answer("Нет закрытых дат для удаления", show_alert=True)
        return

    text = f"🗑 <b>УДАЛЕНИЕ ЗАКРЫТОЙ ДАТЫ: {master['name']}</b>\n\nВыберите дату для открытия:"

    keyboard_rows = []
    for cd in closed_dates:
        date_obj = datetime.strptime(cd['date'], '%Y-%m-%d').date()
        date_display = date_obj.strftime('%d.%m.%Y')
        reason = cd.get('reason', '')
        btn_text = f"🗑 {date_display}" + (f" ({reason})" if reason else "")
        keyboard_rows.append([
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f"remove_closed_{master_id}_{cd['date']}"
            )
        ])

    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"closed_dates_{master_id}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("remove_closed_") & ~F.data.startswith("remove_closed_list_"))
async def remove_closed_date(callback: CallbackQuery, config: dict, config_manager):
    """Удалить закрытую дату"""

    parts = callback.data.replace("remove_closed_", "").split("_", 1)
    if len(parts) != 2:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    master_id, date_str = parts

    # Удаляем
    editor = get_config_editor(config)
    editor.remove_closed_date(master_id, date_str)

    # Обновляем в памяти
    for master in config.get('staff', {}).get('masters', []):
        if master['id'] == master_id:
            master['closed_dates'] = [
                cd for cd in master.get('closed_dates', [])
                if cd['date'] != date_str
            ]
            break

    config_manager.config['staff'] = config['staff']

    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    date_display = date_obj.strftime('%d.%m.%Y')

    await callback.answer(f"✅ Дата {date_display} открыта")

    # Возвращаемся к закрытым датам
    await show_master_closed_dates(callback, config)
