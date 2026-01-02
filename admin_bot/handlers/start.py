"""
Обработчики команды /start и PIN-авторизации.
"""

import hashlib
import time

from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from admin_bot.states import AdminPinStates
from admin_bot.keyboards import get_admin_reply_keyboard


async def cmd_start(message: Message, config: dict, db_manager):
    """Команда /start для админов"""
    business_name = config.get('business_name', 'Ваш бизнес')
    stats = db_manager.get_stats('today')

    planned_text = f"\n├ Планируемая: {stats.get('planned_revenue', 0)}₽" if stats.get('planned_revenue', 0) > 0 else ""
    text = (
        f"🎯 <b>Админ-панель \"{business_name}\"</b>\n\n"
        f"📅 Сегодня:\n"
        f"├ Заказов: {stats['total_orders']}\n"
        f"├ Выручка: {stats['total_revenue']}₽{planned_text}\n"
        f"└ Новых клиентов: {stats.get('new_clients', 0)}\n\n"
        "Используйте кнопки внизу для навигации."
    )

    await message.answer(text, reply_markup=get_admin_reply_keyboard())


async def cmd_start_with_pin(message: Message, state: FSMContext, config: dict, pin_middleware, db_manager):
    """Команда /start с проверкой PIN"""
    pin_hash = config.get('admin_pin_hash')
    if isinstance(pin_hash, str) and pin_hash.strip() and message.from_user.id not in pin_middleware.authorized_user_ids:
        await state.set_state(AdminPinStates.waiting_pin)
        await message.answer("🔐 Введите PIN для доступа к админ-панели:")
        return

    await cmd_start(message, config, db_manager)


async def process_pin(message: Message, state: FSMContext, config: dict, pin_middleware, db_manager):
    """Обработка ввода PIN"""
    pin_hash = config.get('admin_pin_hash')
    if not (isinstance(pin_hash, str) and pin_hash.strip()):
        await state.clear()
        await cmd_start(message, config, db_manager)
        return

    pin = (message.text or "").strip()
    digest = hashlib.sha256(pin.encode('utf-8')).hexdigest()

    user_id = message.from_user.id

    is_owner_admin = user_id in getattr(pin_middleware, 'admin_ids', set())

    if not is_owner_admin:
        now = time.time()
        global_info = pin_middleware.global_attempts.get(user_id) or {'count': 0, 'window_start': now}
        if now - global_info.get('window_start', 0) > 3600:
            global_info = {'count': 1, 'window_start': now}
        else:
            global_info['count'] = global_info.get('count', 0) + 1
        pin_middleware.global_attempts[user_id] = global_info

    fail_info = pin_middleware.failures.get(user_id) or {'count': 0, 'lock_until': 0}

    if digest == pin_hash:
        pin_middleware.authorized_user_ids.add(user_id)
        pin_middleware.failures.pop(user_id, None)
        await state.clear()
        await message.answer("✅ PIN принят")
        await cmd_start(message, config, db_manager)
        return

    fail_info['count'] = fail_info.get('count', 0) + 1
    lock_duration = 0 if is_owner_admin else min(30 * (2 ** (fail_info['count'] - 1)), 300)
    fail_info['lock_until'] = time.time() + lock_duration
    pin_middleware.failures[user_id] = fail_info

    if is_owner_admin:
        await message.answer(
            f"❌ Неверный PIN.\n"
            f"Попытка {fail_info['count']}.\n"
            f"(Для владельца блокировка отключена)"
        )
    else:
        await message.answer(
            f"❌ Неверный PIN.\n"
            f"Попытка {fail_info['count']}.\n"
            f"Блокировка на {lock_duration} сек."
        )


def register_handlers(dp, pin_middleware):
    """Регистрация обработчиков start и PIN"""
    dp.message.register(cmd_start_with_pin, Command("start"))
    dp.message.register(process_pin, AdminPinStates.waiting_pin)
