"""
Управление акциями и спецпредложениями
"""

import logging
from pathlib import Path
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.config_editor import ConfigEditor

logger = logging.getLogger(__name__)

router = Router()

# Корневая директория проекта
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class PromotionStates(StatesGroup):
    """FSM состояния для редактирования акций"""
    enter_title = State()
    enter_description = State()
    enter_emoji = State()
    enter_valid_until = State()
    edit_title = State()
    edit_description = State()
    edit_emoji = State()
    edit_valid_until = State()


def get_config_editor(config: dict) -> ConfigEditor:
    """Получить ConfigEditor с путём к конфигу"""
    config_path = PROJECT_ROOT / "configs" / "client_lite.json"
    return ConfigEditor(str(config_path))


def get_promotions_keyboard(promotions: list) -> InlineKeyboardMarkup:
    """Клавиатура списка акций"""
    buttons = []

    for i, promo in enumerate(promotions):
        status = "✅" if promo.get('active', True) else "❌"
        emoji = promo.get('emoji', '🎁')
        title = promo.get('title', 'Без названия')[:20]
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {emoji} {title}",
                callback_data=f"promo_edit:{i}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="➕ Добавить акцию", callback_data="promo_add")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "promotions_menu")
async def show_promotions_menu(callback: CallbackQuery, config: dict, state: FSMContext):
    """Главное меню управления акциями"""
    await state.clear()

    promotions = config.get('promotions', [])

    text = "🎁 <b>УПРАВЛЕНИЕ АКЦИЯМИ</b>\n\n"

    if promotions:
        active_count = sum(1 for p in promotions if p.get('active', True))
        text += f"Всего акций: {len(promotions)}\n"
        text += f"Активных: {active_count}\n\n"
        text += "Выберите акцию для редактирования:"
    else:
        text += "Акции пока не добавлены.\n\n"
        text += "Нажмите «➕ Добавить акцию» чтобы создать первую акцию."

    keyboard = get_promotions_keyboard(promotions)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# ==================== ДОБАВЛЕНИЕ АКЦИИ ====================

@router.callback_query(F.data == "promo_add")
async def add_promotion_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление акции"""
    text = """
🎁 <b>ДОБАВЛЕНИЕ АКЦИИ</b>

Шаг 1 из 4: Введите название акции:

<i>Например: Скидка 20% на первое посещение</i>
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="promotions_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(PromotionStates.enter_title)
    await callback.answer()


@router.message(PromotionStates.enter_title)
async def add_promotion_title(message: Message, state: FSMContext):
    """Сохранить название акции"""
    title = message.text.strip()

    if len(title) < 3:
        await message.answer("❌ Название слишком короткое (минимум 3 символа)")
        return

    if len(title) > 100:
        await message.answer("❌ Название слишком длинное (максимум 100 символов)")
        return

    await state.update_data(promo_title=title)

    text = f"""
✅ Название: <b>{title}</b>

Шаг 2 из 4: Введите описание акции:

<i>Например: При записи через бота получите скидку на первую процедуру</i>

Или нажмите «Пропустить».
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="promo_skip_description")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="promotions_menu")]
    ])

    await message.answer(text, reply_markup=keyboard)
    await state.set_state(PromotionStates.enter_description)


@router.callback_query(PromotionStates.enter_description, F.data == "promo_skip_description")
async def skip_description(callback: CallbackQuery, state: FSMContext):
    """Пропустить описание"""
    await state.update_data(promo_description="")
    await ask_for_emoji(callback, state)
    await callback.answer()


@router.message(PromotionStates.enter_description)
async def add_promotion_description(message: Message, state: FSMContext):
    """Сохранить описание акции"""
    description = message.text.strip()

    if len(description) > 500:
        await message.answer("❌ Описание слишком длинное (максимум 500 символов)")
        return

    await state.update_data(promo_description=description)
    await ask_for_emoji_message(message, state)


async def ask_for_emoji(callback: CallbackQuery, state: FSMContext):
    """Запросить эмодзи (callback версия)"""
    data = await state.get_data()

    text = f"""
✅ Название: <b>{data['promo_title']}</b>
✅ Описание: {data.get('promo_description') or '—'}

