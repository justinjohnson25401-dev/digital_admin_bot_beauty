"""
Редактор текстов и интерфейса - сообщения и FAQ.
"""

from pathlib import Path
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from admin_bot.states import TextsEditorStates, FAQEditorStates
from utils.config_editor import ConfigEditor
from utils.validators import validate_message_text, validate_faq_button, validate_faq_answer

router = Router()

# Корневая директория проекта
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Названия ключей сообщений для отображения
MESSAGE_LABELS = {
    'welcome': '💬 Приветствие',
    'success': '✅ Подтверждение записи',
    'booking_cancelled': '❌ Отмена записи',
    'error_phone': '📞 Ошибка телефона',
    'error_generic': '⚠️ Общая ошибка',
    'slot_taken': '🚫 Слот занят'
}


def get_config_editor(config: dict) -> ConfigEditor:
    """Получить ConfigEditor с абсолютным путём к конфигу"""
    config_path = PROJECT_ROOT / "configs" / "client_lite.json"
    return ConfigEditor(str(config_path))


@router.callback_query(F.data == "texts_menu")
async def show_texts_menu(callback: CallbackQuery, config: dict):
    """Главное меню редактирования текстов"""

    text = """
📝 <b>ТЕКСТЫ И ИНТЕРФЕЙС</b>

Здесь вы можете редактировать:
• Сообщения бота клиентам
• Ответы на частые вопросы (FAQ)

Выберите раздел:
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Сообщения бота", callback_data="texts_messages")],
        [InlineKeyboardButton(text="❓ FAQ (Частые вопросы)", callback_data="texts_faq")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# ==================== СООБЩЕНИЯ БОТА ====================

@router.callback_query(F.data == "texts_messages")
async def show_messages_list(callback: CallbackQuery, config: dict):
    """Список сообщений для редактирования"""

    messages = config.get('messages', {})

    text = """
💬 <b>СООБЩЕНИЯ БОТА</b>

Выберите сообщение для редактирования:
"""

    keyboard_rows = []

    for key, label in MESSAGE_LABELS.items():
        current = messages.get(key, '')
        # Показать превью (первые 30 символов)
        preview = current[:30] + '...' if len(current) > 30 else current
        btn_text = f"{label}"
        keyboard_rows.append([
            InlineKeyboardButton(text=btn_text, callback_data=f"edit_message_{key}")
        ])

    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="texts_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("edit_message_"))
async def edit_message_start(callback: CallbackQuery, state: FSMContext, config: dict):
    """Начать редактирование сообщения"""

    message_key = callback.data.replace("edit_message_", "")
    messages = config.get('messages', {})
    current_text = messages.get(message_key, '')
    label = MESSAGE_LABELS.get(message_key, message_key)

    text = f"""
✏️ <b>РЕДАКТИРОВАНИЕ: {label}</b>

Текущий текст:
━━━━━━━━━━━━━━━━━━━━━━
{current_text or '(не задан)'}
━━━━━━━━━━━━━━━━━━━━━━

Введите новый текст (от 5 до 1000 символов):

💡 <i>Можно использовать переменные:</i>
• <code>{{id}}</code> — номер заказа
• <code>{{date}}</code> — дата записи
• <code>{{time}}</code> — время записи
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="texts_messages")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(TextsEditorStates.enter_text)
    await state.update_data(message_key=message_key)
    await callback.answer()


@router.message(TextsEditorStates.enter_text)
async def save_message_text(message: Message, state: FSMContext, config: dict, config_manager):
    """Сохранить новый текст сообщения"""

    data = await state.get_data()
    message_key = data.get('message_key')
    new_text = message.text.strip()

    # Валидация
    is_valid, error = validate_message_text(new_text)

    if not is_valid:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="texts_messages")],
        ])
        await message.answer(f"❌ {error}\n\nПопробуйте ещё раз:", reply_markup=keyboard)
        return

    # Сохранение
    if 'messages' not in config:
        config['messages'] = {}

    config['messages'][message_key] = new_text
    config_manager.config['messages'][message_key] = new_text
    config_manager.save_config()

    label = MESSAGE_LABELS.get(message_key, message_key)
    await message.answer(f"✅ Сообщение <b>{label}</b> обновлено!")
    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 К сообщениям", callback_data="texts_messages")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")],
    ])
    await message.answer("Выберите действие:", reply_markup=keyboard)


# ==================== FAQ ====================

@router.callback_query(F.data == "texts_faq")
async def show_faq_menu(callback: CallbackQuery, config: dict):
    """Управление FAQ"""

    faq = config.get('faq', [])

    text = "❓ <b>FAQ (Частые вопросы)</b>\n\n"

    if faq:
        text += "Текущие вопросы:\n"
        for i, item in enumerate(faq, 1):
            text += f"{i}. {item.get('btn', '???')}\n"
    else:
        text += "<i>Нет добавленных вопросов</i>\n"

    text += "\nВыберите действие:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить вопрос", callback_data="faq_add")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="faq_edit_list")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data="faq_delete_list")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="texts_menu")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# ==================== ДОБАВЛЕНИЕ FAQ ====================

