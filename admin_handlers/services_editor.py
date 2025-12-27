"""Редактор услуг для админ-бота"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

logger = logging.getLogger(__name__)

router = Router()


class ServiceEditStates(StatesGroup):
    """Состояния для редактирования услуг"""
    add_name = State()
    add_price = State()
    add_duration = State()
    
    edit_choosing = State()
    edit_name = State()
    edit_price = State()
    edit_duration = State()


def get_services_keyboard(services: list) -> InlineKeyboardMarkup:
    """Клавиатура со списком услуг"""
    buttons = []
    
    for service in services:
        duration = service.get('duration', 60)
        buttons.append([
            InlineKeyboardButton(
                text=f"{service['name']} — {service['price']}₽ — {duration} мин",
                callback_data=f"service_view:{service['id']}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(text="➕ Добавить услугу", callback_data="service_add")
    ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "admin_services")
async def show_services(callback: CallbackQuery, config_manager):
    """Показ списка услуг"""
    config = config_manager.get_config()
    services = config.get('services', [])
    
    text = f"📋 <b>Услуги ({len(services)})</b>\n\n"
    text += "Выберите услугу для редактирования или добавьте новую:"
    
    keyboard = get_services_keyboard(services)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("service_view:"))
async def view_service(callback: CallbackQuery, config_manager):
    """Просмотр деталей услуги"""
    service_id = callback.data.split(":")[1]
    config = config_manager.get_config()
    services = config.get('services', [])
    
    service = next((s for s in services if s['id'] == service_id), None)
    
    if not service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return
    
    duration = service.get('duration', 60)
    
    text = (
        f"📋 <b>{service['name']}</b>\n\n"
        f"💰 Цена: {service['price']}₽\n"
        f"⏱ Длительность: {duration} мин\n"
        f"🆔 ID: {service['id']}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Изменить", callback_data=f"service_edit:{service_id}"),
            InlineKeyboardButton(text="❌ Удалить", callback_data=f"service_delete:{service_id}")
        ],
        [InlineKeyboardButton(text="🔙 К списку услуг", callback_data="admin_services")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# === ДОБАВЛЕНИЕ УСЛУГИ ===

@router.callback_query(F.data == "service_add")
async def start_add_service(callback: CallbackQuery, state: FSMContext):
    """Начало добавления услуги"""
    await state.set_state(ServiceEditStates.add_name)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_services")]
    ])
    
    await callback.message.edit_text(
        "➕ <b>Добавление услуги</b>\n\n"
        "Шаг 1 из 3\n\n"
        "Введите название услуги:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.message(ServiceEditStates.add_name)
async def process_add_name(message: Message, state: FSMContext):
    """Обработка названия новой услуги"""
    name = message.text.strip()
    
    if len(name) < 2:
        await message.answer("❌ Название слишком короткое. Введите минимум 2 символа:")
        return
    
    await state.update_data(name=name)
    await state.set_state(ServiceEditStates.add_price)
    
    await message.answer(
        f"✅ Название: {name}\n\n"
        "Шаг 2 из 3\n\n"
        "Введите цену услуги (только число, без символов):"
    )


@router.message(ServiceEditStates.add_price)
async def process_add_price(message: Message, state: FSMContext):
    """Обработка цены новой услуги"""
    try:
        price = int(message.text.strip())
        if price <= 0:
            raise ValueError
    except:
        await message.answer("❌ Неверный формат. Введите положительное число (например: 1200):")
        return
    
    await state.update_data(price=price)
    await state.set_state(ServiceEditStates.add_duration)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="30 мин", callback_data="duration:30"),
            InlineKeyboardButton(text="60 мин", callback_data="duration:60")
        ],
        [
            InlineKeyboardButton(text="90 мин", callback_data="duration:90"),
            InlineKeyboardButton(text="120 мин", callback_data="duration:120")
        ],
        [InlineKeyboardButton(text="Другое", callback_data="duration:custom")]
    ])
    
    await message.answer(
        f"✅ Цена: {price}₽\n\n"
        "Шаг 3 из 3\n\n"
        "Выберите длительность услуги:",
        reply_markup=keyboard
    )


@router.callback_query(ServiceEditStates.add_duration, F.data.startswith("duration:"))
async def process_add_duration(callback: CallbackQuery, state: FSMContext, config_manager):
    """Обработка длительности новой услуги"""
    duration_value = callback.data.split(":")[1]
    
    if duration_value == "custom":
        await callback.message.edit_text("Введите длительность в минутах (число от 15 до 240):")
        # Состояние не меняем, ждём текстового сообщения
        await callback.answer()
        return
    
    duration = int(duration_value)
    data = await state.get_data()
    
    # Добавляем услугу
    success = config_manager.add_service(
        name=data['name'],
        price=data['price'],
        duration=duration
    )
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>Услуга добавлена!</b>\n\n"
            f"Название: {data['name']}\n"
            f"Цена: {data['price']}₽\n"
            f"Длительность: {duration} мин"
        )
        
        # Показываем обновлённый список
        await state.clear()
        config = config_manager.reload_config()
        
        keyboard = get_services_keyboard(config.get('services', []))
        await callback.message.answer(
            "📋 <b>Обновлённый список услуг:</b>",
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text("❌ Ошибка при добавлении услуги")
        await state.clear()
    
    await callback.answer()


@router.message(ServiceEditStates.add_duration)
async def process_add_duration_custom(message: Message, state: FSMContext, config_manager):
    """Обработка пользовательской длительности"""
    try:
        duration = int(message.text.strip())
        if duration < 15 or duration > 240:
            raise ValueError
    except:
        await message.answer("❌ Неверный формат. Введите число от 15 до 240:")
        return
    
    data = await state.get_data()
    
    # Добавляем услугу
    success = config_manager.add_service(
        name=data['name'],
        price=data['price'],
        duration=duration
    )
    
    if success:
        await message.answer(
            f"✅ <b>Услуга добавлена!</b>\n\n"
            f"Название: {data['name']}\n"
            f"Цена: {data['price']}₽\n"
            f"Длительность: {duration} мин"
        )
        
        config = config_manager.reload_config()
        keyboard = get_services_keyboard(config.get('services', []))
        await message.answer("📋 <b>Обновлённый список услуг:</b>", reply_markup=keyboard)
    else:
        await message.answer("❌ Ошибка при добавлении услуги")
    
    await state.clear()


# === РЕДАКТИРОВАНИЕ УСЛУГИ ===

@router.callback_query(F.data.startswith("service_edit:"))
async def start_edit_service(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования услуги"""
    service_id = callback.data.split(":")[1]
    await state.update_data(editing_service_id=service_id)
    await state.set_state(ServiceEditStates.edit_choosing)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Изменить название", callback_data="edit_field:name")],
        [InlineKeyboardButton(text="💰 Изменить цену", callback_data="edit_field:price")],
        [InlineKeyboardButton(text="⏱ Изменить длительность", callback_data="edit_field:duration")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"service_view:{service_id}")]
    ])
    
    await callback.message.edit_text(
        "✏️ <b>Редактирование услуги</b>\n\n"
        "Что хотите изменить?",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(ServiceEditStates.edit_choosing, F.data.startswith("edit_field:"))
async def choose_edit_field(callback: CallbackQuery, state: FSMContext):
    """Выбор поля для редактирования"""
    field = callback.data.split(":")[1]
    
    if field == "name":
        await state.set_state(ServiceEditStates.edit_name)
        await callback.message.edit_text("Введите новое название услуги:")
    elif field == "price":
        await state.set_state(ServiceEditStates.edit_price)
        await callback.message.edit_text("Введите новую цену (только число):")
    elif field == "duration":
        await state.set_state(ServiceEditStates.edit_duration)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="30 мин", callback_data="new_duration:30"),
                InlineKeyboardButton(text="60 мин", callback_data="new_duration:60")
            ],
            [
                InlineKeyboardButton(text="90 мин", callback_data="new_duration:90"),
                InlineKeyboardButton(text="120 мин", callback_data="new_duration:120")
            ]
        ])
        await callback.message.edit_text("Выберите новую длительность:", reply_markup=keyboard)
    
    await callback.answer()


