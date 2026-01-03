"""
Объединение роутеров для процесса бронирования.
"""

from aiogram import Router

from . import master, date, time, contact, confirmation, save

booking_router = Router(name="booking")

booking_router.include_router(master.router)
booking_router.include_router(date.router)
booking_router.include_router(time.router)
booking_router.include_router(contact.router)
booking_router.include_router(confirmation.router)
booking_router.include_router(save.router)

# Alias для совместимости
router = booking_router
all_booking_routers = booking_router
