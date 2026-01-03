"""
Редактирование расписания мастера.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from utils.config_editor import ConfigEditor
from utils.staff_manager import StaffManager
from .edit import show_master_edit_menu

logger = logging.getLogger(__name__)

router = Router()


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
    editor = ConfigEditor(config_manager.config_path)
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
    await show_master_edit_menu(callback, config)