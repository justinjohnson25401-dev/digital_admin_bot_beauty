#!/usr/bin/env python3
"""
BOT-BUSINESS V2.0 - Админ-панель
Управление заказами, клиентами, статистикой
"""

import argparse
import asyncio
import logging
import os
import sys
import hashlib
import time
from dotenv import load_dotenv
from typing import Any, Awaitable, Callable, Dict

# Загружаем переменные окружения из .env
load_dotenv()

# Добавляем родительскую директорию в путь для импорта utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, TelegramObject, ReplyKeyboardMarkup, KeyboardButton
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from utils.db_manager import DBManager
from utils.config_manager import ConfigManager

# Импортируем admin handlers
from admin_handlers import services_editor, settings_editor
from admin_handlers import business_settings, texts_editor, notifications_editor, staff_editor
from admin_handlers import promotions_editor

# Настройка логирования
import logging.handlers

# Создаём директорию для логов
import os
os.makedirs('logs', exist_ok=True)

# Настраиваем логирование с ротацией
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Вывод в консоль (для journalctl)
        logging.handlers.RotatingFileHandler(
            'logs/admin_bot.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
    ]
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Загрузка конфигурации"""
    import json
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


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
        # Проверяем только для сообщений/callback
        if hasattr(event, 'from_user'):
            if event.from_user.id not in self.admin_ids:
                if hasattr(event, 'answer'):
                    await event.answer("❌ Доступ запрещён")
                return

        return await handler(event, data)


class AdminPinStates(StatesGroup):
    waiting_pin = State()


class AdminOrdersStates(StatesGroup):
    """Состояния для выбора диапазона дат заказов"""
    input_date_from = State()
    input_date_to = State()


class AdminPinMiddleware(BaseMiddleware):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.admin_ids = set(config.get('admin_ids', []) or [])
        self.authorized_user_ids = set()
        self.failures = {}
        self.global_attempts = {}  # {user_id: {'count': N, 'window_start': timestamp}}
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

        # Для админов (владельцев) не применяем блокировки/лимиты,
        # чтобы избежать ситуации самоблокировки.
        if user_id not in self.admin_ids:
            now = time.time()
            # Проверка глобального rate limit (попыток в час)
            global_info = self.global_attempts.get(user_id)
            if global_info:
                window_start = global_info.get('window_start', 0)
                if now - window_start > 3600:  # Окно истекло, сбрасываем
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


def get_admin_reply_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура админ-панели"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Заказы"), KeyboardButton(text="💼 Услуги")],
            [KeyboardButton(text="👤 Персонал"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="👥 Клиенты")],
        ],
        resize_keyboard=True
    )


def get_orders_reply_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура раздела Заказы"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="◀️ Назад")],
            [KeyboardButton(text="📅 Сегодня"), KeyboardButton(text="📅 Завтра")],
            [KeyboardButton(text="📅 Неделя"), KeyboardButton(text="📥 CSV")],
        ],
        resize_keyboard=True
    )


def get_services_reply_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура раздела Услуги (включает Акции)"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="◀️ Назад"), KeyboardButton(text="🎁 Акции")],
            [KeyboardButton(text="📋 Список услуг"), KeyboardButton(text="➕ Добавить")],
        ],
        resize_keyboard=True
    )


def get_staff_reply_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура раздела Персонал"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="◀️ Назад"), KeyboardButton(text="➕ Добавить мастера")],
            [KeyboardButton(text="✏️ Редактировать"), KeyboardButton(text="📅 Закрытые даты")],
        ],
        resize_keyboard=True
    )


def get_settings_reply_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура раздела Настройки (включает Помощь)"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="◀️ Назад"), KeyboardButton(text="❓ Помощь")],
            [KeyboardButton(text="⚙️ Бизнес"), KeyboardButton(text="📝 Тексты")],
            [KeyboardButton(text="🔔 Уведомления")],
        ],
        resize_keyboard=True
    )


def get_clients_reply_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура раздела Клиенты"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="◀️ Назад"), KeyboardButton(text="🔍 Поиск")],
        ],
        resize_keyboard=True
    )


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню админ-панели (компактное)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Заказы", callback_data="admin_orders"),
            InlineKeyboardButton(text="💼 Услуги", callback_data="admin_services")
        ],
        [
            InlineKeyboardButton(text="👤 Персонал", callback_data="staff_menu"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")
        ],
        [
            InlineKeyboardButton(text="👥 Клиенты", callback_data="admin_clients")
        ]
    ])


async def cmd_start(message: Message, config: dict, db_manager):
    """Команда /start для админов"""
    business_name = config.get('business_name', 'Ваш бизнес')

    # Получаем статистику
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

    # Показываем только постоянную клавиатуру (без inline-меню)
    await message.answer(text, reply_markup=get_admin_reply_keyboard())


async def cmd_start_with_pin(message: Message, state: FSMContext, config: dict, pin_middleware: AdminPinMiddleware, db_manager):
    pin_hash = config.get('admin_pin_hash')
    if isinstance(pin_hash, str) and pin_hash.strip() and message.from_user.id not in pin_middleware.authorized_user_ids:
        await state.set_state(AdminPinStates.waiting_pin)
        await message.answer("🔐 Введите PIN для доступа к админ-панели:")
        return

    await cmd_start(message, config, db_manager)


async def process_pin(message: Message, state: FSMContext, config: dict, pin_middleware: AdminPinMiddleware, db_manager):
    pin_hash = config.get('admin_pin_hash')
    if not (isinstance(pin_hash, str) and pin_hash.strip()):
        await state.clear()
        await cmd_start(message, config, db_manager)
        return

    pin = (message.text or "").strip()
    digest = hashlib.sha256(pin.encode('utf-8')).hexdigest()

    user_id = message.from_user.id

    is_owner_admin = user_id in getattr(pin_middleware, 'admin_ids', set())
    
    # Увеличиваем глобальный счётчик (кроме владельцев-админов)
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

    # Для владельцев-админов не повышаем lockout, чтобы не заблокировать себя.
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


class PinMiddlewareInjector(BaseMiddleware):
    def __init__(self, pin_middleware: AdminPinMiddleware):
        super().__init__()
        self._pin_middleware = pin_middleware

    async def __call__(self, handler, event, data):
        data['pin_middleware'] = self._pin_middleware
        return await handler(event, data)


async def admin_stats_handler(callback, config: dict, db_manager):
    """Обработчик статистики"""
    from datetime import datetime
    
    # Получаем статистику за разные периоды
    stats_today = db_manager.get_stats('today')
    stats_week = db_manager.get_stats('week')
    stats_month = db_manager.get_stats('month')

    cursor = db_manager.connection.cursor()

    def get_period_days(period: str) -> int:
        if period == 'today':
            return 0
        if period == 'week':
            return 7
        return 30

    def fetch_daily_breakdown(days: int) -> list:
        if days == 0:
            cursor.execute(
                """
                SELECT booking_date, COUNT(*), COALESCE(SUM(price), 0)
                FROM orders
                WHERE status = 'active' AND booking_date = date('now')
                GROUP BY booking_date
                ORDER BY booking_date
                """
            )
        else:
            cursor.execute(
                """
                SELECT booking_date, COUNT(*), COALESCE(SUM(price), 0)
                FROM orders
                WHERE status = 'active'
                  AND booking_date IS NOT NULL
                  AND booking_date >= date('now', ?)
                GROUP BY booking_date
                ORDER BY booking_date
                """,
                (f"-{days} days",),
            )
        return cursor.fetchall()

    def fetch_top_services_by_day(days: int) -> dict:
        if days == 0:
            cursor.execute(
                """
                SELECT booking_date, service_name, COUNT(*)
                FROM orders
                WHERE status = 'active' AND booking_date = date('now')
                GROUP BY booking_date, service_name
                ORDER BY booking_date, COUNT(*) DESC
                """
            )
        else:
            cursor.execute(
                """
                SELECT booking_date, service_name, COUNT(*)
                FROM orders
                WHERE status = 'active'
                  AND booking_date IS NOT NULL
                  AND booking_date >= date('now', ?)
                GROUP BY booking_date, service_name
                ORDER BY booking_date, COUNT(*) DESC
                """,
                (f"-{days} days",),
            )

        result = {}
        for booking_date, service_name, count in cursor.fetchall():
            result.setdefault(booking_date, []).append((service_name, count))
        return result

    week_days = get_period_days('week')
    month_days = get_period_days('month')
    breakdown_week = fetch_daily_breakdown(week_days)
    breakdown_month = fetch_daily_breakdown(month_days)
    top_services_week_by_day = fetch_top_services_by_day(week_days)
    top_services_month_by_day = fetch_top_services_by_day(month_days)
    
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"📅 Сегодня ({datetime.now().strftime('%d.%m.%Y')}):\n"
        f"├ Заказов: {stats_today['total_orders']}\n"
        f"└ Выручка: {stats_today['total_revenue']}₽\n\n"
        f"📅 Эта неделя:\n"
        f"├ Заказов: {stats_week['total_orders']}\n"
        f"└ Выручка: {stats_week['total_revenue']}₽\n\n"
        f"📅 Этот месяц:\n"
        f"├ Заказов: {stats_month['total_orders']}\n"
        f"└ Выручка: {stats_month['total_revenue']}₽\n\n"
        f"🏆 Топ услуги (месяц):\n"
    )
    
    for i, (service, count) in enumerate(stats_month['top_services'][:3], 1):
        text += f"{i}. {service} ({count} шт.)\n"

    if breakdown_week:
        text += "\n📅 По дням (неделя):\n"
        for booking_date, cnt, rev in breakdown_week:
            try:
                date_fmt = datetime.fromisoformat(booking_date).strftime('%d.%m.%Y')
            except Exception:
                date_fmt = booking_date
            text += f"• {date_fmt}: {cnt} заказ(ов), {rev}₽\n"
            top_day = top_services_week_by_day.get(booking_date, [])[:3]
            if top_day:
                text += "  └ " + ", ".join([f"{s} ({c})" for s, c in top_day]) + "\n"

    if breakdown_month:
        text += "\n📅 По дням (месяц):\n"
        for booking_date, cnt, rev in breakdown_month:
            try:
                date_fmt = datetime.fromisoformat(booking_date).strftime('%d.%m.%Y')
            except Exception:
                date_fmt = booking_date
            text += f"• {date_fmt}: {cnt} заказ(ов), {rev}₽\n"
            top_day = top_services_month_by_day.get(booking_date, [])[:3]
            if top_day:
                text += "  └ " + ", ".join([f"{s} ({c})" for s, c in top_day]) + "\n"
    
    await callback.message.edit_text(text)
    await callback.answer()


async def admin_client_history_handler(callback, config: dict, db_manager):
    """Полная история клиента с пагинацией"""
    from datetime import datetime
    try:
        _, user_id_str, page_str, return_period, return_page_str, return_order_id_str = callback.data.split(":", 5)
        user_id = int(user_id_str)
        page = int(page_str)
        return_page = int(return_page_str)
        return_order_id = int(return_order_id_str)
    except Exception:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        return

    page_size = 5
    if page < 0:
        page = 0

    history = db_manager.get_user_bookings(user_id, active_only=False)
    total = len(history)
    offset = page * page_size
    items = history[offset: offset + page_size]

    text = f"📚 <b>История клиента</b>\n\nВсего заказов: {total}\n\n"
    if not items:
        text += "Нет данных для отображения."
    else:
        start_n = offset + 1
        end_n = min(offset + len(items), total)
        text += f"Показано: {start_n}-{end_n} из {total}\n\n"
        for b in items:
            bd = b.get('booking_date')
            bt = b.get('booking_time')
            try:
                bd_fmt = datetime.fromisoformat(bd).strftime('%d.%m.%Y') if bd else ""
            except Exception:
                bd_fmt = bd or ""
            comment = b.get('comment')
            comment_text = comment.strip() if isinstance(comment, str) and comment.strip() else "—"
            text += (
                f"#{b.get('id')} — {bd_fmt} {bt or ''}\n"
                f"├ {b.get('service_name')} ({b.get('price')}₽)\n"
                f"└ Комментарий: {comment_text}\n\n"
            )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"admin_client_history:{user_id}:{page-1}:{return_period}:{return_page}:{return_order_id}"
        ))
    if (offset + page_size) < total:
        nav.append(InlineKeyboardButton(
            text="➡️ Далее",
            callback_data=f"admin_client_history:{user_id}:{page+1}:{return_period}:{return_page}:{return_order_id}"
        ))

    keyboard_rows = []
    if nav:
        keyboard_rows.append(nav)
    keyboard_rows.append([
        InlineKeyboardButton(text="🔙 Назад к заказу", callback_data=f"admin_order:{return_order_id}:{return_period}:{return_page}")
    ])
    keyboard_rows.append([
        InlineKeyboardButton(text="🔙 Назад к списку", callback_data=f"admin_orders_page:{return_period}:{return_page}")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def admin_order_detail_handler(callback, config: dict, db_manager):
    """Детальная карточка заказа"""
    from datetime import datetime
    try:
        _, order_id_str, period, page_str = callback.data.split(":", 3)
        order_id = int(order_id_str)
        page = int(page_str)
    except Exception:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        return

    order = db_manager.get_order_by_id(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    user_id = order.get('user_id')
    history = db_manager.get_user_bookings(user_id, active_only=False) if user_id else []
    visits = len(history)

    booking_date = order.get('booking_date')
    try:
        date_fmt = datetime.fromisoformat(booking_date).strftime('%d.%m.%Y') if booking_date else "не указана"
    except Exception:
        date_fmt = booking_date or "не указана"

    time_str = order.get('booking_time') or "не указано"
    comment = order.get('comment')
    comment_text = comment.strip() if isinstance(comment, str) and comment.strip() else "—"

    text = (
        f"🧾 <b>Заказ #{order_id}</b>\n\n"
        f"📅 Дата: {date_fmt}\n"
        f"🕐 Время: {time_str}\n"
        f"💇 Услуга: {order.get('service_name')}\n"
        f"💰 Цена: {order.get('price')}₽\n"
        f"👤 Клиент: {order.get('client_name')}\n"
        f"📞 Телефон: {order.get('phone')}\n"
        f"📝 Комментарий: {comment_text}\n\n"
        f"📚 История клиента: {visits} заказ(ов) всего\n"
    )

    # Показываем последние 5 записей
    if history:
        text += "\nПоследние записи:\n"
        for b in history[:5]:
            bd = b.get('booking_date') or ""
            bt = b.get('booking_time') or ""
            try:
                bd_fmt = datetime.fromisoformat(bd).strftime('%d.%m.%Y') if bd else ""
            except Exception:
                bd_fmt = bd
            text += f"• #{b.get('id')} — {bd_fmt} {bt} — {b.get('service_name')} ({b.get('price')}₽)\n"

    history_btn = None
    if user_id:
        history_btn = InlineKeyboardButton(
            text="📚 История клиента",
            callback_data=f"admin_client_history:{user_id}:0:{period}:{page}:{order_id}"
        )

    keyboard_rows = []
    if history_btn:
        keyboard_rows.append([history_btn])
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Назад к списку", callback_data=f"admin_orders_page:{period}:{page}")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def unknown_message(message: Message):
    await message.answer("Команда не распознана. Нажмите /start для открытия админ-меню.")


async def admin_orders_handler(callback, config: dict, db_manager):
    """Обработчик списка заказов"""
    from datetime import datetime
    
    await _admin_orders_render(callback, db_manager, config, period="today", page=0)


async def admin_orders_tomorrow_handler(callback, config: dict, db_manager):
    await _admin_orders_render(callback, db_manager, config, period="tomorrow", page=0)


async def admin_orders_week_handler(callback, config: dict, db_manager):
    await _admin_orders_render(callback, db_manager, config, period="week", page=0)


async def admin_orders_all_future_handler(callback, config: dict, db_manager):
    await _admin_orders_render(callback, db_manager, config, period="all_future", page=0)


async def admin_orders_page_handler(callback, config: dict, db_manager):
    """Пагинация списка заказов"""
    try:
        _, period, page_str = callback.data.split(":", 2)
        page = int(page_str)
    except Exception:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        return

    if page < 0:
        page = 0

    await _admin_orders_render(callback, db_manager, config, period=period, page=page)


async def _admin_orders_render(callback, db_manager, config: dict, period: str, page: int = 0):
    from datetime import datetime

    def fmt_time(t: str) -> str:
        if not t:
            return "не указано"
        if ":" in t:
            return t
        try:
            return f"{int(t):02d}:00"
        except Exception:
            return t

    cursor = db_manager.connection.cursor()

    tz_offset = config.get('timezone_offset_hours')
    if tz_offset is None:
        tz_modifier = "localtime"
    else:
        try:
            tz_offset_int = int(tz_offset)
        except Exception:
            tz_offset_int = 0
        tz_modifier = f"{tz_offset_int:+d} hours"

    page_size = 5
    offset = page * page_size

    def _count(sql: str, params: tuple) -> int:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return int(row[0] or 0) if row else 0

    if period == "today":
        title = "📋 <b>Заказы на сегодня</b>"
        total = _count(
            """SELECT COUNT(*) FROM orders WHERE status = 'active' AND booking_date = date('now', ?)""",
            (tz_modifier,),
        )
        cursor.execute(
            """
            SELECT id, service_name, booking_date, booking_time, client_name, phone, price
            FROM orders
            WHERE status = 'active' AND booking_date = date('now', ?)
            ORDER BY booking_time
            LIMIT ? OFFSET ?
            """,
            (tz_modifier, page_size, offset)
        )
    elif period == "tomorrow":
        title = "📋 <b>Заказы на завтра</b>"
        total = _count(
            """SELECT COUNT(*) FROM orders WHERE status = 'active' AND booking_date = date('now', ?, '+1 day')""",
            (tz_modifier,),
        )
        cursor.execute(
            """
            SELECT id, service_name, booking_date, booking_time, client_name, phone, price
            FROM orders
            WHERE status = 'active' AND booking_date = date('now', ?, '+1 day')
            ORDER BY booking_time
            LIMIT ? OFFSET ?
            """,
            (tz_modifier, page_size, offset)
        )
    elif period == "week":
        title = "📋 <b>Заказы на неделю</b>"
        total = _count(
            """
            SELECT COUNT(*) FROM orders
            WHERE status = 'active'
              AND booking_date IS NOT NULL
              AND booking_date >= date('now', ?)
              AND booking_date <= date('now', ?, '+7 days')
            """,
            (tz_modifier, tz_modifier),
        )
        cursor.execute(
            """
            SELECT id, service_name, booking_date, booking_time, client_name, phone, price
            FROM orders
            WHERE status = 'active'
              AND booking_date IS NOT NULL
              AND booking_date >= date('now', ?)
              AND booking_date <= date('now', ?, '+7 days')
            ORDER BY booking_date, booking_time
            LIMIT ? OFFSET ?
            """,
            (tz_modifier, tz_modifier, page_size, offset)
        )
    else:
        title = "📋 <b>Все будущие заказы</b>"
        total = _count(
            """
            SELECT COUNT(*) FROM orders
            WHERE status = 'active'
              AND booking_date IS NOT NULL
              AND booking_date >= date('now', ?)
            """,
            (tz_modifier,),
        )
        cursor.execute(
            """
            SELECT id, service_name, booking_date, booking_time, client_name, phone, price
            FROM orders
            WHERE status = 'active'
              AND booking_date IS NOT NULL
              AND booking_date >= date('now', ?)
            ORDER BY booking_date, booking_time
            LIMIT ? OFFSET ?
            """,
            (tz_modifier, page_size, offset)
        )

    orders = cursor.fetchall()

    if not orders:
        text = f"{title}\n\nНет заказов."
    else:
        start_n = offset + 1
        end_n = min(offset + len(orders), total)
        text = f"{title}\n\nПоказано: {start_n}-{end_n} из {total}\n\n"
        for order_id, service, date, time, name, phone, price in orders:
            try:
                date_fmt = datetime.fromisoformat(date).strftime('%d.%m.%Y')
            except Exception:
                date_fmt = date or "не указана"
            text += (
                f"#{order_id} — {date_fmt} {fmt_time(time)}\n"
                f"└ {service} ({price}₽)\n\n"
            )

    keyboard_rows = []

    # Кнопки "Подробнее" по текущей странице
    for row in orders:
        order_id = row[0]
        keyboard_rows.append([
            InlineKeyboardButton(text=f"🔎 Подробнее #{order_id}", callback_data=f"admin_order:{order_id}:{period}:{page}")
        ])

    # Пагинация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_orders_page:{period}:{page-1}"))
    if (offset + page_size) < total:
        nav.append(InlineKeyboardButton(text="➡️ Далее", callback_data=f"admin_orders_page:{period}:{page+1}"))
    if nav:
        keyboard_rows.append(nav)

    # Переключение периодов
    keyboard_rows.extend([
        [
            InlineKeyboardButton(text="📅 Сегодня", callback_data="admin_orders"),
            InlineKeyboardButton(text="📅 Завтра", callback_data="admin_orders_tomorrow"),
        ],
        [
            InlineKeyboardButton(text="📅 Эта неделя", callback_data="admin_orders_week"),
            InlineKeyboardButton(text="📆 Все будущие", callback_data="admin_orders_all_future"),
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data=f"admin_stats_period:{period}"),
            InlineKeyboardButton(text="📥 CSV", callback_data="admin_export_csv"),
        ],
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def admin_stats_period_handler(callback, config: dict, db_manager):
    """Статистика за выбранный период"""
    from datetime import datetime, timedelta

    try:
        _, period = callback.data.split(":", 1)
    except ValueError:
        period = "today"

    # Определяем период и заголовок
    if period == "today":
        title = f"📊 Статистика за сегодня ({datetime.now().strftime('%d.%m.%Y')})"
        start_date = datetime.now().date().isoformat()
        end_date = start_date
    elif period == "tomorrow":
        tomorrow = datetime.now().date() + timedelta(days=1)
        title = f"📊 Статистика на завтра ({tomorrow.strftime('%d.%m.%Y')})"
        start_date = tomorrow.isoformat()
        end_date = start_date
    elif period == "week":
        today = datetime.now().date()
        week_end = today + timedelta(days=7)
        title = f"📊 Статистика за неделю ({today.strftime('%d.%m')} - {week_end.strftime('%d.%m.%Y')})"
        start_date = today.isoformat()
        end_date = week_end.isoformat()
    else:  # all_future
        title = "📊 Статистика (все будущие заказы)"
        start_date = datetime.now().date().isoformat()
        end_date = (datetime.now().date() + timedelta(days=365)).isoformat()

    # Получаем статистику из БД
    cursor = db_manager.connection.cursor()
    cursor.execute("""
        SELECT
            COUNT(*) as total_orders,
            COALESCE(SUM(price), 0) as total_revenue,
            COUNT(DISTINCT user_id) as unique_clients
        FROM orders
        WHERE booking_date >= ? AND booking_date <= ?
          AND status = 'active'
    """, (start_date, end_date))

    row = cursor.fetchone()
    total_orders = row[0] or 0
    total_revenue = row[1] or 0
    unique_clients = row[2] or 0
    avg_check = int(total_revenue / total_orders) if total_orders > 0 else 0

    text = f"""
{title}

