from aiogram import Router, F
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

DAYS_RU = {
    'Monday': 'Пн', 'Tuesday': 'Вт', 'Wednesday': 'Ср',
    'Thursday': 'Чт', 'Friday': 'Пт', 'Saturday': 'Сб', 'Sunday': 'Вс'
}


async def _ensure_fsm_fresh(state: FSMContext, message: Message = None, callback: CallbackQuery = None) -> bool:
    data = await state.get_data()
    started_at = data.get('fsm_started_at')
    if started_at is None:
        return True
    if (time.time() - float(started_at)) <= FSM_TTL_SECONDS:
        return True
    await state.clear()
    text = "⏳ Сессия записи истекла. Начните заново."
    if callback:
        await callback.message.answer(text)
        await callback.answer()
    elif message:
        await message.answer(text)
    return False


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отменить")]],
        resize_keyboard=True
    )


def get_phone_input_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер", request_contact=True)],
            [KeyboardButton(text="✏️ Ввести вручную")],
            [KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True
    )


def get_comment_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Добавить", callback_data="add_comment"),
            InlineKeyboardButton(text="➡️ Пропустить", callback_data="skip_comment")
        ]
    ])


def generate_dates_keyboard(back_callback: str = "back_to_masters") -> InlineKeyboardMarkup:
    buttons = []
    today = datetime.now().date()

    buttons.append([InlineKeyboardButton(
        text=f"📅 Сегодня ({today.strftime('%d.%m')})",
        callback_data=f"date:{today.isoformat()}"
    )])

    tomorrow = today + timedelta(days=1)
    buttons.append([InlineKeyboardButton(
        text=f"📅 Завтра ({tomorrow.strftime('%d.%m')})",
        callback_data=f"date:{tomorrow.isoformat()}"
    )])

    for i in range(2, 7):
        date = today + timedelta(days=i)
        day_name = DAYS_RU.get(date.strftime('%A'), date.strftime('%a'))
        buttons.append([InlineKeyboardButton(
            text=f"{day_name} {date.strftime('%d.%m')}",
            callback_data=f"date:{date.isoformat()}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)])
    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def generate_time_slots_keyboard(config: dict, db_manager, booking_date: str,
                                  master_id: str = None, exclude_order_id: int = None) -> InlineKeyboardMarkup:
    """Генерация клавиатуры с доступными слотами времени.

    ИСПРАВЛЕНО: Теперь корректно работает с slot_duration < 60 минут.
    Используется минутная арифметика вместо часовой.
    """
    buttons = []
    work_start = int(config.get('booking', {}).get('work_start', 10))
    work_end = int(config.get('booking', {}).get('work_end', 20))
    slot_duration = int(config.get('booking', {}).get('slot_duration', 60))

    # Защита от нулевой или отрицательной длительности
    if slot_duration <= 0:
        slot_duration = 60
        logger.warning("slot_duration <= 0, using default 60 minutes")

    current_time = datetime.now()
    selected_date = datetime.fromisoformat(booking_date).date()
    is_today = selected_date == current_time.date()

    # ИСПРАВЛЕНО: Работаем в минутах от начала дня
    # work_start=10 означает 10:00 = 600 минут от полуночи
    # work_end=21 означает 21:00 = 1260 минут от полуночи
    start_minutes = work_start * 60
    end_minutes = work_end * 60
    current_minutes = start_minutes

    while current_minutes < end_minutes:
        # Формируем время слота
        hour = current_minutes // 60
        minute = current_minutes % 60
        slot_time = f"{hour:02d}:{minute:02d}"

        if is_today:
            slot_datetime = datetime.combine(selected_date, datetime.strptime(slot_time, "%H:%M").time())
            if slot_datetime <= current_time:
                current_minutes += slot_duration
                continue

        # Проверка доступности с учётом мастера
        if master_id and hasattr(db_manager, 'check_slot_availability_for_master'):
            if exclude_order_id:
                is_available = db_manager.check_slot_availability_for_master_excluding(
                    booking_date, slot_time, master_id, exclude_order_id)
            else:
                is_available = db_manager.check_slot_availability_for_master(
                    booking_date, slot_time, master_id)
        else:
            if exclude_order_id:
                is_available = db_manager.check_slot_availability_excluding(
                    booking_date, slot_time, exclude_order_id)
            else:
                is_available = db_manager.check_slot_availability(booking_date, slot_time)

        if is_available:
            buttons.append([InlineKeyboardButton(
                text=f"🕐 {slot_time}",
                callback_data=f"time:{slot_time}"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text=f"❌ {slot_time}",
                callback_data="slot_taken"
            )])

        # ИСПРАВЛЕНО: Увеличиваем на slot_duration минут
        current_minutes += slot_duration

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_dates")])
    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_categories_from_services(services: list) -> list:
    """Получить уникальные категории из услуг"""
    categories = []
    seen = set()
    for svc in services:
        cat = svc.get('category', 'Другое')
        if cat not in seen:
            seen.add(cat)
            categories.append(cat)
    return categories


def get_services_by_category(services: list, category: str) -> list:
    """Получить услуги по категории"""
    return [s for s in services if s.get('category', 'Другое') == category]


def get_masters_for_service(config: dict, service_id: str) -> list:
    """Получить мастеров, которые выполняют услугу"""
    staff = config.get('staff', {})
    if not staff.get('enabled', False):
        return []

    masters = staff.get('masters', [])
    result = []
    for master in masters:
        if master.get('active', True):
            master_services = master.get('services', [])
            if not master_services or service_id in master_services:
                result.append(master)
    return result


def get_master_by_id(config: dict, master_id: str) -> dict:
    """Получить мастера по ID"""
    masters = config.get('staff', {}).get('masters', [])
    for m in masters:
        if m.get('id') == master_id:
            return m
    return None


# ==================== НАЧАЛО ЗАПИСИ ====================

async def start_booking_flow(message: Message, state: FSMContext, config: dict):
    """Начало процесса записи (экспортируемая функция)"""
    await state.clear()
    await state.update_data(fsm_started_at=time.time(), booking_confirmed=False)

    services = config.get('services', [])
    if not services:
        await message.answer("К сожалению, услуги временно недоступны.")
        return

    categories = get_categories_from_services(services)

    # Если категорий больше 1 - показываем выбор категорий
    if len(categories) > 1:
        buttons = []
        for cat in categories:
            buttons.append([InlineKeyboardButton(
                text=f"📂 {cat}",
                callback_data=f"cat:{cat}"
            )])
        buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer("Выберите категорию услуг:", reply_markup=keyboard)
        await state.set_state(BookingState.choosing_category)
    else:
        # Если одна категория - сразу показываем услуги
        await show_services_list(message, state, config, services)


@router.message(F.text == "📅 Записаться")
async def start_booking(message: Message, state: FSMContext, config: dict):
    """Начало процесса записи по кнопке"""
    await start_booking_flow(message, state, config)
    logger.info(f"User {message.from_user.id} started booking")


async def show_services_list(message: Message, state: FSMContext, config: dict, services: list):
    """Показать список услуг"""
    buttons = []
    for svc in services:
        duration = svc.get('duration', 0)
        dur_text = f" • {duration}мин" if duration else ""
        btn_text = f"{svc['name']} — {svc['price']}₽{dur_text}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"srv:{svc['id']}")])

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_categories")])
    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите услугу:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_service)


# ==================== ВЫБОР КАТЕГОРИИ ====================

@router.callback_query(BookingState.choosing_category, F.data.startswith("cat:"))
async def category_selected(callback: CallbackQuery, state: FSMContext, config: dict):
    if not await _ensure_fsm_fresh(state, callback=callback):
        return

    category = callback.data.split(":", 1)[1]
    await state.update_data(selected_category=category)

    services = config.get('services', [])
    cat_services = get_services_by_category(services, category)

    buttons = []
    for svc in cat_services:
        duration = svc.get('duration', 0)
        dur_text = f" • {duration}мин" if duration else ""
        btn_text = f"{svc['name']} — {svc['price']}₽{dur_text}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"srv:{svc['id']}")])

    buttons.append([InlineKeyboardButton(text="🔙 К категориям", callback_data="back_to_categories")])
    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(f"📂 {category}\n\nВыберите услугу:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_service)
    await callback.answer()


@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery, state: FSMContext, config: dict):
    services = config.get('services', [])
    categories = get_categories_from_services(services)

    if len(categories) <= 1:
        await show_services_list(callback.message, state, config, services)
        await callback.answer()
        return

    buttons = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(text=f"📂 {cat}", callback_data=f"cat:{cat}")])
    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Выберите категорию услуг:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_category)
    await callback.answer()


