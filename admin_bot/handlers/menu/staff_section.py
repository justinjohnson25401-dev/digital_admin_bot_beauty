"""
Обработчики раздела Персонал (нижняя клавиатура).
"""

from aiogram import F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext


async def reply_add_master_handler(message: Message, state: FSMContext):
    """Добавить мастера"""
    from admin_bot.states import StaffEditorStates
    await state.set_state(StaffEditorStates.enter_name)
    text = """
➕ <b>ДОБАВЛЕНИЕ МАСТЕРА</b>

Шаг 1 из 5: Введите имя мастера (от 2 до 50 символов):

<i>Например: Анна, Мария Иванова</i>
"""
    await message.answer(text)


async def reply_edit_master_handler(message: Message, config: dict):
    """Редактировать мастера"""
    masters = config.get('staff', {}).get('masters', [])
    if not masters:
        await message.answer("❌ Мастера не добавлены")
        return

    keyboard_rows = []
    for master in masters:
        keyboard_rows.append([InlineKeyboardButton(
            text=f"✏️ {master['name']}",
            callback_data=f"edit_master_{master['id']}"
        )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await message.answer("Выберите мастера для редактирования:", reply_markup=keyboard)


async def reply_closed_dates_handler(message: Message, config: dict):
    """Закрытые даты"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Управление датами", callback_data="closed_dates_menu")],
    ])
    await message.answer("📅 <b>Закрытые даты</b>\n\nВыберите мастера для управления:", reply_markup=keyboard)


def register_handlers(dp):
    """Регистрация обработчиков раздела Персонал"""
    dp.message.register(reply_add_master_handler, F.text == "➕ Добавить мастера")
    dp.message.register(reply_edit_master_handler, F.text == "✏️ Редактировать")
    dp.message.register(reply_closed_dates_handler, F.text == "📅 Закрытые даты")
