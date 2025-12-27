#!/usr/bin/env python3
"""
Скрипт мониторинга Telegram-бота

Использование:
    python monitor.py                    # Одноразовая проверка
    python monitor.py --watch            # Непрерывный мониторинг (каждые 5 минут)
    python monitor.py --metrics          # Показать метрики
    python monitor.py --webhook          # Проверить webhook
"""
import asyncio
import logging
import os
import sys
import argparse
import json
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.monitoring import BotMonitor, DatabaseMonitor, MetricsCollector, run_health_check
from utils.db_manager import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_banner():
    """Выводит красивый баннер"""
    print("=" * 70)
    print("  🔍 МОНИТОРИНГ TELEGRAM-БОТА")
    print("=" * 70)
    print()


def print_status_report(report: dict):
    """
    Выводит отчет о статусе в читаемом виде

    Args:
        report: Словарь с результатами проверки
    """
    print(f"📅 Время проверки: {report['timestamp']}")
    print()

    # Общий статус
    if report['overall_status'] == 'healthy':
        print("✅ СТАТУС: Все системы работают нормально")
    else:
        print("⚠️  СТАТУС: Обнаружены проблемы")
    print()

    # Клиентский бот
    client = report['client_bot']
    print("🤖 Клиентский бот:")
    if client['status'] == 'healthy':
        print(f"   ✅ Работает (@{client['username']})")
        print(f"   ⏱  Отклик: {client['response_time_ms']}ms")
    else:
        print(f"   ❌ Ошибка: {client.get('error', 'Неизвестная ошибка')}")
    print()

    # Админ-бот
    admin = report['admin_bot']
    print("👨‍💼 Админ-бот:")
    if admin['status'] == 'healthy':
        print(f"   ✅ Работает (@{admin['username']})")
        print(f"   ⏱  Отклик: {admin['response_time_ms']}ms")
    else:
        print(f"   ❌ Ошибка: {admin.get('error', 'Неизвестная ошибка')}")
    print()

    # База данных
    db = report['database']
    print("💾 База данных:")
    if db['status'] == 'healthy':
        print(f"   ✅ Работает")
        print(f"   📦 Размер: {db['size_mb']} MB")
        print(f"   📝 Чтение: {'✓' if db['readable'] else '✗'}")
        print(f"   ✏️  Запись: {'✓' if db['writable'] else '✗'}")
    else:
        print(f"   ❌ Ошибка: {db.get('error', 'Неизвестная ошибка')}")
    print()


async def check_webhook(client_token: str, admin_token: str):
    """
    Проверяет статус webhook

    Args:
        client_token: Токен клиентского бота
        admin_token: Токен админ-бота
    """
    print_banner()
    print("🔗 Проверка Webhook\n")

    client_monitor = BotMonitor(client_token, "client_bot")
    admin_monitor = BotMonitor(admin_token, "admin_bot")

    # Клиентский бот
    print("🤖 Клиентский бот:")
    client_webhook = await client_monitor.get_webhook_info()
    if client_webhook.get('url'):
        print(f"   ✅ URL: {client_webhook['url']}")
        print(f"   📨 Ожидающих обновлений: {client_webhook.get('pending_update_count', 0)}")
        if client_webhook.get('last_error_message'):
            print(f"   ⚠️  Последняя ошибка: {client_webhook['last_error_message']}")
    else:
        print("   ℹ️  Webhook не установлен (используется polling)")
    print()

    # Админ-бот
    print("👨‍💼 Админ-бот:")
    admin_webhook = await admin_monitor.get_webhook_info()
    if admin_webhook.get('url'):
        print(f"   ✅ URL: {admin_webhook['url']}")
        print(f"   📨 Ожидающих обновлений: {admin_webhook.get('pending_update_count', 0)}")
        if admin_webhook.get('last_error_message'):
            print(f"   ⚠️  Последняя ошибка: {admin_webhook['last_error_message']}")
    else:
        print("   ℹ️  Webhook не установлен (используется polling)")
    print()