📦 Заказов: {total_orders}
💰 Выручка: {total_revenue}₽
📈 Средний чек: {avg_check}₽
👥 Уникальных клиентов: {unique_clients}
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к заказам", callback_data=f"admin_orders_page:{period}:0")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def admin_export_csv_handler(callback, config: dict, db_manager):
    """Экспорт заказов в CSV"""
    from datetime import datetime
    try:
        csv_data = db_manager.get_orders_csv(days=30)
        filename = f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        document = BufferedInputFile(csv_data, filename=filename)
        await callback.message.answer_document(
            document,
            caption="📥 Заказы за последние 30 дней"
        )

        # Удаляем сообщение с кнопкой экспорта для чистоты интерфейса
        try:
            await callback.message.delete()
        except Exception:
            # Если не удалось удалить, редактируем текст и убираем кнопки
            try:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 К записям", callback_data="admin_orders")],
                ])
                await callback.message.edit_text(
                    "✅ CSV файл отправлен выше 👆",
                    reply_markup=keyboard
                )
            except Exception:
                pass

        await callback.answer("✅ Файл отправлен")
    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        await callback.answer("❌ Ошибка экспорта", show_alert=True)


async def admin_clients_handler(callback, config: dict, db_manager):
    """Обработчик базы клиентов"""
    # Получаем всех пользователей
    cursor = db_manager.connection.cursor()
    cursor.execute("""
        SELECT COUNT(DISTINCT user_id) FROM orders
    """)
    total_clients = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT
            o.user_id,
            COUNT(o.id) as orders_count,
            u.username,
            u.first_name,
            u.last_name,
            (
                SELECT oo.phone
                FROM orders oo
                WHERE oo.user_id = o.user_id
                ORDER BY oo.created_at DESC
                LIMIT 1
            ) AS last_phone
        FROM orders o
        LEFT JOIN users u ON u.user_id = o.user_id
        GROUP BY o.user_id
        ORDER BY orders_count DESC
        LIMIT 10
        """
    )

    top_clients = cursor.fetchall()
    
    text = (
        f"👥 <b>База клиентов</b>\n\n"
        f"Всего клиентов: {total_clients}\n\n"
        f"🏆 Топ-10 клиентов:\n"
    )

    for i, (user_id, count, username, first_name, last_name, last_phone) in enumerate(top_clients, 1):
        full_name = " ".join([p for p in [first_name, last_name] if p])
        display_name = full_name or (f"@{username}" if username else f"ID {user_id}")

        text += f"{i}. {display_name} — {count} заказов\n"
        text += f"   ID: {user_id}\n"
        if username:
            text += f"   Username: @{username}\n"
            text += f"   Ссылка: https://t.me/{username}\n"
        if last_phone:
            text += f"   Телефон: {last_phone}\n"
        text += "\n"
    
    await callback.message.edit_text(text)
    await callback.answer()




async def admin_services_all_handler(callback, config_manager):
    """Показать все услуги"""
    from admin_handlers.services_editor import get_services_keyboard
    config = config_manager.get_config()
    services = config.get('services', [])

    text = f"📋 <b>ВСЕ УСЛУГИ</b> ({len(services)})\n\n"
    keyboard = get_services_keyboard(services)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def admin_services_by_category_handler(callback, config_manager):
    """Показать услуги по категории"""
    category = callback.data.replace("admin_services_cat:", "")
    config = config_manager.get_config()
    services = config.get('services', [])

    # Фильтруем по категории
    filtered = [s for s in services if s.get('category', 'Другое') == category]

    text = f"📁 <b>{category}</b> ({len(filtered)} услуг)\n\n"

    keyboard_rows = []
    for svc in filtered:
        dur = svc.get('duration', 0)
        dur_text = f" • {dur}мин" if dur else ""
        keyboard_rows.append([InlineKeyboardButton(
            text=f"✏️ {svc['name']} — {svc['price']}₽{dur_text}",
            callback_data=f"edit_service_{svc['id']}"
        )])

    keyboard_rows.append([InlineKeyboardButton(text="◀️ Все категории", callback_data="admin_services_menu")])
    keyboard_rows.append([InlineKeyboardButton(text="➕ Добавить услугу", callback_data="add_service_start")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def admin_services_menu_handler(callback, config_manager):
    """Меню фильтрации услуг"""
    config = config_manager.get_config()
    services = config.get('services', [])

    # Группируем по категориям
    categories = {}
    for svc in services:
        cat = svc.get('category', 'Другое')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(svc)

    text = f"📋 <b>УСЛУГИ</b> ({len(services)})\n\nВыберите категорию для просмотра:"

    keyboard_rows = []
    keyboard_rows.append([InlineKeyboardButton(text="📂 Все услуги", callback_data="admin_services_all")])

    for cat_name in categories.keys():
        count = len(categories[cat_name])
        keyboard_rows.append([InlineKeyboardButton(
            text=f"📁 {cat_name} ({count})",
            callback_data=f"admin_services_cat:{cat_name}"
        )])

    keyboard_rows.append([InlineKeyboardButton(text="➕ Добавить услугу", callback_data="add_service_start")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def admin_help_handler(callback):
    """Обработчик помощи"""
    text = (
        "❓ <b>Помощь</b>\n\n"
        "<b>Кнопки меню:</b>\n"
        "📊 Статистика — просмотр статистики\n"
        "📅 Заказы — управление записями\n"
        "💼 Услуги — редактирование услуг\n"
        "👤 Персонал — управление мастерами\n"
        "⚙️ Настройки — настройки бизнеса\n\n"
        "<b>Команды:</b>\n"
        "/start — Главное меню\n\n"
        "<b>Навигация:</b>\n"
        "Используйте кнопки внизу экрана или inline-меню для доступа к разделам.\n\n"
        "По вопросам обращайтесь к разработчику: @Oroani"
    )

    await callback.message.edit_text(text)
    await callback.answer()


async def admin_main_handler(callback, config: dict, db_manager, state: FSMContext):
    """Возврат в главное меню"""
    # Очищаем FSM state при возврате в главное меню
    await state.clear()

    business_name = config.get('business_name', 'Ваш бизнес')
    stats = db_manager.get_stats('today')

    planned_text = f"\n├ Планируемая: {stats.get('planned_revenue', 0)}₽" if stats.get('planned_revenue', 0) > 0 else ""
    text = (
        f"🎯 <b>Админ-панель \"{business_name}\"</b>\n\n"
        f"📅 Сегодня:\n"
        f"├ Заказов: {stats['total_orders']}\n"
        f"├ Выручка: {stats['total_revenue']}₽{planned_text}\n"
        f"└ Новых клиентов: {stats.get('new_clients', 0)}\n\n"
        "Выберите действие:"
    )

    keyboard = get_main_menu_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def admin_orders_custom_range_handler(callback, state: FSMContext):
    """Начать выбор диапазона дат"""
    await callback.message.edit_text(
        "📝 <b>Выбор диапазона дат</b>\n\n"
        "Введите дату <b>начала</b> периода в формате ДД.ММ.ГГГГ\n"
        "Например: 01.01.2025",
        parse_mode="HTML"
    )
    await state.set_state(AdminOrdersStates.input_date_from)
    await callback.answer()


async def process_date_from(message: Message, state: FSMContext):
    """Обработка даты начала периода"""
    text = message.text.strip()

    # Пробуем разные форматы
    date_formats = ['%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']
    date_from = None

    for fmt in date_formats:
        try:
            date_from = datetime.strptime(text, fmt).date()
            break
        except ValueError:
            continue

    if not date_from:
        await message.answer(
            "❌ Неверный формат даты.\n\n"
            "Введите дату в формате ДД.ММ.ГГГГ\n"
            "Например: 01.01.2025"
        )
        return

    await state.update_data(date_from=date_from.isoformat())
    await message.answer(
        f"✅ Начало периода: <b>{date_from.strftime('%d.%m.%Y')}</b>\n\n"
        "Теперь введите дату <b>конца</b> периода в формате ДД.ММ.ГГГГ\n"
        "Например: 31.01.2025",
        parse_mode="HTML"
    )
    await state.set_state(AdminOrdersStates.input_date_to)


async def process_date_to(message: Message, state: FSMContext, db_manager):
    """Обработка даты конца периода и показ заказов"""
    text = message.text.strip()

    # Пробуем разные форматы
    date_formats = ['%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']
    date_to = None

    for fmt in date_formats:
        try:
            date_to = datetime.strptime(text, fmt).date()
            break
        except ValueError:
            continue

    if not date_to:
        await message.answer(
            "❌ Неверный формат даты.\n\n"
            "Введите дату в формате ДД.ММ.ГГГГ\n"
            "Например: 31.01.2025"
        )
        return

    data = await state.get_data()
    date_from = datetime.fromisoformat(data.get('date_from')).date()

    if date_to < date_from:
        await message.answer("❌ Дата конца не может быть раньше даты начала. Введите корректную дату:")
        return

    await state.clear()

    # Получаем заказы за период
    cursor = db_manager.connection.cursor()
    cursor.execute("""
        SELECT id, service_name, price, booking_date, booking_time, client_name, phone, status
        FROM orders
        WHERE status = 'active'
          AND booking_date >= ?
          AND booking_date <= ?
        ORDER BY booking_date, booking_time
    """, (date_from.isoformat(), date_to.isoformat()))
    orders = cursor.fetchall()

    date_from_fmt = date_from.strftime('%d.%m.%Y')
    date_to_fmt = date_to.strftime('%d.%m.%Y')

    result_text = f"📋 <b>Заказы за период</b>\n"
    result_text += f"📅 {date_from_fmt} — {date_to_fmt}\n"
    result_text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if not orders:
        result_text += "<i>Заказов за этот период нет</i>"
    else:
        total_revenue = 0
        for order_id, service_name, price, booking_date, booking_time, client_name, phone, status in orders:
            try:
                bd_fmt = datetime.fromisoformat(booking_date).strftime('%d.%m.%Y')
            except:
                bd_fmt = booking_date
            result_text += f"#{order_id} | {bd_fmt} {booking_time or ''}\n"
            result_text += f"├ {service_name} — {price}₽\n"
            result_text += f"└ {client_name}\n\n"
            total_revenue += price or 0

        result_text += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        result_text += f"📊 Всего: {len(orders)} заказов | 💰 {total_revenue}₽"

    await message.answer(result_text, parse_mode="HTML")


async def main():
    """Главная функция админ-бота"""
    parser = argparse.ArgumentParser(description='Admin Bot for Bot-Business V2.0')
    parser.add_argument('--config', type=str, required=True, help='Path to config JSON')
    args = parser.parse_args()
    
    # Загрузка конфигурации
    try:
        config = load_config(args.config)
        logger.info(f"✅ Config loaded: {config.get('business_name')}")
    except Exception as e:
        logger.error(f"❌ Failed to load config: {e}")
        return
    
    # Токен админ-бота
    admin_token = os.getenv('ADMIN_BOT_TOKEN')
    
    if not admin_token:
        logger.error("❌ ADMIN_BOT_TOKEN not found in .env!")
        return
    
    # Инициализация БД
    db_manager = DBManager(config['business_slug'])
    try:
        db_manager.init_db()
        logger.info(f"✅ Database ready: db_{config['business_slug']}.sqlite")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        return
    
    # Инициализация ConfigManager
    config_manager = ConfigManager(args.config)
    logger.info("✅ ConfigManager initialized")

    # Создаём бота
    bot = Bot(token=admin_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # Создаём FSM storage
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Подключаем middlewares
    dp.update.middleware(AdminAuthMiddleware(config))
    pin_middleware = AdminPinMiddleware(config)
    dp.update.middleware(pin_middleware)

    dp.update.middleware(PinMiddlewareInjector(pin_middleware))

    dp.update.middleware(ConfigMiddleware(config, db_manager, config_manager))

    # ==================== ОБРАБОТЧИКИ НИЖНЕЙ КЛАВИАТУРЫ ====================
    # ВАЖНО: Регистрируем ДО подключения роутеров, чтобы они имели приоритет над FSM-хендлерами

    async def reply_orders_handler(message: Message, state: FSMContext, config: dict, db_manager):
        """Обработчик кнопки Заказы — меняет клавиатуру на контекстную"""
        await state.clear()
        from datetime import datetime

        stats_today = db_manager.get_stats('today')

        text = (
            f"📅 <b>ЗАКАЗЫ</b>\n\n"
            f"📊 Сегодня ({datetime.now().strftime('%d.%m.%Y')}):\n"
            f"├ Заказов: {stats_today['total_orders']}\n"
            f"└ Выручка: {stats_today['total_revenue']}₽\n\n"
            f"Используйте кнопки внизу для навигации."
        )

        await message.answer(text, reply_markup=get_orders_reply_keyboard())

    async def reply_services_handler(message: Message, state: FSMContext, config_manager):
        """Обработчик кнопки Услуги — меняет клавиатуру на контекстную"""
        await state.clear()
        config = config_manager.get_config()
        services = config.get('services', [])
        promotions = config.get('promotions', [])
        active_promos = len([p for p in promotions if p.get('active', True)])

        text = f"💼 <b>УСЛУГИ И АКЦИИ</b>\n\n"
        text += f"📋 Услуг: {len(services)}\n"
        text += f"🎁 Акций: {active_promos} активных\n\n"
        text += "Используйте кнопки внизу для навигации."

        await message.answer(text, reply_markup=get_services_reply_keyboard())

    async def reply_staff_handler(message: Message, state: FSMContext, config: dict):
        """Обработчик кнопки Персонал — меняет клавиатуру на контекстную"""
        await state.clear()
        staff_data = config.get('staff', {})
        is_enabled = staff_data.get('enabled', False)
        masters = staff_data.get('masters', [])

        status = "✅ Включена" if is_enabled else "❌ Отключена"

        text = f"👤 <b>УПРАВЛЕНИЕ ПЕРСОНАЛОМ</b>\n\nФункция персонала: <b>{status}</b>\n\n"

        if masters:
            text += f"Текущий состав ({len(masters)}):\n\n"
            for master in masters:
                services_count = len(master.get('services', []))
                text += f"👤 <b>{master['name']}</b> — {master.get('specialization') or master.get('role', 'Мастер')}\n"
                text += f"   📋 Услуг: {services_count}\n\n"
        else:
            text += "<i>Мастера не добавлены</i>\n\n"

        text += "Используйте кнопки внизу для навигации."

        # Inline для toggle
        toggle_text = "🔴 Выключить" if is_enabled else "🟢 Включить"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data="toggle_staff")],
            [InlineKeyboardButton(text="🗑 Удалить мастера", callback_data="delete_master_list")],
        ])

        await message.answer(text, reply_markup=get_staff_reply_keyboard())
        await message.answer("Дополнительные действия:", reply_markup=keyboard)

    async def reply_settings_handler(message: Message, state: FSMContext, config: dict):
        """Обработчик кнопки Настройки — меняет клавиатуру на контекстную"""
        await state.clear()

        business_name = config.get('business_name', 'Не указано')
        booking = config.get('booking', {})
        work_start = int(booking.get('work_start', 10))
        work_end = int(booking.get('work_end', 20))

        text = (
            f"⚙️ <b>НАСТРОЙКИ</b>\n\n"
            f"📍 Бизнес: {business_name}\n"
            f"🕐 Часы: {work_start}:00 - {work_end}:00\n\n"
            f"Используйте кнопки внизу для навигации."
        )

        await message.answer(text, reply_markup=get_settings_reply_keyboard())

    async def reply_back_handler(message: Message, state: FSMContext, config: dict, db_manager):
        """Обработчик кнопки Назад - возврат на предыдущий шаг или в главное меню"""
        from admin_bot.states import StaffEditorStates, ClosedDatesStates
        from admin_handlers.promotions_editor import PromotionStates
        from admin_handlers.services_editor import ServiceEditStates

        current_state = await state.get_state()

        # Определяем куда вернуться в зависимости от текущего состояния
        if current_state:
            state_data = await state.get_data()

            # Состояния добавления/редактирования мастера
            if current_state == StaffEditorStates.enter_name.state:
                await state.clear()
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="👤 К персоналу", callback_data="staff_menu")],
                ])
                await message.answer("↩️ Действие отменено", reply_markup=keyboard)
                return

            elif current_state == StaffEditorStates.enter_role.state:
                # Возврат к вводу имени
                await state.set_state(StaffEditorStates.enter_name)
                text = """
