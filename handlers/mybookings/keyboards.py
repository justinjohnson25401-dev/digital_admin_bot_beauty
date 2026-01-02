
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

def _get_master_name(config: dict, master_id: str) -> str:
    """Получить имя мастера по ID из конфига"""
    if not master_id or not config:
        return None
    staff = config.get('staff', {})
    if not staff.get('enabled', False):
        return None
    for master in staff.get('masters', []):
        if master.get('id') == master_id:
            return master.get('name')
    return None

def format_time(time_str: str) -> str:
    """Форматирует время из 'HH:MM' в 'HH:MM'"""
    if not time_str:
        return ''
    try:
        return datetime.strptime(time_str, '%H:%M').strftime('%H:%M')
    except ValueError:
        return time_str # Возвращаем как есть, если формат некорректный


def format_bookings_list(bookings: list, config: dict = None) -> tuple[str, InlineKeyboardMarkup]:
    """Форматирование списка записей и клавиатуры с отображением мастера"""
    text = "📋 <b>ВАШИ ЗАПИСИ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    if not bookings:
        return "У вас пока нет активных записей.", None

    buttons = []
    for booking in bookings:
        booking_date = booking['booking_date']
        booking_time = booking['booking_time']

        try:
            date_obj = datetime.fromisoformat(booking_date)
            date_formatted = date_obj.strftime('%d.%m.%Y')
        except (ValueError, TypeError):
            date_formatted = "не указана"

        time_formatted = format_time(booking_time)
        master_name = _get_master_name(config, booking.get('master_id'))

        text += f"┌ <b>{booking['service_name']}</b>\n"
        text += f"│\n"
        text += f"│ 📅  <b>{date_formatted}</b> в <b>{time_formatted}</b>\n"
        if master_name:
            text += f"│ 👤  Мастер: {master_name}\n"
        text += f"│ 💰  {booking['price']}₽\n"
        text += f"│\n"
        text += f"└ <i>Запись #{booking['id']}</i>\n\n"

        buttons.append([InlineKeyboardButton(text=f"✏️ Изменить запись #{booking['id']}", callback_data=f"edit_booking:{booking['id']}")])
        buttons.append([InlineKeyboardButton(text=f"🗑 Отменить запись #{booking['id']}", callback_data=f"cancel_order:{booking['id']}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return text, keyboard

def get_cancel_confirmation_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения отмены записи."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"confirm_cancel:{order_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data="back_to_mybookings")
        ]
    ])

def get_edit_menu_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для меню редактирования записи."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Изменить дату и время", callback_data=f"edit_datetime:{order_id}")],
        [InlineKeyboardButton(text="🔄 Изменить услугу", callback_data=f"edit_service_existing:{order_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_mybookings")],
    ])

def get_reschedule_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения переноса записи."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить изменения", callback_data="confirm_edit")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="back_to_mybookings")]
    ])

def get_edit_service_keyboard(services: list, order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для выбора новой услуги при редактировании."""
    buttons = []
    for service in services:
        button_text = f"{service['name']} — {service['price']}₽"
        callback_data = f"new_service:{service['id']}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"edit_booking:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