Шаг 3 из 4: Выберите эмодзи для акции:
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎁", callback_data="promo_emoji:🎁"),
            InlineKeyboardButton(text="💰", callback_data="promo_emoji:💰"),
            InlineKeyboardButton(text="🔥", callback_data="promo_emoji:🔥"),
            InlineKeyboardButton(text="⭐", callback_data="promo_emoji:⭐"),
        ],
        [
            InlineKeyboardButton(text="💎", callback_data="promo_emoji:💎"),
            InlineKeyboardButton(text="🎉", callback_data="promo_emoji:🎉"),
            InlineKeyboardButton(text="💝", callback_data="promo_emoji:💝"),
            InlineKeyboardButton(text="✨", callback_data="promo_emoji:✨"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="promotions_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(PromotionStates.enter_emoji)


async def ask_for_emoji_message(message: Message, state: FSMContext):
    """Запросить эмодзи (message версия)"""
    data = await state.get_data()

    text = f"""
✅ Название: <b>{data['promo_title']}</b>
✅ Описание: {data.get('promo_description') or '—'}

Шаг 3 из 4: Выберите эмодзи для акции:
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎁", callback_data="promo_emoji:🎁"),
            InlineKeyboardButton(text="💰", callback_data="promo_emoji:💰"),
            InlineKeyboardButton(text="🔥", callback_data="promo_emoji:🔥"),
            InlineKeyboardButton(text="⭐", callback_data="promo_emoji:⭐"),
        ],
        [
            InlineKeyboardButton(text="💎", callback_data="promo_emoji:💎"),
            InlineKeyboardButton(text="🎉", callback_data="promo_emoji:🎉"),
            InlineKeyboardButton(text="💝", callback_data="promo_emoji:💝"),
            InlineKeyboardButton(text="✨", callback_data="promo_emoji:✨"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="promotions_menu")]
    ])

    await message.answer(text, reply_markup=keyboard)
    await state.set_state(PromotionStates.enter_emoji)


@router.callback_query(PromotionStates.enter_emoji, F.data.startswith("promo_emoji:"))
async def select_emoji(callback: CallbackQuery, state: FSMContext):
    """Выбрать эмодзи"""
    emoji = callback.data.replace("promo_emoji:", "")
    await state.update_data(promo_emoji=emoji)

    data = await state.get_data()

    text = f"""
✅ Название: <b>{data['promo_title']}</b>
✅ Описание: {data.get('promo_description') or '—'}
✅ Эмодзи: {emoji}

Шаг 4 из 4: Выберите срок действия:
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♾ Постоянная акция", callback_data="promo_permanent")],
        [InlineKeyboardButton(text="📅 До конца месяца", callback_data="promo_end_month")],
        [InlineKeyboardButton(text="📅 На 2 недели", callback_data="promo_2weeks")],
        [InlineKeyboardButton(text="📅 На месяц", callback_data="promo_1month")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="promotions_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(PromotionStates.enter_valid_until)
    await callback.answer()


@router.callback_query(PromotionStates.enter_valid_until, F.data == "promo_permanent")
async def set_permanent(callback: CallbackQuery, state: FSMContext, config: dict, config_manager):
    """Установить постоянную акцию"""
    await state.update_data(promo_permanent=True, promo_valid_until="")
    await save_new_promotion(callback, state, config, config_manager)


@router.callback_query(PromotionStates.enter_valid_until, F.data == "promo_end_month")
async def set_end_month(callback: CallbackQuery, state: FSMContext, config: dict, config_manager):
    """До конца месяца"""
    from datetime import datetime
    import calendar

    now = datetime.now()
    last_day = calendar.monthrange(now.year, now.month)[1]
    valid_until = f"{last_day:02d}.{now.month:02d}.{now.year}"

    await state.update_data(promo_permanent=False, promo_valid_until=valid_until)
    await save_new_promotion(callback, state, config, config_manager)


@router.callback_query(PromotionStates.enter_valid_until, F.data == "promo_2weeks")
async def set_2weeks(callback: CallbackQuery, state: FSMContext, config: dict, config_manager):
    """На 2 недели"""
    from datetime import datetime, timedelta

    valid_until = (datetime.now() + timedelta(days=14)).strftime("%d.%m.%Y")

    await state.update_data(promo_permanent=False, promo_valid_until=valid_until)
    await save_new_promotion(callback, state, config, config_manager)


@router.callback_query(PromotionStates.enter_valid_until, F.data == "promo_1month")
async def set_1month(callback: CallbackQuery, state: FSMContext, config: dict, config_manager):
    """На месяц"""
    from datetime import datetime, timedelta

    valid_until = (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y")

    await state.update_data(promo_permanent=False, promo_valid_until=valid_until)
    await save_new_promotion(callback, state, config, config_manager)


async def save_new_promotion(callback: CallbackQuery, state: FSMContext, config: dict, config_manager):
    """Сохранить новую акцию"""
    data = await state.get_data()

    new_promo = {
        "title": data['promo_title'],
        "description": data.get('promo_description', ''),
        "emoji": data.get('promo_emoji', '🎁'),
        "is_permanent": data.get('promo_permanent', False),
        "valid_until": data.get('promo_valid_until', ''),
        "active": True
    }

    # Добавляем в конфиг
    if 'promotions' not in config:
        config['promotions'] = []

    config['promotions'].append(new_promo)

    # Сохраняем через update_field (правильный метод)
    editor = get_config_editor(config)
    editor.update_field('promotions', config['promotions'])

    config_manager.config['promotions'] = config['promotions']

    text = f"""
✅ <b>АКЦИЯ ДОБАВЛЕНА!</b>

{new_promo['emoji']} <b>{new_promo['title']}</b>
{new_promo['description']}

{'♾ Постоянная акция' if new_promo['is_permanent'] else f"📅 Действует до: {new_promo['valid_until']}"}
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 К акциям", callback_data="promotions_menu")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.clear()
    await callback.answer("✅ Акция добавлена!")


# ==================== РЕДАКТИРОВАНИЕ АКЦИИ ====================

@router.callback_query(F.data.startswith("promo_edit:"))
async def edit_promotion(callback: CallbackQuery, config: dict):
    """Показать акцию для редактирования"""
    try:
        promo_index = int(callback.data.replace("promo_edit:", ""))
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    promotions = config.get('promotions', [])

    if promo_index >= len(promotions):
        await callback.answer("❌ Акция не найдена", show_alert=True)
        return

    promo = promotions[promo_index]

    status = "✅ Активна" if promo.get('active', True) else "❌ Отключена"

    text = f"""
🎁 <b>РЕДАКТИРОВАНИЕ АКЦИИ</b>

{promo.get('emoji', '🎁')} <b>{promo.get('title', 'Без названия')}</b>

📝 Описание: {promo.get('description') or '—'}
📅 Срок: {'Постоянная' if promo.get('is_permanent') else promo.get('valid_until', '—')}
📊 Статус: {status}

Выберите действие:
"""

    toggle_text = "❌ Отключить" if promo.get('active', True) else "✅ Включить"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Название", callback_data=f"promo_edit_title:{promo_index}")],
        [InlineKeyboardButton(text="✏️ Описание", callback_data=f"promo_edit_desc:{promo_index}")],
        [InlineKeyboardButton(text="✏️ Эмодзи", callback_data=f"promo_edit_emoji:{promo_index}")],
        [InlineKeyboardButton(text="✏️ Срок действия", callback_data=f"promo_edit_valid:{promo_index}")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"promo_toggle:{promo_index}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"promo_delete:{promo_index}")],
        [InlineKeyboardButton(text="🔙 К акциям", callback_data="promotions_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("promo_toggle:"))
async def toggle_promotion(callback: CallbackQuery, config: dict, config_manager):
    """Включить/выключить акцию"""
    try:
        promo_index = int(callback.data.replace("promo_toggle:", ""))
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    promotions = config.get('promotions', [])

    if promo_index >= len(promotions):
        await callback.answer("❌ Акция не найдена", show_alert=True)
        return

    # Переключаем статус
    current = promotions[promo_index].get('active', True)
    promotions[promo_index]['active'] = not current

    # Сохраняем через update_field (правильный метод)
    editor = get_config_editor(config)
    editor.update_field('promotions', promotions)

    config_manager.config['promotions'] = promotions

    status = "✅ включена" if not current else "❌ отключена"
    await callback.answer(f"Акция {status}")

    # Обновляем карточку
    await edit_promotion(callback, config)


@router.callback_query(F.data.startswith("promo_delete:"))
async def confirm_delete_promotion(callback: CallbackQuery, config: dict):
    """Подтверждение удаления акции"""
    try:
        promo_index = int(callback.data.replace("promo_delete:", ""))
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    promotions = config.get('promotions', [])

    if promo_index >= len(promotions):
        await callback.answer("❌ Акция не найдена", show_alert=True)
        return

    promo = promotions[promo_index]

    text = f"""
⚠️ <b>УДАЛЕНИЕ АКЦИИ</b>

Вы уверены, что хотите удалить акцию?

{promo.get('emoji', '🎁')} <b>{promo.get('title', 'Без названия')}</b>

<i>Это действие нельзя отменить!</i>
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"promo_confirm_delete:{promo_index}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"promo_edit:{promo_index}")
        ]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("promo_confirm_delete:"))
async def delete_promotion(callback: CallbackQuery, config: dict, config_manager, state: FSMContext):
    """Удалить акцию"""
    try:
        promo_index = int(callback.data.replace("promo_confirm_delete:", ""))
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    promotions = config.get('promotions', [])

    if promo_index >= len(promotions):
        await callback.answer("❌ Акция не найдена", show_alert=True)
        return

    # Удаляем
    deleted = promotions.pop(promo_index)

    # Сохраняем через update_field (правильный метод)
    editor = get_config_editor(config)
    editor.update_field('promotions', promotions)

    config_manager.config['promotions'] = promotions

    await callback.answer(f"✅ Акция '{deleted.get('title')}' удалена")

    # Возвращаемся к списку
    await show_promotions_menu(callback, config, state)


# ==================== РЕДАКТИРОВАНИЕ ПОЛЕЙ ====================

@router.callback_query(F.data.startswith("promo_edit_title:"))
async def edit_title_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование названия"""
    promo_index = callback.data.replace("promo_edit_title:", "")
    await state.update_data(editing_promo_index=int(promo_index))

    text = "✏️ Введите новое название акции:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"promo_edit:{promo_index}")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(PromotionStates.edit_title)
    await callback.answer()


@router.message(PromotionStates.edit_title)
async def save_edited_title(message: Message, state: FSMContext, config: dict, config_manager):
    """Сохранить новое название"""
    title = message.text.strip()

    if len(title) < 3 or len(title) > 100:
        await message.answer("❌ Название должно быть от 3 до 100 символов")
        return

    data = await state.get_data()
    promo_index = data.get('editing_promo_index')

    promotions = config.get('promotions', [])
    promotions[promo_index]['title'] = title

    # Сохраняем через update_field (правильный метод)
    editor = get_config_editor(config)
    editor.update_field('promotions', promotions)

    config_manager.config['promotions'] = promotions

    await message.answer(f"✅ Название обновлено: <b>{title}</b>")
    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 К акциям", callback_data="promotions_menu")],
    ])
    await message.answer("Выберите действие:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("promo_edit_desc:"))
async def edit_description_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование описания"""
    promo_index = callback.data.replace("promo_edit_desc:", "")
    await state.update_data(editing_promo_index=int(promo_index))

    text = "✏️ Введите новое описание акции:\n\n<i>Отправьте «0» чтобы удалить описание</i>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"promo_edit:{promo_index}")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(PromotionStates.edit_description)
    await callback.answer()


@router.message(PromotionStates.edit_description)
async def save_edited_description(message: Message, state: FSMContext, config: dict, config_manager):
    """Сохранить новое описание"""
    description = message.text.strip()

    if description == "0":
        description = ""
    elif len(description) > 500:
        await message.answer("❌ Описание должно быть не более 500 символов")
        return

    data = await state.get_data()
    promo_index = data.get('editing_promo_index')

    promotions = config.get('promotions', [])
    promotions[promo_index]['description'] = description

    # Сохраняем через update_field (правильный метод)
    editor = get_config_editor(config)
    editor.update_field('promotions', promotions)

    config_manager.config['promotions'] = promotions

    await message.answer(f"✅ Описание обновлено")
    await state.clear()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 К акциям", callback_data="promotions_menu")],
    ])
    await message.answer("Выберите действие:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("promo_edit_emoji:"))
async def edit_emoji_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование эмодзи"""
    promo_index = callback.data.replace("promo_edit_emoji:", "")
    await state.update_data(editing_promo_index=int(promo_index))

    text = "✏️ Выберите новый эмодзи:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎁", callback_data="promo_set_emoji:🎁"),
            InlineKeyboardButton(text="💰", callback_data="promo_set_emoji:💰"),
            InlineKeyboardButton(text="🔥", callback_data="promo_set_emoji:🔥"),
            InlineKeyboardButton(text="⭐", callback_data="promo_set_emoji:⭐"),
        ],
        [
            InlineKeyboardButton(text="💎", callback_data="promo_set_emoji:💎"),
            InlineKeyboardButton(text="🎉", callback_data="promo_set_emoji:🎉"),
            InlineKeyboardButton(text="💝", callback_data="promo_set_emoji:💝"),
            InlineKeyboardButton(text="✨", callback_data="promo_set_emoji:✨"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"promo_edit:{promo_index}")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(PromotionStates.edit_emoji)
    await callback.answer()


@router.callback_query(PromotionStates.edit_emoji, F.data.startswith("promo_set_emoji:"))
async def save_edited_emoji(callback: CallbackQuery, state: FSMContext, config: dict, config_manager):
    """Сохранить новый эмодзи"""
    emoji = callback.data.replace("promo_set_emoji:", "")

    data = await state.get_data()
    promo_index = data.get('editing_promo_index')

    promotions = config.get('promotions', [])
    promotions[promo_index]['emoji'] = emoji

    # Сохраняем через update_field (правильный метод)
    editor = get_config_editor(config)
    editor.update_field('promotions', promotions)

    config_manager.config['promotions'] = promotions

    await callback.answer(f"✅ Эмодзи обновлён: {emoji}")
    await state.clear()

    # Возвращаемся к редактированию
    await edit_promotion(callback, config)


@router.callback_query(F.data.startswith("promo_edit_valid:"))
async def edit_valid_until_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование срока действия"""
    promo_index = callback.data.replace("promo_edit_valid:", "")
    await state.update_data(editing_promo_index=int(promo_index))

    text = "✏️ Выберите новый срок действия:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♾ Постоянная акция", callback_data="promo_set_permanent")],
        [InlineKeyboardButton(text="📅 До конца месяца", callback_data="promo_set_end_month")],
        [InlineKeyboardButton(text="📅 На 2 недели", callback_data="promo_set_2weeks")],
        [InlineKeyboardButton(text="📅 На месяц", callback_data="promo_set_1month")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"promo_edit:{promo_index}")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(PromotionStates.edit_valid_until)
    await callback.answer()