# ==================== ВЫБОР УСЛУГИ ====================

@router.callback_query(BookingState.choosing_service, F.data.startswith("srv:"))
async def service_selected(callback: CallbackQuery, state: FSMContext, config: dict):
    if not await _ensure_fsm_fresh(state, callback=callback):
        return

    service_id = callback.data.split(":")[1]
    services = config.get('services', [])

    selected_service = next((s for s in services if s['id'] == service_id), None)
    if not selected_service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.update_data(
        service_id=selected_service['id'],
        service_name=selected_service['name'],
        price=selected_service['price']
    )

    # Проверяем, включены ли мастера
    staff_enabled = config.get('staff', {}).get('enabled', False)
    masters = get_masters_for_service(config, service_id) if staff_enabled else []

    if masters:
        # Показываем выбор мастера
        buttons = []
        for master in masters:
            spec = master.get('specialization') or master.get('role', '')
            spec_text = f" ({spec})" if spec else ""
            buttons.append([InlineKeyboardButton(
                text=f"👤 {master['name']}{spec_text}",
                callback_data=f"master:{master['id']}"
            )])

        # Опция "Любой мастер"
        buttons.append([InlineKeyboardButton(
            text="👥 Любой свободный мастер",
            callback_data="master:any"
        )])
        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_services")])
        buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(
            f"✅ {selected_service['name']} — {selected_service['price']}₽\n\n"
            "Выберите мастера:",
            reply_markup=keyboard
        )
        await state.set_state(BookingState.choosing_master)
    else:
        # Без мастеров - сразу к дате
        await state.update_data(master_id=None, master_name=None)
        await proceed_to_date_selection(callback, state, config, selected_service)

    await callback.answer()


