import asyncio
import json
from datetime import datetime
from typing import Dict, Optional
import re

import requests
import anthropic
from bs4 import BeautifulSoup

from config import (
    ANTHROPIC_API_KEY, SUPPORTED_DOMAINS, HTTP_TIMEOUT, USER_AGENT,
    CONTENT_SELECTORS, MAX_CONTENT_LENGTH, AI_MODEL, AI_MAX_TOKENS, AI_TEMPERATURE
)
from utils.logger import setup_logger

logger = setup_logger(__name__)


class AIContentAnalyzer:
    def __init__(self, anthropic_api_key: str = ANTHROPIC_API_KEY):
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.supported_domains = SUPPORTED_DOMAINS

    def is_supported_url(self, url: str) -> bool:
        """Проверяет, является ли URL валидным HTTP/HTTPS URL"""
        # Проверяем валидность URL с помощью регулярного выражения
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(url_pattern, url):
            return False
        
        # Дополнительная проверка на основные требования к URL
        if not (url.startswith('http://') or url.startswith('https://')):
            return False
            
        # Проверяем, что URL содержит домен
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return bool(parsed.netloc)
        except Exception:
            return False

    def get_domain_emoji(self, url: str) -> str:
        """Возвращает эмодзи для домена"""
        for domain, emoji in self.supported_domains.items():
            if domain in url.lower():
                return emoji
        # Возвращаем общий эмодзи для неизвестных доменов
        return '🌐'

    async def fetch_content(self, url: str) -> Optional[str]:
        """Получает содержимое веб-страницы"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.session.get(url, timeout=HTTP_TIMEOUT)
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Ошибка при получении контента с {url}: {e}")
            return None

    def extract_text_content(self, html_content: str) -> Dict:
        """Извлекает текстовое содержимое из HTML"""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Удаляем ненужные элементы
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript']):
                element.decompose()
            
            # Извлекаем заголовок
            title = soup.find('title')
            title_text = title.get_text().strip() if title else ""
            
            # Извлекаем мета описание как дополнительный контент
            meta_description = ""
            meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            if meta_desc:
                meta_description = meta_desc.get('content', '').strip()
            
            # Извлекаем основной контент
            main_content = ""
            
            # Расширенный список селекторов для разных типов сайтов
            extended_selectors = CONTENT_SELECTORS + [
                '.container', '.wrapper', '.main-content', '.page-content',
                '[role="main"]', '.post', '.story', '.text', '.description',
                'p', 'div.content', '.article-body', '.entry', '.single-content'
            ]
            
            for selector in extended_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    content_text = content_element.get_text(separator='\n', strip=True)
                    if len(content_text) > 100:  # Минимальная длина контента
                        main_content = content_text
                        break
            
            # Если основной контент не найден, пробуем извлечь все параграфы
            if not main_content or len(main_content) < 100:
                paragraphs = soup.find_all('p')
                if paragraphs:
                    main_content = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            
            # Если всё ещё нет контента, берём всё содержимое body
            if not main_content:
                body = soup.find('body')
                if body:
                    main_content = body.get_text(separator='\n', strip=True)
            
            # Объединяем мета описание с основным контентом если оно есть
            if meta_description and meta_description not in main_content:
                main_content = f"{meta_description}\n\n{main_content}"
            
            # Очищаем и ограничиваем размер
            main_content = main_content.strip()
            if not main_content:
                main_content = "Не удалось извлечь текстовое содержимое"
            
            return {
                'title': title_text or "Без названия",
                'content': main_content[:MAX_CONTENT_LENGTH]
            }
        except Exception as e:
            logger.error(f"Ошибка при извлечении текста: {e}")
            return {
                'title': 'Ошибка извлечения заголовка',
                'content': f'Не удалось извлечь содержимое: {str(e)}'
            }

    async def analyze_with_ai(self, content_data: Dict, url: str) -> Dict:
        """Анализирует контент с помощью ИИ"""
        try:
            title = content_data.get('title', 'Не указан')
            content = content_data.get('content', 'Не удалось получить')
            
            prompt = f"""