@router.callback_query(PromotionStates.edit_valid_until, F.data == "promo_set_permanent")
async def save_permanent(callback: CallbackQuery, state: FSMContext, config: dict, config_manager):
    """Установить постоянную акцию"""
    data = await state.get_data()
    promo_index = data.get('editing_promo_index')

    promotions = config.get('promotions', [])
    promotions[promo_index]['is_permanent'] = True
    promotions[promo_index]['valid_until'] = ""

    # Сохраняем через update_field (правильный метод)
    editor = get_config_editor(config)
    editor.update_field('promotions', promotions)

    config_manager.config['promotions'] = promotions

    await callback.answer("✅ Акция теперь постоянная")
    await state.clear()
    await edit_promotion(callback, config)


@router.callback_query(PromotionStates.edit_valid_until, F.data == "promo_set_end_month")
async def save_end_month(callback: CallbackQuery, state: FSMContext, config: dict, config_manager):
    """До конца месяца"""
    from datetime import datetime
    import calendar

    now = datetime.now()
    last_day = calendar.monthrange(now.year, now.month)[1]
    valid_until = f"{last_day:02d}.{now.month:02d}.{now.year}"

    data = await state.get_data()
    promo_index = data.get('editing_promo_index')

    promotions = config.get('promotions', [])
    promotions[promo_index]['is_permanent'] = False
    promotions[promo_index]['valid_until'] = valid_until

    # Сохраняем через update_field (правильный метод)
    editor = get_config_editor(config)
    editor.update_field('promotions', promotions)

    config_manager.config['promotions'] = promotions

    await callback.answer(f"✅ Акция действует до {valid_until}")
    await state.clear()
    await edit_promotion(callback, config)