@router.callback_query(F.data == "faq_add")
async def faq_add_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление FAQ"""

    text = """
➕ <b>ДОБАВЛЕНИЕ ВОПРОСА</b>

Введите текст кнопки (от 2 до 40 символов):

<i>Например: 💰 Цены, 📍 Адрес, 🕐 Часы работы</i>
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="texts_faq")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(FAQEditorStates.add_button_text)
    await callback.answer()


@router.message(FAQEditorStates.add_button_text)
async def faq_add_button(message: Message, state: FSMContext):
    """Сохранить текст кнопки FAQ"""

    button_text = message.text.strip()

    is_valid, error = validate_faq_button(button_text)

    if not is_valid:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="texts_faq")],
        ])
        await message.answer(f"❌ {error}\n\nПопробуйте ещё раз:", reply_markup=keyboard)
        return

    await state.update_data(faq_button=button_text)

    text = f"""
✅ Кнопка: <b>{button_text}</b>

Теперь введите ответ на этот вопрос (от 5 до 1000 символов):
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="texts_faq")],
    ])

    await message.answer(text, reply_markup=keyboard)
    await state.set_state(FAQEditorStates.add_answer)


@router.message(FAQEditorStates.add_answer)
async def faq_add_answer(message: Message, state: FSMContext, config: dict, config_manager):
    """Сохранить ответ FAQ"""

    answer = message.text.strip()

    is_valid, error = validate_faq_answer(answer)

    if not is_valid:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="texts_faq")],
        ])
        await message.answer(f"❌ {error}\n\nПопробуйте ещё раз:", reply_markup=keyboard)
        return

    data = await state.get_data()
    button_text = data.get('faq_button')

    # Сохранение
    if 'faq' not in config:
        config['faq'] = []

    new_faq = {'btn': button_text, 'answer': answer}
    config['faq'].append(new_faq)
    config_manager.config['faq'] = config['faq']
    config_manager.save_config()

    await message.answer(f"✅ Вопрос добавлен!\n\nКнопка: <b>{button_text}</b>")
    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ К FAQ", callback_data="texts_faq")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")],
    ])
    await message.answer("Выберите действие:", reply_markup=keyboard)


# ==================== РЕДАКТИРОВАНИЕ FAQ ====================

@router.callback_query(F.data == "faq_edit_list")
async def faq_edit_list(callback: CallbackQuery, config: dict):
    """Список FAQ для редактирования"""

    faq = config.get('faq', [])

    if not faq:
        await callback.answer("Нет вопросов для редактирования", show_alert=True)
        return

    text = "✏️ <b>РЕДАКТИРОВАНИЕ FAQ</b>\n\nВыберите вопрос для редактирования:"

    keyboard_rows = []
    for i, item in enumerate(faq):
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"{i + 1}. {item.get('btn', '???')}",
                callback_data=f"faq_edit_{i}"
            )
        ])

    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="texts_faq")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("faq_edit_") & ~F.data.startswith("faq_edit_list"))
async def faq_edit_item(callback: CallbackQuery, state: FSMContext, config: dict):
    """Редактирование конкретного FAQ"""

    try:
        index = int(callback.data.replace("faq_edit_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    faq = config.get('faq', [])

    if index < 0 or index >= len(faq):
        await callback.answer("❌ Вопрос не найден", show_alert=True)
        return

    item = faq[index]

    text = f"""
✏️ <b>РЕДАКТИРОВАНИЕ FAQ #{index + 1}</b>

Кнопка: <b>{item.get('btn', '')}</b>

Ответ:
━━━━━━━━━━━━━━━━━━━━━━
{item.get('answer', '')}
━━━━━━━━━━━━━━━━━━━━━━

