"""
Менеджер для работы с PostgreSQL
Управление пользователями, авторизацией и настройками
"""

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from config import POSTGRES_URL
from storage.postgres_models import Base, User, UserSettings, UserUsageStats, AdminAction, UserSession
from utils.logger import setup_logger

logger = setup_logger(__name__)


class PostgresManager:
    """Менеджер для работы с PostgreSQL"""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialized = False
    
    async def initialize(self):
        """Инициализация подключения к БД"""
        try:
            # Используем асинхронный движок для PostgreSQL
            # Преобразуем URL из postgresql:// в postgresql+asyncpg://
            async_url = POSTGRES_URL.replace('postgresql://', 'postgresql+asyncpg://')
            
            self.engine = create_async_engine(
                async_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                echo=False  # Установить True для отладки SQL запросов
            )
            
            self.SessionLocal = async_sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine,
                expire_on_commit=False,
                class_=AsyncSession
            )
            
            # Создаем таблицы
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            self._initialized = True
            logger.info("✅ PostgreSQL подключение инициализировано")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации PostgreSQL: {e}")
            raise
    
    @asynccontextmanager
    async def get_session(self):
        """Контекстный менеджер для работы с сессией БД"""
        if not self._initialized:
            await self.initialize()
        
        session = self.SessionLocal()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка в сессии БД: {e}")
            raise
        finally:
            await session.close()
    
    # === Управление пользователями ===
    
    async def create_user(self, telegram_id: int, username: str = None, 
                         first_name: str = None, last_name: str = None, 
                         is_admin: bool = False) -> Optional[User]:
        """Создает нового пользователя"""
        try:
            async with self.get_session() as session:
                # Проверяем, существует ли пользователь
                result = await session.execute(
                    select(User).filter(User.telegram_id == telegram_id)
                )
                existing_user = result.scalars().first()
                
                if existing_user:
                    logger.warning(f"Пользователь {telegram_id} уже существует")
                    return existing_user
                
                # Создаем нового пользователя
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    is_admin=is_admin,
                    last_activity=datetime.now()
                )
                
                session.add(user)
                await session.flush()  # Получаем ID пользователя
                
                # Создаем настройки по умолчанию
                settings = UserSettings(user_id=user.id)
                session.add(settings)
                
                # Создаем статистику по умолчанию
                stats = UserUsageStats(user_id=user.id)
                session.add(stats)
                
                await session.commit()
                logger.info(f"✅ Создан пользователь {telegram_id}")
                return user
                
        except Exception as e:
            logger.error(f"❌ Ошибка создания пользователя {telegram_id}: {e}")
            return None
    
    async def get_user(self, telegram_id: int) -> Optional[User]:
        """Получает пользователя по Telegram ID"""
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    select(User).filter(User.telegram_id == telegram_id)
                )
                user = result.scalars().first()
                return user
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователя {telegram_id}: {e}")
            return None
    
    async def update_user_activity(self, telegram_id: int) -> bool:
        """Обновляет время последней активности пользователя"""
        try:
            async with self.get_session() as session:
                stmt = update(User).where(
                    User.telegram_id == telegram_id
                ).values(
                    last_activity=datetime.now()
                )
                
                result = await session.execute(stmt)
                
                if result.rowcount > 0:
                    await session.commit()
                    return True
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления активности {telegram_id}: {e}")
            return False
    
    async def set_user_active_status(self, telegram_id: int, is_active: bool) -> bool:
        """Устанавливает статус активности пользователя"""
        try:
            async with self.get_session() as session:
                stmt = update(User).where(
                    User.telegram_id == telegram_id
                ).values(
                    is_active=is_active,
                    updated_at=datetime.now()
                )
                
                result = await session.execute(stmt)
                
                if result.rowcount > 0:
                    await session.commit()
                    logger.info(f"✅ Статус пользователя {telegram_id} изменен на {'активный' if is_active else 'неактивный'}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка изменения статуса {telegram_id}: {e}")
            return False
    
    async def get_all_users(self, include_inactive: bool = False) -> List[User]:
        """Получает список всех пользователей"""
        try:
            async with self.get_session() as session:
                query = select(User)
                if not include_inactive:
                    query = query.filter(User.is_active == True)
                
                query = query.order_by(User.created_at.desc())
                result = await session.execute(query)
                users = result.scalars().all()
                return users
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка пользователей: {e}")
            return []
    
    async def is_user_authorized(self, telegram_id: int) -> bool:
        """Проверяет, авторизован ли пользователь"""
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    select(User).filter(
                        and_(
                            User.telegram_id == telegram_id,
                            User.is_active == True
                        )
                    )
                )
                user = result.scalars().first()
                
                return user is not None
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки авторизации {telegram_id}: {e}")
            return False
    
    async def is_user_admin(self, telegram_id: int) -> bool:
        """Проверяет, является ли пользователь администратором"""
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    select(User).filter(
                        and_(
                            User.telegram_id == telegram_id,
                            User.is_active == True,
                            User.is_admin == True
                        )
                    )
                )
                user = result.scalars().first()
                
                return user is not None
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки прав администратора {telegram_id}: {e}")
            return False
    
    # === Управление статистикой ===
    
    async def update_user_stats(self, telegram_id: int, analysis_data: Dict[str, Any]) -> bool:
        """Обновляет статистику пользователя"""
        try:
            async with self.get_session() as session:
                # Получаем пользователя
                result = await session.execute(
                    select(User).filter(User.telegram_id == telegram_id)
                )
                user = result.scalars().first()
                
                if not user:
                    logger.warning(f"Пользователь {telegram_id} не найден для обновления статистики")
                    return False
                
                # Получаем статистику пользователя
                result = await session.execute(
                    select(UserUsageStats).filter(UserUsageStats.user_id == user.id)
                )
                stats = result.scalars().first()
                
                if not stats:
                    stats = UserUsageStats(user_id=user.id)
                    session.add(stats)
                
                # Обновляем статистику
                analysis = analysis_data.get('analysis', {})
                
                stats.total_analyses += 1
                
                # Приоритеты
                priority = analysis.get('priority_level', 'medium')
                if priority == 'high':
                    stats.priority_high_count += 1
                elif priority == 'medium':
                    stats.priority_medium_count += 1
                else:
                    stats.priority_low_count += 1
                
                # Сложность
                complexity = analysis.get('complexity_level', 'средний')
                if complexity == 'начальный':
                    stats.complexity_beginner_count += 1
                elif complexity == 'средний':
                    stats.complexity_intermediate_count += 1
                else:
                    stats.complexity_advanced_count += 1
                
                # Обновляем средние значения
                try:
                    relevance = float(analysis.get('relevance_score', 5))
                    current_avg = stats.avg_relevance_score / 100.0 if stats.avg_relevance_score else 0
                    new_avg = ((current_avg * (stats.total_analyses - 1)) + relevance) / stats.total_analyses
                    stats.avg_relevance_score = int(new_avg * 100)
                except:
                    pass
                
                try:
                    reading_time = float(analysis.get('estimated_reading_time', 5))
                    current_avg = stats.avg_reading_time if stats.avg_reading_time else 0
                    new_avg = ((current_avg * (stats.total_analyses - 1)) + reading_time) / stats.total_analyses
                    stats.avg_reading_time = int(new_avg)
                except:
                    pass
                
                # Временные метки
                now = datetime.now()
                if not stats.first_analysis:
                    stats.first_analysis = now
                stats.last_analysis = now
                stats.updated_at = now
                
                await session.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статистики {telegram_id}: {e}")
            return False
    
    async def get_user_stats(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получает статистику пользователя"""
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    select(User).filter(User.telegram_id == telegram_id)
                )
                user = result.scalars().first()
                
                if not user:
                    return None
                
                result = await session.execute(
                    select(UserUsageStats).filter(UserUsageStats.user_id == user.id)
                )
                stats = result.scalars().first()
                
                if not stats:
                    return {
                        'total_analyses': 0,
                        'avg_relevance_score': 0,
                        'avg_reading_time': 0
                    }
                
                return {
                    'total_analyses': stats.total_analyses,
                    'total_exports': stats.total_exports,
                    'total_commands': stats.total_commands,
                    'priority_high_count': stats.priority_high_count,
                    'priority_medium_count': stats.priority_medium_count,
                    'priority_low_count': stats.priority_low_count,
                    'complexity_beginner_count': stats.complexity_beginner_count,
                    'complexity_intermediate_count': stats.complexity_intermediate_count,
                    'complexity_advanced_count': stats.complexity_advanced_count,
                    'avg_relevance_score': stats.avg_relevance_score / 100.0,
                    'avg_reading_time': stats.avg_reading_time,
                    'first_analysis': stats.first_analysis,
                    'last_analysis': stats.last_analysis
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики {telegram_id}: {e}")
            return None
    
    async def reset_user_stats(self, telegram_id: int) -> bool:
        """Сбрасывает статистику пользователя"""
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    select(User).filter(User.telegram_id == telegram_id)
                )
                user = result.scalars().first()
                
                if not user:
                    return False
                
                # Удаляем статистику пользователя
                await session.execute(
                    delete(UserUsageStats).filter(UserUsageStats.user_id == user.id)
                )
                
                await session.commit()
                logger.info(f"✅ Статистика пользователя {telegram_id} сброшена")
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка сброса статистики {telegram_id}: {e}")
            return False
    
    # === Логирование административных действий ===
    
    async def log_admin_action(self, admin_telegram_id: int, action_type: str, 
                              target_telegram_id: int = None, description: str = None,
                              action_metadata: Dict = None) -> bool:
        """Логирует административное действие"""
        try:
            async with self.get_session() as session:
                action = AdminAction(
                    admin_telegram_id=admin_telegram_id,
                    target_telegram_id=target_telegram_id,
                    action_type=action_type,
                    description=description,
                    action_metadata=action_metadata or {}
                )
                
                session.add(action)
                await session.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка логирования действия администратора: {e}")
            return False
    
    async def close(self):
        """Закрывает подключение к БД"""
        if self.engine:
            await self.engine.dispose()
            logger.info("✅ PostgreSQL подключение закрыто")


# Глобальный экземпляр менеджера
postgres_manager = PostgresManager() 