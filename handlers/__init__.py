"""
Собирает все роутеры проекта для подключения в main.py.
"""

from aiogram import Router

# Импортируем роутеры из всех модулей
from .start import router as start_router
from .mybookings import mybookings_router
from .booking import all_booking_routers # Теперь импортируем единый роутер бронирования

# Главный роутер, который будет подключен к диспетчеру
all_routers = Router()

all_routers.include_router(start_router)
all_routers.include_router(mybookings_router)
all_routers.include_router(all_booking_routers)
