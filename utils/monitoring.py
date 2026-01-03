"""
Простая система мониторинга для Telegram-бота

Функции:
- Проверка работоспособности бота
- Сбор базовой статистики
- Логирование метрик
"""
import asyncio
import logging
import time
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
import aiohttp

from utils.db import DatabaseManager

logger = logging.getLogger(__name__)


class BotMonitor:
    """
    Монитор для проверки работоспособности бота
    """

    def __init__(self, bot_token: str, bot_name: str = "bot"):
        """
        Args:
            bot_token: Токен Telegram-бота
            bot_name: Имя бота для логов (client/admin)
        """
        self.bot_token = bot_token
        self.bot_name = bot_name
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.last_check_time = None
        self.last_status = None

    async def check_bot_alive(self) -> Dict:
        """
        Проверяет что бот жив и отвечает на запросы

        Returns:
            Dict с информацией о статусе бота
        """
        start_time = time.time()

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.api_url}/getMe") as response:
                    response_time = time.time() - start_time

                    if response.status == 200:
                        data = await response.json()
                        if data.get("ok"):
                            bot_info = data.get("result", {})
                            status = {
                                "status": "healthy",
                                "bot_name": self.bot_name,
                                "username": bot_info.get("username"),
                                "first_name": bot_info.get("first_name"),
                                "response_time_ms": round(response_time * 1000, 2),
                                "checked_at": datetime.now().isoformat()
                            }
                            logger.info(f"✅ {self.bot_name}: Бот работает (отклик {status['response_time_ms']}ms)")
                            self.last_status = status
                            self.last_check_time = datetime.now()
                            return status
                        else:
                            raise Exception(f"API вернул ok=false: {data}")
                    else:
                        raise Exception(f"HTTP {response.status}")

        except asyncio.TimeoutError:
            status = {
                "status": "timeout",
                "bot_name": self.bot_name,
                "error": "Таймаут при обращении к Telegram API",
                "checked_at": datetime.now().isoformat()
            }
            logger.error(f"❌ {self.bot_name}: Таймаут проверки")
            self.last_status = status
            self.last_check_time = datetime.now()
            return status

        except Exception as e:
            status = {
                "status": "error",
                "bot_name": self.bot_name,
                "error": str(e),
                "checked_at": datetime.now().isoformat()
            }
            logger.error(f"❌ {self.bot_name}: Ошибка проверки - {e}")
            self.last_status = status
            self.last_check_time = datetime.now()
            return status

    async def get_webhook_info(self) -> Dict:
        """
        Получает информацию о webhook

        Returns:
            Dict с информацией о webhook
        """
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.api_url}/getWebhookInfo") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("ok"):
                            webhook_info = data.get("result", {})
                            return {
                                "url": webhook_info.get("url", ""),
                                "has_custom_certificate": webhook_info.get("has_custom_certificate", False),
                                "pending_update_count": webhook_info.get("pending_update_count", 0),
                                "last_error_date": webhook_info.get("last_error_date"),
                                "last_error_message": webhook_info.get("last_error_message"),
                                "max_connections": webhook_info.get("max_connections")
                            }
        except Exception as e:
            logger.error(f"Ошибка получения webhook info: {e}")
            return {"error": str(e)}

    def get_last_status(self) -> Optional[Dict]:
        """Возвращает результат последней проверки"""
        return self.last_status


