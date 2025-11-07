import asyncio
import json
from typing import Dict, Optional
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

import anthropic

from config import (
    ANTHROPIC_API_KEY, AI_MODEL, AI_MAX_TOKENS, AI_TEMPERATURE,
    HTTP_TIMEOUT, USER_AGENT, MAX_CONTENT_LENGTH, CONTENT_SELECTORS
)
from utils.logger import setup_logger

logger = setup_logger(__name__)


class SummaryAgent:
    """Агент для составления краткого пересказа статей"""
    
    def __init__(self, anthropic_api_key: str = ANTHROPIC_API_KEY):
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)
        # Создаем сессию для веб-запросов
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
    
    async def create_brief_summary(self, content_data: Dict, url: str) -> Dict:
        """Создает краткий пересказ контента"""
        try:
            title = content_data.get('title', 'Не указан')
            content = content_data.get('content', 'Не удалось получить')
            original_analysis = content_data.get('analysis', {})
            
            prompt = f"""
Создай краткий, структурированный пересказ следующего контента.
Пересказ должен быть сжатым, но информативным, подходящим для быстрого изучения.

URL: {url}
ЗАГОЛОВОК: {title}
СОДЕРЖИМОЕ: {content}

Создай пересказ в следующем JSON формате:
{{
    "brief_summary": "Очень краткое изложение основной сути в 1-2 предложениях",
    "main_thesis": "Главная идея или тезис статьи",
    "key_facts": ["Ключевой факт 1", "Ключевой факт 2", "Ключевой факт 3"],
    "conclusions": ["Основной вывод 1", "Основной вывод 2"],
    "practical_value": "Какую практическую пользу можно извлечь",
    "who_should_read": "Кому будет интересно/полезно",
    "reading_difficulty": "легко/средне/сложно",
    "summary_length": "количество слов в кратком пересказе (только число)",
    "compression_ratio": "во сколько раз сжат контент (например: 10:1)",
    "memorable_quote": "Наиболее запоминающаяся цитата или мысль из текста",
    "related_topics": ["Связанная тема 1", "Связанная тема 2", "Связанная тема 3"]
}}

ТРЕБОВАНИЯ:
- brief_summary должен быть максимально сжатым (до 50 слов)
- Сфокусируйся на главном, отбрось второстепенное
- Если контент некачественный, укажи это в brief_summary
- Отвечай только валидным JSON без дополнительных комментариев
"""
            
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model=AI_MODEL,
                    max_tokens=AI_MAX_TOKENS,
                    temperature=AI_TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            
            summary_data = json.loads(message.content[0].text)
            
            # Добавляем метаданные
            summary_data.update({
                'created_at': datetime.now().isoformat(),
                'original_length': len(content),
                'source_url': url,
                'agent_version': '1.0'
            })
            
            logger.info(f"✅ Создан пересказ для {url}")
            return summary_data
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания пересказа: {e}")
            return self._get_fallback_summary()

    async def create_detailed_summary(self, content_data: Dict, url: str) -> Dict:
        """Создает подробный пересказ контента"""
        try:
            title = content_data.get('title', 'Не указан')
            content = content_data.get('content', 'Не удалось получить')
            
            prompt = f"""
Создай подробный, структурированный пересказ следующего контента.
Пересказ должен быть полным, но организованным по разделам.

URL: {url}
ЗАГОЛОВОК: {title}
СОДЕРЖИМОЕ: {content}

Создай пересказ в следующем JSON формате:
{{
    "executive_summary": "Краткое резюме для руководителей (2-3 предложения)",
    "introduction": "Введение и контекст",
    "main_sections": [
        {{
            "section_title": "Название раздела",
            "content": "Содержание раздела",
            "key_points": ["Ключевой момент 1", "Ключевой момент 2"]
        }}
    ],
    "methodology": "Методология или подход (если применимо)",
    "findings": ["Основное открытие 1", "Основное открытие 2", "Основное открытие 3"],
    "implications": "Значение и последствия",
    "recommendations": ["Рекомендация 1", "Рекомендация 2"],
    "limitations": "Ограничения или предостережения",
    "future_directions": "Направления для дальнейшего изучения",
    "author_perspective": "Позиция автора или источника",
    "critical_analysis": "Критический анализ представленной информации"
}}

ТРЕБОВАНИЯ:
- Сохрани логическую структуру оригинала
- Включи важные детали и нюансы
- Если контент неполный, укажи это
- Отвечай только валидным JSON без дополнительных комментариев
"""
            
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model=AI_MODEL,
                    max_tokens=AI_MAX_TOKENS,  # Используем настройку из конфига
                    temperature=AI_TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            
            detailed_summary = json.loads(message.content[0].text)
            
            # Добавляем метаданные
            detailed_summary.update({
                'created_at': datetime.now().isoformat(),
                'original_length': len(content),
                'source_url': url,
                'summary_type': 'detailed',
                'agent_version': '1.0'
            })
            
            logger.info(f"✅ Создан подробный пересказ для {url}")
            return detailed_summary
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания подробного пересказа: {e}")
            return self._get_fallback_detailed_summary()

    def _get_fallback_summary(self) -> Dict:
        """Возвращает базовый пересказ в случае ошибки"""
        return {
            "brief_summary": "Не удалось создать пересказ контента",
            "main_thesis": "Контент недоступен для анализа",
            "key_facts": ["Возможны проблемы с доступом к источнику"],
            "conclusions": ["Требуется ручная проверка"],
            "practical_value": "Ограниченная польза без доступа к контенту",
            "who_should_read": "Администратор системы",
            "reading_difficulty": "неопределено",
            "summary_length": "20",
            "compression_ratio": "1:1",
            "memorable_quote": "Контент временно недоступен",
            "related_topics": ["техническая_проблема", "недоступный_контент"],
            "created_at": datetime.now().isoformat(),
            "agent_version": "1.0"
        }

    def _get_fallback_detailed_summary(self) -> Dict:
        """Возвращает базовый подробный пересказ в случае ошибки"""
        return {
            "executive_summary": "Контент недоступен для создания пересказа",
            "introduction": "Произошла ошибка при получении или обработке контента",
            "main_sections": [
                {
                    "section_title": "Техническая проблема",
                    "content": "Не удалось создать пересказ из-за технических проблем",
                    "key_points": ["Проверить доступность источника", "Повторить попытку позже"]
                }
            ],
            "methodology": "Автоматический анализ с помощью ИИ",
            "findings": ["Контент недоступен"],
            "implications": "Требуется ручная проверка",
            "recommendations": ["Проверить URL", "Обратиться к администратору"],
            "limitations": "Техническая недоступность контента",
            "future_directions": "Устранение технических проблем",
            "author_perspective": "Системное сообщение",
            "critical_analysis": "Невозможно провести анализ без доступа к контенту",
            "created_at": datetime.now().isoformat(),
            "summary_type": "detailed",
            "agent_version": "1.0"
        }

    async def get_summary_stats(self, summary_data: Dict) -> Dict:
        """Получает статистику пересказа"""
        try:
            brief_summary = summary_data.get('brief_summary', '')
            word_count = len(brief_summary.split())
            
            stats = {
                'word_count': word_count,
                'character_count': len(brief_summary),
                'estimated_read_time_seconds': max(word_count * 0.3, 5),  # ~200 слов в минуту
                'compression_achieved': summary_data.get('compression_ratio', 'неизвестно'),
                'difficulty_level': summary_data.get('reading_difficulty', 'неопределено'),
                'summary_quality_score': self._calculate_quality_score(summary_data)
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета статистики пересказа: {e}")
            return {}

    def _calculate_quality_score(self, summary_data: Dict) -> int:
        """Рассчитывает оценку качества пересказа (1-10)"""
        try:
            score = 5  # Базовая оценка
            
            # Проверяем наличие ключевых полей
            required_fields = ['brief_summary', 'main_thesis', 'key_facts']
            for field in required_fields:
                if summary_data.get(field):
                    score += 1
            
            # Проверяем длину пересказа
            summary_length = len(summary_data.get('brief_summary', ''))
            if 50 < summary_length < 500:  # Оптимальная длина
                score += 1
            
            # Проверяем наличие практической ценности
            if summary_data.get('practical_value'):
                score += 1
                
            return min(score, 10)
            
        except Exception:
            return 5

    async def fetch_page_content(self, url: str) -> Optional[Dict]:
        """Извлекает контент непосредственно со страницы"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.session.get(url, timeout=HTTP_TIMEOUT)
            )
            response.raise_for_status()
            
            # Извлекаем текстовое содержимое
            return self._extract_article_content(response.text, url)
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения контента с {url}: {e}")
            return None

    def _extract_article_content(self, html_content: str, url: str) -> Dict:
        """Извлекает статейный контент из HTML, оптимизированный для пересказов"""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Удаляем ненужные элементы
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript', 'form', 'button']):
                element.decompose()
            
            # Извлекаем заголовок
            title = self._extract_title(soup)
            
            # Извлекаем основной контент статьи
            article_content = self._extract_main_article(soup)
            
            # Извлекаем дополнительную информацию
            metadata = self._extract_metadata(soup)
            
            return {
                'title': title,
                'content': article_content,
                'metadata': metadata,
                'url': url,
                'content_length': len(article_content),
                'extracted_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения контента: {e}")
            return {
                'title': 'Ошибка извлечения',
                'content': f'Не удалось извлечь контент: {str(e)}',
                'metadata': {},
                'url': url
            }

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Извлекает заголовок статьи"""
        # Приоритетные селекторы для заголовков статей
        title_selectors = [
            'h1.title', 'h1.headline', 'h1.article-title', 'h1.post-title',
            '.article-header h1', '.post-header h1', '.entry-title',
            'h1', 'title'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title and len(title) > 5:
                    return title
        
        # Если не найден, пробуем meta теги
        meta_title = soup.find('meta', attrs={'property': 'og:title'}) or soup.find('meta', attrs={'name': 'title'})
        if meta_title:
            title = meta_title.get('content', '').strip()
            if title:
                return title
        
        return "Без названия"

    def _extract_main_article(self, soup: BeautifulSoup) -> str:
        """Извлекает основной текст статьи"""
        # Приоритетные селекторы для контента статей
        article_selectors = [
            'article', '.article-content', '.post-content', '.entry-content',
            '.article-body', '.post-body', '.content', 'main',
            '[role="main"]', '.text', '.story-body', '.article-text'
        ] + CONTENT_SELECTORS
        
        best_content = ""
        max_content_length = 0
        
        for selector in article_selectors:
            elements = soup.select(selector)
            for element in elements:
                # Очищаем от вложенных навигационных элементов
                for nested in element.find_all(['nav', 'aside', '.sidebar', '.related', '.comments']):
                    nested.decompose()
                
                content = element.get_text(separator='\n', strip=True)
                if len(content) > max_content_length and len(content) > 200:
                    max_content_length = len(content)
                    best_content = content
        
        # Если основной контент не найден, извлекаем параграфы
        if not best_content or len(best_content) < 200:
            paragraphs = soup.find_all('p')
            if paragraphs:
                para_texts = []
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if len(text) > 20:  # Пропускаем очень короткие параграфы
                        para_texts.append(text)
                best_content = '\n\n'.join(para_texts)
        
        return best_content[:MAX_CONTENT_LENGTH] if best_content else "Контент не найден"

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict:
        """Извлекает метаданные статьи"""
        metadata = {}
        
        # Описание
        meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
        if meta_desc:
            metadata['description'] = meta_desc.get('content', '').strip()
        
        # Автор
        author_selectors = [
            'meta[name="author"]', 'meta[property="article:author"]',
            '.author', '.byline', '.article-author', '.post-author'
        ]
        for selector in author_selectors:
            author_elem = soup.select_one(selector)
            if author_elem:
                if author_elem.name == 'meta':
                    author = author_elem.get('content', '').strip()
                else:
                    author = author_elem.get_text(strip=True)
                if author:
                    metadata['author'] = author
                    break
        
        # Дата публикации
        date_selectors = [
            'meta[property="article:published_time"]', 'meta[name="publish_date"]',
            'time[datetime]', '.publish-date', '.article-date', '.post-date'
        ]
        for selector in date_selectors:
            date_elem = soup.select_one(selector)
            if date_elem:
                if date_elem.name == 'meta':
                    date = date_elem.get('content', '').strip()
                elif date_elem.name == 'time':
                    date = date_elem.get('datetime', '') or date_elem.get_text(strip=True)
                else:
                    date = date_elem.get_text(strip=True)
                if date:
                    metadata['publish_date'] = date
                    break
        
        return metadata

    async def create_brief_summary_from_url(self, url: str) -> Dict:
        """Создает краткий пересказ непосредственно с URL"""
        try:
            # Извлекаем контент со страницы
            page_content = await self.fetch_page_content(url)
            if not page_content:
                return self._get_fallback_summary()
            
            title = page_content.get('title', 'Без названия')
            content = page_content.get('content', '')
            metadata = page_content.get('metadata', {})
            
            # Улучшенный промпт с учетом метаданных
            author_info = f"Автор: {metadata.get('author', 'Не указан')}" if metadata.get('author') else ""
            date_info = f"Дата: {metadata.get('publish_date', 'Не указана')}" if metadata.get('publish_date') else ""
            description_info = f"Описание: {metadata.get('description', '')}" if metadata.get('description') else ""
            
            additional_context = "\n".join(filter(None, [author_info, date_info, description_info]))
            
            prompt = f"""
Создай краткий, структурированный пересказ следующей статьи.
Пересказ должен быть сжатым, но информативным, подходящим для быстрого изучения.

URL: {url}
ЗАГОЛОВОК: {title}
{additional_context}

СОДЕРЖИМОЕ СТАТЬИ: {content}

Создай пересказ в следующем JSON формате:
{{
    "brief_summary": "Очень краткое изложение основной сути в 1-2 предложениях",
    "main_thesis": "Главная идея или тезис статьи",
    "key_facts": ["Ключевой факт 1", "Ключевой факт 2", "Ключевой факт 3"],
    "conclusions": ["Основной вывод 1", "Основной вывод 2"],
    "practical_value": "Какую практическую пользу можно извлечь",
    "who_should_read": "Кому будет интересно/полезно",
    "reading_difficulty": "легко/средне/сложно",
    "summary_length": "количество слов в кратком пересказе (только число)",
    "compression_ratio": "во сколько раз сжат контент (например: 10:1)",
    "memorable_quote": "Наиболее запоминающаяся цитата или мысль из текста",
    "related_topics": ["Связанная тема 1", "Связанная тема 2", "Связанная тема 3"],
    "article_type": "тип статьи (техническая, новость, блог, исследование, обзор, гайд, мнение)",
    "expertise_level": "необходимый уровень знаний для понимания"
}}

ТРЕБОВАНИЯ:
- brief_summary должен быть максимально сжатым (до 50 слов)
- Сфокусируйся на главном, отбрось второстепенное
- Учти контекст автора и даты публикации если они есть
- Отвечай только валидным JSON без дополнительных комментариев
"""
            
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model=AI_MODEL,
                    max_tokens=AI_MAX_TOKENS,
                    temperature=AI_TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            
            summary_data = json.loads(message.content[0].text)
            
            # Добавляем метаданные
            summary_data.update({
                'created_at': datetime.now().isoformat(),
                'original_length': len(content),
                'source_url': url,
                'extracted_metadata': metadata,
                'content_extraction_quality': 'high' if len(content) > 1000 else 'medium' if len(content) > 300 else 'low',
                'agent_version': '1.1'
            })
            
            logger.info(f"✅ Создан пересказ с URL {url}")
            return summary_data
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания пересказа с URL: {e}")
            return self._get_fallback_summary()

    async def create_detailed_summary_from_url(self, url: str) -> Dict:
        """Создает подробный пересказ непосредственно с URL"""
        try:
            # Извлекаем контент со страницы
            page_content = await self.fetch_page_content(url)
            if not page_content:
                return self._get_fallback_detailed_summary()
            
            title = page_content.get('title', 'Без названия')
            content = page_content.get('content', '')
            metadata = page_content.get('metadata', {})
            
            # Улучшенный промпт с учетом метаданных
            author_info = f"Автор: {metadata.get('author', 'Не указан')}" if metadata.get('author') else ""
            date_info = f"Дата: {metadata.get('publish_date', 'Не указана')}" if metadata.get('publish_date') else ""
            description_info = f"Описание: {metadata.get('description', '')}" if metadata.get('description') else ""
            
            additional_context = "\n".join(filter(None, [author_info, date_info, description_info]))
            
            prompt = f"""
Создай подробный, структурированный пересказ следующей статьи.
Пересказ должен быть полным, но организованным по разделам.

URL: {url}
ЗАГОЛОВОК: {title}
{additional_context}

СОДЕРЖИМОЕ СТАТЬИ: {content}

Создай пересказ в следующем JSON формате:
{{
    "executive_summary": "Краткое резюме для руководителей (2-3 предложения)",
    "introduction": "Введение и контекст статьи",
    "main_sections": [
        {{
            "section_title": "Название раздела",
            "content": "Содержание раздела",
            "key_points": ["Ключевой момент 1", "Ключевой момент 2"]
        }}
    ],
    "methodology": "Методология или подход (если применимо)",
    "findings": ["Основное открытие 1", "Основное открытие 2", "Основное открытие 3"],
    "implications": "Значение и последствия",
    "recommendations": ["Рекомендация 1", "Рекомендация 2"],
    "limitations": "Ограничения или предостережения",
    "future_directions": "Направления для дальнейшего изучения",
    "author_perspective": "Позиция автора или источника",
    "critical_analysis": "Критический анализ представленной информации",
    "key_takeaways": ["Главный вывод 1", "Главный вывод 2", "Главный вывод 3"],
    "conclusion": "Общее заключение",
    "practical_value": "Практическая ценность для читателя"
}}

ТРЕБОВАНИЯ:
- Сохрани логическую структуру оригинала
- Включи важные детали и нюансы
- Учти авторский контекст и временные рамки
- Отвечай только валидным JSON без дополнительных комментариев
"""
            
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model=AI_MODEL,
                    max_tokens=AI_MAX_TOKENS,  # Используем настройку из конфига
                    temperature=AI_TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            
            detailed_summary = json.loads(message.content[0].text)
            
            # Добавляем метаданные
            detailed_summary.update({
                'created_at': datetime.now().isoformat(),
                'original_length': len(content),
                'source_url': url,
                'extracted_metadata': metadata,
                'summary_type': 'detailed',
                'content_extraction_quality': 'high' if len(content) > 1000 else 'medium' if len(content) > 300 else 'low',
                'agent_version': '1.1'
            })
            
            logger.info(f"✅ Создан подробный пересказ с URL {url}")
            return detailed_summary
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания подробного пересказа с URL: {e}")
            return self._get_fallback_detailed_summary() 