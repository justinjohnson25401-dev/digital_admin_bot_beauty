"""
Обработчики нижней Reply-клавиатуры.
"""

from . import main_nav
from . import orders_section
from . import services_section
from . import staff_section
from . import settings_section
from . import clients_section


def register_handlers(dp):
    """Регистрация всех обработчиков нижней клавиатуры"""
    main_nav.register_handlers(dp)
    orders_section.register_handlers(dp)
    services_section.register_handlers(dp)
    staff_section.register_handlers(dp)
    settings_section.register_handlers(dp)
    clients_section.register_handlers(dp)
