import argparse
import asyncio
import logging
import os
import json
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject
from typing import Any, Awaitable, Callable, Dict

# Загружаем переменные окружения из .env
load_dotenv()

# Импорты из проекта
from utils.db_manager import DBManager

# Импортируем handlers
from handlers import start, booking, mybookings

# Настройка логирования
import logging.handlers
import os

# Создаём директорию для логов
os.makedirs('logs', exist_ok=True)

# Настраиваем логирование с ротацией
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Вывод в консоль (для journalctl)
        logging.handlers.RotatingFileHandler(
            'logs/client_bot.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
    ]
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Загрузка конфигурации из JSON"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Файл конфигурации не найден: {config_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        raise


async def watch_config_updates(config_path: str, config: dict, poll_interval_seconds: float = 3.0):
    """
    Отслеживает изменения в конфигурационном файле.
    ОПТИМИЗИРОВАНО: файл читается только если изменился mtime или версия.
    """
    last_mtime = None
    last_version = None

    try:
        last_mtime = os.path.getmtime(config_path)
    except Exception:
        last_mtime = None

    try:
        last_version = int(config.get('config_version') or 0)
    except Exception:
        last_version = 0

    while True:
        await asyncio.sleep(poll_interval_seconds)

        # Проверяем изменился ли файл
        try:
            current_mtime = os.path.getmtime(config_path)
        except Exception:
            # Если не можем получить mtime, пропускаем итерацию
            continue

        # Оптимизация: если mtime не изменился, не читаем файл
        if last_mtime is not None and current_mtime == last_mtime:
            continue

        # Файл изменился, загружаем новую конфигурацию
        try:
            new_config = load_config(config_path)
        except Exception as e:
            logger.error(f"❌ Не удалось перезагрузить конфигурацию: {e}")
            continue

        try:
            new_version = int(new_config.get('config_version') or 0)
        except Exception:
            new_version = 0

        # Проверяем, изменилась ли версия
        if new_version == last_version and last_mtime is not None:
            # Версия не изменилась, обновляем только mtime
            last_mtime = current_mtime
            continue

        # Применяем новую конфигурацию
        config.clear()
        config.update(new_config)

        last_mtime = current_mtime
        last_version = new_version
        logger.info(f"🔄 Конфигурация обновлена (config_version={last_version})")


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
        data['admin_bot'] = self.admin_bot  # Для уведомлений админам
        return await handler(event, data)


async def main():
    # ИСПРАВЛЕНО: Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Telegram Business Bot V2.0')
    parser.add_argument('--config', type=str, required=True, 
                        help='Путь к JSON конфигурации (например, configs/client_lite.json)')
    args = parser.parse_args()

    # Загрузка конфигурации
    try:
        config = load_config(args.config)
        logger.info(f"✅ Конфигурация загружена: {config.get('business_name', 'Неизвестно')}")
    except Exception as e:
        logger.error(f"❌ Не удалось загрузить конфигурацию: {e}")
        return

    # ИСПРАВЛЕНО: Получаем токен из переменных окружения
    # Приоритет: переменная окружения > config['bot_token']
    bot_token = os.getenv('BOT_TOKEN') or config.get('bot_token')
    
    if not bot_token:
        logger.error("❌ BOT_TOKEN не найден ни в .env, ни в конфиге!")
        return

    # Инициализация базы данных
    business_slug = config.get('business_slug', 'default_business')
    db_manager = DBManager(business_slug)
    
    try:
        db_manager.init_db()
        logger.info(f"✅ База данных инициализирована: db_{business_slug}.sqlite")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return

    # Создаём клиентского бота
    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Создаём админ-бота для уведомлений (если токен указан)
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

    # Создаём FSM storage с TTL (30 минут для автоочистки)
    storage = MemoryStorage()

    # Создаём Dispatcher с FSM storage
    dp = Dispatcher(storage=storage)

    # Подключаем middleware (передаём config, db_manager и admin_bot)
    dp.update.middleware(ConfigMiddleware(config, db_manager, admin_bot))

    watcher_task = asyncio.create_task(watch_config_updates(args.config, config))

    # Подключаем роутеры (порядок важен!)
    dp.include_router(start.router)          # /start и главное меню
    dp.include_router(mybookings.router)      # Мои записи (приоритет)
    dp.include_router(booking.router)         # Создание записей
    
    # Fallback для неизвестных сообщений (должен быть последним)
    from aiogram.filters import StateFilter
    from aiogram import F
    
    known_menu_texts = {
        # Новые кнопки главного меню
        "📅 Записаться",
        "📋 Мои записи",
        "💅 Услуги и цены",
        "📍 Адрес",
        "❓ FAQ",
        # Старые кнопки (обратная совместимость)
        "📅 Записаться / Заказать",
        "❓ Часто задаваемые вопросы",
        "🏠 Главное меню",
    }
    
    @dp.message(StateFilter(None), F.text, ~F.text.startswith("/"), ~F.text.in_(known_menu_texts))
    async def unknown_message_handler(message):
        """Обработчик неизвестных сообщений"""
        from handlers.start import get_main_keyboard
        await message.answer(
            "Я не понял ваш запрос. Воспользуйтесь кнопками меню ниже:",
            reply_markup=get_main_keyboard()
        )

    logger.info(f"🚀 Бот '{config.get('business_name', 'Неизвестно')}' запущен!")
    logger.info(f"📂 Конфигурация: {args.config}")
    logger.info(f"💾 База данных: db_{business_slug}.sqlite")

    try:
        # Удаляем вебхук и запускаем polling
        await bot.delete_webhook(drop_pending_updates=True)

        # Запускаем polling напрямую (без asyncio.create_task для лучшей совместимости)
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt")
    except Exception as e:
        logger.error(f"❌ Ошибка во время работы: {e}")
    finally:
        watcher_task.cancel()
        try:
            await watcher_task
        except asyncio.CancelledError:
            pass
        # Корректное закрытие ресурсов
        db_manager.close()
        await bot.session.close()
        if admin_bot:
            await admin_bot.session.close()
        logger.info("🛑 Бот остановлен")


if __name__ == '__main__':
    asyncio.run(main())
