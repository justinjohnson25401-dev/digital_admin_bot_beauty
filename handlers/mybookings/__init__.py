
from aiogram import Router

from . import view, cancel, reschedule

# Главный роутер для раздела "Мои записи"
mybookings_router = Router(name="mybookings")

# Подключаем роутеры из подмодулей
mybookings_router.include_routers(
    view.router,
    cancel.router,
    reschedule.router,
)

# Alias для совместимости
router = mybookings_router
