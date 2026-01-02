"""
Middleware для передачи конфигурации и менеджеров.
"""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from .auth import AdminPinMiddleware


class ConfigMiddleware(BaseMiddleware):
    """Middleware для передачи config, db_manager и config_manager"""

    def __init__(self, config: dict, db_manager, config_manager):
        super().__init__()
        self.config = config
        self.db_manager = db_manager
        self.config_manager = config_manager

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        data['config'] = self.config
        data['db_manager'] = self.db_manager
        data['config_manager'] = self.config_manager
        return await handler(event, data)


class PinMiddlewareInjector(BaseMiddleware):
    """Middleware для инъекции pin_middleware в data"""

    def __init__(self, pin_middleware: AdminPinMiddleware):
        super().__init__()
        self._pin_middleware = pin_middleware

    async def __call__(self, handler, event, data):
        data['pin_middleware'] = self._pin_middleware
        return await handler(event, data)
