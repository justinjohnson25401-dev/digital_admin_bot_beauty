
import logging
from logging.handlers import RotatingFileHandler
import sys

# Размер файла лога в байтах (5 MB)
MAX_BYTES = 5 * 1024 * 1024
# Количество бэкап-файлов
BACKUP_COUNT = 3
# Имя файла лога
LOG_FILE = "bot.log"

def setup_logger():
    """Настраивает глобальный логгер для записи в файл и вывода в консоль."""
    # Устанавливаем базовую конфигурацию для корневого логгера
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            RotatingFileHandler(
                LOG_FILE,
                maxBytes=MAX_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            ),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Устанавливаем более высокий уровень логирования для библиотек, чтобы не засорять лог
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Сообщение о том, что логгер успешно настроен
    logging.info("Logger has been successfully configured.")

