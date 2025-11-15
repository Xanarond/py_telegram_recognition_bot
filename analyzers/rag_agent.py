"""
RAG (Retrieval-Augmented Generation) агент
Отвечает на вопросы пользователя на основе его базы знаний
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
import anthropic

from config import (
    ANTHROPIC_API_KEY, AI_MODEL, RAG_CONTEXT_SOURCES,
    RAG_MAX_CONTEXT_LENGTH, RAG_TEMPERATURE, ENABLE_RAG
)
from utils.logger import setup_logger

logger = setup_logger(__name__)


class RAGAgent:
    """RAG агент для ответов на вопросы по базе знаний"""
    
    def __init__(self, anthropic_api_key: str = ANTHROPIC_API_KEY):
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)
        self.vectorization_service = None
        self.mongodb_manager = None
        self._initialized = False
    
    async def initialize(self):
        """Инициализация RAG агента"""
        try:
            if not ENABLE_RAG:
                logger.info("⚠️ RAG функциональность отключена в конфигурации")
                return
            
            from analyzers.vectorization_service import vectorization_service
            from storage.mongodb_manager import mongodb_manager
            
            self.vectorization_service = vectorization_service
            self.mongodb_manager = mongodb_manager
            
            # Инициализируем сервис векторизации
            await self.vectorization_service.initialize()
            
            self._initialized = True
            logger.info("✅ RAG агент инициализирован")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации RAG агента: {e}")
            self._initialized = False
    
    async def ask_question(
        self,
        question: str,
        user_id: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Отвечает на вопрос пользователя на основе его базы знаний
        
        Args:
            question: Вопрос пользователя
            user_id: ID пользователя
            filters: Дополнительные фильтры для поиска
        
        Returns:
            Dict: Ответ с источниками и метаданными
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            if not self._initialized:
                return {
                    'success': False,
                    'error': 'RAG агент не инициализирован',
                    'answer': 'Извините, система RAG временно недоступна.'
                }
            
            # Шаг 1: Поиск релевантных документов
            logger.info(f"🔍 Поиск контекста для вопроса: {question[:100]}...")
            relevant_docs = await self.vectorization_service.search_similar_content(
                query=question,
                user_id=user_id,
                top_k=RAG_CONTEXT_SOURCES,
                filters=filters
            )
            
            if not relevant_docs:
                return {
                    'success': True,
                    'answer': 'К сожалению, я не нашел релевантной информации в вашей базе знаний по этому вопросу.',
                    'sources': [],
                    'context_used': 0
                }
            
            # Шаг 2: Получаем полную информацию о документах из MongoDB
            sources_info = await self._fetch_sources_details(relevant_docs)
            
            # Шаг 3: Формируем контекст для Claude
            context = self._build_context(relevant_docs, sources_info)
            
            # Шаг 4: Генерируем ответ с помощью Claude
            answer = await self._generate_answer(question, context)
            
            # Шаг 5: Форматируем результат
            result = {
                'success': True,
                'answer': answer,
                'sources': sources_info,
                'context_used': len(relevant_docs),
                'question': question
            }
            
            logger.info(f"✅ Ответ сгенерирован на основе {len(relevant_docs)} источников")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки вопроса: {e}")
            return {
                'success': False,
                'error': str(e),
                'answer': f'Произошла ошибка при обработке вопроса: {str(e)}'
            }
    
    async def compare_sources(
        self,
        topic: str,
        user_id: int,
        num_sources: int = 5
    ) -> Dict[str, Any]:
        """
        Сравнивает разные источники по заданной теме
        
        Args:
            topic: Тема для сравнения
            user_id: ID пользователя
            num_sources: Количество источников для сравнения
        
        Returns:
            Dict: Сравнительный анализ
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            if not self._initialized:
                return {'success': False, 'error': 'RAG агент не инициализирован'}
            
            # Находим релевантные источники
            relevant_docs = await self.vectorization_service.search_similar_content(
                query=topic,
                user_id=user_id,
                top_k=num_sources
            )
            
            if len(relevant_docs) < 2:
                return {
                    'success': True,
                    'analysis': 'Недостаточно источников для сравнения. Нужно минимум 2 источника.',
                    'sources': []
                }
            
            # Получаем детали источников
            sources_info = await self._fetch_sources_details(relevant_docs)
            
            # Формируем контекст
            context = self._build_context(relevant_docs, sources_info)
            
            # Генерируем сравнительный анализ
            prompt = f"""На основе предоставленных источников, проведи сравнительный анализ по теме: "{topic}"

Контекст из базы знаний пользователя:
{context}

Задача:
1. Выдели общие темы и идеи между источниками
2. Укажи различия в подходах и мнениях
3. Отметь уникальные инсайты из каждого источника
4. Сделай общий вывод о том, что говорят эти материалы по теме

Отвечай структурированно на русском языке."""
            
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model=AI_MODEL,
                    max_tokens=3000,
                    temperature=RAG_TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            
            analysis = message.content[0].text
            
            return {
                'success': True,
                'analysis': analysis,
                'sources': sources_info,
                'topic': topic
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка сравнения источников: {e}")
            return {'success': False, 'error': str(e)}
    
    async def synthesize_topic(
        self,
        topic: str,
        user_id: int,
        synthesis_type: str = "summary"
    ) -> Dict[str, Any]:
        """
        Создает синтез информации по теме из всех релевантных источников
        
        Args:
            topic: Тема для синтеза
            user_id: ID пользователя
            synthesis_type: Тип синтеза (summary, detailed, outline)
        
        Returns:
            Dict: Синтезированная информация
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            if not self._initialized:
                return {'success': False, 'error': 'RAG агент не инициализирован'}
            
            # Находим все релевантные источники
            relevant_docs = await self.vectorization_service.search_similar_content(
                query=topic,
                user_id=user_id,
                top_k=10  # Больше источников для полного синтеза
            )
            
            if not relevant_docs:
                return {
                    'success': True,
                    'synthesis': f'Не найдено информации по теме "{topic}" в вашей базе знаний.',
                    'sources': []
                }
            
            # Получаем детали
            sources_info = await self._fetch_sources_details(relevant_docs)
            context = self._build_context(relevant_docs, sources_info)
            
            # Формируем промпт в зависимости от типа синтеза
            synthesis_prompts = {
                "summary": "Создай краткий обзор (2-3 абзаца) основных идей по теме",
                "detailed": "Создай подробный конспект со всеми важными деталями, структурированный по разделам",
                "outline": "Создай структурированный план (outline) с основными пунктами и подпунктами"
            }
            
            task = synthesis_prompts.get(synthesis_type, synthesis_prompts["summary"])
            
            prompt = f"""На основе всех предоставленных источников, {task}: "{topic}"

Контекст из базы знаний пользователя:
{context}

Требования:
- Объедини информацию из всех источников
- Избегай повторений
- Структурируй информацию логично
- Укажи ключевые концепции и идеи
- Отвечай на русском языке

Создай качественный синтез информации."""
            
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model=AI_MODEL,
                    max_tokens=4000,
                    temperature=RAG_TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            
            synthesis = message.content[0].text
            
            return {
                'success': True,
                'synthesis': synthesis,
                'sources': sources_info,
                'sources_count': len(sources_info),
                'topic': topic,
                'type': synthesis_type
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка синтеза темы: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _fetch_sources_details(self, relevant_docs: List[Dict]) -> List[Dict[str, Any]]:
        """Получает полную информацию о документах из MongoDB"""
        sources_info = []
        
        for doc in relevant_docs:
            try:
                # Получаем полную информацию из MongoDB
                synopsis = await self.mongodb_manager.get_synopsis_by_id(doc['id'])
                
                if synopsis:
                    sources_info.append({
                        'id': doc['id'],
                        'title': synopsis.get('title', 'Без названия'),
                        'url': synopsis.get('url', ''),
                        'category': synopsis.get('category', ''),
                        'relevance': 1 - doc.get('distance', 0),  # Конвертируем distance в relevance
                        'summary': synopsis.get('summary', ''),
                        'tags': synopsis.get('tags', [])
                    })
            except Exception as e:
                logger.warning(f"⚠️ Не удалось получить детали источника {doc['id']}: {e}")
        
        return sources_info
    
    def _build_context(
        self,
        relevant_docs: List[Dict],
        sources_info: List[Dict[str, Any]]
    ) -> str:
        """Формирует контекст для Claude из найденных документов"""
        context_parts = []
        total_length = 0
        
        for i, (doc, info) in enumerate(zip(relevant_docs, sources_info), 1):
            # Формируем блок контекста для каждого источника
            source_block = f"""
[Источник {i}]
Название: {info['title']}
Категория: {info['category']}
URL: {info['url']}
Релевантность: {info['relevance']:.2f}

Содержание:
{doc.get('document', '')[:2000]}  # Ограничиваем длину каждого документа

---
"""
            
            # Проверяем, не превышаем ли лимит контекста
            if total_length + len(source_block) > RAG_MAX_CONTEXT_LENGTH:
                logger.info(f"⚠️ Достигнут лимит контекста, использовано {i-1} источников из {len(relevant_docs)}")
                break
            
            context_parts.append(source_block)
            total_length += len(source_block)
        
        return "\n".join(context_parts)
    
    async def _generate_answer(self, question: str, context: str) -> str:
        """Генерирует ответ на вопрос с использованием контекста"""
        try:
            prompt = f"""Ты - персональный ассистент по базе знаний пользователя. Ответь на вопрос пользователя, используя ТОЛЬКО информацию из предоставленного контекста.

Контекст из базы знаний пользователя:
{context}

Вопрос пользователя: {question}

Инструкции:
1. Отвечай ТОЛЬКО на основе предоставленного контекста
2. Если информации недостаточно, честно скажи об этом
3. Цитируй конкретные источники при ответе (например, "Согласно Источнику 1...")
4. Будь конкретным и структурированным
5. Отвечай на русском языке
6. Если в контексте есть противоречивая информация, укажи на это

Ответь на вопрос пользователя."""
            
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model=AI_MODEL,
                    max_tokens=2000,
                    temperature=RAG_TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            
            answer = message.content[0].text
            
            return answer
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации ответа: {e}")
            return f"Извините, произошла ошибка при генерации ответа: {str(e)}"


# Глобальный экземпляр RAG агента
rag_agent = RAGAgent()