@router.callback_query(PromotionStates.edit_valid_until, F.data == "promo_set_2weeks")
async def save_2weeks(callback: CallbackQuery, state: FSMContext, config: dict, config_manager):
    """На 2 недели"""
    from datetime import datetime, timedelta

    valid_until = (datetime.now() + timedelta(days=14)).strftime("%d.%m.%Y")

    data = await state.get_data()
    promo_index = data.get('editing_promo_index')

    promotions = config.get('promotions', [])
    promotions[promo_index]['is_permanent'] = False
    promotions[promo_index]['valid_until'] = valid_until

    # Сохраняем через update_field (правильный метод)
    editor = get_config_editor(config)
    editor.update_field('promotions', promotions)

    config_manager.config['promotions'] = promotions

    await callback.answer(f"✅ Акция действует до {valid_until}")
    await state.clear()
    await edit_promotion(callback, config)


@router.callback_query(PromotionStates.edit_valid_until, F.data == "promo_set_1month")
async def save_1month(callback: CallbackQuery, state: FSMContext, config: dict, config_manager):
    """На месяц"""
    from datetime import datetime, timedelta

    valid_until = (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y")

    data = await state.get_data()
    promo_index = data.get('editing_promo_index')

    promotions = config.get('promotions', [])
    promotions[promo_index]['is_permanent'] = False
    promotions[promo_index]['valid_until'] = valid_until

    # Сохраняем через update_field (правильный метод)
    editor = get_config_editor(config)
    editor.update_field('promotions', promotions)

    config_manager.config['promotions'] = promotions

    await callback.answer(f"✅ Акция действует до {valid_until}")
    await state.clear()
    await edit_promotion(callback, config)
