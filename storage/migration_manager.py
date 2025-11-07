"""
Менеджер миграции данных
Перенос данных из JSON файлов в PostgreSQL и MongoDB
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any

from config import STATS_FILE, ENABLE_DATA_MIGRATION
from storage.postgres_manager import postgres_manager
from storage.mongodb_manager import mongodb_manager
from utils.logger import setup_logger

logger = setup_logger(__name__)


class MigrationManager:
    """Менеджер для миграции данных из JSON в БД"""
    
    def __init__(self):
        self.migration_completed = False
    
    async def migrate_all_data(self) -> bool:
        """Выполняет полную миграцию данных"""
        if not ENABLE_DATA_MIGRATION:
            logger.info("ℹ️ Миграция данных отключена в настройках")
            return True
        
        if self.migration_completed:
            logger.info("ℹ️ Миграция уже выполнена")
            return True
        
        try:
            logger.info("🔄 Начинаю миграцию данных из JSON в базы данных...")
            
            # Инициализируем подключения к БД
            await postgres_manager.initialize()
            await mongodb_manager.initialize()
            
            # Загружаем данные из JSON
            json_data = await self._load_json_stats()
            if not json_data:
                logger.info("ℹ️ JSON файл со статистикой не найден или пуст")
                self.migration_completed = True
                return True
            
            # Мигрируем пользователей в PostgreSQL
            migrated_users = await self._migrate_users_to_postgres(json_data)
            logger.info(f"✅ Мигрировано пользователей: {migrated_users}")
            
            # Мигрируем синопсисы в MongoDB
            migrated_synopses = await self._migrate_synopses_to_mongodb(json_data)
            logger.info(f"✅ Мигрировано синопсисов: {migrated_synopses}")
            
            # Создаем резервную копию JSON файла
            await self._backup_json_file()
            
            self.migration_completed = True
            logger.info("🎉 Миграция данных успешно завершена!")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка миграции данных: {e}")
            return False
    
    async def _load_json_stats(self) -> Dict[str, Any]:
        """Загружает статистику из JSON файла"""
        try:
            if not os.path.exists(STATS_FILE):
                return {}
            
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Конвертируем строковые ключи в int
                return {int(k): v for k, v in data.items()}
                
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки JSON статистики: {e}")
            return {}
    
    async def _migrate_users_to_postgres(self, json_data: Dict[int, Any]) -> int:
        """Мигрирует пользователей в PostgreSQL"""
        migrated_count = 0
        
        for user_id, user_data in json_data.items():
            try:
                # Создаем пользователя (если не существует)
                user = await postgres_manager.create_user(
                    telegram_id=user_id,
                    username=None,  # В JSON нет информации о username
                    first_name=None,
                    last_name=None,
                    is_admin=False  # Определим администраторов отдельно
                )
                
                if user:
                    # Обновляем статистику пользователя
                    await self._migrate_user_stats_to_postgres(user_id, user_data)
                    migrated_count += 1
                    
            except Exception as e:
                logger.error(f"❌ Ошибка миграции пользователя {user_id}: {e}")
        
        return migrated_count
    
    async def _migrate_user_stats_to_postgres(self, user_id: int, user_data: Dict[str, Any]):
        """Мигрирует статистику пользователя в PostgreSQL"""
        try:
            async with postgres_manager.get_session() as session:
                from storage.postgres_models import User, UserUsageStats
                from sqlalchemy import select
                
                # Получаем пользователя
                result = await session.execute(
                    select(User).filter(User.telegram_id == user_id)
                )
                user = result.scalars().first()
                
                if not user:
                    return
                
                # Получаем или создаем статистику
                result = await session.execute(
                    select(UserUsageStats).filter(UserUsageStats.user_id == user.id)
                )
                stats = result.scalars().first()
                
                if not stats:
                    stats = UserUsageStats(user_id=user.id)
                    session.add(stats)
                
                # Переносим данные
                stats.total_analyses = user_data.get('total_analyzed', 0)
                stats.priority_high_count = user_data.get('priority_high', 0)
                stats.priority_medium_count = user_data.get('priority_medium', 0)
                stats.priority_low_count = user_data.get('priority_low', 0)
                stats.complexity_beginner_count = user_data.get('complexity_beginner', 0)
                stats.complexity_intermediate_count = user_data.get('complexity_intermediate', 0)
                stats.complexity_advanced_count = user_data.get('complexity_advanced', 0)
                
                # Средние значения
                relevance_scores = user_data.get('relevance_scores', [])
                if relevance_scores:
                    avg_relevance = sum(relevance_scores) / len(relevance_scores)
                    stats.avg_relevance_score = int(avg_relevance * 100)
                
                reading_times = user_data.get('reading_times', [])
                if reading_times:
                    avg_reading_time = sum(reading_times) / len(reading_times)
                    stats.avg_reading_time = int(avg_reading_time)
                
                # Временные метки (используем текущее время, так как в JSON нет точных дат)
                if stats.total_analyses > 0:
                    stats.first_analysis = datetime.now()
                    stats.last_analysis = datetime.now()
                
                await session.commit()
                
        except Exception as e:
            logger.error(f"❌ Ошибка миграции статистики пользователя {user_id}: {e}")
    
    async def _migrate_synopses_to_mongodb(self, json_data: Dict[int, Any]) -> int:
        """Мигрирует синопсисы в MongoDB"""
        migrated_count = 0
        
        for user_id, user_data in json_data.items():
            sources = user_data.get('sources', [])
            
            for source in sources:
                try:
                    # Подготавливаем данные для MongoDB
                    analysis_data = {
                        'url': source.get('url', ''),
                        'title': source.get('title', 'Без названия'),
                        'domain_emoji': source.get('domain_emoji', '📄'),
                        'analysis': {
                            'category': source.get('category', 'unknown'),
                            'relevance_score': source.get('relevance_score', '5'),
                            'priority_level': source.get('priority_level', 'medium'),
                            'complexity_level': source.get('complexity_level', 'средний'),
                            'estimated_reading_time': source.get('estimated_reading_time', '5'),
                            'tags': source.get('tags', []),
                            'summary': f"Мигрировано из JSON. Категория: {source.get('category', 'unknown')}",
                            'key_points': []
                        }
                    }
                    
                    # Сохраняем в MongoDB
                    synopsis_id = await mongodb_manager.save_synopsis(user_id, analysis_data)
                    
                    if synopsis_id:
                        # Обновляем статус прочтения
                        read_status = source.get('read_status', 'unread')
                        if read_status == 'read':
                            await mongodb_manager.mark_synopsis_as_read(synopsis_id, 'read')
                        
                        migrated_count += 1
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка миграции синопсиса пользователя {user_id}: {e}")
        
        return migrated_count
    
    async def _backup_json_file(self):
        """Создает резервную копию JSON файла"""
        try:
            if os.path.exists(STATS_FILE):
                backup_file = f"{STATS_FILE}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                with open(STATS_FILE, 'r', encoding='utf-8') as src:
                    with open(backup_file, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                
                logger.info(f"✅ Создана резервная копия: {backup_file}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка создания резервной копии: {e}")
    
    async def check_migration_status(self) -> Dict[str, Any]:
        """Проверяет статус миграции"""
        try:
            # Проверяем наличие данных в PostgreSQL
            postgres_users = 0
            try:
                await postgres_manager.initialize()
                async with postgres_manager.get_session() as session:
                    from storage.postgres_models import User
                    from sqlalchemy import select, func
                    result = await session.execute(select(func.count(User.id)))
                    postgres_users = result.scalar()
            except:
                pass
            
            # Проверяем наличие данных в MongoDB
            mongodb_synopses = 0
            try:
                await mongodb_manager.initialize()
                mongodb_synopses = mongodb_manager.db.synopses.count_documents({})
            except:
                pass
            
            # Проверяем наличие JSON файла
            json_exists = os.path.exists(STATS_FILE)
            json_size = 0
            if json_exists:
                json_size = os.path.getsize(STATS_FILE)
            
            return {
                'migration_completed': self.migration_completed,
                'postgres_users': postgres_users,
                'mongodb_synopses': mongodb_synopses,
                'json_file_exists': json_exists,
                'json_file_size': json_size,
                'migration_enabled': ENABLE_DATA_MIGRATION
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки статуса миграции: {e}")
            return {}


# Глобальный экземпляр менеджера
migration_manager = MigrationManager() 