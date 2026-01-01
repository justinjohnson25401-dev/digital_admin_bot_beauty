from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import calendar

# Константы для локализации
DAYS_RU = {
    'Monday': 'Пн', 'Tuesday': 'Вт', 'Wednesday': 'Ср',
    'Thursday': 'Чт', 'Friday': 'Пт', 'Saturday': 'Сб', 'Sunday': 'Вс'
}

MONTHS_RU = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
    5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
    9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
}


def generate_calendar_keyboard(
    year: int,
    month: int,
    config: dict = None,
    master_id: str = None,
    min_date: datetime.date = None,
    max_date: datetime.date = None,
    mode: str = "booking"
) -> InlineKeyboardMarkup:
    """
    Генерирует универсальный интерактивный календарь.
    """
    
    # Динамический импорт для избежания циклических зависимостей
    from handlers.booking import is_date_closed_for_master

    # Установка дефолтных ограничений
    if min_date is None:
        min_date = datetime.now().date() if mode == "booking" else datetime(2020, 1, 1).date()
    if max_date is None:
        # Увеличим дефолтный диапазон для админа, чтобы он мог смотреть далеко вперед
        max_date = (datetime.now() + timedelta(days=60)).date() if mode == "booking" else datetime(2030, 12, 31).date()
    
    buttons = []
    
    # Строка 1: Заголовок с месяцем и годом
    header = f"📅 {MONTHS_RU[month]} {year}"
    buttons.append([InlineKeyboardButton(text=header, callback_data="ignore")])
    
    # Строка 2: Дни недели
    week_days = [InlineKeyboardButton(text=day, callback_data="ignore") for day in ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']]
    buttons.append(week_days)
    
    # Получаем календарь месяца
    cal = calendar.monthcalendar(year, month)
    
    # Строки с датами
    for week in cal:
        week_buttons = []
        for day in week:
            if day == 0:
                week_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date_obj = datetime(year, month, day).date()
                date_str = date_obj.isoformat()
                
                is_available = True
                display_text = str(day)
                
                # Проверка 1: Дата вне допустимого диапазона
                if not (min_date <= date_obj <= max_date):
                    is_available = False
                    display_text = f"•" # Просто точка для неактивных дат
                
                # Проверка 2: Дата закрыта для мастера (только в режиме booking)
                elif mode == "booking" and config:
                    is_closed, reason = is_date_closed_for_master(config, master_id, date_obj)
                    if is_closed:
                        is_available = False
                        display_text = f"🚫"
                
                # Проверка 3: Выделение сегодняшней даты
                if date_obj == datetime.now().date() and is_available:
                    display_text = f"• {day} •"
                
                callback_data = f"cal_date:{date_str}" if is_available else "cal_closed"
                if not is_available and display_text == "•":
                    callback_data = "ignore" # Не даем нажимать на даты вне диапазона

                week_buttons.append(InlineKeyboardButton(text=display_text, callback_data=callback_data))
        
        buttons.append(week_buttons)
    
    # Последняя строка: Навигация
    nav_buttons = []
    
    # Кнопка "Предыдущий месяц"
    first_day_of_current_month = datetime(year, month, 1).date()
    if first_day_of_current_month > min_date:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Пред.", callback_data="cal_prev_month"))
    else:
        nav_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore")) # Пустышка для верстки
    
    # Кнопка "Отмена"
    nav_buttons.append(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_calendar"))
    
    # Кнопка "Следующий месяц"
    last_day_of_current_month = datetime(year, month, calendar.monthrange(year, month)[1]).date()
    if last_day_of_current_month < max_date:
        nav_buttons.append(InlineKeyboardButton(text="След. ▶️", callback_data="cal_next_month"))
    else:
        nav_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore")) # Пустышка
    
    buttons.append(nav_buttons)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
