"""
Package for all admin handlers.
"""

from aiogram import Router

from . import staff, base, services, orders

def setup_admin_handlers() -> Router:
    """
    Setup all admin handlers.
    """
    router = Router()

    router.include_router(base.router)
    router.include_router(services.router)
    router.include_router(orders.router)
    router.include_router(staff.router)

    return router