async def proceed_to_date_selection(callback: CallbackQuery, state: FSMContext, config: dict, service: dict):
    """Переход к выбору даты"""
    if config.get('features', {}).get('enable_slot_booking', True):
        keyboard = generate_dates_keyboard(back_callback="back_to_services")
        await callback.message.edit_text(
            f"✅ {service['name']} — {service['price']}₽\n\n"
            "Выберите дату:",
            reply_markup=keyboard
        )
        await state.set_state(BookingState.choosing_date)
    else:
        # Без слотов - сразу имя
        await callback.message.edit_text(f"✅ {service['name']} — {service['price']}₽")
        await callback.message.answer("Как вас зовут?", reply_markup=get_cancel_keyboard())
        await state.set_state(BookingState.input_name)


# ==================== ВЫБОР МАСТЕРА ====================

@router.callback_query(BookingState.choosing_master, F.data.startswith("master:"))
async def master_selected(callback: CallbackQuery, state: FSMContext, config: dict):
    if not await _ensure_fsm_fresh(state, callback=callback):
        return

    master_id = callback.data.split(":")[1]
    data = await state.get_data()

    if master_id == "any":
        await state.update_data(master_id=None, master_name="Любой мастер")
        master_text = "Любой свободный мастер"
    else:
        master = get_master_by_id(config, master_id)
        if not master:
            await callback.answer("Мастер не найден", show_alert=True)
            return
        await state.update_data(master_id=master_id, master_name=master['name'])
        master_text = master['name']

    keyboard = generate_dates_keyboard(back_callback="back_to_masters")
    await callback.message.edit_text(
        f"✅ {data['service_name']} — {data['price']}₽\n"
        f"👤 Мастер: {master_text}\n\n"
        "Выберите дату:",
        reply_markup=keyboard
    )
    await state.set_state(BookingState.choosing_date)
    await callback.answer()


@router.callback_query(F.data == "back_to_masters")
async def back_to_masters(callback: CallbackQuery, state: FSMContext, config: dict):
    data = await state.get_data()
    service_id = data.get('service_id')

    masters = get_masters_for_service(config, service_id)
    if not masters:
        await back_to_services(callback, state, config)
        return

    buttons = []
    for master in masters:
        spec = master.get('specialization') or master.get('role', '')
        spec_text = f" ({spec})" if spec else ""
        buttons.append([InlineKeyboardButton(
            text=f"👤 {master['name']}{spec_text}",
            callback_data=f"master:{master['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="👥 Любой свободный мастер", callback_data="master:any")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_services")])
    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        f"✅ {data['service_name']} — {data['price']}₽\n\nВыберите мастера:",
        reply_markup=keyboard
    )
    await state.set_state(BookingState.choosing_master)
    await callback.answer()


