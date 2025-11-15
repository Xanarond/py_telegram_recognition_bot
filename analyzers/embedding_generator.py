"""
Генератор эмбеддингов для векторизации контента
Поддержка OpenAI и локальных моделей Sentence-Transformers
"""

import asyncio
from typing import List, Optional, Union
import os

from utils.logger import setup_logger

logger = setup_logger(__name__)


class EmbeddingGenerator:
    """Генератор эмбеддингов с поддержкой различных моделей"""
    
    def __init__(
        self,
        provider: str = "sentence-transformers",
        model_name: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Инициализация генератора эмбеддингов
        
        Args:
            provider: Провайдер эмбеддингов ("openai", "sentence-transformers", "cohere")
            model_name: Название модели (опционально, используется дефолтная)
            api_key: API ключ для облачных провайдеров
        """
        self.provider = provider.lower()
        self.model_name = model_name
        self.api_key = api_key or os.getenv(f"{provider.upper()}_API_KEY")
        self.model = None
        self._initialized = False
    
    async def initialize(self):
        """Инициализация модели эмбеддингов"""
        try:
            if self.provider == "openai":
                await self._initialize_openai()
            elif self.provider == "sentence-transformers":
                await self._initialize_sentence_transformers()
            elif self.provider == "cohere":
                await self._initialize_cohere()
            else:
                raise ValueError(f"Неподдерживаемый провайдер: {self.provider}")
            
            self._initialized = True
            logger.info(f"✅ Embedding generator инициализирован: {self.provider}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации embedding generator: {e}")
            raise
    
    async def _initialize_openai(self):
        """Инициализация OpenAI эмбеддингов"""
        try:
            import openai
            
            if not self.api_key:
                raise ValueError("OpenAI API key не найден")
            
            self.client = openai.AsyncOpenAI(api_key=self.api_key)
            self.model_name = self.model_name or "text-embedding-3-small"
            
            logger.info(f"✅ OpenAI embeddings инициализированы: {self.model_name}")
            
        except ImportError:
            logger.error("❌ Библиотека openai не установлена. Установите: pip install openai")
            raise
    
    async def _initialize_sentence_transformers(self):
        """Инициализация Sentence-Transformers"""
        try:
            from sentence_transformers import SentenceTransformer
            
            # Используем многоязычную модель по умолчанию
            self.model_name = self.model_name or "intfloat/multilingual-e5-large"
            
            # Загружаем модель в отдельном потоке, чтобы не блокировать
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None,
                lambda: SentenceTransformer(self.model_name)
            )
            
            logger.info(f"✅ Sentence-Transformers инициализирована: {self.model_name}")
            
        except ImportError:
            logger.error("❌ Библиотека sentence-transformers не установлена. Установите: pip install sentence-transformers")
            raise
    
    async def _initialize_cohere(self):
        """Инициализация Cohere эмбеддингов"""
        try:
            import cohere
            
            if not self.api_key:
                raise ValueError("Cohere API key не найден")
            
            self.client = cohere.AsyncClient(api_key=self.api_key)
            self.model_name = self.model_name or "embed-multilingual-v3.0"
            
            logger.info(f"✅ Cohere embeddings инициализированы: {self.model_name}")
            
        except ImportError:
            logger.error("❌ Библиотека cohere не установлена. Установите: pip install cohere")
            raise
    
    async def generate_embedding(
        self,
        text: Union[str, List[str]],
        prefix: Optional[str] = None
    ) -> Union[List[float], List[List[float]]]:
        """
        Генерирует эмбеддинг для текста
        
        Args:
            text: Текст или список текстов для векторизации
            prefix: Префикс для улучшения качества (для некоторых моделей)
        
        Returns:
            Вектор эмбеддинга или список векторов
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            # Обрабатываем одиночный текст
            is_single = isinstance(text, str)
            texts = [text] if is_single else text
            
            # Добавляем префикс если указан (для E5 моделей)
            if prefix and self.provider == "sentence-transformers" and "e5" in self.model_name.lower():
                texts = [f"{prefix}: {t}" for t in texts]
            
            # Генерируем эмбеддинги в зависимости от провайдера
            if self.provider == "openai":
                embeddings = await self._generate_openai_embedding(texts)
            elif self.provider == "sentence-transformers":
                embeddings = await self._generate_sentence_transformers_embedding(texts)
            elif self.provider == "cohere":
                embeddings = await self._generate_cohere_embedding(texts)
            else:
                raise ValueError(f"Неподдерживаемый провайдер: {self.provider}")
            
            # Возвращаем одиночный вектор или список
            return embeddings[0] if is_single else embeddings
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации эмбеддинга: {e}")
            raise
    
    async def _generate_openai_embedding(self, texts: List[str]) -> List[List[float]]:
        """Генерирует эмбеддинги через OpenAI API"""
        try:
            response = await self.client.embeddings.create(
                model=self.model_name,
                input=texts
            )
            
            embeddings = [item.embedding for item in response.data]
            logger.debug(f"✅ Сгенерировано {len(embeddings)} OpenAI эмбеддингов")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"❌ Ошибка OpenAI API: {e}")
            raise
    
    async def _generate_sentence_transformers_embedding(self, texts: List[str]) -> List[List[float]]:
        """Генерирует эмбеддинги через Sentence-Transformers"""
        try:
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: self.model.encode(texts, convert_to_numpy=True)
            )
            
            # Конвертируем numpy array в список
            embeddings_list = [emb.tolist() for emb in embeddings]
            logger.debug(f"✅ Сгенерировано {len(embeddings_list)} Sentence-Transformers эмбеддингов")
            
            return embeddings_list
            
        except Exception as e:
            logger.error(f"❌ Ошибка Sentence-Transformers: {e}")
            raise
    
    async def _generate_cohere_embedding(self, texts: List[str]) -> List[List[float]]:
        """Генерирует эмбеддинги через Cohere API"""
        try:
            response = await self.client.embed(
                texts=texts,
                model=self.model_name,
                input_type="search_document"
            )
            
            embeddings = response.embeddings
            logger.debug(f"✅ Сгенерировано {len(embeddings)} Cohere эмбеддингов")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"❌ Ошибка Cohere API: {e}")
            raise
    
    async def generate_query_embedding(self, query: str) -> List[float]:
        """
        Генерирует эмбеддинг для поискового запроса
        (некоторые модели используют разные эмбеддинги для запросов и документов)
        
        Args:
            query: Поисковый запрос
        
        Returns:
            Вектор эмбеддинга
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            # Для E5 моделей используем специальный префикс для запросов
            if self.provider == "sentence-transformers" and "e5" in self.model_name.lower():
                return await self.generate_embedding(query, prefix="query")
            
            # Для Cohere используем другой input_type
            if self.provider == "cohere":
                response = await self.client.embed(
                    texts=[query],
                    model=self.model_name,
                    input_type="search_query"
                )
                return response.embeddings[0]
            
            # Для остальных провайдеров используем обычную генерацию
            return await self.generate_embedding(query)
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации query эмбеддинга: {e}")
            raise
    
    def get_embedding_dimension(self) -> int:
        """Возвращает размерность эмбеддинга"""
        dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
            "intfloat/multilingual-e5-large": 1024,
            "intfloat/multilingual-e5-base": 768,
            "sentence-transformers/all-MiniLM-L6-v2": 384,
            "embed-multilingual-v3.0": 1024,
            "embed-english-v3.0": 1024,
        }
        
        return dimensions.get(self.model_name, 768)  # Дефолтная размерность
    
    async def batch_generate_embeddings(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Генерирует эмбеддинги пакетами для больших объемов данных
        
        Args:
            texts: Список текстов
            batch_size: Размер пакета
        
        Returns:
            Список векторов эмбеддингов
        """
        try:
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                embeddings = await self.generate_embedding(batch)
                all_embeddings.extend(embeddings)
                
                logger.info(f"✅ Обработано {min(i + batch_size, len(texts))}/{len(texts)} текстов")
            
            return all_embeddings
            
        except Exception as e:
            logger.error(f"❌ Ошибка пакетной генерации эмбеддингов: {e}")
            raise


# Глобальный экземпляр генератора (по умолчанию Sentence-Transformers)
embedding_generator = EmbeddingGenerator(provider="sentence-transformers")

