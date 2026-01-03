"""
Package for all admin handlers.
Содержит редакторы для админ-панели.
"""

from . import (
    staff,
    services_editor,
    settings_editor,
    business_settings,
    texts_editor,
    notifications_editor,
    promotions_editor,
)

__all__ = [
    'staff',
    'services_editor',
    'settings_editor',
    'business_settings',
    'texts_editor',
    'notifications_editor',
    'promotions_editor',
]
