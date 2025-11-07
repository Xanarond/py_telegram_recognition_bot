"""
Объединенный менеджер баз данных
Координирует работу с PostgreSQL и MongoDB
"""

from typing import Dict, List, Optional, Any

from storage.postgres_manager import postgres_manager
from storage.mongodb_manager import mongodb_manager
from storage.migration_manager import migration_manager
from utils.logger import setup_logger

logger = setup_logger(__name__)


class DatabaseManager:
    """Объединенный менеджер для работы с базами данных"""
    
    def __init__(self):
        self.postgres = postgres_manager
        self.mongodb = mongodb_manager
        self.migration = migration_manager
        self._initialized = False
    
    async def initialize(self):
        """Инициализация всех подключений к БД"""
        try:
            logger.info("🔄 Инициализация подключений к базам данных...")
            
            # Инициализируем PostgreSQL
            await self.postgres.initialize()
            
            # Инициализируем MongoDB
            await self.mongodb.initialize()
            
            # Выполняем миграцию данных (если необходимо)
            await self.migration.migrate_all_data()
            
            self._initialized = True
            logger.info("✅ Все базы данных инициализированы")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации баз данных: {e}")
            raise
    
    # === Управление пользователями ===
    
    async def create_user(self, telegram_id: int, username: str = None, 
                         first_name: str = None, last_name: str = None, 
                         is_admin: bool = False) -> bool:
        """Создает нового пользователя"""
        try:
            user = await self.postgres.create_user(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                is_admin=is_admin
            )
            return user is not None
        except Exception as e:
            logger.error(f"❌ Ошибка создания пользователя {telegram_id}: {e}")
            return False
    
    async def is_user_authorized(self, telegram_id: int) -> bool:
        """Проверяет авторизацию пользователя"""
        try:
            return await self.postgres.is_user_authorized(telegram_id)
        except Exception as e:
            logger.error(f"❌ Ошибка проверки авторизации {telegram_id}: {e}")
            return False
    
    async def is_user_admin(self, telegram_id: int) -> bool:
        """Проверяет права администратора"""
        try:
            return await self.postgres.is_user_admin(telegram_id)
        except Exception as e:
            logger.error(f"❌ Ошибка проверки прав администратора {telegram_id}: {e}")
            return False
    
    async def get_user(self, telegram_id: int):
        """Получает информацию о пользователе"""
        try:
            return await self.postgres.get_user(telegram_id)
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователя {telegram_id}: {e}")
            return None
    
    async def update_user_activity(self, telegram_id: int) -> bool:
        """Обновляет активность пользователя"""
        try:
            return await self.postgres.update_user_activity(telegram_id)
        except Exception as e:
            logger.error(f"❌ Ошибка обновления активности {telegram_id}: {e}")
            return False
    
    # === Управление контентом и синопсисами ===
    
    async def save_analysis(self, user_id: int, analysis_data: Dict[str, Any]) -> Optional[str]:
        """Сохраняет анализ контента в обе БД"""
        try:
            # Сохраняем синопсис в MongoDB
            synopsis_id = await self.mongodb.save_synopsis(user_id, analysis_data)
            
            # Обновляем статистику пользователя в PostgreSQL
            await self.postgres.update_user_stats(user_id, analysis_data)
            
            return synopsis_id
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения анализа для пользователя {user_id}: {e}")
            return None
    
    async def get_user_sources(self, user_id: int, page: int = 1, per_page: int = 10,
                              read_filter: str = 'all', category_filter: str = None,
                              priority_filter: str = None, search_query: str = None) -> Dict[str, Any]:
        """Получает источники пользователя из MongoDB"""
        try:
            return await self.mongodb.get_user_synopses(
                user_id=user_id,
                page=page,
                per_page=per_page,
                read_filter=read_filter,
                category_filter=category_filter,
                priority_filter=priority_filter,
                search_query=search_query
            )
        except Exception as e:
            logger.error(f"❌ Ошибка получения источников пользователя {user_id}: {e}")
            return {'synopses': [], 'total_count': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}
    
    async def get_synopsis_by_id(self, synopsis_id: str) -> Optional[Dict[str, Any]]:
        """Получает полный синопсис по ID"""
        try:
            return await self.mongodb.get_synopsis_by_id(synopsis_id)
        except Exception as e:
            logger.error(f"❌ Ошибка получения синопсиса {synopsis_id}: {e}")
            return None
    
    async def mark_source_as_read(self, synopsis_id: str, read_status: str = 'read') -> bool:
        """Отмечает источник как прочитанный/непрочитанный"""
        try:
            return await self.mongodb.mark_synopsis_as_read(synopsis_id, read_status)
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статуса синопсиса {synopsis_id}: {e}")
            return False
    
    async def update_source_rating(self, synopsis_id: str, rating: int) -> bool:
        """Обновляет рейтинг источника"""
        try:
            return await self.mongodb.update_synopsis_rating(synopsis_id, rating)
        except Exception as e:
            logger.error(f"❌ Ошибка обновления рейтинга синопсиса {synopsis_id}: {e}")
            return False
    
    async def delete_synopsis(self, synopsis_id: str, user_id: int) -> bool:
        """Удаляет синопсис пользователя"""
        try:
            return await self.mongodb.delete_synopsis(synopsis_id, user_id)
        except Exception as e:
            logger.error(f"❌ Ошибка удаления синопсиса {synopsis_id}: {e}")
            return False
    
    # === Статистика ===
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Получает объединенную статистику пользователя"""
        try:
            # Получаем статистику из PostgreSQL
            postgres_stats = await self.postgres.get_user_stats(user_id) or {}
            
            # Получаем статистику контента из MongoDB
            mongodb_stats = await self.mongodb.get_user_content_stats(user_id) or {}
            
            # Объединяем статистику
            combined_stats = {
                # Основные показатели
                'total_analyzed': mongodb_stats.get('total_synopses', 0),
                'total_exports': postgres_stats.get('total_exports', 0),
                'total_commands': postgres_stats.get('total_commands', 0),
                
                # Статистика прочтения
                'read_count': mongodb_stats.get('read_count', 0),
                'unread_count': mongodb_stats.get('unread_count', 0),
                
                # Приоритеты
                'priority_high': mongodb_stats.get('priority_high', 0),
                'priority_medium': mongodb_stats.get('priority_medium', 0),
                'priority_low': mongodb_stats.get('priority_low', 0),
                
                # Сложность
                'complexity_beginner': postgres_stats.get('complexity_beginner_count', 0),
                'complexity_intermediate': postgres_stats.get('complexity_intermediate_count', 0),
                'complexity_advanced': postgres_stats.get('complexity_advanced_count', 0),
                
                # Средние значения
                'avg_relevance': mongodb_stats.get('avg_relevance', 0),
                'avg_reading_time': mongodb_stats.get('avg_reading_time', 0),
                
                # Рейтинги
                'avg_rating': mongodb_stats.get('avg_rating', 0),
                'rated_count': mongodb_stats.get('rated_count', 0),
                'rating_5': mongodb_stats.get('rating_5', 0),
                'rating_4': mongodb_stats.get('rating_4', 0),
                'rating_3': mongodb_stats.get('rating_3', 0),
                'rating_2': mongodb_stats.get('rating_2', 0),
                'rating_1': mongodb_stats.get('rating_1', 0),
                
                # Категории и домены
                'categories': mongodb_stats.get('categories', []),
                'domains': mongodb_stats.get('domains', []),
                
                # Временные метки
                'first_analysis': postgres_stats.get('first_analysis'),
                'last_analysis': postgres_stats.get('last_analysis')
            }
            
            return combined_stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики пользователя {user_id}: {e}")
            return {}
    
    async def get_trending_topics(self, days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
        """Получает популярные темы"""
        try:
            return await self.mongodb.get_trending_topics(days, limit)
        except Exception as e:
            logger.error(f"❌ Ошибка получения популярных тем: {e}")
            return []
    
    async def clear_user_data(self, user_id: int) -> bool:
        """Очищает все данные пользователя из обеих БД"""
        try:
            # Очищаем синопсисы из MongoDB
            mongodb_result = await self.mongodb.clear_user_synopses(user_id)
            
            # Сбрасываем статистику в PostgreSQL
            postgres_result = await self.postgres.reset_user_stats(user_id)
            
            return mongodb_result and postgres_result
            
        except Exception as e:
            logger.error(f"❌ Ошибка очистки данных пользователя {user_id}: {e}")
            return False
    
    # === Административные функции ===
    
    async def get_all_users(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """Получает список всех пользователей"""
        try:
            users = await self.postgres.get_all_users(include_inactive)
            
            # Конвертируем в словари для удобства
            user_list = []
            for user in users:
                user_dict = {
                    'telegram_id': user.telegram_id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_active': user.is_active,
                    'is_admin': user.is_admin,
                    'created_at': user.created_at,
                    'last_activity': user.last_activity
                }
                user_list.append(user_dict)
            
            return user_list
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка пользователей: {e}")
            return []
    
    async def set_user_active_status(self, telegram_id: int, is_active: bool) -> bool:
        """Устанавливает статус активности пользователя"""
        try:
            return await self.postgres.set_user_active_status(telegram_id, is_active)
        except Exception as e:
            logger.error(f"❌ Ошибка изменения статуса пользователя {telegram_id}: {e}")
            return False
    
    async def log_admin_action(self, admin_telegram_id: int, action_type: str, 
                              target_telegram_id: int = None, description: str = None,
                              action_metadata: Dict = None) -> bool:
        """Логирует административное действие"""
        try:
            return await self.postgres.log_admin_action(
                admin_telegram_id=admin_telegram_id,
                action_type=action_type,
                target_telegram_id=target_telegram_id,
                description=description,
                action_metadata=action_metadata
            )
        except Exception as e:
            logger.error(f"❌ Ошибка логирования действия администратора: {e}")
            return False
    
    # === Управление жизненным циклом ===
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверяет состояние всех баз данных"""
        health_status = {
            'postgres': False,
            'mongodb': False,
            'overall': False
        }
        
        try:
            # Проверяем PostgreSQL
            try:
                async with self.postgres.get_session() as session:
                    session.execute("SELECT 1")
                health_status['postgres'] = True
            except:
                pass
            
            # Проверяем MongoDB
            try:
                await self.mongodb.initialize()
                self.mongodb.client.admin.command('ping')
                health_status['mongodb'] = True
            except:
                pass
            
            health_status['overall'] = health_status['postgres'] and health_status['mongodb']
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки состояния БД: {e}")
        
        return health_status
    
    async def close(self):
        """Закрывает все подключения к БД"""
        try:
            await self.postgres.close()
            await self.mongodb.close()
            logger.info("✅ Все подключения к БД закрыты")
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия подключений к БД: {e}")


# Глобальный экземпляр менеджера
database_manager = DatabaseManager() 