
import argparse
import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage  # ИЗМЕНЕНО
from aiogram.types import TelegramObject, Message
from typing import Any, Awaitable, Callable, Dict

# Загружаем переменные окружения из .env
load_dotenv()

# Импорты из проекта
from utils.db import DBManager
from utils.logger import setup_logger
from utils.config_loader import load_config

# Импортируем handlers
from handlers import start
from handlers.booking import booking_router
from handlers.mybookings import mybookings_router


async def watch_config_updates(config_path: str, config: dict, poll_interval_seconds: float = 3.0):
    """
    Отслеживает изменения в директории с конфигурационными файлами.
    ОПТИМИЗИРОВАНО: файлы читаются только если изменился mtime или версия.
    """
    last_mtime = None
    last_version = config.get('config_version', 0)

    def get_latest_mtime(path: str):
        try:
            files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.json')]
            if not files:
                return None
            return max(os.path.getmtime(f) for f in files)
        except Exception:
            return None

    last_mtime = get_latest_mtime(config_path)

    while True:
        await asyncio.sleep(poll_interval_seconds)

        current_mtime = get_latest_mtime(config_path)
        if current_mtime is None:
            continue

        if last_mtime is not None and current_mtime == last_mtime:
            continue

        try:
            new_config = load_config(config_path)
        except Exception as e:
            logging.error(f"❌ Не удалось перезагрузить конфигурацию: {e}")
            last_mtime = current_mtime
            continue

        new_version = new_config.get('config_version', 0)

        if new_version == last_version:
            last_mtime = current_mtime
            continue

        config.clear()
        config.update(new_config)

        last_mtime = current_mtime
        last_version = new_version
        logging.info(f"🔄 Конфигурация обновлена (config_version={last_version})")


class ConfigMiddleware(BaseMiddleware):
    """Middleware для передачи config, db_manager и admin_bot в handlers"""
    def __init__(self, config: dict, db_manager, admin_bot: Bot = None):
        super().__init__()
        self.config = config
        self.db_manager = db_manager
        self.admin_bot = admin_bot

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        data['config'] = self.config
        data['messages'] = self.config.get('messages', {})
        data['db_manager'] = self.db_manager
        data['admin_bot'] = self.admin_bot
        return await handler(event, data)


async def main():
    setup_logger()
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description='Telegram Business Bot V2.0')
    parser.add_argument('--config-dir', type=str, default='config',
                        help='Путь к директории с JSON файлами конфигурации.')
    args = parser.parse_args()

    try:
        config = load_config(args.config_dir)
        logger.info(f"✅ Конфигурация загружена: {config.get('business_name', 'Неизвестно')}")
    except Exception as e:
        logger.critical(f"❌ Не удалось загрузить конфигурацию из '{args.config_dir}': {e}", exc_info=True)
        return

    bot_token = os.getenv('BOT_TOKEN') or config.get('bot_token')
    
    if not bot_token:
        logger.critical("❌ BOT_TOKEN не найден ни в .env, ни в конфиге!")
        return

    business_slug = config.get('business_slug', 'default_business')
    db_manager = DBManager(business_slug)
    
    try:
        db_manager.init_db()
        logger.info(f"✅ База данных инициализирована: db_{business_slug}.sqlite")
    except Exception as e:
        logger.critical(f"❌ Ошибка инициализации БД: {e}", exc_info=True)
        return

    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    admin_bot = None
    admin_token = os.getenv('ADMIN_BOT_TOKEN')
    if admin_token:
        admin_bot = Bot(
            token=admin_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        logger.info("✅ Админ-бот для уведомлений инициализирован")
    else:
        logger.warning("⚠️ ADMIN_BOT_TOKEN не найден - уведомления будут через клиентского бота")

    storage = MemoryStorage()  # ИЗМЕНЕНО
    dp = Dispatcher(storage=storage)

    dp.update.middleware(ConfigMiddleware(config, db_manager, admin_bot))

    watcher_task = asyncio.create_task(watch_config_updates(args.config_dir, config))

    dp.include_router(start.router)
    dp.include_router(mybookings_router)
    dp.include_router(booking_router)
    
    from aiogram.filters import StateFilter
    from aiogram import F

    known_menu_texts = {
        "🏠 Меню", "◀️ Назад", "📅 Записаться", "📋 Мои записи",
        "💅 Услуги и цены", "👩‍🎨 Мастера", "🎁 Акции", "ℹ️ О нас", "❓ FAQ",
        "📍 Адрес", "📅 Записаться / Заказать", "❓ Часто задаваемые вопросы",
        "🏠 Главное меню",
    }

    @dp.message(StateFilter(None), F.text, ~F.text.startswith("/"), ~F.text.in_(known_menu_texts))
    async def unknown_message_handler(message: Message):
        from handlers.start import get_main_keyboard
        await message.answer(
            "Я не понял ваш запрос. Воспользуйтесь кнопками меню ниже:",
            reply_markup=get_main_keyboard()
        )

    logger.info(f"🚀 Бот '{config.get('business_name', 'Неизвестно')}' запущен!")
    logger.info(f"📂 Конфигурация из директории: {args.config_dir}")
    logger.info(f"💾 База данных: db_{business_slug}.sqlite")
    logger.info("💾 Хранилище FSM: MemoryStorage") # ИЗМЕНЕНО

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Получено прерывание с клавиатуры")
    except Exception as e:
        logger.error(f"❌ Ошибка во время работы: {e}", exc_info=True)
    finally:
        watcher_task.cancel()
        try:
            await watcher_task
        except asyncio.CancelledError:
            pass
        db_manager.close()
        await bot.session.close()
        if admin_bot:
            await admin_bot.session.close()
        logger.info("🛑 Бот остановлен")


if __name__ == '__main__':
    asyncio.run(main())
