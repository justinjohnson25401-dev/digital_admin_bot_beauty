"""
Все клавиатуры для модуля staff.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def _build_masters_list_keyboard(masters: list, action: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком мастеров для различных действий.

    :param masters: Список мастеров.
    :param action: Действие (например, "edit_master", "delete_master").
    :return: Клавиатура со списком мастеров.
    """
    keyboard_rows = []
    for master in masters:
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"👤 {master['name']} — {master.get('specialization') or master.get('role', 'Мастер')}",
                callback_data=f"{action}_{master['id']}"
            )
        ])
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="staff_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

def _build_services_keyboard(services: list, selected_services: list) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора услуг.

    :param services: Список всех услуг.
    :param selected_services: Список ID выбранных услуг.
    :return: Клавиатура для выбора услуг.
    """
    keyboard_rows = []
    for service in services:
        is_selected = service['id'] in selected_services
        mark = "☑" if is_selected else "☐"
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"{mark} {service['name']} ({service['price']}₽)",
                callback_data=f"select_service_{service['id']}"
            )
        ])
    keyboard_rows.append([InlineKeyboardButton(text="✅ Продолжить", callback_data="services_done")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

def _build_days_keyboard(selected_days: list) -> InlineKeyboardMarkup:
    """Построить клавиатуру с мультиселектом дней недели"""
    days = [
        ('monday', 'Понедельник'),
        ('tuesday', 'Вторник'),
        ('wednesday', 'Среда'),
        ('thursday', 'Четверг'),
        ('friday', 'Пятница'),
        ('saturday', 'Суббота'),
        ('sunday', 'Воскресенье'),
    ]

    keyboard_rows = []
    for day_id, day_name in days:
        is_selected = day_id in selected_days
        mark = "☑" if is_selected else "☐"
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"{mark} {day_name}",
                callback_data=f"toggle_day_{day_id}"
            )
        ])

    keyboard_rows.append([InlineKeyboardButton(text="✅ Продолжить", callback_data="days_done")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

def _build_hours_keyboard(business_start: int, business_end: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора часов работы.

    :param business_start: Начало рабочего дня компании.
    :param business_end: Конец рабочего дня компании.
    :return: Клавиатура для выбора часов работы.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐ По графику бизнеса ({business_start:02d}:00 - {business_end:02d}:00)", callback_data=f"hours_{business_start:02d}_{business_end:02d}")],
        [InlineKeyboardButton(text="🕘 09:00 - 18:00", callback_data="hours_09_18")],
        [InlineKeyboardButton(text="🕙 10:00 - 19:00", callback_data="hours_10_19")],
        [InlineKeyboardButton(text="🕙 10:00 - 20:00", callback_data="hours_10_20")],
        [InlineKeyboardButton(text="🕛 12:00 - 21:00", callback_data="hours_12_21")],
        [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="hours_custom")],
    ])

def _build_master_edit_keyboard(master_id: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для меню редактирования мастера.

    :param master_id: ID мастера.
    :return: Клавиатура для редактирования мастера.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить имя", callback_data=f"edit_master_name_{master_id}")],
        [InlineKeyboardButton(text="✏️ Изменить должность", callback_data=f"edit_master_role_{master_id}")],
        [InlineKeyboardButton(text="📋 Изменить услуги", callback_data=f"edit_master_services_{master_id}")],
        [InlineKeyboardButton(text="📅 Изменить график", callback_data=f"edit_master_schedule_{master_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="edit_master_list")],
    ])

def _build_closed_dates_keyboard(master_id: str, closed_dates: list) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для меню закрытых дат.

    :param master_id: ID мастера.
    :param closed_dates: Список закрытых дат.
    :return: Клавиатура для управления закрытыми датами.
    """
    keyboard_rows = []
    for cd in closed_dates:
        date_obj = datetime.strptime(cd['date'], '%Y-%m-%d').date()
        date_display = date_obj.strftime('%d.%m.%Y')
        reason = cd.get('reason', '')
        btn_text = f"🗑 {date_display}" + (f" ({reason})" if reason else "")
        keyboard_rows.append([
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f"remove_closed_{master_id}_{cd['date']}"
            )
        ])

    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"closed_dates_{master_id}")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)