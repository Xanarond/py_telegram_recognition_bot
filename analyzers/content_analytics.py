"""
Модуль аналитики контента и кластеризации
Анализирует интересы пользователя и выявляет паттерны
"""

import asyncio
from typing import Dict, List, Any, Optional
from collections import Counter
from datetime import datetime, timedelta

from utils.logger import setup_logger

logger = setup_logger(__name__)


class ContentAnalytics:
    """Аналитика контента и интересов пользователя"""
    
    def __init__(self):
        self.mongodb_manager = None
        self.vector_manager = None
        self._initialized = False
    
    async def initialize(self):
        """Инициализация модуля аналитики"""
        try:
            from storage.mongodb_manager import mongodb_manager
            from storage.vector_manager import vector_manager
            
            self.mongodb_manager = mongodb_manager
            self.vector_manager = vector_manager
            
            self._initialized = True
            logger.info("✅ Модуль аналитики инициализирован")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации модуля аналитики: {e}")
            self._initialized = False
    
    async def analyze_user_interests(self, user_id: int) -> Dict[str, Any]:
        """
        Анализирует интересы пользователя на основе сохраненного контента
        
        Args:
            user_id: ID пользователя
        
        Returns:
            Dict: Аналитика интересов
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            # Получаем все источники пользователя
            sources_data = await self.mongodb_manager.get_user_sources(
                user_id=user_id,
                page=1,
                per_page=1000  # Получаем все источники
            )
            
            sources = sources_data.get('sources', [])
            
            if not sources:
                return {
                    'total_sources': 0,
                    'message': 'Недостаточно данных для анализа'
                }
            
            # Анализируем категории
            categories = Counter()
            tags = Counter()
            complexity_levels = Counter()
            priority_levels = Counter()
            domains = Counter()
            
            for source in sources:
                categories[source.get('category', 'unknown')] += 1
                
                source_tags = source.get('tags', [])
                if isinstance(source_tags, list):
                    for tag in source_tags:
                        tags[tag] += 1
                
                complexity_levels[source.get('complexity_level', 'средний')] += 1
                priority_levels[source.get('priority_level', 'medium')] += 1
                
                url = source.get('url', '')
                if url:
                    domain = self._extract_domain(url)
                    domains[domain] += 1
            
            # Формируем результат
            analytics = {
                'total_sources': len(sources),
                'top_categories': dict(categories.most_common(5)),
                'top_tags': dict(tags.most_common(10)),
                'complexity_distribution': dict(complexity_levels),
                'priority_distribution': dict(priority_levels),
                'top_domains': dict(domains.most_common(5)),
                'diversity_score': self._calculate_diversity_score(categories, tags),
                'timestamp': datetime.now().isoformat()
            }
            
            # Добавляем временной анализ
            time_analysis = await self._analyze_temporal_patterns(sources)
            analytics['temporal_patterns'] = time_analysis
            
            # Добавляем анализ прогресса
            progress_analysis = self._analyze_reading_progress(sources)
            analytics['reading_progress'] = progress_analysis
            
            logger.info(f"✅ Анализ интересов выполнен для пользователя {user_id}")
            
            return analytics
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа интересов пользователя {user_id}: {e}")
            return {'error': str(e)}
    
    async def get_trending_topics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Определяет трендовые темы в последнее время
        
        Args:
            user_id: ID пользователя
            days: Период анализа в днях
        
        Returns:
            Dict: Трендовые темы
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            # Получаем источники за последний период
            cutoff_date = datetime.now() - timedelta(days=days)
            
            sources_data = await self.mongodb_manager.get_user_sources(
                user_id=user_id,
                page=1,
                per_page=1000
            )
            
            sources = sources_data.get('sources', [])
            
            # Фильтруем по дате
            recent_sources = [
                s for s in sources
                if self._parse_date(s.get('created_at')) >= cutoff_date
            ]
            
            if not recent_sources:
                return {
                    'period_days': days,
                    'sources_count': 0,
                    'message': 'Нет данных за указанный период'
                }
            
            # Анализируем тренды
            categories = Counter()
            tags = Counter()
            
            for source in recent_sources:
                categories[source.get('category', 'unknown')] += 1
                
                source_tags = source.get('tags', [])
                if isinstance(source_tags, list):
                    for tag in source_tags:
                        tags[tag] += 1
            
            return {
                'period_days': days,
                'sources_count': len(recent_sources),
                'trending_categories': dict(categories.most_common(5)),
                'trending_tags': dict(tags.most_common(10)),
                'growth_rate': len(recent_sources) / days,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа трендов для пользователя {user_id}: {e}")
            return {'error': str(e)}
    
    async def identify_knowledge_gaps(self, user_id: int) -> Dict[str, Any]:
        """
        Выявляет пробелы в знаниях пользователя
        
        Args:
            user_id: ID пользователя
        
        Returns:
            Dict: Анализ пробелов
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            # Получаем интересы пользователя
            interests = await self.analyze_user_interests(user_id)
            
            top_categories = interests.get('top_categories', {})
            top_tags = interests.get('top_tags', {})
            
            # Определяем основные области интересов
            main_areas = list(top_categories.keys())[:3]
            
            # Находим связанные темы, которых нет в базе
            # (это упрощенная версия, в реальности нужна более сложная логика)
            related_topics = self._suggest_related_topics(main_areas, top_tags)
            
            return {
                'main_interests': main_areas,
                'suggested_topics': related_topics,
                'coverage_score': self._calculate_coverage_score(top_categories, top_tags),
                'recommendations': self._generate_recommendations(interests)
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа пробелов для пользователя {user_id}: {e}")
            return {'error': str(e)}
    
    async def cluster_content(self, user_id: int, num_clusters: int = 5) -> Dict[str, Any]:
        """
        Кластеризует контент пользователя по темам
        (упрощенная версия на основе категорий и тегов)
        
        Args:
            user_id: ID пользователя
            num_clusters: Количество кластеров
        
        Returns:
            Dict: Результаты кластеризации
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            # Получаем все источники
            sources_data = await self.mongodb_manager.get_user_sources(
                user_id=user_id,
                page=1,
                per_page=1000
            )
            
            sources = sources_data.get('sources', [])
            
            if not sources:
                return {
                    'clusters': [],
                    'message': 'Недостаточно данных для кластеризации'
                }
            
            # Группируем по категориям (упрощенная кластеризация)
            clusters = {}
            
            for source in sources:
                category = source.get('category', 'unknown')
                
                if category not in clusters:
                    clusters[category] = {
                        'name': category,
                        'sources': [],
                        'tags': Counter(),
                        'avg_complexity': [],
                        'count': 0
                    }
                
                clusters[category]['sources'].append({
                    'id': source.get('_id'),
                    'title': source.get('title', 'Без названия'),
                    'url': source.get('url', '')
                })
                
                # Собираем теги
                source_tags = source.get('tags', [])
                if isinstance(source_tags, list):
                    for tag in source_tags:
                        clusters[category]['tags'][tag] += 1
                
                # Сложность
                complexity = source.get('complexity_level', 'средний')
                clusters[category]['avg_complexity'].append(complexity)
                
                clusters[category]['count'] += 1
            
            # Форматируем результат
            formatted_clusters = []
            for category, data in sorted(clusters.items(), key=lambda x: x[1]['count'], reverse=True)[:num_clusters]:
                formatted_clusters.append({
                    'name': category,
                    'count': data['count'],
                    'top_tags': dict(data['tags'].most_common(5)),
                    'sources_sample': data['sources'][:3],  # Первые 3 источника
                    'dominant_complexity': Counter(data['avg_complexity']).most_common(1)[0][0] if data['avg_complexity'] else 'средний'
                })
            
            return {
                'num_clusters': len(formatted_clusters),
                'clusters': formatted_clusters,
                'total_sources': len(sources),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка кластеризации для пользователя {user_id}: {e}")
            return {'error': str(e)}
    
    def _extract_domain(self, url: str) -> str:
        """Извлекает домен из URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return 'unknown'
    
    def _calculate_diversity_score(self, categories: Counter, tags: Counter) -> float:
        """Вычисляет оценку разнообразия интересов (0-1)"""
        try:
            # Чем больше разных категорий и тегов, тем выше разнообразие
            category_diversity = min(len(categories) / 10, 1.0)  # Нормализуем к 10 категориям
            tag_diversity = min(len(tags) / 50, 1.0)  # Нормализуем к 50 тегам
            
            # Средняя оценка
            diversity = (category_diversity + tag_diversity) / 2
            
            return round(diversity, 2)
        except:
            return 0.5
    
    async def _analyze_temporal_patterns(self, sources: List[Dict]) -> Dict[str, Any]:
        """Анализирует временные паттерны"""
        try:
            # Группируем по месяцам
            monthly_counts = Counter()
            
            for source in sources:
                created_at = self._parse_date(source.get('created_at'))
                if created_at:
                    month_key = created_at.strftime('%Y-%m')
                    monthly_counts[month_key] += 1
            
            # Находим самый активный месяц
            most_active_month = monthly_counts.most_common(1)[0] if monthly_counts else ('N/A', 0)
            
            return {
                'monthly_distribution': dict(monthly_counts.most_common(6)),
                'most_active_month': most_active_month[0],
                'most_active_count': most_active_month[1]
            }
        except:
            return {}
    
    def _analyze_reading_progress(self, sources: List[Dict]) -> Dict[str, Any]:
        """Анализирует прогресс чтения"""
        try:
            total = len(sources)
            read = sum(1 for s in sources if s.get('read_status') == 'read')
            unread = total - read
            
            # Анализ рейтингов
            rated = sum(1 for s in sources if s.get('rating', 0) > 0)
            avg_rating = 0
            if rated > 0:
                total_rating = sum(s.get('rating', 0) for s in sources)
                avg_rating = round(total_rating / rated, 2)
            
            return {
                'total': total,
                'read': read,
                'unread': unread,
                'read_percentage': round((read / total * 100) if total > 0 else 0, 1),
                'rated': rated,
                'avg_rating': avg_rating
            }
        except:
            return {}
    
    def _parse_date(self, date_str: Any) -> Optional[datetime]:
        """Парсит дату из строки или datetime объекта"""
        try:
            if isinstance(date_str, datetime):
                return date_str
            elif isinstance(date_str, str):
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return None
        except:
            return None
    
    def _suggest_related_topics(self, main_areas: List[str], top_tags: Dict) -> List[str]:
        """Предлагает связанные темы"""
        # Упрощенная логика предложений
        suggestions = []
        
        topic_relations = {
            'техническая статья': ['архитектура', 'best practices', 'паттерны проектирования'],
            'блог': ['личный опыт', 'кейс-стади', 'туториалы'],
            'документация': ['API reference', 'гайды', 'примеры использования'],
            'исследование': ['методология', 'эксперименты', 'результаты'],
        }
        
        for area in main_areas:
            if area in topic_relations:
                suggestions.extend(topic_relations[area])
        
        return list(set(suggestions))[:5]
    
    def _calculate_coverage_score(self, categories: Dict, tags: Dict) -> float:
        """Вычисляет оценку покрытия тем (0-1)"""
        try:
            # Оценка на основе количества категорий и тегов
            category_score = min(len(categories) / 8, 1.0)
            tag_score = min(len(tags) / 30, 1.0)
            
            return round((category_score + tag_score) / 2, 2)
        except:
            return 0.5
    
    def _generate_recommendations(self, interests: Dict) -> List[str]:
        """Генерирует рекомендации на основе интересов"""
        recommendations = []
        
        diversity_score = interests.get('diversity_score', 0.5)
        
        if diversity_score < 0.3:
            recommendations.append("Попробуйте изучать материалы из разных областей для расширения кругозора")
        
        top_categories = interests.get('top_categories', {})
        if len(top_categories) > 0:
            main_category = list(top_categories.keys())[0]
            recommendations.append(f"Вы активно изучаете '{main_category}' - продолжайте углубляться в эту тему")
        
        reading_progress = interests.get('reading_progress', {})
        unread_percentage = 100 - reading_progress.get('read_percentage', 0)
        if unread_percentage > 50:
            recommendations.append(f"У вас {unread_percentage:.0f}% непрочитанных статей - уделите время их изучению")
        
        return recommendations


# Глобальный экземпляр аналитики
content_analytics = ContentAnalytics()