@router.message(ServiceEditStates.edit_name)
async def process_edit_name(message: Message, state: FSMContext, config_manager):
    """Обработка нового названия"""
    new_name = message.text.strip()
    
    if len(new_name) < 2:
        await message.answer("❌ Название слишком короткое")
        return
    
    data = await state.get_data()
    service_id = data['editing_service_id']
    
    success = config_manager.update_service(service_id, name=new_name)
    
    if success:
        config = config_manager.reload_config()
        services = config.get('services', [])
        service = next((s for s in services if s.get('id') == service_id), None)
        if service:
            duration = service.get('duration', 60)
            text = (
                f"✅ Название изменено на: {new_name}\n\n"
                f"📋 <b>{service['name']}</b>\n\n"
                f"💰 Цена: {service['price']}₽\n"
                f"⏱ Длительность: {duration} мин\n"
                f"🆔 ID: {service['id']}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Изменить", callback_data=f"service_edit:{service_id}"),
                    InlineKeyboardButton(text="❌ Удалить", callback_data=f"service_delete:{service_id}")
                ],
                [InlineKeyboardButton(text="🔙 К списку услуг", callback_data="admin_services")]
            ])
            await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer(f"✅ Название изменено на: {new_name}")
    else:
        await message.answer("❌ Ошибка при сохранении")
    
    await state.clear()


