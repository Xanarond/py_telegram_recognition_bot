"""
Сервис векторизации контента
Обрабатывает контент и сохраняет эмбеддинги в векторную БД
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from config import ENABLE_VECTOR_DB, EMBEDDING_PROVIDER, EMBEDDING_MODEL
from utils.logger import setup_logger

logger = setup_logger(__name__)


class VectorizationService:
    """Сервис для векторизации и индексирования контента"""
    
    def __init__(self):
        self.vector_manager = None
        self.embedding_generator = None
        self._initialized = False
    
    async def initialize(self):
        """Инициализация сервиса векторизации"""
        try:
            if not ENABLE_VECTOR_DB:
                logger.info("⚠️ Векторная БД отключена в конфигурации")
                return
            
            # Импортируем менеджеры
            from storage.vector_manager import vector_manager
            
            self.vector_manager = vector_manager
            
            # Инициализируем только vector_manager
            # EmbeddingGenerator будет создан при необходимости
            await self.vector_manager.initialize()
            
            self._initialized = True
            logger.info("✅ Сервис векторизации инициализирован")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации сервиса векторизации: {e}")
            self._initialized = False
    
    async def vectorize_and_store(
        self,
        synopsis_id: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Векторизует контент и сохраняет в векторную БД
        
        Args:
            synopsis_id: ID синопсиса из MongoDB
            content: Текстовое содержимое для векторизации
            metadata: Метаданные документа
        
        Returns:
            bool: Успешность операции
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            if not self._initialized:
                logger.warning("⚠️ Векторизация пропущена - сервис не инициализирован")
                return False
            
            # Подготавливаем текст для векторизации
            text_to_vectorize = self._prepare_text_for_vectorization(content, metadata)
            
            # Генерируем эмбеддинг (используем префикс для E5 моделей)
            # Это не нужно для Chroma, так как он сам генерирует эмбеддинги
            # но мы оставляем возможность для будущих расширений
            
            # Сохраняем в векторную БД
            success = await self.vector_manager.add_document(
                doc_id=synopsis_id,
                content=text_to_vectorize,
                metadata=metadata
            )
            
            if success:
                logger.info(f"✅ Контент векторизован и сохранен: {synopsis_id}")
            else:
                logger.warning(f"⚠️ Не удалось векторизовать контент: {synopsis_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Ошибка векторизации контента {synopsis_id}: {e}")
            return False
    
    async def update_vectorized_content(
        self,
        synopsis_id: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Обновляет векторизованный контент"""
        try:
            if not self._initialized:
                await self.initialize()
            
            if not self._initialized:
                return False
            
            text_to_vectorize = self._prepare_text_for_vectorization(content, metadata)
            
            success = await self.vector_manager.update_document(
                doc_id=synopsis_id,
                content=text_to_vectorize,
                metadata=metadata
            )
            
            if success:
                logger.info(f"✅ Векторизованный контент обновлен: {synopsis_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления векторизованного контента {synopsis_id}: {e}")
            return False
    
    async def delete_vectorized_content(self, synopsis_id: str) -> bool:
        """Удаляет векторизованный контент"""
        try:
            if not self._initialized:
                await self.initialize()
            
            if not self._initialized:
                return False
            
            success = await self.vector_manager.delete_document(synopsis_id)
            
            if success:
                logger.info(f"✅ Векторизованный контент удален: {synopsis_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления векторизованного контента {synopsis_id}: {e}")
            return False
    
    async def search_similar_content(
        self,
        query: str,
        user_id: Optional[int] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Семантический поиск похожего контента
        
        Args:
            query: Поисковый запрос
            user_id: ID пользователя для фильтрации
            top_k: Количество результатов
            filters: Дополнительные фильтры
        
        Returns:
            List[Dict]: Список найденных документов
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            if not self._initialized:
                return []
            
            results = await self.vector_manager.search_similar(
                query=query,
                n_results=top_k,
                user_id=user_id,
                filters=filters
            )
            
            logger.info(f"✅ Найдено {len(results)} похожих документов для запроса: {query[:50]}...")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска похожего контента: {e}")
            return []
    
    async def get_recommendations(
        self,
        synopsis_id: str,
        top_k: int = 5,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Получает рекомендации похожих статей на основе конкретного документа
        
        Args:
            synopsis_id: ID документа для поиска похожих
            top_k: Количество рекомендаций
            user_id: ID пользователя для фильтрации
        
        Returns:
            List[Dict]: Список рекомендованных документов
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            if not self._initialized:
                return []
            
            # Получаем документ
            doc = await self.vector_manager.get_document(synopsis_id)
            
            if not doc:
                logger.warning(f"⚠️ Документ {synopsis_id} не найден для рекомендаций")
                return []
            
            # Ищем похожие документы
            results = await self.vector_manager.search_similar(
                query=doc['document'],
                n_results=top_k + 1,  # +1 чтобы исключить сам документ
                user_id=user_id
            )
            
            # Фильтруем сам документ из результатов
            recommendations = [r for r in results if r['id'] != synopsis_id][:top_k]
            
            logger.info(f"✅ Найдено {len(recommendations)} рекомендаций для {synopsis_id}")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения рекомендаций для {synopsis_id}: {e}")
            return []
    
    async def batch_vectorize(
        self,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Пакетная векторизация документов
        
        Args:
            documents: Список документов с полями: synopsis_id, content, metadata
        
        Returns:
            Dict: Статистика обработки
        """
        stats = {
            'total': len(documents),
            'success': 0,
            'failed': 0
        }
        
        try:
            if not self._initialized:
                await self.initialize()
            
            if not self._initialized:
                logger.warning("⚠️ Пакетная векторизация пропущена - сервис не инициализирован")
                return stats
            
            for doc in documents:
                success = await self.vectorize_and_store(
                    synopsis_id=doc['synopsis_id'],
                    content=doc['content'],
                    metadata=doc['metadata']
                )
                
                if success:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
            
            logger.info(f"✅ Пакетная векторизация завершена: {stats}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка пакетной векторизации: {e}")
        
        return stats
    
    def _prepare_text_for_vectorization(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Подготавливает текст для векторизации
        Объединяет контент с важными метаданными для лучшего поиска
        
        Args:
            content: Основной контент
            metadata: Метаданные документа
        
        Returns:
            str: Подготовленный текст
        """
        # Извлекаем важные метаданные
        title = metadata.get('title', '')
        summary = metadata.get('summary', '')
        tags = metadata.get('tags', [])
        category = metadata.get('category', '')
        
        # Формируем текст для векторизации
        parts = []
        
        if title:
            parts.append(f"Заголовок: {title}")
        
        if summary:
            parts.append(f"Резюме: {summary}")
        
        if category:
            parts.append(f"Категория: {category}")
        
        if tags:
            tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
            parts.append(f"Теги: {tags_str}")
        
        # Добавляем основной контент
        if content:
            parts.append(f"Контент: {content}")
        
        return "\n\n".join(parts)
    
    async def get_user_content_stats(self, user_id: int) -> Dict[str, Any]:
        """Получает статистику векторизованного контента пользователя"""
        try:
            if not self._initialized:
                await self.initialize()
            
            if not self._initialized:
                return {'total': 0, 'error': 'Сервис не инициализирован'}
            
            count = await self.vector_manager.count_documents(user_id=user_id)
            
            return {
                'total': count,
                'user_id': user_id,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики пользователя {user_id}: {e}")
            return {'total': 0, 'error': str(e)}


# Глобальный экземпляр сервиса
vectorization_service = VectorizationService()

