import logging
import os
from config import LOG_LEVEL, LOG_DIR, LOG_FILE

def setup_logger(name: str = __name__) -> logging.Logger:
    """Настраивает и возвращает логгер"""
    # Создаем директорию для логов
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # Настройка логирования
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=getattr(logging, LOG_LEVEL),
        handlers=[
            logging.FileHandler(os.path.join(LOG_DIR, LOG_FILE), encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(name) 