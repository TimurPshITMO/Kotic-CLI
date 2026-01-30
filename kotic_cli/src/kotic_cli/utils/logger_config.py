import logging
import os
import sys

def setup_logging():
    """
    Настраивает централизованное логирование для приложения.
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Создаем логгер
    logger = logging.getLogger("kotic_cli")
    logger.setLevel(log_level)

    # Предотвращаем дублирование логов, если обработчик уже был добавлен
    if not logger.handlers:
        # Консольный обработчик
        console_handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

# Инициализируем логгер при импорте модуля
logger = setup_logging()