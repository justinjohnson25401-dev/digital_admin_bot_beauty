from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from states.booking import BookingState
from utils.validators import is_valid_phone, clean_phone
from utils.notify import send_order_to_admins
from datetime import datetime, timedelta
import time
import logging

logger = logging.getLogger(__name__)

router = Router()

FSM_TTL_SECONDS = 30 * 60


async def _ensure_fsm_fresh(state: FSMContext, message: Message | None = None, callback: CallbackQuery | None = None) -> bool:
    data = await state.get_data()
    started_at = data.get('fsm_started_at')
    if started_at is None:
        return True
    if (time.time() - float(started_at)) <= FSM_TTL_SECONDS:
        return True

    await state.clear()
    text = "⏳ Сессия записи истекла (прошло слишком много времени). Начните заново."
    if callback is not None:
        await callback.message.answer(text)
        await callback.answer()
    elif message is not None:
        await message.answer(text)
    return False

# Словарь русских дней недели
DAYS_RU = {
    'Monday': 'Пн',
    'Tuesday': 'Вт',
    'Wednesday': 'Ср',
    'Thursday': 'Чт',
    'Friday': 'Пт',
    'Saturday': 'Сб',
    'Sunday': 'Вс'
}

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отменить")]],
        resize_keyboard=True
    )

def get_phone_input_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для ввода телефона с кнопкой отправки контакта"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)],
            [KeyboardButton(text="✏️ Ввести вручную")],
            [KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True
    )

def get_comment_choice_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора: добавить комментарий или пропустить"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Добавить комментарий", callback_data="add_comment"),
            InlineKeyboardButton(text="➡️ Пропустить", callback_data="skip_comment")
        ]
    ])

def get_reuse_details_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Использовать прошлые данные", callback_data="reuse_details"),
            InlineKeyboardButton(text="✏️ Ввести заново", callback_data="enter_details")
        ]
    ])

def generate_dates_keyboard() -> InlineKeyboardMarkup:
    """Генерация клавиатуры с датами"""
    buttons = []
    today = datetime.now().date()

    # Сегодня
    buttons.append([InlineKeyboardButton(
        text=f"📅 Сегодня ({today.strftime('%d.%m')})",
        callback_data=f"date:{today.isoformat()}"
    )])

    # Завтра
    tomorrow = today + timedelta(days=1)
    buttons.append([InlineKeyboardButton(
        text=f"📅 Завтра ({tomorrow.strftime('%d.%m')})",
        callback_data=f"date:{tomorrow.isoformat()}"
    )])

    # Следующие 5 дней с русскими названиями
    for i in range(2, 7):
        date = today + timedelta(days=i)
        day_name_en = date.strftime('%A')
        day_name_ru = DAYS_RU.get(day_name_en, day_name_en[:2])
        buttons.append([InlineKeyboardButton(
            text=f"{day_name_ru} {date.strftime('%d.%m')}",
            callback_data=f"date:{date.isoformat()}"
        )])

    # Кнопка назад
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_services")])
    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ИЗМЕНЕНО: Добавлен параметр exclude_order_id для исправления ошибки #4
def generate_time_slots_keyboard(config: dict, db_manager, booking_date: str, exclude_order_id: int = None) -> InlineKeyboardMarkup:
    """Генерация клавиатуры со временными слотами"""
    buttons = []
    work_start = config.get('booking', {}).get('work_start', 10)
    work_end = config.get('booking', {}).get('work_end', 20)
    slot_duration = config.get('booking', {}).get('slot_duration', 60)

    current_time = datetime.now()
    selected_date = datetime.fromisoformat(booking_date).date()
    is_today = selected_date == current_time.date()

    # Генерируем слоты
    current_slot = work_start
    while current_slot < work_end:
        slot_time = f"{current_slot:02d}:00"

        # Проверяем, не прошло ли время (если сегодня)
        if is_today:
            slot_datetime = datetime.combine(selected_date, datetime.strptime(slot_time, "%H:%M").time())
            if slot_datetime <= current_time:
                current_slot += slot_duration // 60
                continue

        # ИЗМЕНЕНО: Используем check_slot_availability_excluding если передан exclude_order_id (ошибка #4)
        if exclude_order_id:
            is_available = db_manager.check_slot_availability_excluding(booking_date, slot_time, exclude_order_id)
        else:
            is_available = db_manager.check_slot_availability(booking_date, slot_time)

        if is_available:
            button_text = f"🕐 {slot_time}"
        else:
            button_text = f"❌ {slot_time}"

        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"time:{slot_time}" if is_available else "slot_taken"
        )])

        current_slot += slot_duration // 60

    # Кнопка назад
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_dates")])
    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(F.text == "📅 Записаться / Заказать")
