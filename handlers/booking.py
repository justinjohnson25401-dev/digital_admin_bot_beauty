
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


def generate_dates_keyboard(back_callback: str = "back_to_masters", config: dict = None, master_id: str = None) -> InlineKeyboardMarkup:
    buttons = []
    today = datetime.now().date()
    for i in range(7):
        date = today + timedelta(days=i)
        day_name = DAYS_RU.get(date.strftime('%A'), date.strftime('%a'))
        is_closed, reason = is_date_closed_for_master(config, master_id, date) if config else (False, None)
        if is_closed:
            buttons.append([InlineKeyboardButton(text=f"🚫 {day_name} {date.strftime('%d.%m')} (закрыто)", callback_data="date_closed")])
        else:
            text = f"📅 {day_name} {date.strftime('%d.%m')}"
            if i == 0:
                text += " — Сегодня"
            elif i == 1:
                text += " — Завтра"
            buttons.append([InlineKeyboardButton(text=text, callback_data=f"date:{date.isoformat()}")])
    buttons.append([InlineKeyboardButton(text="📝 Ввести дату вручную", callback_data="input_custom_date")])
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

@router.callback_query(BookingState.choosing_date, F.data.startswith("date:"))
async def date_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    if not await _ensure_fsm_fresh(state, callback=callback): return
    booking_date = callback.data.split(":")[1]
    try:
        selected_date = datetime.fromisoformat(booking_date).date()
    except Exception:
        await callback.answer("Некорректная дата", show_alert=True)
        return
    if selected_date < datetime.now().date():
        await callback.answer("Нельзя выбрать прошедшую дату", show_alert=True)
        return

    data = await state.get_data()
    is_closed, reason = is_date_closed_for_master(config, data.get('master_id'), selected_date)
    if is_closed:
        await callback.answer(f"❌ Мастер не работает в этот день{f' ({reason})' if reason else ''}", show_alert=True)
        return

    await state.update_data(booking_date=booking_date)
    keyboard = generate_time_slots_keyboard(config, db_manager, booking_date, master_id=data.get('master_id'))
    await callback.message.edit_text(f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n\nВыберите время:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_time)
    await callback.answer()

@router.callback_query(F.data == "slot_taken")
async def slot_taken_handler(callback: CallbackQuery):
    await callback.answer("Это время уже занято", show_alert=True)

@router.callback_query(F.data == "date_closed")
async def date_closed_handler(callback: CallbackQuery):
    await callback.answer("❌ Мастер не работает в этот день", show_alert=True)


# --- Calendar Handlers (Universal) ---

@router.callback_query(BookingState.choosing_date, F.data == "input_custom_date")
async def show_calendar(callback: CallbackQuery, state: FSMContext, config: dict):
    """Показать интерактивный календарь для выбора даты"""
    from datetime import datetime
    
    now = datetime.now()
    data = await state.get_data()
    
    await state.update_data(
        calendar_year=now.year,
        calendar_month=now.month,
        using_calendar=True
    )
    
    keyboard = generate_calendar_keyboard(
        year=now.year,
        month=now.month,
        config=config,
        master_id=data.get('master_id'),
        mode="booking"
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

    if not db_manager.check_slot_availability(data.get('booking_date'), booking_time, master_id=data.get('master_id')):
        await callback.answer("Это время занято. Выберите другое.", show_alert=True)
        return

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


# ... (the rest of the file remains the same)
