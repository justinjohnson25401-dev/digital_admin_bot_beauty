"""
Собирает все роутеры из модуля booking в один.
"""

from aiogram import Router

# Импортируем роутеры из всех частей процесса бронирования
from .router_nav import router as nav_router
from .category import router as category_router
from .service import router as service_router
from .master import router as master_router
from .date import router as date_router
from .time import router as time_router
from .contact import router as contact_router
from .confirmation import router as confirmation_router

# Собираем все роутеры в один, чтобы подключить в главном __init__.py
all_booking_routers = Router()

all_booking_routers.include_router(nav_router)
all_booking_routers.include_router(category_router)
all_booking_routers.include_router(service_router)
all_booking_routers.include_router(master_router)
all_booking_routers.include_router(date_router)
all_booking_routers.include_router(time_router)
all_booking_routers.include_router(contact_router)
all_booking_routers.include_router(confirmation_router)
