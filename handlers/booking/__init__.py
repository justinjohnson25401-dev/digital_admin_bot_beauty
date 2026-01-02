"""
Объединение роутеров для процесса бронирования.
"""

from aiogram import Router

from . import start, master, date, time, contact, confirmation, save

booking_router = Router()

booking_router.include_router(start.router)
booking_router.include_router(master.router)
booking_router.include_router(date.router)
booking_router.include_router(time.router)
booking_router.include_router(contact.router)
booking_router.include_router(confirmation.router)
booking_router.include_router(save.router)