Проанализируй следующий веб-контент любого типа и предоставь структурированный анализ.
Адаптируй анализ под тип и качество контента:

URL: {url}
ЗАГОЛОВОК: {title}
СОДЕРЖИМОЕ: {content}

Предоставь анализ в следующем JSON формате:
{{
    "summary": "Краткое резюме содержимого (2-3 предложения). Если контент неполный или некачественный, укажи это",
    "key_points": ["Ключевой момент 1", "Ключевой момент 2", "Ключевой момент 3"],
    "category": "категория контента (техническая статья, новость, блог, документация, коммерческий сайт, социальная сеть, форум, обучающий материал, исследование, личная страница, корпоративный сайт, и т.д.)",
    "complexity_level": "уровень сложности (начальный, средний, продвинутый, неопределен)",
    "estimated_reading_time": "примерное время чтения в минутах (только число от 1 до 60)",
    "relevance_score": "оценка релевантности и качества контента от 1 до 10 (только число)",
    "action_items": ["Практическое действие 1", "Практическое действие 2", "Практическое действие 3"],
    "tags": ["тег1", "тег2", "тег3", "тег4", "тег5"],
    "priority_level": "high/medium/low",
    "target_audience": "целевая аудитория (разработчики, бизнес, студенты, общая, специалисты, и т.д.)"
}}

ВАЖНО: 
- Если контент плохо извлечён или неполный, снизь relevance_score и укажи это в summary
- Для коммерческих сайтов, лендингов используй соответствующие категории
- Адаптируй теги под фактический тип контента
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
            
            # Проверяем, что получили ответ
            if not message.content or len(message.content) == 0:
                logger.error("Claude API вернул пустой ответ")
                return self._get_fallback_analysis()
            
            response_text = message.content[0].text
            
            # Логируем ответ для отладки
            logger.debug(f"Ответ от Claude API (первые 500 символов): {response_text[:500]}")
            
            # Проверяем, что ответ не пустой
            if not response_text or not response_text.strip():
                logger.error("Claude API вернул пустой текст")
                return self._get_fallback_analysis()
            
            # Пытаемся извлечь JSON из ответа (на случай если Claude обернул JSON в текст)
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                response_text = json_match.group(0)
            
            # Парсим JSON
            ai_analysis = json.loads(response_text)
            return ai_analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON от Claude API: {e}")
            logger.error(f"Полученный текст: {response_text if 'response_text' in locals() else 'недоступен'}")
            return self._get_fallback_analysis()
        except Exception as e:
            logger.error(f"Ошибка при анализе с ИИ: {e}")
            return self._get_fallback_analysis()

    def _get_fallback_analysis(self) -> Dict:
        """Возвращает базовый анализ в случае ошибки"""
        return {
            "summary": "Не удалось автоматически проанализировать контент. Требуется ручная проверка.",
            "key_points": ["Контент недоступен для автоматического анализа", "Возможны проблемы с доступом к сайту", "Может потребоваться альтернативный способ анализа"],
            "category": "неопределенный",
            "complexity_level": "неопределен",
            "estimated_reading_time": "5",
            "relevance_score": "3",
            "action_items": ["Открыть ссылку в браузере для ручной проверки", "Проверить доступность сайта", "Попробовать позже"],
            "tags": ["требует_проверки", "недоступен", "ошибка_анализа"],
            "priority_level": "low",
            "target_audience": "общая"
        }

    async def analyze_url(self, url: str) -> Dict:
        """Полный анализ URL"""
        if not self.is_supported_url(url):
            return None
        
        html_content = await self.fetch_content(url)
        if not html_content:
            return None
        
        content_data = self.extract_text_content(html_content)
        ai_analysis = await self.analyze_with_ai(content_data, url)
        
        return {
            'url': url,
            'title': content_data.get('title', 'Без названия'),
            'domain_emoji': self.get_domain_emoji(url),
            'analysis': ai_analysis,
            'timestamp': datetime.now().isoformat()
        } 