@router.callback_query(F.data == "back_to_services")
async def back_to_services(callback: CallbackQuery, state: FSMContext, config: dict):
    data = await state.get_data()
    category = data.get('selected_category')
    services = config.get('services', [])

    if category:
        cat_services = get_services_by_category(services, category)
    else:
        cat_services = services

    buttons = []
    for svc in cat_services:
        duration = svc.get('duration', 0)
        dur_text = f" • {duration}мин" if duration else ""
        btn_text = f"{svc['name']} — {svc['price']}₽{dur_text}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"srv:{svc['id']}")])

    buttons.append([InlineKeyboardButton(text="🔙 К категориям", callback_data="back_to_categories")])
    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    title = f"📂 {category}\n\n" if category else ""
    await callback.message.edit_text(f"{title}Выберите услугу:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_service)
    await callback.answer()


# ==================== ВЫБОР ДАТЫ ====================

@router.callback_query(BookingState.choosing_date, F.data.startswith("date:"))
async def date_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
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
    data = await state.get_data()
    master_id = data.get('master_id')

    keyboard = generate_time_slots_keyboard(config, db_manager, booking_date, master_id=master_id)
    date_formatted = selected_date.strftime('%d.%m.%Y')

    await callback.message.edit_text(
        f"📅 Дата: {date_formatted}\n\nВыберите время:",
        reply_markup=keyboard
    )
    await state.set_state(BookingState.choosing_time)
    await callback.answer()


@router.callback_query(F.data == "back_to_dates")
async def back_to_dates(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    back_cb = "back_to_masters" if data.get('master_name') else "back_to_services"
    keyboard = generate_dates_keyboard(back_callback=back_cb)
    await callback.message.edit_text("Выберите дату:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_date)
    await callback.answer()


# ==================== ВЫБОР ВРЕМЕНИ ====================

@router.callback_query(BookingState.choosing_time, F.data.startswith("time:"))
async def time_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    if not await _ensure_fsm_fresh(state, callback=callback):
        return

    booking_time = callback.data.split(":", 1)[1]
    data = await state.get_data()
    booking_date = data.get('booking_date')
    master_id = data.get('master_id')

    # Валидация
    try:
        selected_date = datetime.fromisoformat(booking_date).date()
        slot_dt = datetime.combine(selected_date, datetime.strptime(booking_time, "%H:%M").time())
    except Exception:
        await callback.answer("Некорректное время", show_alert=True)
        return

    if slot_dt <= datetime.now():
        await callback.answer("Это время уже прошло", show_alert=True)
        return

    # Проверка занятости
    if master_id:
        if hasattr(db_manager, 'check_slot_availability_for_master'):
            available = db_manager.check_slot_availability_for_master(booking_date, booking_time, master_id)
        else:
            available = db_manager.check_slot_availability(booking_date, booking_time)
    else:
        available = db_manager.check_slot_availability(booking_date, booking_time)

    if not available:
        await callback.answer("Это время занято. Выберите другое.", show_alert=True)
        return

    await state.update_data(booking_time=booking_time)
    date_formatted = datetime.fromisoformat(booking_date).strftime('%d.%m.%Y')

    await callback.message.edit_text(f"📅 {date_formatted} в {booking_time}")

    # Проверяем предыдущие данные клиента
    last_details = None
    if hasattr(db_manager, 'get_last_client_details'):
        last_details = db_manager.get_last_client_details(callback.from_user.id)

    if last_details and last_details.get('client_name') and last_details.get('phone'):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Использовать", callback_data="reuse_details"),
                InlineKeyboardButton(text="✏️ Ввести заново", callback_data="enter_details")
            ]
        ])
        await callback.message.answer(
            f"Использовать данные с прошлой записи?\n"
            f"Имя: {last_details['client_name']}\n"
            f"Телефон: {last_details['phone']}",
            reply_markup=keyboard
        )
    else:
        await callback.message.answer("Как вас зовут?", reply_markup=get_cancel_keyboard())

    await state.set_state(BookingState.input_name)
    await callback.answer()


@router.callback_query(F.data == "slot_taken")
async def slot_taken_handler(callback: CallbackQuery):
    await callback.answer("Это время уже занято", show_alert=True)


# ==================== ВВОД ИМЕНИ ====================