@router.message(ServiceEditStates.edit_price)
async def process_edit_price(message: Message, state: FSMContext, config_manager):
    """Обработка новой цены"""
    try:
        new_price = int(message.text.strip())
        if new_price <= 0:
            raise ValueError
    except:
        await message.answer("❌ Неверный формат. Введите положительное число:")
        return
    
    data = await state.get_data()
    service_id = data['editing_service_id']
    
    success = config_manager.update_service(service_id, price=new_price)
    
    if success:
        config = config_manager.reload_config()
        services = config.get('services', [])
        service = next((s for s in services if s.get('id') == service_id), None)
        if service:
            duration = service.get('duration', 60)
            text = (
                f"✅ Цена изменена на: {new_price}₽\n\n"
                f"📋 <b>{service['name']}</b>\n\n"
                f"💰 Цена: {service['price']}₽\n"
                f"⏱ Длительность: {duration} мин\n"
                f"🆔 ID: {service['id']}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Изменить", callback_data=f"service_edit:{service_id}"),
                    InlineKeyboardButton(text="❌ Удалить", callback_data=f"service_delete:{service_id}")
                ],
                [InlineKeyboardButton(text="🔙 К списку услуг", callback_data="admin_services")]
            ])
            await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer(f"✅ Цена изменена на: {new_price}₽")
    else:
        await message.answer("❌ Ошибка при сохранении")
    
    await state.clear()


@router.callback_query(ServiceEditStates.edit_duration, F.data.startswith("new_duration:"))
async def process_edit_duration(callback: CallbackQuery, state: FSMContext, config_manager):
    """Обработка новой длительности"""
    new_duration = int(callback.data.split(":")[1])
    
    data = await state.get_data()
    service_id = data['editing_service_id']
    
    success = config_manager.update_service(service_id, duration=new_duration)
    
    if success:
        config = config_manager.reload_config()
        services = config.get('services', [])
        service = next((s for s in services if s.get('id') == service_id), None)
        if service:
            duration = service.get('duration', 60)
            text = (
                f"✅ Длительность изменена на: {new_duration} мин\n\n"
                f"📋 <b>{service['name']}</b>\n\n"
                f"💰 Цена: {service['price']}₽\n"
                f"⏱ Длительность: {duration} мин\n"
                f"🆔 ID: {service['id']}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Изменить", callback_data=f"service_edit:{service_id}"),
                    InlineKeyboardButton(text="❌ Удалить", callback_data=f"service_delete:{service_id}")
                ],
                [InlineKeyboardButton(text="🔙 К списку услуг", callback_data="admin_services")]
            ])
            await callback.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback.message.edit_text(f"✅ Длительность изменена на: {new_duration} мин")
    else:
        await callback.message.edit_text("❌ Ошибка при сохранении")
    
    await state.clear()
    await callback.answer()


# === УДАЛЕНИЕ УСЛУГИ ===

@router.callback_query(F.data.startswith("service_delete:"))
async def confirm_delete_service(callback: CallbackQuery):
    """Подтверждение удаления услуги"""
    service_id = callback.data.split(":")[1]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"service_delete_confirm:{service_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"service_view:{service_id}")
        ]
    ])
    
    await callback.message.edit_text(
        "⚠️ <b>Удаление услуги</b>\n\n"
        "Вы уверены? Это действие нельзя отменить.",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("service_delete_confirm:"))
async def delete_service(callback: CallbackQuery, config_manager):
    """Удаление услуги"""
    service_id = callback.data.split(":")[1]
    
    success = config_manager.delete_service(service_id)
    
    if success:
        await callback.message.edit_text("✅ Услуга удалена")
        config = config_manager.reload_config()
        
        keyboard = get_services_keyboard(config.get('services', []))
        await callback.message.answer("📋 <b>Обновлённый список услуг:</b>", reply_markup=keyboard)
    else:
        await callback.message.edit_text("❌ Ошибка при удалении")
    
    await callback.answer()
