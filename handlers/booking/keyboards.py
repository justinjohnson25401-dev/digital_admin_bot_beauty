"""
Функции для создания клавиатур в процессе бронирования и главного меню.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from calendar import monthcalendar
from datetime import date

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создание главной клавиатуры с навигацией"""
    buttons = [
        [
            KeyboardButton(text="📅 Записаться"),
            KeyboardButton(text="📋 Мои записи")
        ],
        [
            KeyboardButton(text="💅 Услуги и цены"),
            KeyboardButton(text="👩‍🎨 Мастера")
        ],
        [
            KeyboardButton(text="🎁 Акции"),
            KeyboardButton(text="ℹ️ О нас")
        ],
        [
            KeyboardButton(text="❓ FAQ"),
            KeyboardButton(text="◀️ Назад"),
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

def get_info_keyboard(add_booking_button: bool = True) -> InlineKeyboardMarkup:
    """Создает стандартную inline-клавиатуру для информационных разделов."""
    buttons = []
    if add_booking_button:
        buttons.append([InlineKeyboardButton(text="📅 Записаться", callback_data="start_booking")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_categories_keyboard(categories: list) -> InlineKeyboardMarkup:
    """Creates a keyboard with service categories."""
    buttons = []
    for category in categories:
        buttons.append([InlineKeyboardButton(text=category, callback_data=f"cat:{category}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_services_keyboard(services: list, category_name: str = None) -> InlineKeyboardMarkup:
    """Creates a keyboard with services."""
    buttons = []
    for service in services:
        button_text = f"{service['name']} - {service['price']}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"srv:{service['id']}")])
    # Add a back button if inside a category
    if category_name:
        buttons.append([InlineKeyboardButton(text="◀️ Назад к категориям", callback_data="back_to_categories")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_masters_keyboard(masters: list) -> InlineKeyboardMarkup:
    """Creates a keyboard for selecting a master."""
    buttons = []
    for master in masters:
        buttons.append([InlineKeyboardButton(text=master['name'], callback_data=f"master:{master['id']}")])
    buttons.append([InlineKeyboardButton(text="Любой свободный мастер", callback_data="master:any")])
    # Add a back button to go back to service selection
    buttons.append([InlineKeyboardButton(text="◀️ Назад к услугам", callback_data="back_to_services")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_calendar_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    """Creates a calendar keyboard for a given month and year."""
    buttons = []
    # Month and year header
    header = date(year, month, 1).strftime('%B %Y')
    buttons.append([InlineKeyboardButton(text=header, callback_data="calendar:ignore:0:0:0")])
    # Day of the week headers
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    buttons.append([InlineKeyboardButton(text=day, callback_data="calendar:ignore:0:0:0") for day in week_days])

    # Calendar days
    month_cal = monthcalendar(year, month)
    for week in month_cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="calendar:ignore:0:0:0"))
            else:
                row.append(InlineKeyboardButton(text=str(day), callback_data=f"calendar:select-day:{year}:{month}:{day}"))
        buttons.append(row)

    # Navigation buttons
    nav_row = [
        InlineKeyboardButton(text="<", callback_data=f"calendar:prev-month:{year}:{month}:1"),
        InlineKeyboardButton(text=">", callback_data=f"calendar:next-month:{year}:{month}:1")
    ]
    buttons.append(nav_row)
    
    # Back button
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_master_choice")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_time_slots_keyboard(slots: list) -> InlineKeyboardMarkup:
    """Creates a keyboard with available time slots."""
    buttons = []
    row = []
    for slot in slots:
        row.append(InlineKeyboardButton(text=slot, callback_data=f"time:{slot}"))
        if len(row) == 4: # Adjust number of columns here
            buttons.append(row)
            row = []
    if row: # Add the last row if it's not full
        buttons.append(row)
        
    # Back button
    buttons.append([InlineKeyboardButton(text="◀️ Назад к выбору даты", callback_data="back_to_date_choice")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