@router.callback_query(BookingState.input_name, F.data == "reuse_details")
async def reuse_details(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    if not await _ensure_fsm_fresh(state, callback=callback):
        return

    last_details = db_manager.get_last_client_details(callback.from_user.id)
    if not last_details:
        await callback.answer("Данные не найдены", show_alert=True)
        return

    await state.update_data(client_name=last_details['client_name'], phone=last_details['phone'])

    if config.get('features', {}).get('ask_comment', True):
        await callback.message.edit_text("✅ Данные использованы")
        await callback.message.answer("Хотите добавить комментарий?", reply_markup=get_comment_choice_keyboard())
        await state.set_state(BookingState.waiting_comment_choice)
    else:
        await show_confirmation(callback.message, state, config)

    await callback.answer()


@router.callback_query(BookingState.input_name, F.data == "enter_details")
async def enter_details(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Как вас зовут?", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.message(BookingState.input_name, F.text)
async def process_name(message: Message, state: FSMContext, config: dict):
    if not await _ensure_fsm_fresh(state, message=message):
        return

    name = message.text.strip()

    # Проверки
    if name in ["📅 Записаться", "📋 Мои записи", "💅 Услуги и цены", "📍 Адрес", "❓ FAQ"]:
        await message.answer("Введите ваше имя, а не текст кнопки:")
        return

    if len(name) < 2:
        await message.answer("Минимум 2 символа:")
        return

    if len(name) > 100:
        await message.answer("Максимум 100 символов:")
        return

    await state.update_data(client_name=name)

    if config.get('features', {}).get('require_phone', True):
        await message.answer("Отправьте номер телефона:", reply_markup=get_phone_input_keyboard())
        await state.set_state(BookingState.choosing_phone_method)
    else:
        await state.update_data(phone="не указан")
        if config.get('features', {}).get('ask_comment', True):
            await message.answer("Хотите добавить комментарий?", reply_markup=get_comment_choice_keyboard())
            await state.set_state(BookingState.waiting_comment_choice)
        else:
            await show_confirmation(message, state, config)


# ==================== ВВОД ТЕЛЕФОНА ====================

@router.message(BookingState.choosing_phone_method, F.text == "✏️ Ввести вручную")
async def phone_manual(message: Message, state: FSMContext):
    await message.answer("Введите номер (+79991234567):", reply_markup=get_cancel_keyboard())
    await state.set_state(BookingState.input_phone)


@router.message(BookingState.choosing_phone_method, F.contact)
async def process_contact(message: Message, state: FSMContext, config: dict):
    phone = message.contact.phone_number
    if not phone.startswith('+'):
        phone = '+' + phone

    await state.update_data(phone=phone)
    await message.answer("✅ Телефон получен", reply_markup=ReplyKeyboardRemove())

    if config.get('features', {}).get('ask_comment', True):
        await message.answer("Хотите добавить комментарий?", reply_markup=get_comment_choice_keyboard())
        await state.set_state(BookingState.waiting_comment_choice)
    else:
        await show_confirmation(message, state, config)


@router.message(BookingState.choosing_phone_method, F.text)
async def phone_direct_input(message: Message, state: FSMContext, config: dict):
    """Прямой ввод телефона без нажатия 'Ввести вручную'"""
    text = message.text.strip()

    # Игнорируем кнопки меню
    if text in ["✏️ Ввести вручную", "❌ Отменить", "📱 Отправить номер"]:
        return

    # Проверяем валидность номера
    if not is_valid_phone(text):
        await message.answer("Некорректный номер. Используйте кнопки или введите номер в формате +79991234567:")
        return

    # Обрабатываем номер
    cleaned = clean_phone(text)
    if cleaned.startswith('8'):
        cleaned = '+7' + cleaned[1:]
    elif cleaned.startswith('7'):
        cleaned = '+' + cleaned
    elif not cleaned.startswith('+'):
        cleaned = '+7' + cleaned

    await state.update_data(phone=cleaned)
    await message.answer("✅ Телефон получен", reply_markup=ReplyKeyboardRemove())

    if config.get('features', {}).get('ask_comment', True):
        await message.answer("Хотите добавить комментарий?", reply_markup=get_comment_choice_keyboard())
        await state.set_state(BookingState.waiting_comment_choice)
    else:
        await show_confirmation(message, state, config)


@router.message(BookingState.input_phone, F.text)
async def process_phone(message: Message, state: FSMContext, config: dict):
    phone = message.text.strip()

    if not is_valid_phone(phone):
        await message.answer("Некорректный номер. Попробуйте ещё:")
        return

    cleaned = clean_phone(phone)
    if cleaned.startswith('8'):
        cleaned = '+7' + cleaned[1:]
    elif cleaned.startswith('7'):
        cleaned = '+' + cleaned
    elif not cleaned.startswith('+'):
        cleaned = '+7' + cleaned

    await state.update_data(phone=cleaned)
    await message.answer("✅ Телефон получен", reply_markup=ReplyKeyboardRemove())

    if config.get('features', {}).get('ask_comment', True):
        await message.answer("Хотите добавить комментарий?", reply_markup=get_comment_choice_keyboard())
        await state.set_state(BookingState.waiting_comment_choice)
    else:
        await show_confirmation(message, state, config)


# ==================== КОММЕНТАРИЙ ====================

@router.callback_query(BookingState.waiting_comment_choice, F.data == "add_comment")
async def add_comment(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✏️ Введите комментарий:", reply_markup=get_cancel_keyboard())
    await state.set_state(BookingState.input_comment)
    await callback.answer()


@router.callback_query(BookingState.waiting_comment_choice, F.data == "skip_comment")
async def skip_comment(callback: CallbackQuery, state: FSMContext, config: dict):
    await state.update_data(comment=None)
    await callback.message.edit_text("✅ Комментарий пропущен")
    await show_confirmation(callback.message, state, config)
    await callback.answer()


@router.message(BookingState.input_comment, F.text)
async def process_comment(message: Message, state: FSMContext, config: dict):
    if not await _ensure_fsm_fresh(state, message=message):
        return

    comment = message.text.strip()
    if len(comment) > 500:
        await message.answer("Максимум 500 символов:")
        return

    await state.update_data(comment=comment)
    await show_confirmation(message, state, config)


# ==================== ПОДТВЕРЖДЕНИЕ ====================

async def show_confirmation(message: Message, state: FSMContext, config: dict):
    data = await state.get_data()

    text = "📋 <b>ПОДТВЕРЖДЕНИЕ ЗАПИСИ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"💅 Услуга: {data['service_name']}\n"
    text += f"💰 Цена: {data['price']}₽\n"

    if data.get('master_name'):
        text += f"👤 Мастер: {data['master_name']}\n"

    if data.get('booking_date'):
        date_obj = datetime.fromisoformat(data['booking_date'])
        text += f"📅 Дата: {date_obj.strftime('%d.%m.%Y')}\n"
        text += f"🕐 Время: {data.get('booking_time', '-')}\n"

    text += f"\n👤 Имя: {data['client_name']}\n"
    text += f"📱 Телефон: {data['phone']}\n"

    if data.get('comment'):
        text += f"💬 Комментарий: {data['comment']}\n"

    text += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "Всё верно?"

    buttons = [
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_booking")],
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
            InlineKeyboardButton(text="💬 Коммент", callback_data="edit_comment")
        ]
    ]

    # Кнопка редактирования мастера если есть
    if data.get('master_name'):
        buttons.insert(2, [InlineKeyboardButton(text="👤 Мастер", callback_data="edit_master")])

    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(BookingState.confirmation)


@router.callback_query(BookingState.confirmation, F.data == "confirm_booking")
async def confirm_booking(callback: CallbackQuery, state: FSMContext, config: dict, db_manager, scheduler=None, admin_bot=None):
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

    db_manager.add_user(user_id, username, callback.from_user.first_name, callback.from_user.last_name)

    booking_date = data.get('booking_date')
    booking_time = data.get('booking_time')
    master_id = data.get('master_id')

    # Проверка времени
    if booking_date and booking_time:
        try:
            slot_dt = datetime.combine(
                datetime.fromisoformat(booking_date).date(),
                datetime.strptime(booking_time, "%H:%M").time()
            )
            if slot_dt <= datetime.now():
                await callback.answer("Время уже прошло", show_alert=True)
                await state.update_data(booking_confirmed=False)
                return
        except Exception:
            pass

        if not db_manager.check_slot_availability(booking_date, booking_time):
            await callback.answer("Слот уже занят", show_alert=True)
            await state.update_data(booking_confirmed=False)
            return

    # Создаём заказ
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
            booking_time=booking_time,
            master_id=master_id
        )
    except ValueError:
        await callback.answer("Слот занят. Выберите другое время.", show_alert=True)
        await state.update_data(booking_confirmed=False)
        return
    except Exception as e:
        logger.error(f"Order creation error: {e}")
        await callback.answer("Ошибка. Попробуйте позже.", show_alert=True)
        await state.clear()
        return

    # Напоминания
    if scheduler and booking_date and booking_time:
        try:
            scheduler.schedule_reminders(
                order_id=order_id,
                user_id=user_id,
                service_name=data['service_name'],
                booking_date=booking_date,
                booking_time=booking_time
            )
        except Exception as e:
            logger.error(f"Reminder error: {e}")

    # Уведомление админов
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
            'user_id': user_id,
            'master_name': data.get('master_name')
        }
        try:
            notify_bot = admin_bot if admin_bot else callback.message.bot
            await send_order_to_admins(
                bot=notify_bot,
                admin_ids=config['admin_ids'],
                order_data=order_data,
                business_name=config['business_name'],
                db_manager=db_manager
            )
        except Exception as e:
            logger.error(f"Admin notify error: {e}")

    # Сообщение пользователю
    text = f"✅ <b>ЗАПИСЬ СОЗДАНА!</b>\n\n"
    text += f"📋 ID: #{order_id}\n"
    text += f"💅 {data['service_name']}\n"
    text += f"💰 {data['price']}₽\n"

    if data.get('master_name'):
        text += f"👤 Мастер: {data['master_name']}\n"

    if booking_date:
        date_formatted = datetime.fromisoformat(booking_date).strftime('%d.%m.%Y')
        text += f"📅 {date_formatted} в {booking_time}\n"

    text += "\nПосмотреть записи: «📋 Мои записи»"

    await callback.message.edit_text(text, parse_mode="HTML")

    from handlers.start import get_main_keyboard
    await callback.message.answer("Главное меню:", reply_markup=get_main_keyboard())

    await state.clear()
    await callback.answer()
    logger.info(f"Order #{order_id} created by {user_id}")