async def start_booking(message: Message, state: FSMContext, config: dict):
    """Начало процесса записи"""
    # Разрешаем запуск записи из любого состояния
    await state.clear()
    await state.update_data(fsm_started_at=time.time(), booking_confirmed=False)
    services = config.get('services', [])

    if not services:
        await message.answer("К сожалению, услуги временно недоступны.")
        return

    buttons = []
    for service in services:
        button_text = f"{service['name']} — {service['price']}₽"
        callback_data = f"srv:{service['id']}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])

    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите услугу:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_service)
    logger.info(f"User {message.from_user.id} started booking process")

@router.callback_query(BookingState.choosing_service, F.data.startswith("srv:"))
async def service_selected(callback: CallbackQuery, state: FSMContext, config: dict):
    """Обработка выбора услуги"""
    if not await _ensure_fsm_fresh(state, callback=callback):
        return
    service_id = callback.data.split(":")[1]
    services = config.get('services', [])

    selected_service = None
    for service in services:
        if service['id'] == service_id:
            selected_service = service
            break

    if not selected_service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.update_data(
        service_id=selected_service['id'],
        service_name=selected_service['name'],
        price=selected_service['price']
    )

    # Проверяем, включен ли режим бронирования по слотам
    if config.get('features', {}).get('enable_slot_booking', True):
        keyboard = generate_dates_keyboard()
        await callback.message.edit_text(
            f"Вы выбрали: {selected_service['name']} — {selected_service['price']}₽\n\n"
            "Выберите дату:",
            reply_markup=keyboard
        )
        await state.set_state(BookingState.choosing_date)
    else:
        # Старая логика без слотов
        await callback.message.edit_text(f"Вы выбрали: {selected_service['name']} — {selected_service['price']}₽")
        cancel_kb = get_cancel_keyboard()
        await callback.message.answer("Как вас зовут? Введите ваше имя:", reply_markup=cancel_kb)
        await state.set_state(BookingState.input_name)

    await callback.answer()

@router.callback_query(BookingState.choosing_date, F.data.startswith("date:"))
async def date_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    """Обработка выбора даты"""
    if not await _ensure_fsm_fresh(state, callback=callback):
        return
    booking_date = callback.data.split(":")[1]
    try:
        selected_date = datetime.fromisoformat(booking_date).date()
    except Exception:
        await callback.answer("Некорректная дата", show_alert=True)
        return
    if selected_date < datetime.now().date():
        await callback.answer("Нельзя выбрать прошедшую дату", show_alert=True)
        return
    await state.update_data(booking_date=booking_date)

    # Генерируем слоты времени (без exclude_order_id для новой записи)
    keyboard = generate_time_slots_keyboard(config, db_manager, booking_date)

    date_obj = datetime.fromisoformat(booking_date)
    date_formatted = date_obj.strftime('%d.%m.%Y')

    await callback.message.edit_text(
        f"Дата: {date_formatted}\n\n"
        "Выберите время:",
        reply_markup=keyboard
    )

    await state.set_state(BookingState.choosing_time)
    await callback.answer()

