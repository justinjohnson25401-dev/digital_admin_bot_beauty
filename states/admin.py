from aiogram.fsm.state import State, StatesGroup

class AdminStatsState(StatesGroup):
    """Состояния для статистики и отчётов"""
    choosing_stats_period = State()
    selecting_range_start = State()
    selecting_range_end = State()
