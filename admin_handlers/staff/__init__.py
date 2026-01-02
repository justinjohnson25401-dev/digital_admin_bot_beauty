"""
Модуль управления персоналом.
"""

from aiogram import Router

# Порядок важен для правильной работы FSM
from . import menu, add, edit, delete, schedule, closed_dates

router = Router()

# Регистрируем все роутеры из текущего пакета
router.include_router(menu.router)
router.include_router(add.router)
router.include_router(edit.router)
router.include_router(delete.router)
router.include_router(schedule.router)
router.include_router(closed_dates.router)