➕ <b>ДОБАВЛЕНИЕ МАСТЕРА</b>

Шаг 1 из 5: Введите имя мастера (от 2 до 50 символов):

<i>Например: Анна, Мария Иванова</i>
"""
                await message.answer(text)
                return

            elif current_state == StaffEditorStates.choose_services.state:
                # Возврат к вводу должности
                await state.set_state(StaffEditorStates.enter_role)
                name = state_data.get('master_name', '')
                text = f"""
✅ Имя: <b>{name}</b>

Шаг 2 из 5: Введите должность/специализацию:

<i>Например: Парикмахер, Мастер маникюра, Косметолог</i>
"""
                await message.answer(text)
                return

            elif current_state == StaffEditorStates.choose_schedule_days.state:
                # Возврат к выбору услуг - показываем inline кнопку
                await state.clear()
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Начать заново", callback_data="add_master")],
                    [InlineKeyboardButton(text="👤 К персоналу", callback_data="staff_menu")],
                ])
                await message.answer("↩️ Вернитесь к выбору услуг или начните заново", reply_markup=keyboard)
                return

            elif current_state == StaffEditorStates.choose_schedule_hours.state:
                # Возврат к выбору дней
                from admin_handlers.staff_editor import _build_days_keyboard
                selected_days = state_data.get('selected_days', [])
                await state.set_state(StaffEditorStates.choose_schedule_days)
                name = state_data.get('master_name', '')
                role = state_data.get('master_role', '')
                services_count = len(state_data.get('selected_services', []))
                text = f"""
