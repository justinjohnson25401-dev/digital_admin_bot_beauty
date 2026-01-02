from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import calendar

# Константы для локализации
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
    mode: str = "booking",  # "booking", "admin_view", "date_range"
    range_start: datetime.date = None,  # Начало выбранного диапазона
    range_end: datetime.date = None     # Конец выбранного диапазона
) -> InlineKeyboardMarkup:
    """
    Генерирует календарь с поддержкой выбора одной даты или диапазона.
    
    mode:
    - "booking": обычный выбор даты для записи клиента
    - "admin_view": админ может выбирать любые даты
    - "date_range": выбор диапазона дат (start -> end)
    """
    
    # Установка дефолтных ограничений
    if min_date is None:
        min_date = datetime.now().date() if mode == "booking" else datetime(2020, 1, 1).date()
    if max_date is None:
        max_date = (datetime.now() + timedelta(days=60)).date() if mode == "booking" else datetime(2030, 12, 31).date()
    
    buttons = []
    
    # Строка 1: Заголовок
    header_text = f"📅 {MONTHS_RU[month]} {year}"
    if mode == "date_range" and range_start:
        if range_end:
            header_text = f"📅 {range_start.strftime('%d.%m')} — {range_end.strftime('%d.%m')}"
        else:
            header_text = f"📅 С {range_start.strftime('%d.%m.%Y')}"
    
    buttons.append([InlineKeyboardButton(text=header_text, callback_data="ignore")])
    
    # Строка 2: Дни недели
    week_days = [InlineKeyboardButton(text=day, callback_data="ignore") 
                 for day in ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']]
    buttons.append(week_days)
    
    # Получаем календарь месяца
    cal = calendar.monthcalendar(year, month)
    
    # Импорт функции проверки закрытых дат (только для режима booking)
    if mode == "booking":
        from handlers.booking import is_date_closed_for_master
    
    # Строки с датами
    for week in cal:
        week_buttons = []
        for day in week:
            if day == 0:
                # Пустая клетка
                week_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date_obj = datetime(year, month, day).date()
                date_str = date_obj.isoformat()
                
                # Определяем доступность и отображение даты
                is_available = True
                display_text = str(day)
                
                # Проверка 1: Дата в допустимом диапазоне
                if not (min_date <= date_obj <= max_date):
                    is_available = False
                    display_text = "•"
                
                # Проверка 2: Дата закрыта для мастера (только в режиме booking)
                elif mode == "booking" and config and master_id:
                    is_closed, reason = is_date_closed_for_master(config, master_id, date_obj)
                    if is_closed:
                        is_available = False
                        display_text = "🚫"
                
                # Проверка 3: Выделение диапазона (режим date_range)
                if mode == "date_range" and is_available:
                    if range_start and date_obj == range_start:
                        display_text = f"🔵 {day}"  # Начало диапазона
                    elif range_end and date_obj == range_end:
                        display_text = f"🔵 {day}"  # Конец диапазона
                    elif range_start and range_end and range_start < date_obj < range_end:
                        display_text = f"🟦 {day}"  # Внутри диапазона
                
                # Проверка 4: Сегодня
                if date_obj == datetime.now().date() and is_available and display_text == str(day):
                    display_text = f"• {day} •"
                
                # Создаём кнопку
                if mode == "date_range":
                    callback_data = f"range_date:{date_str}" if is_available else "cal_closed"
                else:
                    callback_data = f"cal_date:{date_str}" if is_available else "cal_closed"
                
                if not is_available and display_text == "•":
                    callback_data = "ignore"

                week_buttons.append(InlineKeyboardButton(text=display_text, callback_data=callback_data))
        
        buttons.append(week_buttons)
    
    # Последняя строка: Навигация
    nav_buttons = []
    
    # Кнопка "Предыдущий месяц"
    prev_month_date = (datetime(year, month, 1) - timedelta(days=1)).date()
    if prev_month_date.replace(day=1) >= min_date.replace(day=1):
        nav_buttons.append(InlineKeyboardButton(text="◀️ Пред.", callback_data="cal_prev_month"))
    else:
        nav_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
    
    # Кнопка "Отмена" или "Применить"
    if mode == "date_range" and range_start and range_end:
        nav_buttons.append(InlineKeyboardButton(text="✅ Применить", callback_data="apply_date_range"))
    else:
        nav_buttons.append(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_calendar"))
    
    # Кнопка "Следующий месяц"
    # Вычисляем первый день следующего месяца
    next_month_date = (datetime(year, month, 28) + timedelta(days=4)).date().replace(day=1)
    if next_month_date <= max_date:
        nav_buttons.append(InlineKeyboardButton(text="След. ▶️", callback_data="cal_next_month"))
    else:
        nav_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore"))

    buttons.append(nav_buttons)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
