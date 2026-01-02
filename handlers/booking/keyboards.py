"""
Все клавиатуры для процесса бронирования.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime, timedelta
import logging

from utils.calendar import generate_calendar_keyboard

logger = logging.getLogger(__name__)

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены FSM."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отменить")]],
        resize_keyboard=True
    )

def get_phone_input_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для запроса номера телефона."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер", request_contact=True)],
            [KeyboardButton(text="✏️ Ввести вручную")],
            [KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True
    )

def get_comment_choice_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора - добавить комментарий или пропустить."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Добавить", callback_data="add_comment"),
            InlineKeyboardButton(text="➡️ Пропустить", callback_data="skip_comment")
        ]
    ])

def get_categories_keyboard(categories: list) -> InlineKeyboardMarkup:
    """Клавиатура для выбора категории услуг."""
    buttons = [[InlineKeyboardButton(text=f"📂 {cat}", callback_data=f"cat:{cat}")] for cat in categories]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_services_keyboard(services: list, category_name: str = None) -> InlineKeyboardMarkup:
    """Клавиатура для выбора услуги."""
    buttons = []
    for svc in services:
        dur_text = f" • {svc.get('duration', 0)}мин" if svc.get('duration') else ""
        buttons.append([InlineKeyboardButton(text=f"{svc['name']} — {svc['price']}₽{dur_text}", callback_data=f"srv:{svc['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_masters_keyboard(masters: list) -> InlineKeyboardMarkup:
    """Клавиатура для выбора мастера."""
    buttons = [[InlineKeyboardButton(text=f"👤 {m['name']}", callback_data=f"master:{m['id']}")] for m in masters]
    buttons.append([InlineKeyboardButton(text="👥 Любой свободный мастер", callback_data="master:any")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_dates_keyboard(config: dict = None, master_id: str = None) -> InlineKeyboardMarkup:
    """
    Генерирует упрощённую клавиатуру выбора даты:
    - Сегодня
    - Завтра
    - Другой день (календарь)
    """
    from .utils import is_date_closed_for_master  # Local import to avoid circular dependency
    today = datetime.now().date()
    tomorrow = (datetime.now() + timedelta(days=1)).date()
    buttons = []
    
    is_today_closed, _ = is_date_closed_for_master(config, master_id, today) if config else (False, None)
    is_tomorrow_closed, _ = is_date_closed_for_master(config, master_id, tomorrow) if config else (False, None)
    
    if not is_today_closed:
        buttons.append([InlineKeyboardButton(text="📅 Сегодня", callback_data=f"quick_date:{today.isoformat()}")])
    else:
        buttons.append([InlineKeyboardButton(text="🚫 Сегодня (закрыто)", callback_data="date_closed")])
        
    if not is_tomorrow_closed:
        buttons.append([InlineKeyboardButton(text="📅 Завтра", callback_data=f"quick_date:{tomorrow.isoformat()}")])
    else:
        buttons.append([InlineKeyboardButton(text="🚫 Завтра (закрыто)", callback_data="date_closed")])
        
    buttons.append([InlineKeyboardButton(text="📅 Другой день", callback_data="open_calendar")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_time_slots_keyboard(config: dict, db_manager, booking_date: str, master_id: str = None, exclude_order_id: int = None) -> InlineKeyboardMarkup:
    """Генерирует клавиатуру со слотами времени."""
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


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения записи."""
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
    return keyboard