@router.callback_query(BookingState.choosing_time, F.data.startswith("time:"))
async def time_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    """Обработка выбора времени"""
    if not await _ensure_fsm_fresh(state, callback=callback):
        return
    booking_time = callback.data.split(":", 1)[1]
    data = await state.get_data()
    booking_date = data.get('booking_date')

    try:
        selected_date = datetime.fromisoformat(booking_date).date() if booking_date else None
        slot_dt = datetime.combine(selected_date, datetime.strptime(booking_time, "%H:%M").time()) if selected_date else None
    except Exception:
        await callback.answer("Некорректные дата/время", show_alert=True)
        return
    if slot_dt and slot_dt <= datetime.now():
        await callback.answer("Нельзя выбрать прошедшее время", show_alert=True)
        return

    # Дополнительная проверка доступности
    if not db_manager.check_slot_availability(booking_date, booking_time):
        await callback.answer("Это время уже занято. Выберите другой слот.", show_alert=True)
        return

    await state.update_data(booking_time=booking_time)

    await callback.message.edit_text(
        f"Дата и время: {booking_date} в {booking_time}"
    )

    last_details = None
    if hasattr(db_manager, 'get_last_client_details'):
        last_details = db_manager.get_last_client_details(callback.from_user.id)

    if last_details and last_details.get('client_name') and last_details.get('phone'):
        text = (
            "У вас уже есть предыдущая запись. "
            "Использовать прошлые имя и телефон или ввести заново?"
        )
        await callback.message.answer(text, reply_markup=get_reuse_details_keyboard())
        await state.set_state(BookingState.input_name)
    else:
        cancel_kb = get_cancel_keyboard()
        await callback.message.answer("Как вас зовут? Введите ваше имя:", reply_markup=cancel_kb)
        await state.set_state(BookingState.input_name)
    await callback.answer()


