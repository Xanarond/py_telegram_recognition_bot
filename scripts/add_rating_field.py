#!/usr/bin/env python3
"""
Скрипт миграции для добавления поля rating в существующие синопсисы
Запуск: python scripts/add_rating_field.py
Или: MONGODB_URL="mongodb://admin:admin_password@localhost:27017/telegram_bot_analytics?authSource=admin" python scripts/add_rating_field.py
"""

import asyncio
import sys
import os

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Устанавливаем MongoDB URL с авторизацией, если не установлен
if 'MONGODB_URL' not in os.environ:
    os.environ['MONGODB_URL'] = 'mongodb://admin:admin_password@localhost:27017/telegram_bot_analytics?authSource=admin'
    logger_setup = __import__('utils.logger', fromlist=['setup_logger']).setup_logger(__name__)
    logger_setup.info("⚠️ Используется MONGODB_URL по умолчанию. Установите переменную окружения для другого подключения.")

from storage.mongodb_manager import mongodb_manager
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def add_rating_field():
    """Добавляет поле rating в существующие синопсисы"""
    try:
        # Инициализируем подключение к MongoDB
        await mongodb_manager.initialize()
        
        logger.info("🔄 Начало миграции: добавление поля rating...")
        
        # Обновляем все документы, у которых нет поля rating
        result = mongodb_manager.db.synopses.update_many(
            {'rating': {'$exists': False}},
            {
                '$set': {
                    'rating': 0,
                    'rating_timestamp': None
                }
            }
        )
        
        logger.info(f"✅ Миграция завершена успешно!")
        logger.info(f"📊 Обновлено документов: {result.modified_count}")
        logger.info(f"📊 Найдено документов: {result.matched_count}")
        
        # Создаем индексы для рейтинга (если их еще нет)
        logger.info("🔄 Создание индексов для рейтинга...")
        
        try:
            mongodb_manager.db.synopses.create_index([("rating", -1)])
            logger.info("✅ Создан индекс: rating")
        except Exception as e:
            logger.info(f"ℹ️ Индекс rating уже существует: {e}")
        
        try:
            mongodb_manager.db.synopses.create_index([("user_id", 1), ("rating", -1)])
            logger.info("✅ Создан индекс: user_id + rating")
        except Exception as e:
            logger.info(f"ℹ️ Индекс user_id + rating уже существует: {e}")
        
        logger.info("🎉 Миграция полностью завершена!")
        
        # Выводим статистику по рейтингам
        logger.info("\n📊 Статистика по рейтингам:")
        
        pipeline = [
            {
                '$group': {
                    '_id': None,
                    'total': {'$sum': 1},
                    'rated': {'$sum': {'$cond': [{'$gt': ['$rating', 0]}, 1, 0]}},
                    'not_rated': {'$sum': {'$cond': [{'$eq': ['$rating', 0]}, 1, 0]}},
                }
            }
        ]
        
        stats = list(mongodb_manager.db.synopses.aggregate(pipeline))
        if stats:
            stat = stats[0]
            logger.info(f"  • Всего синопсисов: {stat.get('total', 0)}")
            logger.info(f"  • С рейтингом: {stat.get('rated', 0)}")
            logger.info(f"  • Без рейтинга: {stat.get('not_rated', 0)}")
        
        await mongodb_manager.close()
        
    except Exception as e:
        logger.error(f"❌ Ошибка миграции: {e}")
        raise


if __name__ == "__main__":
    logger.info("🚀 Запуск скрипта миграции рейтингов...")
    asyncio.run(add_rating_field())
    logger.info("👋 Скрипт миграции завершен")

