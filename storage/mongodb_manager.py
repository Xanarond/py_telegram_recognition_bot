"""
Менеджер для работы с MongoDB
Хранение синопсисов, анализов контента и статистики по источникам
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from bson import ObjectId
import pymongo
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from pymongo.errors import DuplicateKeyError, PyMongoError

from config import MONGODB_URL, MONGODB_DATABASE, SOURCES_PER_PAGE
from utils.logger import setup_logger

logger = setup_logger(__name__)


class MongoDBManager:
    """Менеджер для работы с MongoDB"""
    
    def __init__(self):
        self.client = None
        self.db = None
        self._initialized = False
    
    async def initialize(self):
        """Инициализация подключения к MongoDB"""
        try:
            self.client = MongoClient(
                MONGODB_URL,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000
            )
            
            # Проверяем подключение
            self.client.admin.command('ping')
            
            self.db = self.client[MONGODB_DATABASE]
            
            # Создаем индексы
            await self._create_indexes()
            
            self._initialized = True
            logger.info("✅ MongoDB подключение инициализировано")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации MongoDB: {e}")
            raise
    
    async def _create_indexes(self):
        """Создает необходимые индексы"""
        try:
            # Индексы для коллекции синопсисов
            synopses = self.db.synopses
            synopses.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
            synopses.create_index([("url", ASCENDING)], unique=True)
            synopses.create_index([("domain", ASCENDING)])
            synopses.create_index([("category", ASCENDING)])
            synopses.create_index([("priority_level", ASCENDING)])
            synopses.create_index([("read_status", ASCENDING)])
            synopses.create_index([("rating", DESCENDING)])
            synopses.create_index([("user_id", ASCENDING), ("rating", DESCENDING)])
            synopses.create_index([("tags", ASCENDING)])
            synopses.create_index([("title", TEXT), ("summary", TEXT), ("key_points", TEXT)])
            
            # Индексы для коллекции источников пользователей
            user_sources = self.db.user_sources
            user_sources.create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
            user_sources.create_index([("user_id", ASCENDING), ("read_status", ASCENDING)])
            user_sources.create_index([("source_id", ASCENDING)], unique=True)
            
            # Индексы для коллекции статистики по доменам
            domain_stats = self.db.domain_stats
            domain_stats.create_index([("domain", ASCENDING)], unique=True)
            domain_stats.create_index([("total_analyses", DESCENDING)])
            
            logger.info("✅ Индексы MongoDB созданы")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания индексов MongoDB: {e}")
    
    # === Управление синопсисами ===
    
    async def save_synopsis(self, user_id: int, analysis_data: Dict[str, Any]) -> Optional[str]:
        """Сохраняет синопсис в MongoDB"""
        try:
            if not self._initialized:
                await self.initialize()
            
            analysis = analysis_data.get('analysis', {})
            
            # Подготавливаем документ
            synopsis_doc = {
                'user_id': user_id,
                'url': analysis_data.get('url', ''),
                'title': analysis_data.get('title', 'Без названия'),
                'domain': self._extract_domain(analysis_data.get('url', '')),
                'domain_emoji': analysis_data.get('domain_emoji', '📄'),
                
                # Анализ контента
                'summary': analysis.get('summary', ''),
                'key_points': analysis.get('key_points', []),
                'category': analysis.get('category', 'unknown'),
                'relevance_score': float(analysis.get('relevance_score', 5)),
                'priority_level': analysis.get('priority_level', 'medium'),
                'complexity_level': analysis.get('complexity_level', 'средний'),
                'estimated_reading_time': int(analysis.get('estimated_reading_time', 5)),
                'tags': analysis.get('tags', [])[:10],  # Ограничиваем количество тегов
                
                # Статус и временные метки
                'read_status': 'unread',
                'read_timestamp': None,
                'rating': 0,  # Рейтинг от 0 (не установлен) до 5 звезд
                'rating_timestamp': None,
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                
                # Дополнительные данные
                'content_length': len(analysis_data.get('content', '')),
                'language': analysis.get('language', 'ru'),
                'source_type': self._determine_source_type(analysis_data.get('url', '')),
                
                # Метаданные для поиска и фильтрации
                'search_text': f"{analysis_data.get('title', '')} {analysis.get('summary', '')} {' '.join(analysis.get('tags', []))}".lower()
            }
            
            # Сохраняем в коллекцию синопсисов
            result = self.db.synopses.insert_one(synopsis_doc)
            
            # Обновляем статистику по домену
            await self._update_domain_stats(synopsis_doc['domain'])
            
            logger.info(f"✅ Синопсис сохранен для пользователя {user_id}: {result.inserted_id}")
            return str(result.inserted_id)
            
        except DuplicateKeyError:
            logger.warning(f"Синопсис для URL уже существует: {analysis_data.get('url', '')}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения синопсиса: {e}")
            return None
    
    async def get_user_synopses(self, user_id: int, page: int = 1, per_page: int = None,
                               read_filter: str = 'all', category_filter: str = None,
                               priority_filter: str = None, search_query: str = None) -> Dict[str, Any]:
        """Получает синопсисы пользователя с фильтрацией и пагинацией"""
        try:
            if not self._initialized:
                await self.initialize()
            
            if per_page is None:
                per_page = SOURCES_PER_PAGE
            
            # Строим фильтр
            filter_query = {'user_id': user_id}
            
            if read_filter != 'all':
                filter_query['read_status'] = read_filter
            
            if category_filter:
                filter_query['category'] = category_filter
            
            if priority_filter:
                filter_query['priority_level'] = priority_filter
            
            if search_query:
                filter_query['$text'] = {'$search': search_query}
            
            # Подсчитываем общее количество
            total_count = self.db.synopses.count_documents(filter_query)
            
            # Получаем данные с пагинацией
            skip = (page - 1) * per_page
            cursor = self.db.synopses.find(filter_query).sort('created_at', DESCENDING).skip(skip).limit(per_page)
            
            synopses = []
            for doc in cursor:
                synopsis = {
                    'id': str(doc['_id']),
                    'url': doc['url'],
                    'title': doc['title'],
                    'domain_emoji': doc['domain_emoji'],
                    'category': doc['category'],
                    'relevance_score': doc['relevance_score'],
                    'priority_level': doc['priority_level'],
                    'complexity_level': doc['complexity_level'],
                    'estimated_reading_time': doc['estimated_reading_time'],
                    'tags': doc['tags'][:3],  # Первые 3 тега для отображения
                    'read_status': doc['read_status'],
                    'rating': doc.get('rating', 0),
                    'created_at': doc['created_at'],
                    'summary': doc['summary'][:200] + '...' if len(doc['summary']) > 200 else doc['summary']
                }
                synopses.append(synopsis)
            
            return {
                'synopses': synopses,
                'total_count': total_count,
                'page': page,
                'per_page': per_page,
                'total_pages': (total_count + per_page - 1) // per_page
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения синопсисов пользователя {user_id}: {e}")
            return {'synopses': [], 'total_count': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}
    
    async def get_synopsis_by_id(self, synopsis_id: str) -> Optional[Dict[str, Any]]:
        """Получает полный синопсис по ID"""
        try:
            if not self._initialized:
                await self.initialize()
            
            # Проверяем валидность ObjectId
            if not ObjectId.is_valid(synopsis_id):
                logger.error(f"❌ Невалидный ObjectId: {synopsis_id} (длина: {len(synopsis_id)})")
                return None
            
            doc = self.db.synopses.find_one({'_id': ObjectId(synopsis_id)})
            if not doc:
                return None
            
            # Конвертируем ObjectId в строку
            doc['id'] = str(doc['_id'])
            del doc['_id']
            
            return doc
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения синопсиса {synopsis_id}: {e}")
            return None
    
    async def mark_synopsis_as_read(self, synopsis_id: str, read_status: str = 'read') -> bool:
        """Отмечает синопсис как прочитанный/непрочитанный"""
        try:
            if not self._initialized:
                await self.initialize()
            
            # Проверяем валидность ObjectId
            if not ObjectId.is_valid(synopsis_id):
                logger.error(f"❌ Невалидный ObjectId для обновления статуса: {synopsis_id} (длина: {len(synopsis_id)})")
                return False
            
            update_data = {
                'read_status': read_status,
                'updated_at': datetime.now()
            }
            
            if read_status == 'read':
                update_data['read_timestamp'] = datetime.now()
            else:
                update_data['read_timestamp'] = None
            
            result = self.db.synopses.update_one(
                {'_id': ObjectId(synopsis_id)},
                {'$set': update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статуса синопсиса {synopsis_id}: {e}")
            return False
    
    async def update_synopsis_rating(self, synopsis_id: str, rating: int) -> bool:
        """Обновляет рейтинг синопсиса (0-5 звезд)"""
        try:
            if not self._initialized:
                await self.initialize()
            
            # Проверяем валидность ObjectId
            if not ObjectId.is_valid(synopsis_id):
                logger.error(f"❌ Невалидный ObjectId для обновления рейтинга: {synopsis_id} (длина: {len(synopsis_id)})")
                return False
            
            # Проверяем валидность рейтинга
            if not isinstance(rating, int) or rating < 0 or rating > 5:
                logger.error(f"❌ Невалидный рейтинг: {rating}. Должен быть от 0 до 5")
                return False
            
            update_data = {
                'rating': rating,
                'rating_timestamp': datetime.now() if rating > 0 else None,
                'updated_at': datetime.now()
            }
            
            result = self.db.synopses.update_one(
                {'_id': ObjectId(synopsis_id)},
                {'$set': update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"✅ Рейтинг синопсиса {synopsis_id} обновлен на {rating}")
                return True
            else:
                logger.warning(f"⚠️ Рейтинг не обновлен для {synopsis_id}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления рейтинга синопсиса {synopsis_id}: {e}")
            return False
    
    async def delete_synopsis(self, synopsis_id: str, user_id: int) -> bool:
        """Удаляет синопсис пользователя"""
        try:
            if not self._initialized:
                await self.initialize()
            
            # Проверяем валидность ObjectId
            if not ObjectId.is_valid(synopsis_id):
                logger.error(f"❌ Невалидный ObjectId для удаления: {synopsis_id} (длина: {len(synopsis_id)})")
                return False
            
            result = self.db.synopses.delete_one({
                '_id': ObjectId(synopsis_id),
                'user_id': user_id
            })
            
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления синопсиса {synopsis_id}: {e}")
            return False
    
    # === Статистика и аналитика ===
    
    async def get_user_content_stats(self, user_id: int) -> Dict[str, Any]:
        """Получает статистику контента пользователя"""
        try:
            if not self._initialized:
                await self.initialize()
            
            pipeline = [
                {'$match': {'user_id': user_id}},
                {'$group': {
                    '_id': None,
                    'total_synopses': {'$sum': 1},
                    'read_count': {'$sum': {'$cond': [{'$eq': ['$read_status', 'read']}, 1, 0]}},
                    'unread_count': {'$sum': {'$cond': [{'$eq': ['$read_status', 'unread']}, 1, 0]}},
                    'avg_relevance': {'$avg': '$relevance_score'},
                    'avg_reading_time': {'$avg': '$estimated_reading_time'},
                    'categories': {'$addToSet': '$category'},
                    'domains': {'$addToSet': '$domain'},
                    'priority_high': {'$sum': {'$cond': [{'$eq': ['$priority_level', 'high']}, 1, 0]}},
                    'priority_medium': {'$sum': {'$cond': [{'$eq': ['$priority_level', 'medium']}, 1, 0]}},
                    'priority_low': {'$sum': {'$cond': [{'$eq': ['$priority_level', 'low']}, 1, 0]}},
                    'avg_rating': {'$avg': {'$cond': [{'$gt': ['$rating', 0]}, '$rating', None]}},
                    'rated_count': {'$sum': {'$cond': [{'$gt': ['$rating', 0]}, 1, 0]}},
                    'rating_5': {'$sum': {'$cond': [{'$eq': ['$rating', 5]}, 1, 0]}},
                    'rating_4': {'$sum': {'$cond': [{'$eq': ['$rating', 4]}, 1, 0]}},
                    'rating_3': {'$sum': {'$cond': [{'$eq': ['$rating', 3]}, 1, 0]}},
                    'rating_2': {'$sum': {'$cond': [{'$eq': ['$rating', 2]}, 1, 0]}},
                    'rating_1': {'$sum': {'$cond': [{'$eq': ['$rating', 1]}, 1, 0]}},
                }}
            ]
            
            result = list(self.db.synopses.aggregate(pipeline))
            
            if not result:
                return {
                    'total_synopses': 0,
                    'read_count': 0,
                    'unread_count': 0,
                    'avg_relevance': 0,
                    'avg_reading_time': 0,
                    'categories': [],
                    'domains': [],
                    'priority_high': 0,
                    'priority_medium': 0,
                    'priority_low': 0,
                    'avg_rating': 0,
                    'rated_count': 0,
                    'rating_5': 0,
                    'rating_4': 0,
                    'rating_3': 0,
                    'rating_2': 0,
                    'rating_1': 0
                }
            
            stats = result[0]
            del stats['_id']
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики контента {user_id}: {e}")
            return {}
    
    async def get_trending_topics(self, days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
        """Получает популярные темы за период"""
        try:
            if not self._initialized:
                await self.initialize()
            
            start_date = datetime.now() - timedelta(days=days)
            
            pipeline = [
                {'$match': {'created_at': {'$gte': start_date}}},
                {'$unwind': '$tags'},
                {'$group': {
                    '_id': '$tags',
                    'count': {'$sum': 1},
                    'avg_relevance': {'$avg': '$relevance_score'}
                }},
                {'$sort': {'count': DESCENDING}},
                {'$limit': limit}
            ]
            
            results = list(self.db.synopses.aggregate(pipeline))
            
            trending = []
            for item in results:
                trending.append({
                    'tag': item['_id'],
                    'count': item['count'],
                    'avg_relevance': round(item['avg_relevance'], 1)
                })
            
            return trending
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения популярных тем: {e}")
            return []
    
    # === Вспомогательные методы ===
    
    def _extract_domain(self, url: str) -> str:
        """Извлекает домен из URL"""
        try:
            if '://' in url:
                domain = url.split('://')[1].split('/')[0]
            else:
                domain = url.split('/')[0]
            return domain.lower()
        except:
            return 'unknown'
    
    def _determine_source_type(self, url: str) -> str:
        """Определяет тип источника по URL"""
        domain = self._extract_domain(url)
        
        if 'youtube.com' in domain or 'youtu.be' in domain:
            return 'video'
        elif 'github.com' in domain:
            return 'code'
        elif 'arxiv.org' in domain:
            return 'academic'
        elif any(blog in domain for blog in ['medium.com', 'dev.to', 'habr.com']):
            return 'blog'
        else:
            return 'article'
    
    async def clear_user_synopses(self, user_id: int) -> bool:
        """Очищает все синопсисы пользователя"""
        try:
            if not self._initialized:
                await self.initialize()
            
            result = self.db.synopses.delete_many({'user_id': user_id})
            logger.info(f"✅ Удалено {result.deleted_count} синопсисов пользователя {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка очистки синопсисов пользователя {user_id}: {e}")
            return False
    
    async def _update_domain_stats(self, domain: str):
        """Обновляет статистику по домену"""
        try:
            self.db.domain_stats.update_one(
                {'domain': domain},
                {
                    '$inc': {'total_analyses': 1},
                    '$set': {'last_analysis': datetime.now()}
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статистики домена {domain}: {e}")
    
    async def close(self):
        """Закрывает подключение к MongoDB"""
        if self.client:
            self.client.close()
            logger.info("✅ MongoDB подключение закрыто")


# Глобальный экземпляр менеджера
mongodb_manager = MongoDBManager() 