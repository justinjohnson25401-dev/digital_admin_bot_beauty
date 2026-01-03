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

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from utils.db import DatabaseManager
from utils.config_loader import load_config  # ИСПРАВЛЕННЫЙ ИМПОРТ
from utils.logger import setup_logger

from admin_bot.middleware import (
    AdminAuthMiddleware,
    AdminPinMiddleware,
    ConfigMiddleware,
    PinMiddlewareInjector,
)
from admin_bot.handlers import setup_handlers

# Импортируем admin handlers (роутеры)
from admin_handlers import (
    services_editor,
    settings_editor,
    business_settings,
    texts_editor,
    notifications_editor,
    staff_editor,
    promotions_editor,
)


async def main():
    """Главная функция админ-бота"""
    parser = argparse.ArgumentParser(description='Admin Bot for Bot-Business V2.0')
    # Аргумент изменен на --config-dir для единообразия с main.py
    parser.add_argument('--config-dir', type=str, default='config', help='Path to config directory')
    args = parser.parse_args()

    # Загрузка конфигурации
    try:
        config = load_config(args.config_dir)
        # Инициализация логгера после загрузки конфига
        logger = setup_logger(config['business_slug'], 'admin_bot')
        logger.info(f"✅ Config loaded: {config.get('business_name')}")
    except Exception as e:
        logging.critical(f"❌ Failed to load config from '{args.config_dir}': {e}", exc_info=True)
        return

    # Токен админ-бота
    admin_token = os.getenv('ADMIN_BOT_TOKEN')
    if not admin_token:
        logger.error("❌ ADMIN_BOT_TOKEN not found in .env!")
        return

    # Инициализация БД
    db_manager = DatabaseManager(config['business_slug'])
    try:
        logger.info(f"✅ Database ready: db_{config['business_slug']}.sqlite")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        return

    # Создаём бота и диспетчер
    bot = Bot(token=admin_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Подключаем middlewares
    # УДАЛЕНО: config_manager больше не используется
    dp.update.middleware(ConfigMiddleware(config, db_manager))
    dp.update.middleware(AdminAuthMiddleware(config))
    pin_middleware = AdminPinMiddleware(config)
    dp.update.middleware(pin_middleware)
    dp.update.middleware(PinMiddlewareInjector(pin_middleware))

    # Регистрируем handlers из модулей
    setup_handlers(dp, pin_middleware)

    # Подключаем роутеры из admin_handlers
    dp.include_router(services_editor.router)
    dp.include_router(settings_editor.router)
    dp.include_router(business_settings.router)
    dp.include_router(texts_editor.router)
    dp.include_router(notifications_editor.router)
    dp.include_router(staff_editor.router)
    dp.include_router(promotions_editor.router)

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
