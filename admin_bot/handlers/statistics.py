from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from utils.calendar import generate_calendar_keyboard
from datetime import datetime
from states.admin import AdminStatsState

router = Router()

@router.message(F.text == "📊 Статистика за период")
async def admin_request_stats_period(message: Message, state: FSMContext):
    """Админ запрашивает статистику за период"""
    now = datetime.now()
    
    await state.update_data(
        calendar_year=now.year,
        calendar_month=now.month,
        range_start_date=None,
        range_end_date=None
    )
    
    keyboard = generate_calendar_keyboard(
        year=now.year,
        month=now.month,
        mode="date_range"
    )
    
    await message.answer(
        "📅 Выберите начальную дату периода:",
        reply_markup=keyboard
    )
    await state.set_state(AdminStatsState.selecting_range_start)


@router.callback_query(AdminStatsState.selecting_range_start, F.data.startswith("range_date:"))
async def select_range_start(callback: CallbackQuery, state: FSMContext):
    """Выбор начальной даты диапазона"""
    date_str = callback.data.split(":", 1)[1]
    
    try:
        start_date = datetime.fromisoformat(date_str).date()
    except Exception:
        await callback.answer("❌ Некорректная дата", show_alert=True)
        return
    
    data = await state.get_data()
    
    # Сохраняем начальную дату
    await state.update_data(range_start_date=date_str)
    
    # Обновляем календарь с выделенной начальной датой
    keyboard = generate_calendar_keyboard(
        year=data.get('calendar_year'),
        month=data.get('calendar_month'),
        mode="date_range",
        range_start=start_date
    )
    
    await callback.message.edit_text(
        f"📅 Начало: {start_date.strftime('%d.%m.%Y')}\n\nВыберите конечную дату:",
        reply_markup=keyboard
    )
    await state.set_state(AdminStatsState.selecting_range_end)
    await callback.answer()


@router.callback_query(AdminStatsState.selecting_range_end, F.data.startswith("range_date:"))
async def select_range_end(callback: CallbackQuery, state: FSMContext):
    """Выбор конечной даты диапазона"""
    date_str = callback.data.split(":", 1)[1]
    
    try:
        end_date = datetime.fromisoformat(date_str).date()
    except Exception:
        await callback.answer("❌ Некорректная дата", show_alert=True)
        return
    
    data = await state.get_data()
    start_date = datetime.fromisoformat(data.get('range_start_date')).date()
    
    # Проверка: конечная дата не раньше начальной
    if end_date < start_date:
        await callback.answer("❌ Конечная дата не может быть раньше начальной", show_alert=True)
        return
    
    # Сохраняем конечную дату
    await state.update_data(range_end_date=date_str)
    
    # Показываем календарь с полным диапазоном и кнопкой "Применить"
    keyboard = generate_calendar_keyboard(
        year=data.get('calendar_year'),
        month=data.get('calendar_month'),
        mode="date_range",
        range_start=start_date,
        range_end=end_date
    )
    
    await callback.message.edit_text(
        f"📅 Период: {start_date.strftime('%d.%m.%Y')} — {end_date.strftime('%d.%m.%Y')}\n\n"
        f"Нажмите ✅ Применить",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(AdminStatsState.selecting_range_end, F.data == "apply_date_range")
async def apply_date_range(callback: CallbackQuery, state: FSMContext, db_manager):
    """Применить выбранный диапазон и показать статистику"""
    data = await state.get_data()
    
    start_date_str = data.get('range_start_date')
    end_date_str = data.get('range_end_date')
    
    if not start_date_str or not end_date_str:
        await callback.answer("❌ Выберите обе даты", show_alert=True)
        return
    
    start_date = datetime.fromisoformat(start_date_str).date()
    end_date = datetime.fromisoformat(end_date_str).date()
    
    # Получаем статистику из БД
    stats = db_manager.get_statistics_by_period(start_date_str, end_date_str)
    
    # Формируем текст статистики
    stats_text = f"📊 Статистика за период\n"
    stats_text += f"📅 {start_date.strftime('%d.%m.%Y')} — {end_date.strftime('%d.%m.%Y')}\n\n"
    stats_text += f"📝 Записей: {stats.get('total_bookings', 0)}\n"
    stats_text += f"✅ Завершено: {stats.get('completed', 0)}\n"
    stats_text += f"❌ Отменено: {stats.get('cancelled', 0)}\n"
    stats_text += f"💰 Выручка: {stats.get('revenue', 0)}₽"
    
    await callback.message.edit_text(stats_text)
    await state.clear()
    await callback.answer()


# Обработчики навигации по месяцам (для обоих состояний)
@router.callback_query(
    F.data.in_(["cal_prev_month", "cal_next_month"]),
    AdminStatsState.selecting_range_start | AdminStatsState.selecting_range_end
)
async def navigate_calendar_month(callback: CallbackQuery, state: FSMContext):
    """Навигация по месяцам в календаре диапазона"""
    data = await state.get_data()
    year = data.get('calendar_year')
    month = data.get('calendar_month')
    
    if callback.data == "cal_prev_month":
        month -= 1
        if month < 1:
            month = 12
            year -= 1
    else:
        month += 1
        if month > 12:
            month = 1
            year += 1
    
    await state.update_data(calendar_year=year, calendar_month=month)
    
    # Определяем текущее состояние
    current_state = await state.get_state()
    
    range_start = None
    range_end = None
    
    if data.get('range_start_date'):
        range_start = datetime.fromisoformat(data.get('range_start_date')).date()
    
    if current_state == AdminStatsState.selecting_range_end and data.get('range_end_date'):
        range_end = datetime.fromisoformat(data.get('range_end_date')).date()
    
    keyboard = generate_calendar_keyboard(
        year=year,
        month=month,
        mode="date_range",
        range_start=range_start,
        range_end=range_end
    )
    
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()