class DatabaseMonitor:
    """
    Монитор для проверки базы данных
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def check_db_health(self) -> Dict:
        """
        Проверяет работоспособность БД

        Returns:
            Dict с информацией о БД
        """
        try:
            # Проверяем существование файла
            if not os.path.exists(self.db_path):
                return {
                    "status": "error",
                    "error": "База данных не найдена",
                    "db_path": self.db_path
                }

            # Проверяем размер файла
            db_size = os.path.getsize(self.db_path)

            # Проверяем права доступа
            readable = os.access(self.db_path, os.R_OK)
            writable = os.access(self.db_path, os.W_OK)

            status = {
                "status": "healthy" if readable and writable else "warning",
                "db_path": self.db_path,
                "size_bytes": db_size,
                "size_mb": round(db_size / 1024 / 1024, 2),
                "readable": readable,
                "writable": writable,
                "checked_at": datetime.now().isoformat()
            }

            if status["status"] == "healthy":
                logger.info(f"✅ БД: Работает ({status['size_mb']} MB)")
            else:
                logger.warning(f"⚠️  БД: Проблемы с правами доступа")

            return status

        except Exception as e:
            status = {
                "status": "error",
                "error": str(e),
                "db_path": self.db_path,
                "checked_at": datetime.now().isoformat()
            }
            logger.error(f"❌ БД: Ошибка проверки - {e}")
            return status


class MetricsCollector:
    """
    Сборщик метрик для аналитики
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Args:
            db_manager: Экземпляр DatabaseManager
        """
        self.db_manager = db_manager

    def collect_daily_metrics(self) -> Dict:
        """
        Собирает метрики за последние 24 часа

        Returns:
            Dict с метриками
        """
        try:
            from datetime import date

            today = date.today()
            today_str = today.strftime("%Y-%m-%d")

            # Получаем статистику
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Количество заказов за сегодня
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM orders
                    WHERE date(created_at) = date('now')
                """)
                orders_today = cursor.fetchone()[0]

                # Количество новых пользователей за сегодня
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM users
                    WHERE date(created_at) = date('now')
                """)
                new_users_today = cursor.fetchone()[0]

                # Всего пользователей
                cursor.execute("SELECT COUNT(*) FROM users")
                total_users = cursor.fetchone()[0]

                # Всего заказов
                cursor.execute("SELECT COUNT(*) FROM orders")
                total_orders = cursor.fetchone()[0]

                # Популярные услуги за неделю
                cursor.execute("""
                    SELECT service_name, COUNT(*) as count
                    FROM orders
                    WHERE created_at >= datetime('now', '-7 days')
                    GROUP BY service_name
                    ORDER BY count DESC
                    LIMIT 5
                """)
                popular_services = [
                    {"service": row[0], "count": row[1]}
                    for row in cursor.fetchall()
                ]

                metrics = {
                    "date": today_str,
                    "orders_today": orders_today,
                    "new_users_today": new_users_today,
                    "total_users": total_users,
                    "total_orders": total_orders,
                    "popular_services_week": popular_services,
                    "collected_at": datetime.now().isoformat()
                }

                logger.info(f"📊 Метрики: {orders_today} заказов сегодня, "
                           f"{new_users_today} новых пользователей")

                return metrics

        except Exception as e:
            logger.error(f"Ошибка сбора метрик: {e}")
            return {
                "error": str(e),
                "collected_at": datetime.now().isoformat()
            }


async def run_health_check(client_token: str, admin_token: str, db_path: str) -> Dict:
    """
    Выполняет полную проверку работоспособности системы

    Args:
        client_token: Токен клиентского бота
        admin_token: Токен админ-бота
        db_path: Путь к базе данных

    Returns:
        Dict со сводным отчетом о здоровье системы
    """
    logger.info("🔍 Начало проверки работоспособности...")

    # Проверяем боты
    client_monitor = BotMonitor(client_token, "client_bot")
    admin_monitor = BotMonitor(admin_token, "admin_bot")

    client_status = await client_monitor.check_bot_alive()
    admin_status = await admin_monitor.check_bot_alive()

    # Проверяем БД
    db_monitor = DatabaseMonitor(db_path)
    db_status = db_monitor.check_db_health()

    # Формируем отчет
    all_healthy = (
        client_status.get("status") == "healthy" and
        admin_status.get("status") == "healthy" and
        db_status.get("status") == "healthy"
    )

    report = {
        "overall_status": "healthy" if all_healthy else "degraded",
        "client_bot": client_status,
        "admin_bot": admin_status,
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }

    if all_healthy:
        logger.info("✅ Все системы работают нормально!")
    else:
        logger.warning("⚠️  Обнаружены проблемы в работе системы")

    return report
