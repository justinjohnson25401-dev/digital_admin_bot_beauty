"""
Middleware для аутентификации и авторизации админов.
"""

import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.fsm.context import FSMContext

from admin_bot.states import AdminPinStates


class AdminAuthMiddleware(BaseMiddleware):
    """Middleware для проверки прав админа"""

    def __init__(self, config: dict):
        super().__init__()
        self.admin_ids = config.get('admin_ids', [])

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if hasattr(event, 'from_user'):
            if event.from_user.id not in self.admin_ids:
                if hasattr(event, 'answer'):
                    await event.answer("❌ Доступ запрещён")
                return

        return await handler(event, data)


class AdminPinMiddleware(BaseMiddleware):
    """Middleware для PIN-авторизации админов"""

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.admin_ids = set(config.get('admin_ids', []) or [])
        self.authorized_user_ids = set()
        self.failures = {}
        self.global_attempts = {}
        self.max_attempts_per_hour = 10

    def _pin_enabled(self) -> bool:
        pin_hash = self.config.get('admin_pin_hash')
        return bool(isinstance(pin_hash, str) and pin_hash.strip())

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not self._pin_enabled():
            return await handler(event, data)

        if not hasattr(event, 'from_user'):
            return await handler(event, data)

        user_id = event.from_user.id

        state: FSMContext | None = data.get('state')
        if state is not None:
            try:
                current_state = await state.get_state()
            except Exception:
                current_state = None
            if current_state == AdminPinStates.waiting_pin.state:
                return await handler(event, data)

        if user_id in self.authorized_user_ids:
            return await handler(event, data)

        if user_id not in self.admin_ids:
            now = time.time()
            global_info = self.global_attempts.get(user_id)
            if global_info:
                window_start = global_info.get('window_start', 0)
                if now - window_start > 3600:
                    self.global_attempts[user_id] = {'count': 0, 'window_start': now}
                elif global_info.get('count', 0) >= self.max_attempts_per_hour:
                    if hasattr(event, 'answer'):
                        await event.answer("❌ Превышен лимит попыток ввода PIN. Повторите позже.")
                    return

            fail_info = self.failures.get(user_id)
            if fail_info and fail_info.get('lock_until', 0) > now:
                remaining = int(fail_info['lock_until'] - now)
                if hasattr(event, 'answer'):
                    await event.answer(f"🔒 Доступ временно заблокирован. Подождите {remaining} сек.")
                return

        if hasattr(event, 'answer'):
            await event.answer("🔐 Введите PIN: отправьте /start")
        return