# ==================== ОТМЕНА ====================

@router.callback_query(F.data == "cancel_booking_process")
async def cancel_process(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Запись отменена")

    from handlers.start import get_main_keyboard
    await callback.message.answer("Главное меню:", reply_markup=get_main_keyboard())
    await callback.answer()


@router.callback_query(BookingState.confirmation, F.data == "cancel_booking")
async def cancel_from_confirmation(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Запись отменена")

    from handlers.start import get_main_keyboard
    await callback.message.answer("Главное меню:", reply_markup=get_main_keyboard())
    await callback.answer()


@router.message(F.text == "❌ Отменить")
async def cancel_message(message: Message, state: FSMContext):
    await state.clear()

    from handlers.start import get_main_keyboard
    await message.answer("❌ Запись отменена", reply_markup=get_main_keyboard())


# ==================== РЕДАКТИРОВАНИЕ ИЗ ПОДТВЕРЖДЕНИЯ ====================

@router.callback_query(BookingState.confirmation, F.data == "edit_service")
async def edit_service(callback: CallbackQuery, state: FSMContext, config: dict):
    services = config.get('services', [])
    buttons = [[InlineKeyboardButton(
        text=f"{s['name']} — {s['price']}₽",
        callback_data=f"srv_edit:{s['id']}"
    )] for s in services]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_confirmation")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Выберите услугу:", reply_markup=keyboard)
    await state.set_state(BookingState.edit_service)
    await callback.answer()


@router.callback_query(BookingState.edit_service, F.data.startswith("srv_edit:"))
async def service_edited(callback: CallbackQuery, state: FSMContext, config: dict):
    service_id = callback.data.split(":")[1]
    service = next((s for s in config.get('services', []) if s['id'] == service_id), None)

    if not service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.update_data(
        service_id=service['id'],
        service_name=service['name'],
        price=service['price']
    )
    await show_confirmation(callback.message, state, config)
    await callback.answer()


@router.callback_query(BookingState.confirmation, F.data == "edit_master")
async def edit_master(callback: CallbackQuery, state: FSMContext, config: dict):
    data = await state.get_data()
    masters = get_masters_for_service(config, data.get('service_id'))

    buttons = []
    for m in masters:
        buttons.append([InlineKeyboardButton(text=f"👤 {m['name']}", callback_data=f"master_edit:{m['id']}")])
    buttons.append([InlineKeyboardButton(text="👥 Любой мастер", callback_data="master_edit:any")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_confirmation")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Выберите мастера:", reply_markup=keyboard)
    await state.set_state(BookingState.edit_master)
    await callback.answer()


@router.callback_query(BookingState.edit_master, F.data.startswith("master_edit:"))
async def master_edited(callback: CallbackQuery, state: FSMContext, config: dict):
    master_id = callback.data.split(":")[1]

    if master_id == "any":
        await state.update_data(master_id=None, master_name="Любой мастер")
    else:
        master = get_master_by_id(config, master_id)
        if master:
            await state.update_data(master_id=master_id, master_name=master['name'])

    await show_confirmation(callback.message, state, config)
    await callback.answer()


@router.callback_query(BookingState.confirmation, F.data == "edit_date")
async def edit_date(callback: CallbackQuery, state: FSMContext):
    keyboard = generate_dates_keyboard(back_callback="back_to_confirmation")
    await callback.message.edit_text("Выберите дату:", reply_markup=keyboard)
    await state.set_state(BookingState.edit_date)
    await callback.answer()


@router.callback_query(BookingState.edit_date, F.data.startswith("date:"))
async def date_edited(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    booking_date = callback.data.split(":")[1]
    await state.update_data(booking_date=booking_date)

    data = await state.get_data()
    keyboard = generate_time_slots_keyboard(config, db_manager, booking_date, master_id=data.get('master_id'))

    await callback.message.edit_text(
        f"📅 {datetime.fromisoformat(booking_date).strftime('%d.%m.%Y')}\n\nВыберите время:",
        reply_markup=keyboard
    )
    await state.set_state(BookingState.edit_time)
    await callback.answer()


@router.callback_query(BookingState.confirmation, F.data == "edit_time")
async def edit_time(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    data = await state.get_data()
    booking_date = data.get('booking_date')

    if not booking_date:
        await callback.answer("Сначала выберите дату", show_alert=True)
        return

    keyboard = generate_time_slots_keyboard(config, db_manager, booking_date, master_id=data.get('master_id'))
    await callback.message.edit_text("Выберите время:", reply_markup=keyboard)
    await state.set_state(BookingState.edit_time)
    await callback.answer()


@router.callback_query(BookingState.edit_time, F.data.startswith("time:"))
async def time_edited(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    booking_time = callback.data.split(":", 1)[1]
    data = await state.get_data()

    if not db_manager.check_slot_availability(data.get('booking_date'), booking_time):
        await callback.answer("Время занято", show_alert=True)
        return

    await state.update_data(booking_time=booking_time)
    await show_confirmation(callback.message, state, config)
    await callback.answer()


@router.callback_query(BookingState.confirmation, F.data == "edit_name")
async def edit_name(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✏️ Введите новое имя:", reply_markup=get_cancel_keyboard())
    await state.set_state(BookingState.edit_name)
    await callback.answer()


@router.message(BookingState.edit_name, F.text)
async def name_edited(message: Message, state: FSMContext, config: dict):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Минимум 2 символа:")
        return

    await state.update_data(client_name=name)
    await show_confirmation(message, state, config)


@router.callback_query(BookingState.confirmation, F.data == "edit_phone")
async def edit_phone(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📞 Отправьте номер:", reply_markup=get_phone_input_keyboard())
    await state.set_state(BookingState.edit_phone)
    await callback.answer()


@router.message(BookingState.edit_phone, F.contact)
async def phone_edited_contact(message: Message, state: FSMContext, config: dict):
    phone = message.contact.phone_number
    if not phone.startswith('+'):
        phone = '+' + phone

    await state.update_data(phone=phone)
    await message.answer("✅", reply_markup=ReplyKeyboardRemove())
    await show_confirmation(message, state, config)


@router.message(BookingState.edit_phone, F.text == "✏️ Ввести вручную")
async def phone_edit_manual(message: Message, state: FSMContext):
    await message.answer("Введите номер:", reply_markup=get_cancel_keyboard())


@router.message(BookingState.edit_phone, F.text)
async def phone_edited_text(message: Message, state: FSMContext, config: dict):
    phone = message.text.strip()
    if not is_valid_phone(phone):
        await message.answer("Некорректный номер:")
        return

    cleaned = clean_phone(phone)
    if cleaned.startswith('8'):
        cleaned = '+7' + cleaned[1:]
    elif not cleaned.startswith('+'):
        cleaned = '+' + cleaned

    await state.update_data(phone=cleaned)
    await show_confirmation(message, state, config)


@router.callback_query(BookingState.confirmation, F.data == "edit_comment")
async def edit_comment(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✏️ Введите комментарий (0 - удалить):", reply_markup=get_cancel_keyboard())
    await state.set_state(BookingState.edit_comment)
    await callback.answer()


@router.message(BookingState.edit_comment, F.text)
async def comment_edited(message: Message, state: FSMContext, config: dict):
    comment = message.text.strip()
    if comment == '0':
        await state.update_data(comment=None)
    else:
        await state.update_data(comment=comment)

    await show_confirmation(message, state, config)


@router.callback_query(F.data == "back_to_confirmation")
async def back_to_confirmation(callback: CallbackQuery, state: FSMContext, config: dict):
    await show_confirmation(callback.message, state, config)
    await callback.answer()
