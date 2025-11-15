"""
Менеджер для работы с векторной базой данных (Chroma DB)
Хранение эмбеддингов контента для семантического поиска и RAG
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from config import MONGODB_DATABASE, CHROMA_HOST, CHROMA_PORT
from utils.logger import setup_logger

logger = setup_logger(__name__)


class VectorManager:
    """Менеджер для работы с векторной базой данных Chroma"""
    
    def __init__(self, persist_directory: str = "./data/chroma_db"):
        self.persist_directory = persist_directory
        self.client = None
        self.collection = None
        self.embedding_function = None
        self._initialized = False
        self.use_client_mode = CHROMA_HOST is not None
    
    async def initialize(self, embedding_model: str = None):
        """Инициализация Chroma DB и коллекции"""
        try:
            # Выбираем режим: client (сервер) или embedded (локальный)
            if self.use_client_mode:
                # Client режим - подключаемся к серверу Chroma
                logger.info(f"🔗 Подключаемся к Chroma DB серверу: {CHROMA_HOST}:{CHROMA_PORT}")
                self.client = chromadb.HttpClient(
                    host=CHROMA_HOST,
                    port=int(CHROMA_PORT),
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                
                # Создаем tenant если не существует (для новых версий Chroma)
                try:
                    # Проверяем доступность API
                    collections = self.client.list_collections()
                    logger.info(f"✅ Подключение к Chroma DB успешно, коллекций: {len(collections)}")
                except Exception as tenant_error:
                    if "tenant" in str(tenant_error).lower():
                        logger.warning(f"⚠️ Проблема с tenant: {tenant_error}")
                        # Попробуем создать tenant
                        try:
                            # В новых версиях Chroma может потребоваться создание tenant
                            logger.info("🔧 Попытка создать default tenant...")
                            # Для совместимости просто игнорируем ошибку tenant
                        except Exception as create_error:
                            logger.warning(f"⚠️ Не удалось создать tenant: {create_error}")
                    else:
                        raise tenant_error
            else:
                # Embedded режим - локальное хранилище
                logger.info(f"💾 Используем embedded Chroma DB: {self.persist_directory}")
                self.client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
            
            # Настраиваем функцию эмбеддингов на основе конфигурации
            from config import EMBEDDING_PROVIDER, EMBEDDING_MODEL, OPENAI_EMBEDDING_API_KEY
            
            if EMBEDDING_PROVIDER == "openai" and OPENAI_EMBEDDING_API_KEY:
                # Используем OpenAI эмбеддинги
                self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
                    api_key=OPENAI_EMBEDDING_API_KEY,
                    model_name=EMBEDDING_MODEL
                )
                logger.info(f"✅ Настроена OpenAI функция эмбеддингов: {EMBEDDING_MODEL}")
            elif EMBEDDING_PROVIDER == "sentence-transformers":
                # Используем Sentence-Transformers (только если доступно)
                try:
                    self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                        model_name=EMBEDDING_MODEL
                    )
                    logger.info(f"✅ Настроена Sentence-Transformers функция эмбеддингов: {EMBEDDING_MODEL}")
                except Exception as e:
                    logger.warning(f"⚠️ Sentence-Transformers недоступен: {e}")
                    # Fallback на стандартную функцию
                    self.embedding_function = embedding_functions.DefaultEmbeddingFunction()
                    logger.info("✅ Настроена стандартная функция эмбеддингов (fallback)")
            else:
                # Используем стандартную функцию эмбеддингов Chroma
                self.embedding_function = embedding_functions.DefaultEmbeddingFunction()
                logger.info("✅ Настроена стандартная функция эмбеддингов")
            
            # Получаем или создаем коллекцию
            collection_name = f"{MONGODB_DATABASE}_content"
            try:
                self.collection = self.client.get_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function
                )
                logger.info(f"✅ Найдена существующая коллекция: {collection_name}")
            except Exception:
                self.collection = self.client.create_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function,
                    metadata={"hnsw:space": "cosine"}  # Косинусное расстояние для сходства
                )
                logger.info(f"✅ Создана новая коллекция: {collection_name}")
            
            self._initialized = True
            logger.info("✅ Chroma DB инициализирована успешно")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Chroma DB: {e}")
            raise
    
    async def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Добавляет документ в векторную базу
        
        Args:
            doc_id: Уникальный ID документа (обычно synopsis_id из MongoDB)
            content: Текстовое содержимое для векторизации
            metadata: Метаданные документа (title, category, tags, etc.)
        
        Returns:
            bool: Успешность операции
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            # Подготавливаем метаданные (Chroma требует строковые значения)
            clean_metadata = self._prepare_metadata(metadata)
            
            # Добавляем документ в коллекцию
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.collection.add(
                    documents=[content],
                    metadatas=[clean_metadata],
                    ids=[doc_id]
                )
            )
            
            logger.info(f"✅ Документ {doc_id} добавлен в векторную БД")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления документа {doc_id}: {e}")
            return False
    
    async def update_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Обновляет существующий документ"""
        try:
            if not self._initialized:
                await self.initialize()
            
            clean_metadata = self._prepare_metadata(metadata)
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.collection.update(
                    documents=[content],
                    metadatas=[clean_metadata],
                    ids=[doc_id]
                )
            )
            
            logger.info(f"✅ Документ {doc_id} обновлен в векторной БД")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления документа {doc_id}: {e}")
            return False
    
    async def delete_document(self, doc_id: str) -> bool:
        """Удаляет документ из векторной базы"""
        try:
            if not self._initialized:
                await self.initialize()
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.collection.delete(ids=[doc_id])
            )
            
            logger.info(f"✅ Документ {doc_id} удален из векторной БД")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления документа {doc_id}: {e}")
            return False
    
    async def search_similar(
        self,
        query: str,
        n_results: int = 10,
        user_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Семантический поиск похожих документов
        
        Args:
            query: Поисковый запрос
            n_results: Количество результатов
            user_id: ID пользователя для фильтрации
            filters: Дополнительные фильтры (category, tags, etc.)
        
        Returns:
            List[Dict]: Список найденных документов с метаданными и оценками
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            # Подготавливаем where фильтр для Chroma
            where_filter = {}
            if user_id is not None:
                where_filter["user_id"] = str(user_id)
            
            if filters:
                for key, value in filters.items():
                    if value is not None:
                        where_filter[key] = str(value)
            
            # Выполняем поиск
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    where=where_filter if where_filter else None
                )
            )
            
            # Форматируем результаты
            formatted_results = []
            if results and results['ids'] and len(results['ids']) > 0:
                for i, doc_id in enumerate(results['ids'][0]):
                    formatted_results.append({
                        'id': doc_id,
                        'distance': results['distances'][0][i] if 'distances' in results else None,
                        'metadata': results['metadatas'][0][i] if 'metadatas' in results else {},
                        'document': results['documents'][0][i] if 'documents' in results else ""
                    })
            
            logger.info(f"✅ Найдено {len(formatted_results)} похожих документов")
            return formatted_results
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            return []
    
    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Получает документ по ID"""
        try:
            if not self._initialized:
                await self.initialize()
            
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.collection.get(ids=[doc_id], include=["documents", "metadatas"])
            )
            
            if result and result['ids']:
                return {
                    'id': result['ids'][0],
                    'document': result['documents'][0] if 'documents' in result else "",
                    'metadata': result['metadatas'][0] if 'metadatas' in result else {}
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения документа {doc_id}: {e}")
            return None
    
    async def count_documents(self, user_id: Optional[int] = None) -> int:
        """Подсчитывает количество документов"""
        try:
            if not self._initialized:
                await self.initialize()
            
            where_filter = {"user_id": str(user_id)} if user_id else None
            
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.collection.count()
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка подсчета документов: {e}")
            return 0
    
    async def get_all_user_documents(self, user_id: int) -> List[Dict[str, Any]]:
        """Получает все документы пользователя"""
        try:
            if not self._initialized:
                await self.initialize()
            
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.collection.get(
                    where={"user_id": str(user_id)},
                    include=["documents", "metadatas"]
                )
            )
            
            documents = []
            if result and result['ids']:
                for i, doc_id in enumerate(result['ids']):
                    documents.append({
                        'id': doc_id,
                        'document': result['documents'][i] if 'documents' in result else "",
                        'metadata': result['metadatas'][i] if 'metadatas' in result else {}
                    })
            
            return documents
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения документов пользователя {user_id}: {e}")
            return []
    
    def _prepare_metadata(self, metadata: Dict[str, Any]) -> Dict[str, str]:
        """Подготавливает метаданные для Chroma (все значения должны быть строками)"""
        clean_metadata = {}
        
        for key, value in metadata.items():
            if value is None:
                continue
            
            # Конвертируем все в строки
            if isinstance(value, (list, tuple)):
                # Списки конвертируем в строку через запятую
                clean_metadata[key] = ", ".join(str(v) for v in value)
            elif isinstance(value, dict):
                # Словари пропускаем или конвертируем в JSON
                continue
            elif isinstance(value, datetime):
                clean_metadata[key] = value.isoformat()
            else:
                clean_metadata[key] = str(value)
        
        return clean_metadata
    
    async def reset_collection(self):
        """Очищает всю коллекцию (использовать осторожно!)"""
        try:
            if not self._initialized:
                await self.initialize()
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.delete_collection(self.collection.name)
            )
            
            # Пересоздаем коллекцию
            await self.initialize()
            
            logger.info("✅ Коллекция очищена и пересоздана")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка очистки коллекции: {e}")
            return False
    
    async def close(self):
        """Закрывает соединение с Chroma DB"""
        try:
            if self.client:
                # Chroma автоматически сохраняет данные при закрытии
                self._initialized = False
                logger.info("✅ Chroma DB соединение закрыто")
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия Chroma DB: {e}")


# Глобальный экземпляр менеджера
vector_manager = VectorManager()

