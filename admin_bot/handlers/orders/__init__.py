"""
Обработчики заказов.
"""

from . import list_view
from . import detail
from . import date_range


def register_handlers(dp):
    """Регистрация всех обработчиков заказов"""
    list_view.register_handlers(dp)
    detail.register_handlers(dp)
    date_range.register_handlers(dp)
