
import logging
import sys

class SensitiveDataFilter(logging.Filter):
    """
    Фильтр для скрытия чувствительных данных в логах, например, токенов.
    """
    def filter(self, record):
        # Здесь можно будет добавить логику скрытия данных, если понадобится.
        # Например, скрывать токен бота.
        return True

def setup_logger():
    """
    Настраивает и конфигурирует стандартный логгер Python.
    """
    # Удаляем все существующие обработчики у корневого логгера
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Конфигурируем логгер
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
        stream=sys.stdout,
    )

    # Добавляем фильтр (пока он ничего не делает, но готов к использованию)
    logger = logging.getLogger()
    logger.addFilter(SensitiveDataFilter())
    
    # Устанавливаем уровень INFO для aiogram, чтобы избежать спама DEBUG-сообщениями
    logging.getLogger('aiogram').setLevel(logging.INFO)
    logging.getLogger('aiogram.dispatcher').setLevel(logging.INFO)

    logging.info("Logger configured.")
