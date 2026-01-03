"""
Управление нерабочими датами (выходными, отпуском и т.д).
"""

import logging
from datetime import datetime, date
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from utils.calendar import DialogCalendar, DialogCalendarCallback

from admin_bot.states import StaffEditorStates
from utils.config_editor import ConfigEditor
from .keyboards import _build_masters_list_keyboard, _build_closed_dates_keyboard

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == "closed_dates_menu")
async def show_masters_for_closed_dates(callback: CallbackQuery, config: dict):
    """Показать список мастеров для управления закрытыми датами"""

    masters = config.get('staff', {}).get('masters', [])

    if not masters:
        await callback.answer("Нет мастеров для настройки дат", show_alert=True)
        return

    text = "📅 <b>ЗАКРЫТЫЕ ДАТЫ</b>\n\nВыберите мастера, чтобы настроить выходные/отпуск:"
    keyboard = _build_masters_list_keyboard(masters, "closed_dates")

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("closed_dates_"))
async def show_closed_dates_menu(callback: CallbackQuery, state: FSMContext, config: dict):
    """Показать меню управления закрытыми датами для мастера"""

    master_id = callback.data.replace("closed_dates_", "")
    await state.update_data(current_master_id=master_id)

    masters = config.get('staff', {}).get('masters', [])
    master = next((m for m in masters if m['id'] == master_id), None)

    if not master:
        await callback.answer("❌ Мастер не найден", show_alert=True)
        return

    closed_dates = sorted(master.get('closed_dates', []), key=lambda x: x['date'])

    text = f"""
📅 <b>ЗАКРЫТЫЕ ДАТЫ: {master['name']}</b>

Здесь можно указать дни, когда мастер не работает (отпуск, больничный и т.д.).

"""

    if closed_dates:
        text += "<b>Текущие закрытые даты:</b>\n"
        for cd in closed_dates:
            date_obj = datetime.strptime(cd['date'], '%Y-%m-%d').date()
            reason = cd.get('reason')
            text += f"• {date_obj.strftime('%d.%m.%Y')}" + (f" - <i>{reason}</i>" if reason else "") + "\n"
    else:
        text += "<i>Нет запланированных выходных.</i>\n"

    text += "\nВыберите действие:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить дату", callback_data=f"add_closed_date_{master_id}")],
        [InlineKeyboardButton(text="🗑 Удалить дату", callback_data=f"remove_closed_date_{master_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="staff_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("add_closed_date_"))
async def add_closed_date_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление закрытой даты - показать календарь"""

    master_id = callback.data.replace("add_closed_date_", "")
    await state.update_data(current_master_id=master_id)
    await state.set_state(StaffEditorStates.add_closed_date_cal)

    keyboard = await DialogCalendar().start_calendar()

    await callback.message.edit_text("🗓 Выберите дату:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(DialogCalendarCallback.filter(), StaffEditorStates.add_closed_date_cal)
async def process_add_closed_date(callback: CallbackQuery, callback_data: DialogCalendarCallback, state: FSMContext):
    """Обработка выбора даты в календаре и запрос причины"""

    selected, date_val = await DialogCalendar().process_selection(callback, callback_data)

    if not selected:
        return

    if date_val <= datetime.now().date():
        await callback.answer("❌ Нельзя выбрать прошедшую или сегодняшнюю дату", show_alert=True)
        keyboard = await DialogCalendar().start_calendar()
        await callback.message.edit_text("🗓 Выберите дату (будущую):", reply_markup=keyboard)
        return

    await state.update_data(selected_date=date_val.strftime("%Y-%m-%d"))
    await state.set_state(StaffEditorStates.add_closed_date_reason)

    text = f"""
🗓 Выбрана дата: <b>{date_val.strftime('%d.%m.%Y')}</b>

✏️ Укажите причину (необязательно):

<i>Например: Отпуск, Больничный, Учёба</i>
"""

    await callback.message.edit_text(text)


@router.message(StaffEditorStates.add_closed_date_reason)
async def process_closed_date_reason(message: Message, state: FSMContext, config: dict, config_manager):
    """Сохранение закрытой даты с причиной"""

    reason = message.text.strip()
    data = await state.get_data()
    selected_date = data.get('selected_date')
    master_id = data.get('current_master_id')

    if not selected_date or not master_id:
        await message.answer("❌ Произошла ошибка. Начните заново.")
        await state.clear()
        return

    masters = config.get('staff', {}).get('masters', [])
    master = next((m for m in masters if m['id'] == master_id), None)

    if not master:
        await message.answer("❌ Мастер не найден.")
        await state.clear()
        return

    editor = ConfigEditor(config_manager.config_path)
    editor.add_closed_date(master_id, selected_date, reason)

    closed_dates = master.get('closed_dates', [])
    closed_dates.append({'date': selected_date, 'reason': reason})
    master['closed_dates'] = closed_dates
    config_manager.config['staff'] = config['staff']

    await message.answer(f"✅ Дата <b>{datetime.strptime(selected_date, '%Y-%m-%d').strftime('%d.%m.%Y')}</b> добавлена как нерабочая.")
    await state.clear()

    closed_dates = sorted(master.get('closed_dates', []), key=lambda x: x['date'])
    text = f"""
📅 <b>ЗАКРЫТЫЕ ДАТЫ: {master['name']}</b>

Здесь можно указать дни, когда мастер не работает (отпуск, больничный и т.д.).

"""
    if closed_dates:
        text += "<b>Текущие закрытые даты:</b>\n"
        for cd in closed_dates:
            date_obj = datetime.strptime(cd['date'], '%Y-%m-%d').date()
            reason = cd.get('reason')
            text += f"• {date_obj.strftime('%d.%m.%Y')}" + (f" - <i>{reason}</i>" if reason else "") + "\n"
    else:
        text += "<i>Нет запланированных выходных.</i>\n"

    text += "\nВыберите действие:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить дату", callback_data=f"add_closed_date_{master_id}")],
        [InlineKeyboardButton(text="🗑 Удалить дату", callback_data=f"remove_closed_date_{master_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="staff_menu")]
    ])

    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("remove_closed_date_"))
async def remove_closed_date_start(callback: CallbackQuery, config: dict):
    """Показать список закрытых дат для удаления"""

    master_id = callback.data.replace("remove_closed_date_", "")

    masters = config.get('staff', {}).get('masters', [])
    master = next((m for m in masters if m['id'] == master_id), None)

    if not master:
        await callback.answer("❌ Мастер не найден", show_alert=True)
        return

    closed_dates = sorted(master.get('closed_dates', []), key=lambda x: x['date'])

    if not closed_dates:
        await callback.answer("Нет дат для удаления", show_alert=True)
        return

    text = "🗑 <b>УДАЛЕНИЕ ЗАКРЫТОЙ ДАТЫ</b>\n\nНажмите на дату, чтобы удалить:"
    keyboard = _build_closed_dates_keyboard(master_id, closed_dates)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("remove_closed_"))
async def remove_closed_date_confirm(callback: CallbackQuery, config: dict, config_manager, state: FSMContext):
    """Удалить закрытую дату"""

    parts = callback.data.replace("remove_closed_", "").split("_")
    if len(parts) < 2:
        await callback.answer("❌ Ошибка: неверный формат callback", show_alert=True)
        return

    master_id = parts[0]
    date_to_remove = "-".join(parts[1:])

    editor = ConfigEditor(config_manager.config_path)
    editor.remove_closed_date(master_id, date_to_remove)

    masters = config.get('staff', {}).get('masters', [])
    master = None
    for m in masters:
        if m['id'] == master_id:
            m['closed_dates'] = [d for d in m.get('closed_dates', []) if d['date'] != date_to_remove]
            master = m
            break

    config_manager.config['staff'] = config['staff']

    await callback.answer(f"✅ Дата {datetime.strptime(date_to_remove, '%Y-%m-%d').strftime('%d.%m.%Y')} удалена.")

    if not master:
        await callback.message.edit_text("Мастер не найден, список не может быть обновлен.")
        return

    closed_dates = sorted(master.get('closed_dates', []), key=lambda x: x['date'])

    text = f"""
📅 <b>ЗАКРЫТЫЕ ДАТЫ: {master['name']}</b>

Здесь можно указать дни, когда мастер не работает (отпуск, больничный и т.д.).

"""

    if closed_dates:
        text += "<b>Текущие закрытые даты:</b>\n"
        for cd in closed_dates:
            date_obj = datetime.strptime(cd['date'], '%Y-%m-%d').date()
            reason = cd.get('reason')
            text += f"• {date_obj.strftime('%d.%m.%Y')}" + (f" - <i>{reason}</i>" if reason else "") + "\n"
    else:
        text += "<i>Нет запланированных выходных.</i>\n"

    text += "\nВыберите действие:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить дату", callback_data=f"add_closed_date_{master_id}")],
        [InlineKeyboardButton(text="🗑 Удалить дату", callback_data=f"remove_closed_date_{master_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="staff_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