Что изменить?
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить кнопку", callback_data=f"faq_edit_btn_{index}")],
        [InlineKeyboardButton(text="✏️ Изменить ответ", callback_data=f"faq_edit_ans_{index}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="faq_edit_list")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("faq_edit_btn_"))
async def faq_edit_button_start(callback: CallbackQuery, state: FSMContext, config: dict):
    """Начать редактирование кнопки FAQ"""

    try:
        index = int(callback.data.replace("faq_edit_btn_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    faq = config.get('faq', [])
    current = faq[index].get('btn', '') if index < len(faq) else ''

    text = f"""
✏️ <b>РЕДАКТИРОВАНИЕ КНОПКИ</b>

Текущий текст: <b>{current}</b>

Введите новый текст кнопки:
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"faq_edit_{index}")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(FAQEditorStates.edit_button)
    await state.update_data(faq_index=index)
    await callback.answer()


@router.message(FAQEditorStates.edit_button)
async def faq_edit_button_save(message: Message, state: FSMContext, config: dict, config_manager):
    """Сохранить новую кнопку FAQ"""

    data = await state.get_data()
    index = data.get('faq_index')
    new_button = message.text.strip()

    is_valid, error = validate_faq_button(new_button)

    if not is_valid:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"faq_edit_{index}")],
        ])
        await message.answer(f"❌ {error}\n\nПопробуйте ещё раз:", reply_markup=keyboard)
        return

    # Сохранение
    config['faq'][index]['btn'] = new_button
    config_manager.config['faq'] = config['faq']
    config_manager.save_config()

    await message.answer(f"✅ Кнопка обновлена: <b>{new_button}</b>")
    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ К FAQ", callback_data="texts_faq")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")],
    ])
    await message.answer("Выберите действие:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("faq_edit_ans_"))
async def faq_edit_answer_start(callback: CallbackQuery, state: FSMContext, config: dict):
    """Начать редактирование ответа FAQ"""

    try:
        index = int(callback.data.replace("faq_edit_ans_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    faq = config.get('faq', [])
    current = faq[index].get('answer', '') if index < len(faq) else ''

    text = f"""
✏️ <b>РЕДАКТИРОВАНИЕ ОТВЕТА</b>

Текущий ответ:
━━━━━━━━━━━━━━━━━━━━━━
{current}
━━━━━━━━━━━━━━━━━━━━━━

Введите новый ответ:
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"faq_edit_{index}")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(FAQEditorStates.edit_answer)
    await state.update_data(faq_index=index)
    await callback.answer()


@router.message(FAQEditorStates.edit_answer)
async def faq_edit_answer_save(message: Message, state: FSMContext, config: dict, config_manager):
    """Сохранить новый ответ FAQ"""

    data = await state.get_data()
    index = data.get('faq_index')
    new_answer = message.text.strip()

    is_valid, error = validate_faq_answer(new_answer)

    if not is_valid:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"faq_edit_{index}")],
        ])
        await message.answer(f"❌ {error}\n\nПопробуйте ещё раз:", reply_markup=keyboard)
        return

    # Сохранение
    config['faq'][index]['answer'] = new_answer
    config_manager.config['faq'] = config['faq']
    config_manager.save_config()

    await message.answer("✅ Ответ обновлён!")
    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ К FAQ", callback_data="texts_faq")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")],
    ])
    await message.answer("Выберите действие:", reply_markup=keyboard)


# ==================== УДАЛЕНИЕ FAQ ====================

@router.callback_query(F.data == "faq_delete_list")
async def faq_delete_list(callback: CallbackQuery, config: dict):
    """Список FAQ для удаления"""

    faq = config.get('faq', [])

    if not faq:
        await callback.answer("Нет вопросов для удаления", show_alert=True)
        return

    text = "🗑 <b>УДАЛЕНИЕ FAQ</b>\n\nВыберите вопрос для удаления:"

    keyboard_rows = []
    for i, item in enumerate(faq):
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"🗑 {i + 1}. {item.get('btn', '???')}",
                callback_data=f"faq_delete_{i}"
            )
        ])

    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="texts_faq")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("faq_delete_") & ~F.data.startswith("faq_delete_list"))
async def faq_delete_confirm(callback: CallbackQuery, config: dict):
    """Подтверждение удаления FAQ"""

    try:
        index = int(callback.data.replace("faq_delete_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    faq = config.get('faq', [])

    if index < 0 or index >= len(faq):
        await callback.answer("❌ Вопрос не найден", show_alert=True)
        return

    item = faq[index]

    text = f"""
⚠️ <b>УДАЛЕНИЕ FAQ</b>

Вы уверены, что хотите удалить?

Кнопка: <b>{item.get('btn', '')}</b>

Ответ: {item.get('answer', '')[:100]}...
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"faq_confirm_delete_{index}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="faq_delete_list"),
        ],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("faq_confirm_delete_"))
async def faq_delete_execute(callback: CallbackQuery, config: dict, config_manager):
    """Выполнить удаление FAQ"""

    try:
        index = int(callback.data.replace("faq_confirm_delete_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    faq = config.get('faq', [])

    if index < 0 or index >= len(faq):
        await callback.answer("❌ Вопрос не найден", show_alert=True)
        return

    deleted = faq.pop(index)
    config_manager.config['faq'] = faq
    config_manager.save_config()

    await callback.answer(f"✅ Вопрос \"{deleted.get('btn', '')}\" удалён!")

    # Вернуться к списку FAQ
    await show_faq_menu(callback, config)