@router.callback_query(BookingState.input_name, F.data == "enter_details")
async def enter_details_callback(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_fsm_fresh(state, callback=callback):
        return
    cancel_kb = get_cancel_keyboard()
    await callback.message.answer("Как вас зовут? Введите ваше имя:", reply_markup=cancel_kb)
    await callback.answer()


@router.callback_query(BookingState.input_name, F.data == "reuse_details")
async def reuse_details_callback(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    if not await _ensure_fsm_fresh(state, callback=callback):
        return
    last_details = None
    if hasattr(db_manager, 'get_last_client_details'):
        last_details = db_manager.get_last_client_details(callback.from_user.id)
    if not last_details or not last_details.get('client_name') or not last_details.get('phone'):
        await callback.answer("Нет сохранённых данных", show_alert=True)
        return

    await state.update_data(client_name=last_details['client_name'], phone=last_details['phone'])

    if config.get('features', {}).get('ask_comment', True):
        comment_kb = get_comment_choice_keyboard()
        await callback.message.answer("Хотите добавить комментарий к заявке?", reply_markup=comment_kb)
        await state.set_state(BookingState.waiting_comment_choice)
    else:
        await show_confirmation(callback.message, state, config)

    await callback.answer("✅ Данные подставлены")

@router.callback_query(F.data == "slot_taken")
async def slot_taken_handler(callback: CallbackQuery, messages: dict):
    """Обработка нажатия на занятый слот"""
    await callback.answer(
        messages.get('slot_taken', 'Это время уже занято'),
        show_alert=True
    )

@router.callback_query(F.data == "back_to_services")
async def back_to_services(callback: CallbackQuery, state: FSMContext, config: dict):
    """Возврат к выбору услуг"""
    services = config.get('services', [])
    buttons = []

    for service in services:
        button_text = f"{service['name']} — {service['price']}₽"
        callback_data = f"srv:{service['id']}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])

    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Выберите услугу:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_service)
    await callback.answer()

@router.callback_query(F.data == "back_to_dates")
async def back_to_dates(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору даты"""
    keyboard = generate_dates_keyboard()
    await callback.message.edit_text("Выберите дату:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_date)
    await callback.answer()

@router.callback_query(F.data == "cancel_booking_process")
async def cancel_booking_process_callback(callback: CallbackQuery, state: FSMContext, config: dict):
    """Отмена процесса записи через callback"""
    await state.clear()
    await callback.message.edit_text("Запись отменена. Используйте кнопку меню для новой записи.")
    await callback.answer()

@router.message(F.text == "❌ Отменить")
async def cancel_booking_process_message(message: Message, state: FSMContext, config: dict):
    """Отмена процесса записи через сообщение"""
    await state.clear()

    # Возвращаем главное меню
    from handlers.start import get_main_keyboard
    keyboard = get_main_keyboard()

    await message.answer(
        "Запись отменена. Используйте кнопку меню для новой записи.",
        reply_markup=keyboard
    )

@router.message(BookingState.input_name, F.text)
async def process_name(message: Message, state: FSMContext, config: dict, db_manager, messages: dict):
    """Обработка имени клиента"""
    if not await _ensure_fsm_fresh(state, message=message):
        return
    client_name = message.text.strip()

    # Проверка на кнопки
    faq_buttons = [item['btn'] for item in config.get('faq', [])]
    if client_name in faq_buttons or client_name in ["📅 Записаться / Заказать", "📞 Контакты", "📋 Мои записи"]:
        await message.answer("Пожалуйста, введите ваше настоящее имя, а не текст кнопки:")
        return

    if len(client_name) < 2:
        await message.answer("Пожалуйста, введите корректное имя (минимум 2 символа):")
        return

    if len(client_name) > 100:
        await message.answer("Имя слишком длинное. Максимум 100 символов:")
        return

    await state.update_data(client_name=client_name)

    if config.get('features', {}).get('require_phone', True):
        phone_kb = get_phone_input_keyboard()
        await message.answer(
            "Отправьте ваш номер телефона:",
            reply_markup=phone_kb
        )
        await state.set_state(BookingState.choosing_phone_method)
    else:
        await state.update_data(phone="не указан")
        if config.get('features', {}).get('ask_comment', True):
            comment_kb = get_comment_choice_keyboard()
            await message.answer(
                "Хотите добавить комментарий к заявке?",
                reply_markup=comment_kb
            )
            await state.set_state(BookingState.waiting_comment_choice)
        else:
            await show_confirmation(message, state, config)

@router.message(BookingState.choosing_phone_method, F.text == "✏️ Ввести вручную")
async def phone_manual_input(message: Message, state: FSMContext):
    """Ручной ввод телефона"""
    cancel_kb = get_cancel_keyboard()
    await message.answer(
        "Введите номер телефона в формате +79991234567 или 89991234567:",
        reply_markup=cancel_kb
    )
    await state.set_state(BookingState.input_phone)

# ИЗМЕНЕНО: Добавлен ReplyKeyboardRemove() для исправления ошибки #1
@router.message(BookingState.choosing_phone_method, F.contact)
async def process_phone_contact(message: Message, state: FSMContext, config: dict):
    """Обработка получения контакта"""
    phone = message.contact.phone_number
    if not phone.startswith('+'):
        phone = '+' + phone

    await state.update_data(phone=phone)

    if config.get('features', {}).get('ask_comment', True):
        comment_kb = get_comment_choice_keyboard()
        await message.answer("✅ Телефон получен", reply_markup=ReplyKeyboardRemove())
        await message.answer("Хотите добавить комментарий к заявке?", reply_markup=comment_kb)
        await state.set_state(BookingState.waiting_comment_choice)
    else:
        # ИЗМЕНЕНО: Убираем клавиатуру с кнопкой телефона (ошибка #1)
        await message.answer("✅ Телефон получен", reply_markup=ReplyKeyboardRemove())
        await show_confirmation(message, state, config)

@router.message(BookingState.input_phone, F.text)
async def process_phone(message: Message, state: FSMContext, config: dict, db_manager, messages: dict):
    """Обработка номера телефона"""
    phone_text = message.text.strip()

    if not is_valid_phone(phone_text):
        error_msg = messages.get('error_phone', 'Некорректный формат номера.')
        await message.answer(error_msg)
        return

    cleaned_phone = clean_phone(phone_text)

    if cleaned_phone.startswith('8'):
        cleaned_phone = '+7' + cleaned_phone[1:]
    elif cleaned_phone.startswith('7'):
        cleaned_phone = '+' + cleaned_phone
    elif not cleaned_phone.startswith('+'):
        cleaned_phone = '+7' + cleaned_phone

    await state.update_data(phone=cleaned_phone)

    if config.get('features', {}).get('ask_comment', True):
        comment_kb = get_comment_choice_keyboard()
        await message.answer("✅ Телефон получен", reply_markup=ReplyKeyboardRemove())
        await message.answer("Хотите добавить комментарий к заявке?", reply_markup=comment_kb)
        await state.set_state(BookingState.waiting_comment_choice)
    else:
        await message.answer("✅ Телефон получен", reply_markup=ReplyKeyboardRemove())
        await show_confirmation(message, state, config)

@router.callback_query(BookingState.waiting_comment_choice, F.data == "add_comment")
async def add_comment_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора 'Добавить комментарий'"""
    await callback.message.edit_text("Хотите добавить комментарий к заявке?")
    cancel_kb = get_cancel_keyboard()
    await callback.message.answer(
        "Введите ваш комментарий:",
        reply_markup=cancel_kb
    )
    await state.set_state(BookingState.input_comment)
    await callback.answer()

@router.callback_query(BookingState.waiting_comment_choice, F.data == "skip_comment")
async def skip_comment_callback(callback: CallbackQuery, state: FSMContext, config: dict):
    """Обработка выбора 'Пропустить'"""
    await state.update_data(comment=None)
    await callback.message.edit_text("Хотите добавить комментарий к заявке?\n\n✅ Пропущено")
    await show_confirmation(callback.message, state, config)
    await callback.answer()

@router.message(BookingState.input_comment, F.text)
async def process_comment(message: Message, state: FSMContext, config: dict, db_manager, messages: dict):
    """Обработка комментария"""
    if not await _ensure_fsm_fresh(state, message=message):
        return
    comment = message.text.strip()
    if len(comment) > 500:
        await message.answer("Комментарий слишком длинный. Максимум 500 символов:")
        return
    await state.update_data(comment=comment)
    await show_confirmation(message, state, config)

async def show_confirmation(message: Message, state: FSMContext, config: dict):
    """Показ финального подтверждения"""
    data = await state.get_data()

    confirmation_text = (
        "📋 Подтверждение записи\n\n"
        f"Услуга: {data['service_name']}\n"
        f"Цена: {data['price']}₽\n"
    )

    if data.get('booking_date'):
        date_obj = datetime.fromisoformat(data['booking_date'])
        date_formatted = date_obj.strftime('%d.%m.%Y')
        confirmation_text += f"Дата: {date_formatted}\n"
        confirmation_text += f"Время: {data.get('booking_time', 'не указано')}\n"

    confirmation_text += (
        f"Имя: {data['client_name']}\n"
        f"Телефон: {data['phone']}\n"
    )

    if data.get('comment'):
        confirmation_text += f"Комментарий: {data['comment']}\n"

    confirmation_text += "\nВсё верно?"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, подтвердить", callback_data="confirm_booking")],
        [
            InlineKeyboardButton(text="📝 Услуга", callback_data="edit_service"),
            InlineKeyboardButton(text="📅 Дата", callback_data="edit_date")
        ],
        [
            InlineKeyboardButton(text="🕐 Время", callback_data="edit_time"),
            InlineKeyboardButton(text="👤 Имя", callback_data="edit_name")
        ],
        [
            InlineKeyboardButton(text="📱 Телефон", callback_data="edit_phone"),
            InlineKeyboardButton(text="✏️ Комментарий", callback_data="edit_comment")
        ],
        [InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel_booking")]
    ])

    await message.answer(confirmation_text, reply_markup=keyboard)
    await state.set_state(BookingState.confirmation)

@router.callback_query(BookingState.confirmation, F.data == "confirm_booking")
async def confirm_booking(callback: CallbackQuery, state: FSMContext, config: dict, db_manager, messages: dict, scheduler=None, admin_bot=None):
    """Финальное подтверждение и создание записи"""
    if not await _ensure_fsm_fresh(state, callback=callback):
        return
    data = await state.get_data()

    if data.get('booking_confirmed'):
        await callback.answer("Уже обработано", show_alert=True)
        return

    await state.update_data(booking_confirmed=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    user_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name
    last_name = callback.from_user.last_name

    # Добавляем пользователя в БД
    db_manager.add_user(user_id, username, first_name, last_name)

    booking_date = data.get('booking_date')
    booking_time = data.get('booking_time')
    try:
        if booking_date and booking_time:
            selected_date = datetime.fromisoformat(booking_date).date()
            slot_dt = datetime.combine(selected_date, datetime.strptime(booking_time, "%H:%M").time())
            if slot_dt <= datetime.now():
                await callback.answer("Выбранное время уже прошло. Выберите другое.", show_alert=True)
                await state.update_data(booking_confirmed=False)
                keyboard = generate_time_slots_keyboard(config, db_manager, booking_date)
                await callback.message.answer("Выберите другое время:", reply_markup=keyboard)
                await state.set_state(BookingState.choosing_time)
                return
    except Exception:
        await callback.answer("Некорректные дата/время", show_alert=True)
        await state.update_data(booking_confirmed=False)
        return

    if booking_date and booking_time:
        if not db_manager.check_slot_availability(booking_date, booking_time):
            await callback.answer("Этот слот уже занят. Выберите другое время.", show_alert=True)
            await state.update_data(booking_confirmed=False)
            keyboard = generate_time_slots_keyboard(config, db_manager, booking_date)
            await callback.message.answer("Выберите другое время:", reply_markup=keyboard)
            await state.set_state(BookingState.choosing_time)
            return

    try:
        order_id = db_manager.add_order(
            user_id=user_id,
            service_id=data['service_id'],
            service_name=data['service_name'],
            price=data['price'],
            client_name=data['client_name'],
            phone=data['phone'],
            comment=data.get('comment'),
            booking_date=booking_date,
            booking_time=booking_time
        )
    except ValueError:
        await callback.answer("Слот уже занят. Выберите другое время.", show_alert=True)
        await state.update_data(booking_confirmed=False)
        if booking_date:
            keyboard = generate_time_slots_keyboard(config, db_manager, booking_date)
            await callback.message.answer("Выберите другое время:", reply_markup=keyboard)
            await state.set_state(BookingState.choosing_time)
        return
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        await callback.answer("Ошибка создания записи. Попробуйте позже.", show_alert=True)
        await state.clear()
        return

    # Планируем напоминания (если scheduler передан)
    if scheduler and hasattr(scheduler, 'schedule_reminders') and booking_date and booking_time:
        try:
            scheduler.schedule_reminders(
                order_id=order_id,
                user_id=user_id,
                service_name=data['service_name'],
                booking_date=booking_date,
                booking_time=booking_time
            )
        except Exception as e:
            logger.error(f"Error scheduling reminders: {e}")

    # ИЗМЕНЕНО: Передаём db_manager в уведомления (для ошибки #3)
    # Уведомляем админов
    if config.get('features', {}).get('enable_admin_notify', True):
        order_data = {
            'order_id': order_id,
            'service_name': data['service_name'],
            'price': data['price'],
            'booking_date': booking_date,
            'booking_time': booking_time,
            'client_name': data['client_name'],
            'phone': data['phone'],
            'comment': data.get('comment'),
            'username': username or 'не указан',
            'user_id': user_id  # НОВОЕ: для получения истории клиента
        }

        try:
            # Используем админ-бота для уведомлений, если он доступен
            notify_bot = admin_bot if admin_bot else callback.message.bot
            await send_order_to_admins(
                bot=notify_bot,
                admin_ids=config['admin_ids'],
                order_data=order_data,
                business_name=config['business_name'],
                db_manager=db_manager
            )
        except Exception as e:
            logger.error(f"Error notifying admins: {e}")

    # Формируем сообщение пользователю
    success_msg = messages.get('booking_success', 'Запись создана!')

    confirmation_text = (
        f"{success_msg}\n\n"
        f"📋 ID заявки: #{order_id}\n"
        f"🎯 {data['service_name']}\n"
        f"💰 {data['price']}₽\n"
    )

    if booking_date:
        date_obj = datetime.fromisoformat(booking_date)
        date_formatted = date_obj.strftime('%d.%m.%Y')
        confirmation_text += f"📅 {date_formatted} в {booking_time}\n"

    confirmation_text += "\nМожете посмотреть свои записи через кнопку '📋 Мои записи'"

    await callback.message.edit_text(confirmation_text)

    # Возвращаем главное меню
    from handlers.start import get_main_keyboard
    keyboard = get_main_keyboard()
    await callback.message.answer("Главное меню:", reply_markup=keyboard)

    await state.clear()
    await callback.answer()

    logger.info(f"Order #{order_id} created by user {user_id}")

# === ОБРАБОТЧИКИ РЕДАКТИРОВАНИЯ ПОДТВЕРЖДЕНИЯ ===

@router.callback_query(BookingState.confirmation, F.data == "edit_service")
async def edit_service_from_confirmation(callback: CallbackQuery, state: FSMContext, config: dict):
    """Редактирование услуги из подтверждения"""
    services = config.get('services', [])
    buttons = []

    for service in services:
        button_text = f"{service['name']} — {service['price']}₽"
        callback_data = f"srv_edit:{service['id']}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])

    buttons.append([InlineKeyboardButton(text="🔙 Назад к подтверждению", callback_data="back_to_confirmation")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Выберите новую услугу:", reply_markup=keyboard)
    await state.set_state(BookingState.edit_service)
    await callback.answer()

@router.callback_query(BookingState.edit_service, F.data.startswith("srv_edit:"))
async def service_edit_selected(callback: CallbackQuery, state: FSMContext, config: dict):
    """Обработка выбора новой услуги"""
    service_id = callback.data.split(":")[1]
    services = config.get('services', [])

    selected_service = None
    for service in services:
        if service['id'] == service_id:
            selected_service = service
            break

    if not selected_service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.update_data(
        service_id=selected_service['id'],
        service_name=selected_service['name'],
        price=selected_service['price']
    )

    await show_confirmation(callback.message, state, config)
    await callback.answer()

@router.callback_query(BookingState.confirmation, F.data == "edit_date")
async def edit_date_from_confirmation(callback: CallbackQuery, state: FSMContext):
    """Редактирование даты из подтверждения"""
    keyboard = generate_dates_keyboard()
    await callback.message.edit_text("Выберите новую дату:", reply_markup=keyboard)
    await state.set_state(BookingState.edit_date)
    await callback.answer()

@router.callback_query(BookingState.edit_date, F.data.startswith("date:"))
async def date_edit_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    """Обработка выбора новой даты"""
    booking_date = callback.data.split(":")[1]
    await state.update_data(booking_date=booking_date)

    # Генерируем слоты времени
    keyboard = generate_time_slots_keyboard(config, db_manager, booking_date)

    date_obj = datetime.fromisoformat(booking_date)
    date_formatted = date_obj.strftime('%d.%m.%Y')

    await callback.message.edit_text(
        f"Дата: {date_formatted}\n\n"
        "Выберите время:",
        reply_markup=keyboard
    )

    await state.set_state(BookingState.edit_time)
    await callback.answer()

@router.callback_query(BookingState.confirmation, F.data == "edit_time")
async def edit_time_from_confirmation(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    """Редактирование времени из подтверждения"""
    data = await state.get_data()
    booking_date = data.get('booking_date')

    if not booking_date:
        await callback.answer("Сначала выберите дату", show_alert=True)
        return

    keyboard = generate_time_slots_keyboard(config, db_manager, booking_date)

    date_obj = datetime.fromisoformat(booking_date)
    date_formatted = date_obj.strftime('%d.%m.%Y')

    await callback.message.edit_text(
        f"Дата: {date_formatted}\n\n"
        "Выберите новое время:",
        reply_markup=keyboard
    )

    await state.set_state(BookingState.edit_time)
    await callback.answer()

@router.callback_query(BookingState.edit_time, F.data.startswith("time:"))
async def time_edit_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    """Обработка выбора нового времени"""
    booking_time = callback.data.split(":", 1)[1]
    data = await state.get_data()
    booking_date = data.get('booking_date')

    # Проверка доступности
    if not db_manager.check_slot_availability(booking_date, booking_time):
        await callback.answer("Это время уже занято. Выберите другой слот.", show_alert=True)
        return

    await state.update_data(booking_time=booking_time)
    await show_confirmation(callback.message, state, config)
    await callback.answer()

@router.callback_query(BookingState.confirmation, F.data == "edit_name")
async def edit_name_from_confirmation(callback: CallbackQuery, state: FSMContext):
    """Редактирование имени из подтверждения"""
    await callback.message.edit_text("Введите новое имя:")
    cancel_kb = get_cancel_keyboard()
    await callback.message.answer("Введите новое имя:", reply_markup=cancel_kb)
    await state.set_state(BookingState.edit_name)
    await callback.answer()

@router.message(BookingState.edit_name, F.text)
async def name_edit_entered(message: Message, state: FSMContext, config: dict):
    """Обработка нового имени"""
    client_name = message.text.strip()

    if len(client_name) < 2:
        await message.answer("Пожалуйста, введите корректное имя (минимум 2 символа):")
        return

    await state.update_data(client_name=client_name)
    await show_confirmation(message, state, config)

@router.callback_query(BookingState.confirmation, F.data == "edit_phone")
async def edit_phone_from_confirmation(callback: CallbackQuery, state: FSMContext):
    """Редактирование телефона из подтверждения"""
    await callback.message.edit_text("Введите новый номер телефона:")
    phone_kb = get_phone_input_keyboard()
    await callback.message.answer("Отправьте новый номер телефона:", reply_markup=phone_kb)
    await state.set_state(BookingState.edit_phone)
    await callback.answer()

@router.message(BookingState.edit_phone, F.contact)
async def phone_edit_contact(message: Message, state: FSMContext, config: dict):
    """Обработка нового контакта телефона"""
    phone = message.contact.phone_number
    if not phone.startswith('+'):
        phone = '+' + phone

    await state.update_data(phone=phone)
    # ИЗМЕНЕНО: Убираем клавиатуру (ошибка #1)
    await message.answer("✅ Телефон обновлён", reply_markup=ReplyKeyboardRemove())
    await show_confirmation(message, state, config)

@router.message(BookingState.edit_phone, F.text == "✏️ Ввести вручную")
async def phone_edit_manual(message: Message, state: FSMContext):
    """Ручной ввод нового телефона"""
    cancel_kb = get_cancel_keyboard()
    await message.answer(
        "Введите номер телефона в формате +79991234567 или 89991234567:",
        reply_markup=cancel_kb
    )

@router.message(BookingState.edit_phone, F.text)
async def phone_edit_entered(message: Message, state: FSMContext, config: dict):
    """Обработка нового номера телефона"""
    phone_text = message.text.strip()

    if not is_valid_phone(phone_text):
        await message.answer('Некорректный формат номера.')
        return

    cleaned_phone = clean_phone(phone_text)

    if cleaned_phone.startswith('8'):
        cleaned_phone = '+7' + cleaned_phone[1:]
    elif cleaned_phone.startswith('7'):
        cleaned_phone = '+' + cleaned_phone
    elif not cleaned_phone.startswith('+'):
        cleaned_phone = '+7' + cleaned_phone

    await state.update_data(phone=cleaned_phone)
    await show_confirmation(message, state, config)

@router.callback_query(BookingState.confirmation, F.data == "edit_comment")
async def edit_comment_from_confirmation(callback: CallbackQuery, state: FSMContext):
    """Редактирование комментария из подтверждения"""
    await callback.message.edit_text("Введите новый комментарий:")
    cancel_kb = get_cancel_keyboard()
    await callback.message.answer("Введите новый комментарий (или '0' чтобы удалить):", reply_markup=cancel_kb)
    await state.set_state(BookingState.edit_comment)
    await callback.answer()

@router.message(BookingState.edit_comment, F.text)
async def comment_edit_entered(message: Message, state: FSMContext, config: dict):
    """Обработка нового комментария"""
    comment = message.text.strip()

    if comment == '0':
        await state.update_data(comment=None)
    else:
        await state.update_data(comment=comment)

    await show_confirmation(message, state, config)

@router.callback_query(F.data == "back_to_confirmation")
async def back_to_confirmation(callback: CallbackQuery, state: FSMContext, config: dict):
    """Возврат к подтверждению"""
    await show_confirmation(callback.message, state, config)
    await callback.answer()

@router.callback_query(BookingState.confirmation, F.data == "cancel_booking")
async def cancel_booking_from_confirmation(callback: CallbackQuery, state: FSMContext, config: dict):
    """Отмена записи из подтверждения"""
    await state.clear()
    await callback.message.edit_text("Запись отменена.")

    from handlers.start import get_main_keyboard
    keyboard = get_main_keyboard()
    await callback.message.answer("Главное меню:", reply_markup=keyboard)
    await callback.answer()