def show_metrics(db_path: str):
    """
    Показывает метрики за последнее время

    Args:
        db_path: Путь к базе данных
    """
    print_banner()
    print("📊 Метрики бота\n")

    try:
        db_manager = DatabaseManager(db_path)
        collector = MetricsCollector(db_manager)
        metrics = collector.collect_daily_metrics()

        if 'error' in metrics:
            print(f"❌ Ошибка сбора метрик: {metrics['error']}")
            return

        print(f"📅 Дата: {metrics['date']}")
        print()
        print("📈 Сегодня:")
        print(f"   📝 Новых заказов: {metrics['orders_today']}")
        print(f"   👤 Новых пользователей: {metrics['new_users_today']}")
        print()
        print("📊 Всего:")
        print(f"   👥 Пользователей: {metrics['total_users']}")
        print(f"   📋 Заказов: {metrics['total_orders']}")
        print()

        if metrics['popular_services_week']:
            print("🔥 Популярные услуги (за неделю):")
            for i, service in enumerate(metrics['popular_services_week'], 1):
                print(f"   {i}. {service['service']}: {service['count']} заказов")
        else:
            print("ℹ️  Нет данных по заказам за последнюю неделю")
        print()

    except Exception as e:
        print(f"❌ Ошибка: {e}")


async def watch_mode(client_token: str, admin_token: str, db_path: str, interval: int = 300):
    """
    Непрерывный мониторинг с заданным интервалом

    Args:
        client_token: Токен клиентского бота
        admin_token: Токен админ-бота
        db_path: Путь к базе данных
        interval: Интервал проверки в секундах (по умолчанию 5 минут)
    """
    print(f"👁️  Запущен непрерывный мониторинг (интервал: {interval}с)")
    print("Нажмите Ctrl+C для остановки\n")

    try:
        while True:
            print_banner()
            report = await run_health_check(client_token, admin_token, db_path)
            print_status_report(report)

            # Сохраняем отчет в файл
            log_dir = "logs/monitoring"
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"health_{datetime.now().strftime('%Y%m%d')}.json")

            with open(log_file, 'a') as f:
                f.write(json.dumps(report) + "\n")

            print(f"📝 Отчет сохранен: {log_file}")
            print(f"\n⏳ Следующая проверка через {interval // 60} минут...\n")

            await asyncio.sleep(interval)

    except KeyboardInterrupt:
        print("\n👋 Мониторинг остановлен")


async def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description='Мониторинг Telegram-бота',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--watch', action='store_true',
                       help='Непрерывный мониторинг (каждые 5 минут)')
    parser.add_argument('--interval', type=int, default=300,
                       help='Интервал проверки в секундах (по умолчанию 300)')
    parser.add_argument('--metrics', action='store_true',
                       help='Показать метрики')
    parser.add_argument('--webhook', action='store_true',
                       help='Проверить статус webhook')
    parser.add_argument('--json', action='store_true',
                       help='Вывод в формате JSON')

    args = parser.parse_args()

    # Загружаем переменные окружения
    from dotenv import load_dotenv
    load_dotenv()

    client_token = os.getenv("CLIENT_BOT_TOKEN")
    admin_token = os.getenv("ADMIN_BOT_TOKEN")
    db_path = "data/bot_data.sqlite"

    if not client_token or not admin_token:
        logger.error("❌ Не заданы токены в .env файле!")
        logger.error("Создайте .env файл по образцу .env.example")
        return

    # Выбираем режим работы
    if args.metrics:
        show_metrics(db_path)
    elif args.webhook:
        await check_webhook(client_token, admin_token)
    elif args.watch:
        await watch_mode(client_token, admin_token, db_path, args.interval)
    else:
        # Одноразовая проверка
        print_banner()
        report = await run_health_check(client_token, admin_token, db_path)

        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print_status_report(report)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Мониторинг остановлен")
