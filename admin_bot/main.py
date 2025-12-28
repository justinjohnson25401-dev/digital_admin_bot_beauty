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
    """Постоянная клавиатура админ-панели"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📅 Заказы")],
            [KeyboardButton(text="💼 Услуги"), KeyboardButton(text="👤 Персонал")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True
    )


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню админ-панели"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="📋 Заказы", callback_data="admin_orders")
        ],
        [
            InlineKeyboardButton(text="📝 Услуги", callback_data="admin_services"),
            InlineKeyboardButton(text="👥 Клиенты", callback_data="admin_clients")
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки бизнеса", callback_data="business_settings")
        ],
        [
            InlineKeyboardButton(text="👤 Персонал", callback_data="staff_menu"),
            InlineKeyboardButton(text="📝 Тексты", callback_data="texts_menu")
        ],
        [
            InlineKeyboardButton(text="🔔 Уведомления", callback_data="notifications_menu"),
            InlineKeyboardButton(text="⚙️ Система", callback_data="admin_settings")
        ],
        [
            InlineKeyboardButton(text="❓ Помощь", callback_data="admin_help")
        ]
    ])


async def cmd_start(message: Message, config: dict, db_manager):
    """Команда /start для админов"""
    business_name = config.get('business_name', 'Ваш бизнес')

    # Получаем статистику
    stats = db_manager.get_stats('today')

    text = (
        f"🎯 <b>Админ-панель \"{business_name}\"</b>\n\n"
        f"📅 Сегодня:\n"
        f"├ Заказов: {stats['total_orders']}\n"
        f"├ Выручка: {stats['total_revenue']}₽\n"
        f"└ Новых клиентов: {stats.get('new_clients', 0)}\n\n"
        "Выберите действие:"
    )

    # Показываем постоянную клавиатуру
    await message.answer("📋 Меню:", reply_markup=get_admin_reply_keyboard())

    keyboard = get_main_menu_keyboard()
    await message.answer(text, reply_markup=keyboard)


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
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
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
    keyboard_rows.append([
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")
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
    keyboard_rows.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")])
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
        [InlineKeyboardButton(text="📥 Выгрузить CSV", callback_data="admin_export_csv")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")],
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

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
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_main")]
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
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")]
    ])
    
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
        "По вопросам обращайтесь к разработчику."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def admin_main_handler(callback, config: dict, db_manager):
    """Возврат в главное меню"""
    business_name = config.get('business_name', 'Ваш бизнес')
    stats = db_manager.get_stats('today')
    
    text = (
        f"🎯 <b>Админ-панель \"{business_name}\"</b>\n\n"
        f"📅 Сегодня:\n"
        f"├ Заказов: {stats['total_orders']}\n"
        f"├ Выручка: {stats['total_revenue']}₽\n"
        f"└ Новых клиентов: {stats.get('new_clients', 0)}\n\n"
        "Выберите действие:"
    )
    
    keyboard = get_main_menu_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


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
    
    # Подключаем роутеры для редактирования
    dp.include_router(services_editor.router)
    dp.include_router(settings_editor.router)
    dp.include_router(business_settings.router)
    dp.include_router(texts_editor.router)
    dp.include_router(notifications_editor.router)
    dp.include_router(staff_editor.router)
    
    # Обработчики кнопок постоянного меню
    async def reply_stats_handler(message: Message, config: dict, db_manager):
        """Обработчик кнопки Статистика"""
        from datetime import datetime

        stats_today = db_manager.get_stats('today')
        stats_week = db_manager.get_stats('week')
        stats_month = db_manager.get_stats('month')

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
            f"└ Выручка: {stats_month['total_revenue']}₽"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")]
        ])

        await message.answer(text, reply_markup=keyboard)

    async def reply_orders_handler(message: Message, config: dict, db_manager):
        """Обработчик кнопки Заказы"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 Сегодня", callback_data="admin_orders"),
                InlineKeyboardButton(text="📅 Завтра", callback_data="admin_orders_tomorrow"),
            ],
            [
                InlineKeyboardButton(text="📅 Эта неделя", callback_data="admin_orders_week"),
                InlineKeyboardButton(text="📆 Все будущие", callback_data="admin_orders_all_future"),
            ],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")],
        ])
        await message.answer("📋 <b>Выберите период:</b>", reply_markup=keyboard)

    async def reply_services_handler(message: Message, config_manager):
        """Обработчик кнопки Услуги"""
        from admin_handlers.services_editor import get_services_keyboard
        config = config_manager.get_config()
        services = config.get('services', [])

        text = f"📋 <b>Услуги ({len(services)})</b>\n\n"
        text += "Выберите услугу для редактирования или добавьте новую:"

        keyboard = get_services_keyboard(services)
        await message.answer(text, reply_markup=keyboard)

    async def reply_staff_handler(message: Message, config: dict):
        """Обработчик кнопки Персонал"""
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

        toggle_text = "🔴 Выключить персонал" if is_enabled else "🟢 Включить персонал"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data="toggle_staff")],
            [InlineKeyboardButton(text="➕ Добавить мастера", callback_data="add_master")],
            [InlineKeyboardButton(text="✏️ Редактировать мастера", callback_data="edit_master_list")],
            [InlineKeyboardButton(text="📅 Закрытые даты", callback_data="closed_dates_menu")],
            [InlineKeyboardButton(text="🗑 Удалить мастера", callback_data="delete_master_list")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")],
        ])

        await message.answer(text, reply_markup=keyboard)

    async def reply_settings_handler(message: Message, config: dict):
        """Обработчик кнопки Настройки"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Настройки бизнеса", callback_data="business_settings")],
            [InlineKeyboardButton(text="📝 Тексты", callback_data="texts_menu")],
            [InlineKeyboardButton(text="🔔 Уведомления", callback_data="notifications_menu")],
            [InlineKeyboardButton(text="⚙️ Система", callback_data="admin_settings")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")],
        ])
        await message.answer("⚙️ <b>Настройки</b>\n\nВыберите раздел:", reply_markup=keyboard)

    async def reply_help_handler(message: Message):
        """Обработчик кнопки Помощь"""
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
            "По вопросам обращайтесь к разработчику."
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin_main")]
        ])

        await message.answer(text, reply_markup=keyboard)

    # Регистрируем handlers
    dp.message.register(cmd_start_with_pin, Command("start"))
    dp.message.register(process_pin, AdminPinStates.waiting_pin)

    # Обработчики кнопок постоянного меню
    dp.message.register(reply_stats_handler, F.text == "📊 Статистика")
    dp.message.register(reply_orders_handler, F.text == "📅 Заказы")
    dp.message.register(reply_services_handler, F.text == "💼 Услуги")
    dp.message.register(reply_staff_handler, F.text == "👤 Персонал")
    dp.message.register(reply_settings_handler, F.text == "⚙️ Настройки")
    dp.message.register(reply_help_handler, F.text == "❓ Помощь")

    dp.message.register(unknown_message, StateFilter(None), ~F.text.startswith("/"))
    
    # Callback handlers
    dp.callback_query.register(admin_stats_handler, F.data == "admin_stats")
    dp.callback_query.register(admin_orders_handler, F.data == "admin_orders")
    dp.callback_query.register(admin_orders_tomorrow_handler, F.data == "admin_orders_tomorrow")
    dp.callback_query.register(admin_orders_week_handler, F.data == "admin_orders_week")
    dp.callback_query.register(admin_orders_all_future_handler, F.data == "admin_orders_all_future")
    dp.callback_query.register(admin_orders_page_handler, F.data.startswith("admin_orders_page:"))
    dp.callback_query.register(admin_order_detail_handler, F.data.startswith("admin_order:"))
    dp.callback_query.register(admin_client_history_handler, F.data.startswith("admin_client_history:"))
    dp.callback_query.register(admin_export_csv_handler, F.data == "admin_export_csv")
    dp.callback_query.register(admin_clients_handler, F.data == "admin_clients")
    # admin_settings теперь обрабатывается в settings_editor.py
    dp.callback_query.register(admin_help_handler, F.data == "admin_help")
    dp.callback_query.register(admin_main_handler, F.data == "admin_main")
    
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
