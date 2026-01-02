"""
Модуль настройки логирования с маскировкой персональных данных и токенов.
"""

import logging
import re
from logging.handlers import RotatingFileHandler
import sys


# Размер файла лога в байтах (5 MB)
MAX_BYTES = 5 * 1024 * 1024
# Количество бэкап-файлов
BACKUP_COUNT = 3
# Имя файла лога
LOG_FILE = "bot.log"


class SensitiveDataFilter(logging.Filter):
    """
    Фильтр для маскировки чувствительных данных в логах.

    Маскирует:
    - Токены ботов (BOT_TOKEN, ADMIN_BOT_TOKEN)
    - Номера телефонов
    - Email адреса
    """

    # Паттерны для токенов Telegram ботов (формат: 123456789:ABCdefGHI...)
    TOKEN_PATTERN = re.compile(r'\b(\d{8,10}):([A-Za-z0-9_-]{35,})\b')

    # Паттерны для российских телефонов
    PHONE_PATTERN = re.compile(r'(\+?[78])(\d{3})(\d{3})(\d{4})')

    # Паттерны для email
    EMAIL_PATTERN = re.compile(r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})')

    def filter(self, record):
        """Применяет маскировку к сообщению лога."""
        if record.msg:
            record.msg = self._mask_sensitive_data(str(record.msg))
        if record.args:
            record.args = tuple(
                self._mask_sensitive_data(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True

    def _mask_sensitive_data(self, text: str) -> str:
        """Маскирует чувствительные данные в тексте."""
        if not text:
            return text

        # Маскируем токены ботов
        text = self.TOKEN_PATTERN.sub(r'\1:***TOKEN_MASKED***', text)

        # Маскируем телефоны: +7999***4567
        text = self.PHONE_PATTERN.sub(r'\1\2***\4', text)

        # Маскируем email: ***@domain.com
        text = self.EMAIL_PATTERN.sub(r'***@\2', text)

        return text


class ColoredFormatter(logging.Formatter):
    """
    Форматтер с цветовой подсветкой уровней логирования для консоли.
    """

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def __init__(self, fmt=None, datefmt=None, use_colors=True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors

    def format(self, record):
        if self.use_colors:
            color = self.COLORS.get(record.levelname, '')
            record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger(use_colors: bool = True):
    """
    Настраивает глобальный логгер для записи в файл и вывода в консоль.

    Args:
        use_colors: Использовать ли цветную подсветку в консоли (по умолчанию True)
    """
    # Формат лога
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Создаём обработчики
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(log_format, date_format))

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter(log_format, date_format, use_colors=use_colors))

    # Добавляем фильтр для маскировки чувствительных данных
    sensitive_filter = SensitiveDataFilter()
    file_handler.addFilter(sensitive_filter)
    console_handler.addFilter(sensitive_filter)

    # Устанавливаем базовую конфигурацию для корневого логгера
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[file_handler, console_handler],
    )

    # Устанавливаем более высокий уровень логирования для библиотек
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)

    # Сообщение о том, что логгер успешно настроен
    logging.info("Logger has been successfully configured with sensitive data masking.")


def get_logger(name: str) -> logging.Logger:
    """
    Получает настроенный логгер с указанным именем.

    Args:
        name: Имя логгера (обычно __name__)

    Returns:
        logging.Logger: Настроенный логгер
    """
    return logging.getLogger(name)
