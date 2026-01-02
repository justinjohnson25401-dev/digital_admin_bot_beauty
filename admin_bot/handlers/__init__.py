"""
Обработчики команд и callback-запросов админ-бота.
"""

from . import start
from . import orders
from . import clients
from . import services
from . import stats
from . import common
from .menu import register_handlers as register_menu_handlers


def setup_handlers(dp, pin_middleware):
    """
    Регистрирует все обработчики в dispatcher.

    Args:
        dp: Dispatcher
        pin_middleware: AdminPinMiddleware для передачи в handlers
    """
    # Сначала регистрируем reply keyboard handlers (имеют приоритет)
    register_menu_handlers(dp)

    # Затем остальные handlers
    start.register_handlers(dp, pin_middleware)
    orders.register_handlers(dp)
    clients.register_handlers(dp)
    services.register_handlers(dp)
    stats.register_handlers(dp)
    common.register_handlers(dp)