✅ Имя: <b>{name}</b>
✅ Должность: <b>{role}</b>
✅ Услуг выбрано: <b>{services_count}</b>

Шаг 4 из 5: Выберите рабочие дни мастера.

Нажимайте на дни для выбора/отмены:
"""
                keyboard = _build_days_keyboard(selected_days)
                await message.answer(text, reply_markup=keyboard)
                return

            elif current_state == StaffEditorStates.edit_name.state or current_state == StaffEditorStates.edit_role.state:
                # Возврат к редактированию мастера
                master_id = state_data.get('editing_master_id', '')
                await state.clear()
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="👤 К мастеру", callback_data=f"edit_master_{master_id}")],
                    [InlineKeyboardButton(text="👤 К персоналу", callback_data="staff_menu")],
                ])
                await message.answer("↩️ Редактирование отменено", reply_markup=keyboard)
                return

            # Состояния акций
            elif current_state and 'PromotionStates' in current_state:
                await state.clear()
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎁 К акциям", callback_data="promotions_menu")],
                ])
                await message.answer("↩️ Действие отменено", reply_markup=keyboard)
                return

            # Состояния услуг
            elif current_state and 'ServiceEditStates' in current_state:
                await state.clear()
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📋 К услугам", callback_data="admin_services")],
                ])
                await message.answer("↩️ Действие отменено", reply_markup=keyboard)
                return

            # Состояния текстов/FAQ
            elif current_state and ('TextsEditorStates' in current_state or 'FAQEditorStates' in current_state):
                await state.clear()
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📝 К текстам", callback_data="texts_menu")],
                ])
                await message.answer("↩️ Действие отменено", reply_markup=keyboard)
                return

            # Состояния настроек
            elif current_state and ('SettingsEditStates' in current_state or 'BusinessSettingsStates' in current_state):
                await state.clear()
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⚙️ К настройкам", callback_data="admin_settings")],
                ])
                await message.answer("↩️ Действие отменено", reply_markup=keyboard)
                return

            # Состояния закрытых дат
            elif current_state and 'ClosedDatesStates' in current_state:
                master_id = state_data.get('master_id', '')
                await state.clear()
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📅 К датам", callback_data=f"closed_dates_{master_id}")],
                    [InlineKeyboardButton(text="👤 К персоналу", callback_data="staff_menu")],
                ])
                await message.answer("↩️ Действие отменено", reply_markup=keyboard)
                return

        # По умолчанию - главное меню
        await state.clear()
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

    async def reply_clients_handler(message: Message, state: FSMContext, db_manager):
        """Обработчик кнопки Клиенты — меняет клавиатуру на контекстную"""
        await state.clear()

        cursor = db_manager.connection.cursor()
        cursor.execute("""
            SELECT
                u.user_id,
                u.username,
                u.first_name,
                u.last_name,
                COUNT(o.id) as orders_count,
                COALESCE(SUM(o.price), 0) as total_spent,
                MAX(o.phone) as last_phone
            FROM users u
            LEFT JOIN orders o ON u.user_id = o.user_id AND o.status = 'active'
            GROUP BY u.user_id
            ORDER BY orders_count DESC
            LIMIT 20
        """)
        clients = cursor.fetchall()

        text = "👥 <b>КЛИЕНТЫ</b>\n\n"
        total_clients = len(clients)
        text += f"Всего клиентов: {total_clients}\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        if not clients:
            text += "<i>Клиентов пока нет</i>"
        else:
            for user_id, username, first_name, last_name, orders_count, total_spent, last_phone in clients:
                name = first_name or "—"
                if last_name:
                    name += f" {last_name}"
                text += f"👤 <b>{name}</b>\n"
                if username:
                    text += f"   @{username}\n"
                text += f"   📦 Заказов: {orders_count} | 💰 {total_spent}₽\n"
                if last_phone:
                    text += f"   📱 {last_phone}\n"
                text += "\n"

        await message.answer(text, reply_markup=get_clients_reply_keyboard())

    # ==================== ОБРАБОТЧИКИ ДИНАМИЧЕСКИХ КНОПОК ====================

    # --- Раздел ЗАКАЗЫ ---
    async def reply_stats_handler(message: Message, state: FSMContext, config: dict, db_manager):
        """Подробная статистика"""
        from datetime import datetime
        stats_today = db_manager.get_stats('today')
        stats_week = db_manager.get_stats('week')
        stats_month = db_manager.get_stats('month')

        text = (
            f"📊 <b>СТАТИСТИКА</b>\n\n"
            f"📅 Сегодня ({datetime.now().strftime('%d.%m.%Y')}):\n"
            f"├ Заказов: {stats_today['total_orders']}\n"
            f"└ Выручка: {stats_today['total_revenue']}₽\n\n"
            f"📅 Эта неделя:\n"
            f"├ Заказов: {stats_week['total_orders']}\n"
            f"└ Выручка: {stats_week['total_revenue']}₽\n\n"
            f"📅 Этот месяц:\n"
            f"├ Заказов: {stats_month['total_orders']}\n"
            f"└ Выручка: {stats_month['total_revenue']}₽\n\n"
            f"🏆 Топ услуги (месяц):\n"
        )
        for i, (service, count) in enumerate(stats_month['top_services'][:5], 1):
            text += f"{i}. {service} ({count} шт.)\n"

        await message.answer(text)

    async def reply_orders_today_handler(message: Message, db_manager, config: dict):
        """Заказы на сегодня"""
        # Используем существующий callback handler через эмуляцию
        from datetime import datetime
        tz_offset = config.get('timezone_offset_hours')
        tz_modifier = f"{int(tz_offset):+d} hours" if tz_offset else "localtime"

        cursor = db_manager.connection.cursor()
        cursor.execute("""
            SELECT id, service_name, booking_date, booking_time, client_name, phone, price
            FROM orders WHERE status = 'active' AND booking_date = date('now', ?)
            ORDER BY booking_time LIMIT 10
        """, (tz_modifier,))
        orders = cursor.fetchall()

        text = f"📅 <b>Заказы на сегодня</b> ({datetime.now().strftime('%d.%m.%Y')})\n\n"
        if not orders:
            text += "<i>Нет заказов</i>"
        else:
            for oid, service, date, time, name, phone, price in orders:
                text += f"#{oid} — {time or '?'}\n└ {service} ({price}₽) — {name}\n\n"

        await message.answer(text)

    async def reply_orders_tomorrow_handler(message: Message, db_manager, config: dict):
        """Заказы на завтра"""
        from datetime import datetime, timedelta
        tz_offset = config.get('timezone_offset_hours')
        tz_modifier = f"{int(tz_offset):+d} hours" if tz_offset else "localtime"

        cursor = db_manager.connection.cursor()
        cursor.execute("""
            SELECT id, service_name, booking_date, booking_time, client_name, phone, price
            FROM orders WHERE status = 'active' AND booking_date = date('now', ?, '+1 day')
            ORDER BY booking_time LIMIT 10
        """, (tz_modifier,))
        orders = cursor.fetchall()

        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
        text = f"📅 <b>Заказы на завтра</b> ({tomorrow})\n\n"
        if not orders:
            text += "<i>Нет заказов</i>"
        else:
            for oid, service, date, time, name, phone, price in orders:
                text += f"#{oid} — {time or '?'}\n└ {service} ({price}₽) — {name}\n\n"

        await message.answer(text)

    async def reply_orders_week_handler(message: Message, db_manager, config: dict):
        """Заказы на неделю"""
        tz_offset = config.get('timezone_offset_hours')
        tz_modifier = f"{int(tz_offset):+d} hours" if tz_offset else "localtime"

        cursor = db_manager.connection.cursor()
        cursor.execute("""
            SELECT id, service_name, booking_date, booking_time, client_name, price
            FROM orders WHERE status = 'active'
              AND booking_date >= date('now', ?)
              AND booking_date <= date('now', ?, '+7 days')
            ORDER BY booking_date, booking_time LIMIT 15
        """, (tz_modifier, tz_modifier))
        orders = cursor.fetchall()

        text = f"📅 <b>Заказы на неделю</b>\n\n"
        if not orders:
            text += "<i>Нет заказов</i>"
        else:
            from datetime import datetime
            for oid, service, date, time, name, price in orders:
                try:
                    date_fmt = datetime.fromisoformat(date).strftime('%d.%m')
                except:
                    date_fmt = date
                text += f"#{oid} — {date_fmt} {time or ''}\n└ {service} ({price}₽)\n\n"

        await message.answer(text)

    async def reply_csv_handler(message: Message, db_manager):
        """Выгрузить CSV"""
        from datetime import datetime
        try:
            csv_data = db_manager.get_orders_csv(days=30)
            filename = f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            document = BufferedInputFile(csv_data, filename=filename)
            await message.answer_document(document, caption="📥 Заказы за последние 30 дней")
        except Exception as e:
            await message.answer(f"❌ Ошибка экспорта: {e}")

    # --- Раздел УСЛУГИ ---
    async def reply_promotions_handler(message: Message, state: FSMContext, config: dict):
        """Управление акциями"""
        await state.clear()
        promotions = config.get('promotions', [])

        text = "🎁 <b>АКЦИИ</b>\n\n"
        if promotions:
            for promo in promotions:
                status = "✅" if promo.get('active', True) else "❌"
                text += f"{status} {promo.get('emoji', '🎁')} {promo.get('title', 'Без названия')}\n"
        else:
            text += "<i>Акций нет</i>\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить акцию", callback_data="promo_add")],
            [InlineKeyboardButton(text="📋 Управлять", callback_data="promotions_menu")],
        ])
        await message.answer(text, reply_markup=keyboard)

    async def reply_services_list_handler(message: Message, config_manager):
        """Список услуг с фильтрацией по категориям"""
        config = config_manager.get_config()
        services = config.get('services', [])

        # Группируем по категориям
        categories = {}
        for svc in services:
            cat = svc.get('category', 'Другое')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(svc)

        text = f"📋 <b>УСЛУГИ</b> ({len(services)})\n\n"

        # Показываем кнопки категорий для фильтрации
        keyboard_rows = []
        keyboard_rows.append([InlineKeyboardButton(text="📂 Все услуги", callback_data="admin_services_all")])

        for cat_name in categories.keys():
            count = len(categories[cat_name])
            keyboard_rows.append([InlineKeyboardButton(
                text=f"📁 {cat_name} ({count})",
                callback_data=f"admin_services_cat:{cat_name}"
            )])

        keyboard_rows.append([InlineKeyboardButton(text="➕ Добавить услугу", callback_data="add_service_start")])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await message.answer(text + "Выберите категорию для просмотра:", reply_markup=keyboard)

    async def reply_add_service_handler(message: Message, state: FSMContext):
        """Добавить услугу — переход к FSM"""
        from admin_handlers.services_editor import ServiceEditStates
        await state.set_state(ServiceEditStates.add_name)
        await message.answer("📝 Введите название новой услуги:")

    # --- Раздел ПЕРСОНАЛ ---
    async def reply_add_master_handler(message: Message, state: FSMContext):
        """Добавить мастера"""
        from admin_bot.states import StaffEditorStates
        await state.set_state(StaffEditorStates.enter_name)
        text = """
