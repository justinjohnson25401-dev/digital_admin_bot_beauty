
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from states.booking import BookingState
from utils.validators import is_valid_phone, clean_phone
from utils.notify import send_order_to_admins
from datetime import datetime, timedelta
import time
import logging
from utils.calendar import generate_calendar_keyboard

logger = logging.getLogger(__name__)

router = Router()

FSM_TTL_SECONDS = 30 * 60

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

def is_date_closed_for_master(config: dict, master_id: str, date_obj) -> tuple:
    if not master_id:
        return False, None
    master = get_master_by_id(config, master_id)
    if not master:
        return False, None
    date_str = date_obj.isoformat() if hasattr(date_obj, 'isoformat') else str(date_obj)
    for closed in master.get('closed_dates', []):
        if closed.get('date') == date_str:
            return True, closed.get('reason', '')
    return False, None

def generate_dates_keyboard(config: dict = None, master_id: str = None) -> InlineKeyboardMarkup:
    """
    Генерирует упрощённую клавиатуру выбора даты:
    - Сегодня
    - Завтра
    - Другой день (календарь)
    """
    from datetime import datetime, timedelta
    
    today = datetime.now().date()
    tomorrow = (datetime.now() + timedelta(days=1)).date()
    
    buttons = []
    
    # Проверяем, не закрыта ли дата для мастера
    is_today_closed, _ = is_date_closed_for_master(config, master_id, today) if config else (False, None)
    is_tomorrow_closed, _ = is_date_closed_for_master(config, master_id, tomorrow) if config else (False, None)
    
    # Кнопка "Сегодня"
    if not is_today_closed:
        buttons.append([InlineKeyboardButton(
            text="📅 Сегодня", 
            callback_data=f"quick_date:{today.isoformat()}"
        )])
    else:
        buttons.append([InlineKeyboardButton(
            text="🚫 Сегодня (закрыто)", 
            callback_data="date_closed"
        )])
    
    # Кнопка "Завтра"
    if not is_tomorrow_closed:
        buttons.append([InlineKeyboardButton(
            text="📅 Завтра", 
            callback_data=f"quick_date:{tomorrow.isoformat()}"
        )])
    else:
        buttons.append([InlineKeyboardButton(
            text="🚫 Завтра (закрыто)", 
            callback_data="date_closed"
        )])
    
    # Кнопка "Другой день" (открывает календарь)
    buttons.append([InlineKeyboardButton(
        text="📅 Другой день", 
        callback_data="open_calendar"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def generate_time_slots_keyboard(config: dict, db_manager, booking_date: str,
                                  master_id: str = None, exclude_order_id: int = None) -> InlineKeyboardMarkup:
    buttons = []
    work_start = int(config.get('booking', {}).get('work_start', 10))
    work_end = int(config.get('booking', {}).get('work_end', 20))
    slot_duration = int(config.get('booking', {}).get('slot_duration', 60))
    if slot_duration <= 0:
        slot_duration = 60
        logger.warning("slot_duration <= 0, using default 60 minutes")

    current_time = datetime.now()
    selected_date = datetime.fromisoformat(booking_date).date()
    is_today = selected_date == current_time.date()
    start_minutes = work_start * 60
    end_minutes = work_end * 60
    current_minutes = start_minutes

    while current_minutes < end_minutes:
        hour = current_minutes // 60
        minute = current_minutes % 60
        slot_time = f"{hour:02d}:{minute:02d}"
        if is_today:
            slot_datetime = datetime.combine(selected_date, datetime.strptime(slot_time, "%H:%M").time())
            if slot_datetime <= current_time:
                current_minutes += slot_duration
                continue

        if master_id and hasattr(db_manager, 'check_slot_availability_for_master'):
            is_available = db_manager.check_slot_availability_for_master(
                booking_date, slot_time, master_id, exclude_order_id=exclude_order_id
            )
        else:
            is_available = db_manager.check_slot_availability(
                booking_date, slot_time, exclude_order_id=exclude_order_id
            )

        if is_available:
            buttons.append([InlineKeyboardButton(text=f"🕐 {slot_time}", callback_data=f"time:{slot_time}")])
        else:
            buttons.append([InlineKeyboardButton(text=f"❌ {slot_time}", callback_data="slot_taken")])
        current_minutes += slot_duration
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_categories_from_services(services: list) -> list:
    categories = []
    seen = set()
    for svc in services:
        cat = svc.get('category', 'Другое')
        if cat not in seen:
            seen.add(cat)
            categories.append(cat)
    return categories

def get_services_by_category(services: list, category: str) -> list:
    return [s for s in services if s.get('category', 'Другое') == category]

def get_masters_for_service(config: dict, service_id: str) -> list:
    staff = config.get('staff', {})
    if not staff.get('enabled', False):
        return []
    masters = staff.get('masters', [])
    return [m for m in masters if m.get('active', True) and (service_id in m.get('services', []) or not m.get('services', []))]

def get_master_by_id(config: dict, master_id: str) -> dict:
    return next((m for m in config.get('staff', {}).get('masters', []) if m.get('id') == master_id), None)

async def start_booking_flow(message: Message, state: FSMContext, config: dict):
    await state.clear()
    await state.update_data(fsm_started_at=time.time(), booking_confirmed=False)
    services = config.get('services', [])
    if not services:
        await message.answer("К сожалению, услуги временно недоступны.")
        return

    categories = get_categories_from_services(services)
    if len(categories) > 1:
        buttons = [[InlineKeyboardButton(text=f"📂 {cat}", callback_data=f"cat:{cat}")] for cat in categories]
        await message.answer("Выберите категорию услуг:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await state.set_state(BookingState.choosing_category)
    else:
        await show_services_list(message, state, config, services)

@router.message(F.text == "📅 Записаться")
async def start_booking(message: Message, state: FSMContext, config: dict):
    logger.info(f"User {message.from_user.id} started booking")
    await start_booking_flow(message, state, config)

async def start_booking_with_master(message: Message, state: FSMContext, config: dict, master_id: str):
    await state.clear()
    master = get_master_by_id(config, master_id)
    if not master:
        await message.answer("Мастер не найден. Попробуйте снова.")
        return

    all_services = config.get('services', [])
    master_services = [s for s in all_services if s.get('id') in master.get('services', [])] if master.get('services') else all_services
    if not master_services:
        await message.answer(f"К сожалению, у мастера {master.get('name', 'мастеру')} нет доступных услуг.")
        return

    await state.update_data(
        fsm_started_at=time.time(), booking_confirmed=False, master_id=master_id,
        master_name=master.get('name'), booking_with_preselected_master=True
    )
    categories = get_categories_from_services(master_services)
    if len(categories) > 1:
        buttons = [[InlineKeyboardButton(text=f"📂 {cat}", callback_data=f"cat:{cat}")] for cat in categories]
        await message.answer(f"📅 <b>Запись к мастеру: {master.get('name')}</b>\n\nВыберите категорию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        await state.set_state(BookingState.choosing_category)
    else:
        await show_services_list(message, state, config, master_services)

async def show_services_list(message: Message, state: FSMContext, config: dict, services: list):
    buttons = []
    for svc in services:
        dur_text = f" • {svc.get('duration', 0)}мин" if svc.get('duration') else ""
        buttons.append([InlineKeyboardButton(text=f"{svc['name']} — {svc['price']}₽{dur_text}", callback_data=f"srv:{svc['id']}")])
    await message.answer("Выберите услугу:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.set_state(BookingState.choosing_service)

@router.callback_query(BookingState.choosing_category, F.data.startswith("cat:"))
async def category_selected(callback: CallbackQuery, state: FSMContext, config: dict):
    if not await _ensure_fsm_fresh(state, callback=callback): return
    category = callback.data.split(":", 1)[1]
    await state.update_data(selected_category=category)
    data = await state.get_data()
    all_services = config.get('services', [])
    services = all_services
    if data.get('booking_with_preselected_master'):
        master = get_master_by_id(config, data.get('master_id'))
        if master:
            services = [s for s in all_services if s.get('id') in master.get('services', [])]

    cat_services = get_services_by_category(services, category)
    buttons = []
    for svc in cat_services:
        dur_text = f" • {svc.get('duration', 0)}мин" if svc.get('duration') else ""
        buttons.append([InlineKeyboardButton(text=f"{svc['name']} — {svc['price']}₽{dur_text}", callback_data=f"srv:{svc['id']}")])
    await callback.message.edit_text(f"📂 {category}\n\nВыберите услугу:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.set_state(BookingState.choosing_service)
    await callback.answer()

@router.callback_query(BookingState.choosing_service, F.data.startswith("srv:"))
async def service_selected(callback: CallbackQuery, state: FSMContext, config: dict):
    if not await _ensure_fsm_fresh(state, callback=callback): return
    service_id = callback.data.split(":")[1]
    selected_service = next((s for s in config.get('services', []) if s['id'] == service_id), None)
    if not selected_service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.update_data(service_id=service_id, service_name=selected_service['name'], price=selected_service['price'])
    data = await state.get_data()
    if data.get('booking_with_preselected_master'):
        await proceed_to_date_selection_with_master(callback, state, config, selected_service)
    else:
        staff_enabled = config.get('staff', {}).get('enabled', False)
        masters = get_masters_for_service(config, service_id) if staff_enabled else []
        if masters:
            buttons = [[InlineKeyboardButton(text=f"👤 {m['name']}", callback_data=f"master:{m['id']}")] for m in masters]
            buttons.append([InlineKeyboardButton(text="👥 Любой свободный мастер", callback_data="master:any")])
            await callback.message.edit_text(f"✅ {selected_service['name']} — {selected_service['price']}₽\n\nВыберите мастера:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
            await state.set_state(BookingState.choosing_master)
        else:
            await state.update_data(master_id=None, master_name=None)
            await proceed_to_date_selection(callback, state, config, selected_service)
    await callback.answer()

async def proceed_to_date_selection(callback: CallbackQuery, state: FSMContext, config: dict, service: dict):
    if config.get('features', {}).get('enable_slot_booking', True):
        keyboard = generate_dates_keyboard(config=config, master_id=None)
        await callback.message.edit_text(f"✅ {service['name']} — {service['price']}₽\n\nВыберите дату:", reply_markup=keyboard)
        await state.set_state(BookingState.choosing_date)
    else:
        await callback.message.edit_text(f"✅ {service['name']} — {service['price']}₽")
        await callback.message.answer("Как вас зовут?", reply_markup=get_cancel_keyboard())
        await state.set_state(BookingState.input_name)

async def proceed_to_date_selection_with_master(callback: CallbackQuery, state: FSMContext, config: dict, service: dict):
    data = await state.get_data()
    if config.get('features', {}).get('enable_slot_booking', True):
        keyboard = generate_dates_keyboard(config=config, master_id=data.get('master_id'))
        await callback.message.edit_text(f"✅ {service['name']} — {service['price']}₽\n👤 Мастер: {data.get('master_name', 'Мастер')}\n\nВыберите дату:", reply_markup=keyboard)
        await state.set_state(BookingState.choosing_date)
    else:
        await callback.message.edit_text(f"✅ {service['name']} — {service['price']}₽\n👤 Мастер: {data.get('master_name')}")
        await callback.message.answer("Как вас зовут?", reply_markup=get_cancel_keyboard())
        await state.set_state(BookingState.input_name)

@router.callback_query(BookingState.choosing_master, F.data.startswith("master:"))
async def master_selected(callback: CallbackQuery, state: FSMContext, config: dict):
    if not await _ensure_fsm_fresh(state, callback=callback): return
    master_id = callback.data.split(":")[1]
    data = await state.get_data()
    if master_id == "any":
        await state.update_data(master_id=None, master_name="Любой мастер")
        master_text = "Любой свободный мастер"
        selected_master_id = None
    else:
        master = get_master_by_id(config, master_id)
        if not master:
            await callback.answer("Мастер не найден", show_alert=True)
            return
        await state.update_data(master_id=master_id, master_name=master['name'])
        master_text = master['name']
        selected_master_id = master_id
    keyboard = generate_dates_keyboard(config=config, master_id=selected_master_id)
    await callback.message.edit_text(f"✅ {data['service_name']} — {data['price']}₽\n👤 Мастер: {master_text}\n\nВыберите дату:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_date)
    await callback.answer()

@router.callback_query(BookingState.choosing_date, F.data.startswith("quick_date:"))
async def quick_date_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    """Быстрый выбор даты (сегодня/завтра)"""
    if not await _ensure_fsm_fresh(state, callback=callback): 
        return
    
    date_str = callback.data.split(":", 1)[1]  # "2026-01-02"
    
    try:
        selected_date = datetime.fromisoformat(date_str).date()
    except Exception:
        await callback.answer("❌ Некорректная дата", show_alert=True)
        return
    
    # Проверка: дата не в прошлом
    if selected_date < datetime.now().date():
        await callback.answer("❌ Нельзя выбрать прошедшую дату", show_alert=True)
        return
    
    data = await state.get_data()
    
    # Проверка: дата не закрыта для мастера
    is_closed, reason = is_date_closed_for_master(config, data.get('master_id'), selected_date)
    if is_closed:
        await callback.answer(
            f"❌ Мастер не работает в этот день{f' ({reason})' if reason else ''}", 
            show_alert=True
        )
        return
    
    # Сохраняем выбранную дату
    await state.update_data(booking_date=date_str)
    
    # Генерируем слоты времени
    keyboard = generate_time_slots_keyboard(
        config, 
        db_manager, 
        date_str, 
        master_id=data.get('master_id')
    )
    
    date_label = "Сегодня" if selected_date == datetime.now().date() else "Завтра"
    
    await callback.message.edit_text(
        f"📅 {date_label} ({selected_date.strftime('%d.%m.%Y')})\n\nВыберите время:",
        reply_markup=keyboard
    )
    await state.set_state(BookingState.choosing_time)
    await callback.answer()

@router.callback_query(F.data == "slot_taken")
async def slot_taken_handler(callback: CallbackQuery):
    await callback.answer("Это время уже занято", show_alert=True)

@router.callback_query(F.data == "date_closed")
async def date_closed_handler(callback: CallbackQuery):
    await callback.answer("❌ Мастер не работает в этот день", show_alert=True)

# --- Calendar Handlers (Universal) ---

@router.callback_query(BookingState.choosing_date, F.data == "open_calendar")
async def show_calendar(callback: CallbackQuery, state: FSMContext, config: dict):
    """Открыть интерактивный календарь"""
    from utils.calendar import generate_calendar_keyboard
    from datetime import datetime
    
    now = datetime.now()
    data = await state.get_data()
    master_id = data.get('master_id')
    
    await state.update_data(
        calendar_year=now.year,
        calendar_month=now.month,
        using_calendar=True
    )
    
    keyboard = generate_calendar_keyboard(
        year=now.year, 
        month=now.month, 
        config=config, 
        master_id=master_id
    )
    
    await callback.message.edit_text(
        "📅 Выберите дату в календаре:",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(BookingState.choosing_date, F.data == "cal_prev_month")
async def calendar_prev_month(callback: CallbackQuery, state: FSMContext, config: dict):
    """Переход к предыдущему месяцу"""
    data = await state.get_data()
    year = data.get('calendar_year')
    month = data.get('calendar_month')
    
    month -= 1
    if month < 1:
        month = 12
        year -= 1
    
    await state.update_data(calendar_year=year, calendar_month=month)
    
    keyboard = generate_calendar_keyboard(
        year=year,
        month=month,
        config=config,
        master_id=data.get('master_id'),
        mode="booking"
    )
    
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(BookingState.choosing_date, F.data == "cal_next_month")
async def calendar_next_month(callback: CallbackQuery, state: FSMContext, config: dict):
    """Переход к следующему месяцу"""
    data = await state.get_data()
    year = data.get('calendar_year')
    month = data.get('calendar_month')
    
    month += 1
    if month > 12:
        month = 1
        year += 1
    
    await state.update_data(calendar_year=year, calendar_month=month)
    
    keyboard = generate_calendar_keyboard(
        year=year,
        month=month,
        config=config,
        master_id=data.get('master_id'),
        mode="booking"
    )
    
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(BookingState.choosing_date, F.data.startswith("cal_date:"))
async def calendar_date_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    """Пользователь выбрал дату из календаря"""
    date_str = callback.data.split(":", 1)[1]
    
    try:
        selected_date = datetime.fromisoformat(date_str).date()
    except Exception:
        await callback.answer("❌ Некорректная дата", show_alert=True)
        return
    
    if selected_date < datetime.now().date():
        await callback.answer("❌ Нельзя выбрать прошедшую дату", show_alert=True)
        return
    
    data = await state.get_data()
    is_closed, reason = is_date_closed_for_master(config, data.get('master_id'), selected_date)
    if is_closed:
        await callback.answer(f"❌ Мастер не работает в этот день", show_alert=True)
        return
    
    await state.update_data(
        booking_date=date_str,
        using_calendar=False
    )
    
    keyboard = generate_time_slots_keyboard(
        config, db_manager, date_str, master_id=data.get('master_id')
    )
    
    await callback.message.edit_text(
        f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n\nВыберите время:",
        reply_markup=keyboard
    )
    await state.set_state(BookingState.choosing_time)
    await callback.answer()


@router.callback_query(F.data == "cal_closed")
async def calendar_closed_handler(callback: CallbackQuery):
    """Нажатие на закрытую/недоступную дату"""
    await callback.answer("❌ Эта дата недоступна", show_alert=True)


@router.callback_query(F.data == "ignore")
async def calendar_ignore_handler(callback: CallbackQuery):
    """Нажатие на пустые/служебные кнопки"""
    await callback.answer()


@router.callback_query(F.data == "cancel_calendar")
async def calendar_cancel_handler(callback: CallbackQuery, state: FSMContext, config: dict):
    """Отмена выбора из календаря"""
    await state.update_data(using_calendar=False)
    
    data = await state.get_data()
    keyboard = generate_dates_keyboard(config=config, master_id=data.get('master_id'))
    await callback.message.edit_text("Выберите дату:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(BookingState.choosing_time, F.data.startswith("time:"))
async def time_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    if not await _ensure_fsm_fresh(state, callback=callback): return
    booking_time = callback.data.split(":", 1)[1]
    data = await state.get_data()
    try:
        slot_dt = datetime.combine(datetime.fromisoformat(data.get('booking_date')).date(), datetime.strptime(booking_time, "%H:%M").time())
    except Exception:
        await callback.answer("Некорректное время", show_alert=True)
        return
    if slot_dt <= datetime.now():
        await callback.answer("Это время уже прошло", show_alert=True)
        return

    # Убрана дублирующая проверка слота - она выполняется внутри add_order() в транзакции
    # для защиты от race condition

    await state.update_data(booking_time=booking_time)
    await callback.message.edit_text(f"📅 {datetime.fromisoformat(data.get('booking_date')).strftime('%d.%m.%Y')} в {booking_time}")

    last_details = db_manager.get_last_client_details(callback.from_user.id)
    if last_details and last_details.get('client_name') and last_details.get('phone'):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Использовать", callback_data="reuse_details"),
             InlineKeyboardButton(text="✏️ Ввести заново", callback_data="enter_details")]])
        await callback.message.answer(f"Использовать данные с прошлой записи?\nИмя: {last_details['client_name']}\nТелефон: {last_details['phone']}", reply_markup=keyboard)
    else:
        await callback.message.answer("Как вас зовут?", reply_markup=get_cancel_keyboard())
    await state.set_state(BookingState.input_name)
    await callback.answer()

@router.message(F.text == "❌ Отменить")
async def cancel_message(message: Message, state: FSMContext):
    await state.clear()
    from handlers.start import get_main_keyboard
    await message.answer("❌ Запись отменена", reply_markup=get_main_keyboard())

@router.callback_query(F.data == "cancel_booking_process")
async def cancel_process(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Запись отменена")
    from handlers.start import get_main_keyboard
    await callback.message.answer("Главное меню:", reply_markup=get_main_keyboard())
    await callback.answer()

# === HANDLERS FOR NAME INPUT ===

@router.callback_query(BookingState.input_name, F.data == "reuse_details")
async def reuse_last_details(callback: CallbackQuery, state: FSMContext, db_manager):
    """Использовать данные с прошлой записи"""
    if not await _ensure_fsm_fresh(state, callback=callback):
        return

    last_details = db_manager.get_last_client_details(callback.from_user.id)
    if last_details:
        await state.update_data(
            client_name=last_details['client_name'],
            phone=last_details['phone']
        )
        logger.info(f"User {callback.from_user.id} reused previous details")
        await callback.message.edit_text(
            f"✅ Данные:\nИмя: {last_details['client_name']}\nТелефон: {last_details['phone']}"
        )
        await ask_for_comment(callback.message, state)
    else:
        await callback.message.answer("Как вас зовут?", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.callback_query(BookingState.input_name, F.data == "enter_details")
async def enter_details_manually(callback: CallbackQuery, state: FSMContext):
    """Ввести данные вручную"""
    if not await _ensure_fsm_fresh(state, callback=callback):
        return
    await callback.message.edit_text("Как вас зовут?")
    await callback.message.answer("Введите ваше имя:", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.message(BookingState.input_name, F.text, ~F.text.in_({"❌ Отменить", "◀️ Назад"}))
async def process_name(message: Message, state: FSMContext, config: dict):
    """Обработка ввода имени"""
    if not await _ensure_fsm_fresh(state, message=message):
        return

    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Имя слишком короткое. Введите минимум 2 символа:")
        return
    if len(name) > 100:
        await message.answer("Имя слишком длинное. Введите до 100 символов:")
        return

    await state.update_data(client_name=name)
    logger.info(f"User {message.from_user.id} entered name in booking FSM")

    # Проверяем, нужен ли телефон
    require_phone = config.get('features', {}).get('require_phone', True)
    if require_phone:
        await message.answer(
            "📱 Как вы хотите указать номер телефона?",
            reply_markup=get_phone_input_keyboard()
        )
        await state.set_state(BookingState.choosing_phone_method)
    else:
        await state.update_data(phone="не указан")
        await ask_for_comment(message, state)


# === HANDLERS FOR PHONE INPUT ===

@router.message(BookingState.choosing_phone_method, F.text == "✏️ Ввести вручную")
async def choose_manual_phone(message: Message, state: FSMContext):
    """Выбран ручной ввод телефона"""
    await message.answer(
        "📞 Введите ваш номер телефона:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(BookingState.input_phone)


@router.message(BookingState.choosing_phone_method, F.contact)
async def process_contact(message: Message, state: FSMContext):
    """Обработка контакта"""
    if not await _ensure_fsm_fresh(state, message=message):
        return

    phone = message.contact.phone_number
    await state.update_data(phone=clean_phone(phone))
    logger.info(f"User {message.from_user.id} shared contact in booking FSM")
    await ask_for_comment(message, state)


@router.message(BookingState.input_phone, F.text, ~F.text.in_({"❌ Отменить", "◀️ Назад"}))
async def process_phone(message: Message, state: FSMContext):
    """Обработка ввода телефона"""
    if not await _ensure_fsm_fresh(state, message=message):
        return

    phone = clean_phone(message.text)
    if not is_valid_phone(phone):
        await message.answer(
            "❌ Неверный формат номера телефона.\n"
            "Введите номер в формате +7XXXXXXXXXX или 8XXXXXXXXXX:"
        )
        return

    await state.update_data(phone=phone)
    logger.info(f"User {message.from_user.id} entered phone in booking FSM")
    await ask_for_comment(message, state)


# === HANDLERS FOR COMMENT ===

async def ask_for_comment(message: Message, state: FSMContext):
    """Запрос комментария"""
    await message.answer(
        "💬 Хотите добавить комментарий к записи?",
        reply_markup=get_comment_choice_keyboard()
    )
    await state.set_state(BookingState.waiting_comment_choice)


@router.callback_query(BookingState.waiting_comment_choice, F.data == "add_comment")
async def want_add_comment(callback: CallbackQuery, state: FSMContext):
    """Пользователь хочет добавить комментарий"""
    await callback.message.edit_text("💬 Введите ваш комментарий:")
    await state.set_state(BookingState.input_comment)
    await callback.answer()


@router.callback_query(BookingState.waiting_comment_choice, F.data == "skip_comment")
async def skip_comment(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    """Пропустить комментарий"""
    await state.update_data(comment=None)
    await callback.answer()
    await show_confirmation(callback.message, state, config, edit=True)


@router.message(BookingState.input_comment, F.text, ~F.text.in_({"❌ Отменить", "◀️ Назад"}))
async def process_comment(message: Message, state: FSMContext, config: dict):
    """Обработка ввода комментария"""
    if not await _ensure_fsm_fresh(state, message=message):
        return

    comment = message.text.strip()
    if len(comment) > 500:
        await message.answer("Комментарий слишком длинный. Максимум 500 символов:")
        return

    await state.update_data(comment=comment)
    logger.info(f"User {message.from_user.id} entered comment in booking FSM")
    await show_confirmation(message, state, config)


# === CONFIRMATION ===

async def show_confirmation(message: Message, state: FSMContext, config: dict, edit: bool = False):
    """Показ подтверждения бронирования"""
    data = await state.get_data()

    service_name = data.get('service_name', 'Услуга')
    price = data.get('price', 0)
    booking_date = data.get('booking_date', '')
    booking_time = data.get('booking_time', '')
    client_name = data.get('client_name', '')
    phone = data.get('phone', '')
    comment = data.get('comment', '')
    master_name = data.get('master_name')

    try:
        date_formatted = datetime.fromisoformat(booking_date).strftime('%d.%m.%Y')
    except Exception:
        date_formatted = booking_date

    text = (
        f"📋 <b>Подтверждение записи</b>\n\n"
        f"💇 Услуга: {service_name}\n"
        f"💰 Цена: {price}₽\n"
    )

    if master_name:
        text += f"👤 Мастер: {master_name}\n"

    text += (
        f"📅 Дата: {date_formatted}\n"
        f"🕐 Время: {booking_time}\n"
        f"👤 Имя: {client_name}\n"
        f"📞 Телефон: {phone}\n"
    )

    if comment:
        text += f"💬 Комментарий: {comment}\n"

    text += "\n✅ Всё верно?"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_booking"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process")
        ],
        [
            InlineKeyboardButton(text="✏️ Изменить имя", callback_data="edit_name"),
            InlineKeyboardButton(text="✏️ Изменить телефон", callback_data="edit_phone")
        ]
    ])

    await state.set_state(BookingState.confirmation)

    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        from handlers.start import get_main_keyboard
        await message.answer(text, reply_markup=keyboard)
        # Убираем клавиатуру отмены
        await message.answer("⬇️", reply_markup=get_main_keyboard())


@router.callback_query(BookingState.confirmation, F.data == "confirm_booking")
async def confirm_booking(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    """Подтверждение и создание записи"""
    if not await _ensure_fsm_fresh(state, callback=callback):
        return

    data = await state.get_data()

    # Проверяем, не была ли запись уже создана
    if data.get('booking_confirmed'):
        await callback.answer("Запись уже создана", show_alert=True)
        return

    user_id = callback.from_user.id
    service_id = data.get('service_id')
    service_name = data.get('service_name')
    price = data.get('price')
    client_name = data.get('client_name')
    phone = data.get('phone')
    comment = data.get('comment')
    booking_date = data.get('booking_date')
    booking_time = data.get('booking_time')
    master_id = data.get('master_id')

    # Отмечаем, что идёт попытка создания
    await state.update_data(booking_confirmed=True)

    try:
        # Атомарная проверка и создание записи (защита от race condition)
        order_id = db_manager.add_order(
            user_id=user_id,
            service_id=service_id,
            service_name=service_name,
            price=price,
            client_name=client_name,
            phone=phone,
            comment=comment,
            booking_date=booking_date,
            booking_time=booking_time,
            master_id=master_id
        )

        # Добавляем пользователя в БД
        db_manager.add_user(
            user_id=user_id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name
        )

        logger.info(f"Booking confirmed: order_id={order_id}, user_id={user_id}")

        # Формируем сообщение об успехе
        try:
            date_formatted = datetime.fromisoformat(booking_date).strftime('%d.%m.%Y')
        except Exception:
            date_formatted = booking_date

        success_text = config.get('messages', {}).get('success',
            "✅ Запись #{id} успешно создана!"
        ).format(id=order_id, date=date_formatted, time=booking_time)

        master_text = f"\n👤 Мастер: {data.get('master_name')}" if data.get('master_name') else ""

        await callback.message.edit_text(
            f"{success_text}\n\n"
            f"📅 {date_formatted} в {booking_time}\n"
            f"💇 {service_name} — {price}₽{master_text}\n\n"
            f"Ждём вас! 💫"
        )

        # Уведомляем админов
        try:
            await send_order_to_admins(
                bot=callback.message.bot,
                admin_ids=config.get('admin_ids', []),
                order_data={
                    'order_id': order_id,
                    'user_id': user_id,
                    'service_name': service_name,
                    'price': price,
                    'booking_date': booking_date,
                    'booking_time': booking_time,
                    'client_name': client_name,
                    'phone': phone,
                    'username': callback.from_user.username,
                    'master_name': data.get('master_name')
                },
                business_name=config.get('business_name', ''),
                db_manager=db_manager
            )
        except Exception as e:
            logger.error(f"Failed to notify admins: {e}")

        # Очищаем состояние
        await state.clear()
        await callback.answer("✅ Запись создана!")

    except ValueError as e:
        # Слот уже занят (race condition обработан)
        logger.warning(f"Slot already taken for user {user_id}: {e}")
        await state.update_data(booking_confirmed=False)
        await callback.answer(
            "❌ К сожалению, это время уже занято. Выберите другое время.",
            show_alert=True
        )
        # Возвращаем к выбору времени
        keyboard = generate_time_slots_keyboard(
            config, db_manager, booking_date, master_id=master_id
        )
        await callback.message.edit_text(
            f"📅 {booking_date}\n\n⚠️ Выбранное время занято. Выберите другое:",
            reply_markup=keyboard
        )
        await state.set_state(BookingState.choosing_time)

    except Exception as e:
        logger.exception(f"Error creating booking for user {user_id}: {e}")
        # Откат: если заказ был создан, отменяем его
        if 'order_id' in locals() and order_id:
            try:
                db_manager.cancel_order(order_id)
                logger.info(f"Rolled back order {order_id} due to error")
            except Exception as rollback_error:
                logger.error(f"Failed to rollback order {order_id}: {rollback_error}")
        await state.update_data(booking_confirmed=False)
        await callback.answer("❌ Произошла ошибка. Попробуйте ещё раз.", show_alert=True)
        await state.clear()


# === EDIT HANDLERS DURING CONFIRMATION ===

@router.callback_query(BookingState.confirmation, F.data == "edit_name")
async def edit_name_in_confirmation(callback: CallbackQuery, state: FSMContext):
    """Редактирование имени из подтверждения"""
    await callback.message.edit_text("✏️ Введите новое имя:")
    await state.set_state(BookingState.edit_name)
    await callback.answer()


@router.callback_query(BookingState.confirmation, F.data == "edit_phone")
async def edit_phone_in_confirmation(callback: CallbackQuery, state: FSMContext):
    """Редактирование телефона из подтверждения"""
    await callback.message.edit_text("✏️ Введите новый номер телефона:")
    await state.set_state(BookingState.edit_phone)
    await callback.answer()


@router.message(BookingState.edit_name, F.text, ~F.text.in_({"❌ Отменить", "◀️ Назад"}))
async def process_edit_name(message: Message, state: FSMContext, config: dict):
    """Обработка редактирования имени"""
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Имя слишком короткое. Введите минимум 2 символа:")
        return

    await state.update_data(client_name=name)
    await show_confirmation(message, state, config)


@router.message(BookingState.edit_phone, F.text, ~F.text.in_({"❌ Отменить", "◀️ Назад"}))
async def process_edit_phone(message: Message, state: FSMContext, config: dict):
    """Обработка редактирования телефона"""
    phone = clean_phone(message.text)
    if not is_valid_phone(phone):
        await message.answer("❌ Неверный формат. Введите номер в формате +7XXXXXXXXXX:")
        return

    await state.update_data(phone=phone)
    await show_confirmation(message, state, config)
