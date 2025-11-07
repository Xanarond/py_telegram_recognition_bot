#!/usr/bin/env python3
"""
Скрипт для проверки подключения к базам данных
"""

import asyncio
from sqlalchemy import text

from config import ensure_directories
from storage.database_manager import database_manager
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def check_postgres():
    """Проверка подключения к PostgreSQL"""
    try:
        logger.info("🔄 Проверка подключения к PostgreSQL...")
        
        # Проверяем подключение
        async with database_manager.postgres.get_session() as session:
            result = await session.execute(text("SELECT 1"))
            if result.scalar() == 1:
                logger.info("✅ PostgreSQL подключение работает")
                return True
            else:
                logger.error("❌ PostgreSQL подключение не работает")
                return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к PostgreSQL: {e}")
        return False


async def check_mongodb():
    """Проверка подключения к MongoDB"""
    try:
        logger.info("🔄 Проверка подключения к MongoDB...")
        
        # Проверяем подключение
        await database_manager.mongodb.initialize()
        database_manager.mongodb.client.admin.command('ping')
        logger.info("✅ MongoDB подключение работает")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к MongoDB: {e}")
        return False


async def main():
    """Главная функция"""
    logger.info("🚀 Запуск проверки подключения к базам данных")
    
    # Создаем необходимые директории
    ensure_directories()
    
    # Инициализируем базы данных
    await database_manager.initialize()
    
    # Проверяем PostgreSQL
    postgres_ok = await check_postgres()
    
    # Проверяем MongoDB
    mongodb_ok = await check_mongodb()
    
    # Закрываем подключения
    await database_manager.close()
    
    # Выводим результаты
    logger.info("\n=== Результаты проверки ===")
    logger.info(f"PostgreSQL: {'✅ Работает' if postgres_ok else '❌ Не работает'}")
    logger.info(f"MongoDB: {'✅ Работает' if mongodb_ok else '❌ Не работает'}")
    
    if postgres_ok and mongodb_ok:
        logger.info("✅ Все базы данных работают")
        return 0
    else:
        logger.error("❌ Проблемы с подключением к базам данных")
        return 1


if __name__ == '__main__':
    try:
        exit_code = asyncio.run(main())
        exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Проверка прервана пользователем")
        exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        exit(1) 