➕ <b>ДОБАВЛЕНИЕ МАСТЕРА</b>

Шаг 1 из 5: Введите имя мастера (от 2 до 50 символов):

<i>Например: Анна, Мария Иванова</i>
"""
        await message.answer(text)

    async def reply_edit_master_handler(message: Message, config: dict):
        """Редактировать мастера"""
        masters = config.get('staff', {}).get('masters', [])
        if not masters:
            await message.answer("❌ Мастера не добавлены")
            return

        keyboard_rows = []
        for master in masters:
            keyboard_rows.append([InlineKeyboardButton(
                text=f"✏️ {master['name']}",
                callback_data=f"edit_master_{master['id']}"
            )])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await message.answer("Выберите мастера для редактирования:", reply_markup=keyboard)

    async def reply_closed_dates_handler(message: Message, config: dict):
        """Закрытые даты"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Управление датами", callback_data="closed_dates_menu")],
        ])
        await message.answer("📅 <b>Закрытые даты</b>\n\nВыберите мастера для управления:", reply_markup=keyboard)

    # --- Раздел НАСТРОЙКИ ---
    async def reply_help_handler(message: Message):
        """Помощь - полезная FAQ для администраторов"""
        text = (
            "❓ <b>ПОМОЩЬ — ЧАСТЫЕ ВОПРОСЫ</b>\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📋 <b>ЗАКАЗЫ И ЗАПИСИ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "<b>Как посмотреть записи на сегодня?</b>\n"
            "→ Заказы → Сегодня\n\n"

            "<b>Как отменить запись клиента?</b>\n"
            "→ Заказы → Сегодня/Завтра/Неделя → выберите запись → Отменить\n\n"

            "<b>Что такое CSV и зачем он?</b>\n"
            "→ CSV — это файл-таблица, который можно открыть в Excel/Google Таблицах.\n"
            "→ Заказы → CSV — скачаете все записи за месяц для учёта и анализа.\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👤 <b>ПЕРСОНАЛ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "<b>Мастер в отпуске — что делать?</b>\n"
            "→ Персонал → Закрытые даты → выберите мастера → добавьте даты отпуска.\n"
            "→ Клиенты не смогут записаться на эти даты.\n\n"

            "<b>Как изменить график мастера?</b>\n"
            "→ Персонал → Редактировать → выберите мастера → Изменить график\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💼 <b>УСЛУГИ И АКЦИИ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "<b>Как добавить новую услугу?</b>\n"
            "→ Услуги → Добавить → введите название, цену, длительность\n\n"

            "<b>Как создать акцию/скидку?</b>\n"
            "→ Услуги → Акции → Добавить акцию\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚙️ <b>НАСТРОЙКИ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "<b>Как изменить часы работы?</b>\n"
            "→ Настройки → Бизнес → Часы работы\n\n"

            "<b>Как изменить приветственное сообщение?</b>\n"
            "→ Настройки → Тексты → Приветствие\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🆘 <b>ПРОБЛЕМЫ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "<b>Бот не отвечает</b>\n"
            "→ Подождите 10-15 секунд и попробуйте снова\n"
            "→ Нажмите /start для перезапуска\n\n"

            "<b>Не могу найти запись</b>\n"
            "→ Проверьте раздел «Неделя» — запись может быть на другую дату\n\n"

            "<b>Техподдержка:</b> @Oroani"
        )
        await message.answer(text)

    async def reply_business_settings_handler(message: Message, config: dict):
        """Настройки бизнеса - показываем сразу без промежуточного экрана"""
        booking = config.get('booking', {})

        text = f"""
⚙️ <b>НАСТРОЙКИ БИЗНЕСА</b>

Текущие данные:
━━━━━━━━━━━━━━━━━━━━━━
📍 <b>Название:</b> {config.get('business_name', 'Не указано')}
🕐 <b>Начало работы:</b> {int(booking.get('work_start', 10))}:00
🕑 <b>Конец работы:</b> {int(booking.get('work_end', 20))}:00
⏱ <b>Длительность слота:</b> {int(booking.get('slot_duration', 60))} минут
🌍 <b>Часовой пояс:</b> {config.get('timezone_city', 'Не указано')} (UTC{int(config.get('timezone_offset_hours', 3)):+d})
━━━━━━━━━━━━━━━━━━━━━━

Выберите что изменить:
"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить название", callback_data="edit_business_name")],
            [InlineKeyboardButton(text="🕐 Изменить время начала", callback_data="edit_work_start")],
            [InlineKeyboardButton(text="🕑 Изменить время конца", callback_data="edit_work_end")],
            [InlineKeyboardButton(text="⏱ Изменить слот", callback_data="edit_slot_duration")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_settings")],
        ])

        await message.answer(text, reply_markup=keyboard)

    async def reply_texts_handler(message: Message):
        """Тексты бота"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Редактировать тексты", callback_data="texts_menu")],
        ])
        await message.answer("📝 <b>Тексты бота</b>", reply_markup=keyboard)

    async def reply_notifications_handler(message: Message):
        """Уведомления"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Настроить уведомления", callback_data="notifications_menu")],
        ])
        await message.answer("🔔 <b>Уведомления</b>", reply_markup=keyboard)

    # --- Раздел КЛИЕНТЫ ---
    async def reply_search_clients_handler(message: Message):
        """Поиск клиентов (заглушка)"""
        await message.answer("🔍 <b>Поиск клиентов</b>\n\n<i>Функция в разработке</i>")

    # ==================== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ====================
    # ВАЖНО: Регистрируем ДО подключения роутеров, чтобы они имели приоритет

    # Главное меню
    dp.message.register(reply_back_handler, F.text == "◀️ Назад")
    dp.message.register(reply_orders_handler, F.text == "📅 Заказы")
    dp.message.register(reply_services_handler, F.text == "💼 Услуги")
    dp.message.register(reply_staff_handler, F.text == "👤 Персонал")
    dp.message.register(reply_settings_handler, F.text == "⚙️ Настройки")
    dp.message.register(reply_clients_handler, F.text == "👥 Клиенты")

    # Раздел ЗАКАЗЫ
    dp.message.register(reply_stats_handler, F.text == "📊 Статистика")
    dp.message.register(reply_orders_today_handler, F.text == "📅 Сегодня")
    dp.message.register(reply_orders_tomorrow_handler, F.text == "📅 Завтра")
    dp.message.register(reply_orders_week_handler, F.text == "📅 Неделя")
    dp.message.register(reply_csv_handler, F.text == "📥 CSV")

    # Раздел УСЛУГИ
    dp.message.register(reply_promotions_handler, F.text == "🎁 Акции")
    dp.message.register(reply_services_list_handler, F.text == "📋 Список услуг")
    dp.message.register(reply_add_service_handler, F.text == "➕ Добавить")

    # Раздел ПЕРСОНАЛ
    dp.message.register(reply_add_master_handler, F.text == "➕ Добавить мастера")
    dp.message.register(reply_edit_master_handler, F.text == "✏️ Редактировать")
    dp.message.register(reply_closed_dates_handler, F.text == "📅 Закрытые даты")

    # Раздел НАСТРОЙКИ
    dp.message.register(reply_help_handler, F.text == "❓ Помощь")
    dp.message.register(reply_business_settings_handler, F.text == "⚙️ Бизнес")
    dp.message.register(reply_texts_handler, F.text == "📝 Тексты")
    dp.message.register(reply_notifications_handler, F.text == "🔔 Уведомления")

    # Раздел КЛИЕНТЫ
    dp.message.register(reply_search_clients_handler, F.text == "🔍 Поиск")

    # Подключаем роутеры для редактирования (ПОСЛЕ обработчиков нижней клавиатуры!)
    dp.include_router(services_editor.router)
    dp.include_router(settings_editor.router)
    dp.include_router(business_settings.router)
    dp.include_router(texts_editor.router)
    dp.include_router(notifications_editor.router)
    dp.include_router(staff_editor.router)
    dp.include_router(promotions_editor.router)

    # Регистрируем остальные handlers
    dp.message.register(cmd_start_with_pin, Command("start"))
    dp.message.register(process_pin, AdminPinStates.waiting_pin)
    dp.message.register(process_date_from, AdminOrdersStates.input_date_from)
    dp.message.register(process_date_to, AdminOrdersStates.input_date_to)
    dp.message.register(unknown_message, StateFilter(None), ~F.text.startswith("/"))
    
    # Callback handlers
    dp.callback_query.register(admin_stats_handler, F.data == "admin_stats")
    dp.callback_query.register(admin_orders_handler, F.data == "admin_orders")
    dp.callback_query.register(admin_orders_tomorrow_handler, F.data == "admin_orders_tomorrow")
    dp.callback_query.register(admin_orders_week_handler, F.data == "admin_orders_week")
    dp.callback_query.register(admin_orders_all_future_handler, F.data == "admin_orders_all_future")
    dp.callback_query.register(admin_orders_custom_range_handler, F.data == "admin_orders_custom_range")
    dp.callback_query.register(admin_orders_page_handler, F.data.startswith("admin_orders_page:"))
    dp.callback_query.register(admin_order_detail_handler, F.data.startswith("admin_order:"))
    dp.callback_query.register(admin_client_history_handler, F.data.startswith("admin_client_history:"))
    dp.callback_query.register(admin_export_csv_handler, F.data == "admin_export_csv")
    dp.callback_query.register(admin_stats_period_handler, F.data.startswith("admin_stats_period:"))
    dp.callback_query.register(admin_clients_handler, F.data == "admin_clients")
    # admin_settings теперь обрабатывается в settings_editor.py
    dp.callback_query.register(admin_help_handler, F.data == "admin_help")
    dp.callback_query.register(admin_main_handler, F.data == "admin_main")

    # Фильтрация услуг по категориям
    dp.callback_query.register(admin_services_all_handler, F.data == "admin_services_all")
    dp.callback_query.register(admin_services_by_category_handler, F.data.startswith("admin_services_cat:"))
    dp.callback_query.register(admin_services_menu_handler, F.data == "admin_services_menu")
    
    logger.info(f"🚀 Admin Bot for '{config.get('business_name')}' started!")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    finally:
        db_manager.close()
        await bot.session.close()
        logger.info("🛑 Admin Bot stopped")


if __name__ == '__main__':
    asyncio.run(main())
