"""
Главное меню, toggle staff-режима.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.config_editor import ConfigEditor

logger = logging.getLogger(__name__)

router = Router()


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
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_settings")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "toggle_staff")
async def toggle_staff_feature(callback: CallbackQuery, config: dict, config_manager, state: FSMContext):
    """Включить/выключить функцию персонала"""

    editor = ConfigEditor(config_manager.config_path)
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