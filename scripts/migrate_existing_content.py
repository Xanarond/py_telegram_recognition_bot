#!/usr/bin/env python3
"""
Скрипт миграции существующего контента в векторную базу данных
Векторизует все статьи из MongoDB, которые еще не были векторизованы
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.mongodb_manager import mongodb_manager
from storage.vector_manager import vector_manager
from analyzers.vectorization_service import vectorization_service
from config import ENABLE_VECTOR_DB
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def migrate_content():
    """Мигрирует существующий контент в векторную БД"""
    
    if not ENABLE_VECTOR_DB:
        logger.error("❌ Векторная БД отключена в конфигурации")
        return
    
    try:
        # Инициализируем подключения
        logger.info("🔄 Инициализация подключений...")
        await mongodb_manager.initialize()
        await vector_manager.initialize()
        await vectorization_service.initialize()
        
        # Получаем существующие ID из векторной БД
        logger.info("📊 Проверяем существующие векторизованные документы...")
        existing_ids = set()
        
        try:
            collection = vector_manager.collection
            if collection:
                # Получаем все ID из коллекции
                result = collection.get(include=[])  # Только метаданные
                if result and 'ids' in result:
                    existing_ids = set(result['ids'])
                    logger.info(f"✅ Найдено {len(existing_ids)} уже векторизованных документов")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить существующие ID: {e}")
        
        # Получаем все синопсисы из MongoDB
        logger.info("📚 Получаем все синопсисы из MongoDB...")
        
        # Используем find для получения всех документов
        cursor = mongodb_manager.db.synopses.find({})
        synopses = list(cursor)
        
        total_count = len(synopses)
        logger.info(f"📊 Найдено {total_count} синопсисов в MongoDB")
        
        if total_count == 0:
            logger.info("ℹ️ Нет синопсисов для векторизации")
            return
        
        # Фильтруем уже векторизованные
        synopses_to_vectorize = [
            s for s in synopses 
            if str(s['_id']) not in existing_ids
        ]
        
        to_vectorize_count = len(synopses_to_vectorize)
        already_vectorized = total_count - to_vectorize_count
        
        logger.info(f"✅ Уже векторизовано: {already_vectorized}")
        logger.info(f"🔄 Нужно векторизовать: {to_vectorize_count}")
        
        if to_vectorize_count == 0:
            logger.info("✅ Все синопсисы уже векторизованы!")
            return
        
        # Векторизуем каждый синопсис
        success_count = 0
        error_count = 0
        
        for idx, synopsis in enumerate(synopses_to_vectorize, 1):
            synopsis_id = str(synopsis['_id'])
            title = synopsis.get('title', 'Без названия')
            
            logger.info(f"🔄 [{idx}/{to_vectorize_count}] Векторизация: {title[:50]}...")
            
            try:
                # Получаем контент (может быть в разных полях)
                content = synopsis.get('content', '')
                if not content:
                    # Пробуем получить из summary
                    content = synopsis.get('summary', '')
                if not content:
                    # Пробуем получить из analysis.summary
                    analysis = synopsis.get('analysis', {})
                    content = analysis.get('summary', '')
                
                if not content:
                    logger.warning(f"⚠️ Пропускаем {synopsis_id}: нет контента")
                    continue
                
                # Подготавливаем метаданные
                analysis = synopsis.get('analysis', {})
                metadata = {
                    'user_id': synopsis.get('user_id'),
                    'title': title,
                    'url': synopsis.get('url', ''),
                    'category': analysis.get('category', ''),
                    'tags': analysis.get('tags', []),
                    'summary': analysis.get('summary', ''),
                    'priority_level': analysis.get('priority_level', 'medium'),
                    'complexity_level': analysis.get('complexity_level', 'средний')
                }
                
                # Векторизуем
                success = await vectorization_service.vectorize_and_store(
                    synopsis_id=synopsis_id,
                    content=content,
                    metadata=metadata
                )
                
                if success:
                    success_count += 1
                    logger.info(f"✅ [{idx}/{to_vectorize_count}] Успешно векторизовано")
                else:
                    error_count += 1
                    logger.error(f"❌ [{idx}/{to_vectorize_count}] Ошибка векторизации")
                
                # Небольшая пауза, чтобы не перегружать API
                if idx % 5 == 0:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                error_count += 1
                logger.error(f"❌ [{idx}/{to_vectorize_count}] Ошибка: {e}")
        
        # Итоговая статистика
        logger.info("=" * 60)
        logger.info("📊 ИТОГИ МИГРАЦИИ:")
        logger.info(f"  Всего синопсисов в MongoDB: {total_count}")
        logger.info(f"  Уже было векторизовано: {already_vectorized}")
        logger.info(f"  Требовалось векторизовать: {to_vectorize_count}")
        logger.info(f"  ✅ Успешно векторизовано: {success_count}")
        logger.info(f"  ❌ Ошибок: {error_count}")
        logger.info("=" * 60)
        
        if error_count > 0:
            logger.warning("⚠️ Миграция завершена с ошибками")
        else:
            logger.info("🎉 Миграция успешно завершена!")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка миграции: {e}", exc_info=True)
    finally:
        # Закрываем подключения
        try:
            await mongodb_manager.close()
            if vector_manager.client:
                # Chroma клиент не требует явного закрытия
                pass
        except Exception as e:
            logger.error(f"Ошибка при закрытии подключений: {e}")


async def check_vectorization_status():
    """Проверяет статус векторизации без миграции"""
    
    if not ENABLE_VECTOR_DB:
        logger.error("❌ Векторная БД отключена в конфигурации")
        return
    
    try:
        logger.info("🔄 Инициализация подключений...")
        await mongodb_manager.initialize()
        await vector_manager.initialize()
        
        # Получаем количество документов в MongoDB
        mongo_count = mongodb_manager.db.synopses.count_documents({})
        
        # Получаем количество документов в векторной БД
        vector_count = 0
        try:
            collection = vector_manager.collection
            if collection:
                result = collection.get(include=[])
                if result and 'ids' in result:
                    vector_count = len(result['ids'])
        except Exception as e:
            logger.error(f"Ошибка получения данных из векторной БД: {e}")
        
        # Выводим статистику
        logger.info("=" * 60)
        logger.info("📊 СТАТУС ВЕКТОРИЗАЦИИ:")
        logger.info(f"  Синопсисов в MongoDB: {mongo_count}")
        logger.info(f"  Векторизовано в Chroma DB: {vector_count}")
        logger.info(f"  Не векторизовано: {mongo_count - vector_count}")
        logger.info("=" * 60)
        
        if mongo_count > vector_count:
            logger.info(f"💡 Запустите миграцию для векторизации {mongo_count - vector_count} документов")
        elif mongo_count == vector_count:
            logger.info("✅ Все документы векторизованы!")
        else:
            logger.warning("⚠️ В векторной БД больше документов, чем в MongoDB")
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки статуса: {e}", exc_info=True)
    finally:
        try:
            await mongodb_manager.close()
        except Exception as e:
            logger.error(f"Ошибка при закрытии подключений: {e}")


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Миграция существующего контента в векторную БД'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Только проверить статус векторизации без миграции'
    )
    parser.add_argument(
        '--migrate',
        action='store_true',
        help='Выполнить миграцию существующего контента'
    )
    
    args = parser.parse_args()
    
    if args.check:
        logger.info("🔍 Проверка статуса векторизации...")
        asyncio.run(check_vectorization_status())
    elif args.migrate:
        logger.info("🚀 Запуск миграции контента...")
        asyncio.run(migrate_content())
    else:
        # По умолчанию показываем статус
        logger.info("🔍 Проверка статуса векторизации...")
        asyncio.run(check_vectorization_status())
        logger.info("\n💡 Для запуска миграции используйте: python scripts/migrate_existing_content.py --migrate")


if __name__ == "__main__":
    main()

