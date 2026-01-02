"""
Редактирование мастера.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from admin_bot.states import StaffEditorStates
from utils.config_editor import ConfigEditor
from utils.staff_manager import StaffManager
from utils.validators import validate_master_name, validate_master_role
from .keyboards import _build_masters_list_keyboard, _build_master_edit_keyboard, _build_services_keyboard

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == "edit_master_list")
async def show_edit_master_list(callback: CallbackQuery, config: dict):
    """Список мастеров для редактирования"""

    masters = config.get('staff', {}).get('masters', [])

    if not masters:
        await callback.answer("Нет мастеров для редактирования", show_alert=True)
        return

    text = "✏️ <b>РЕДАКТИРОВАНИЕ МАСТЕРА</b>\n\nВыберите мастера:"
    keyboard = _build_masters_list_keyboard(masters, "edit_master")

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("edit_master_"))
async def show_master_edit_menu(callback: CallbackQuery, config: dict):
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

    keyboard = _build_master_edit_keyboard(master_id)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("edit_master_name_"))
async def edit_master_name_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование имени мастера"""

    master_id = callback.data.replace("edit_master_name_", "")

    text = "✏️ Введите новое имя мастера:"

    await callback.message.edit_text(text)
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
        await message.answer(f"❌ {error}\n\nПопробуйте ещё раз:")
        return

    # Сохраняем
    editor = ConfigEditor(config_manager.config_path)
    editor.update_master(master_id, {'name': new_name})

    # Обновляем в памяти
    for master in config.get('staff', {}).get('masters', []):
        if master['id'] == master_id:
            master['name'] = new_name
            break

    config_manager.config['staff'] = config['staff']

    await message.answer(f"✅ Имя обновлено: <b>{new_name}</b>")
    await state.clear()

    # Возвращаемся к меню редактирования
    keyboard = _build_master_edit_keyboard(master_id)
    text = f"✅ Изменено!\n\n[показать меню редактирования]"
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("edit_master_role_"))
async def edit_master_role_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование должности мастера"""

    master_id = callback.data.replace("edit_master_role_", "")

    text = "✏️ Введите новую должность/специализацию:"

    await callback.message.edit_text(text)
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
        await message.answer(f"❌ {error}\n\nПопробуйте ещё раз:")
        return

    # Сохраняем оба поля для совместимости
    editor = ConfigEditor(config_manager.config_path)
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

    # Возвращаемся к меню редактирования
    keyboard = _build_master_edit_keyboard(master_id)
    text = f"✅ Изменено!\n\n[показать меню редактирования]"
    await message.answer(text, reply_markup=keyboard)


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

    keyboard = _build_services_keyboard(services, current_services)

    text = f"""
✏️ <b>РЕДАКТИРОВАНИЕ УСЛUG: {master['name']}</b>

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

    if service_id in selected:
        selected.remove(service_id)
    else:
        selected.append(service_id)

    await state.update_data(editing_services=selected)

    # Обновляем клавиатуру
    services = config.get('services', [])
    keyboard = _build_services_keyboard(services, selected)

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
    editor = ConfigEditor(config_manager.config_path)
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
    await show_master_edit_menu(callback, config)