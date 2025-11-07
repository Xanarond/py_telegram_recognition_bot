import json
import os
from datetime import datetime
from typing import Dict

from config import STATS_FILE
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Глобальная статистика
user_stats = {}


class StatsManager:
    @staticmethod
    def load_stats():
        """Загружает статистику из файла"""
        global user_stats
        try:
            # Создаем директорию data если её нет
            os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
            
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, 'r', encoding='utf-8') as f:
                    loaded_stats = json.load(f)
                    # Конвертируем строковые ключи обратно в int
                    user_stats = {int(k): v for k, v in loaded_stats.items()}
                    
                # Выполняем миграцию для добавления полей статуса прочтения
                StatsManager._migrate_read_status()
                
                logger.info("✅ Статистика успешно загружена из файла")
            else:
                user_stats = {}
                logger.info("ℹ️ Файл статистики не найден, создан новый")
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке статистики: {e}")
            user_stats = {}

    @staticmethod
    def _migrate_read_status():
        """Миграция для добавления полей статуса прочтения к существующим источникам"""
        migrated = False
        for user_id, stats in user_stats.items():
            sources = stats.get('sources', [])
            for i, source in enumerate(sources):
                # Проверяем, есть ли уже поля статуса прочтения
                if 'read_status' not in source:
                    source['read_status'] = 'unread'
                    source['read_timestamp'] = None
                    source['source_id'] = f"{user_id}_{i}"
                    migrated = True
        
        # Сохраняем изменения если была выполнена миграция
        if migrated:
            StatsManager.save_stats()
            logger.info("✅ Выполнена миграция статуса прочтения для существующих источников")

    @staticmethod
    def save_stats():
        """Сохраняет статистику в файл"""
        try:
            # Создаем директорию data если её нет
            os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
            
            # Создаем временный файл
            temp_file = f"{STATS_FILE}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(user_stats, f, ensure_ascii=False, indent=2)
            
            # Безопасно заменяем основной файл
            if os.path.exists(STATS_FILE):
                os.replace(temp_file, STATS_FILE)
            else:
                os.rename(temp_file, STATS_FILE)
            
            logger.info("✅ Статистика успешно сохранена в файл")
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении статистики: {e}")
            # Пытаемся удалить временный файл при ошибке
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

    @staticmethod
    def update_user_stats(user_id: int, analysis_data: Dict):
        """Обновляет статистику пользователя"""
        if user_id not in user_stats:
            user_stats[user_id] = {
                'total_analyzed': 0,
                'relevance_scores': [],
                'reading_times': [],
                'priority_high': 0,
                'priority_medium': 0,
                'priority_low': 0,
                'complexity_beginner': 0,
                'complexity_intermediate': 0,
                'complexity_advanced': 0,
                'categories': {},
                'domains': {},
                'sources': []
            }
        
        stats = user_stats[user_id]
        analysis = analysis_data['analysis']
        
        # Обновляем общие показатели
        stats['total_analyzed'] += 1
        
        # Релевантность
        try:
            relevance = float(analysis.get('relevance_score', 5))
            stats['relevance_scores'].append(relevance)
        except:
            stats['relevance_scores'].append(5)
        
        # Время чтения
        try:
            reading_time = float(analysis.get('estimated_reading_time', 5))
            stats['reading_times'].append(reading_time)
        except:
            stats['reading_times'].append(5)
        
        # Приоритет
        priority = analysis.get('priority_level', 'medium')
        stats[f'priority_{priority}'] += 1
        
        # Сложность
        complexity = analysis.get('complexity_level', 'средний')
        complexity_map = {
            'начальный': 'beginner',
            'средний': 'intermediate', 
            'продвинутый': 'advanced'
        }
        complexity_key = complexity_map.get(complexity, 'intermediate')
        stats[f'complexity_{complexity_key}'] += 1
        
        # Категории
        category = analysis.get('category', 'unknown')
        stats['categories'][category] = stats['categories'].get(category, 0) + 1
        
        # Домены
        url = analysis_data['url']
        domain = url.split('/')[2] if '/' in url else url
        stats['domains'][domain] = stats['domains'].get(domain, 0) + 1
        
        # Сохраняем информацию об источнике
        source_info = {
            'url': url,
            'title': analysis_data.get('title', 'Без названия'),
            'domain_emoji': analysis_data.get('domain_emoji', '📄'),
            'category': analysis.get('category', 'unknown'),
            'relevance_score': analysis.get('relevance_score', '5'),
            'priority_level': analysis.get('priority_level', 'medium'),
            'complexity_level': analysis.get('complexity_level', 'средний'),
            'estimated_reading_time': analysis.get('estimated_reading_time', '5'),
            'timestamp': analysis_data.get('timestamp', datetime.now().isoformat()),
            'tags': analysis.get('tags', [])[:3],  # Первые 3 тега
            'read_status': 'unread',  # По умолчанию все источники помечаются как непрочитанные
            'read_timestamp': None,  # Время когда было отмечено как прочитанное
            'source_id': f"{user_id}_{len(stats['sources'])}"  # Уникальный ID источника
        }
        stats['sources'].append(source_info)
        
        # Сохраняем обновленную статистику
        StatsManager.save_stats()

    @staticmethod
    def get_user_stats(user_id: int) -> Dict:
        """Получает статистику пользователя"""
        if user_id not in user_stats:
            return {}
        
        stats = user_stats[user_id].copy()
        
        # Вычисляем средние значения
        if stats['relevance_scores']:
            stats['avg_relevance'] = sum(stats['relevance_scores']) / len(stats['relevance_scores'])
        else:
            stats['avg_relevance'] = 0
        
        if stats['reading_times']:
            stats['avg_reading_time'] = sum(stats['reading_times']) / len(stats['reading_times'])
        else:
            stats['avg_reading_time'] = 0
        
        return stats

    @staticmethod
    def clear_user_stats(user_id: int):
        """Очищает статистику пользователя"""
        if user_id in user_stats:
            del user_stats[user_id]
            StatsManager.save_stats()

    @staticmethod
    def mark_source_as_read(user_id: int, source_index: int, read_status: str = 'read') -> bool:
        """Отмечает источник как прочитанный или непрочитанный"""
        if user_id not in user_stats:
            return False
        
        sources = user_stats[user_id].get('sources', [])
        if source_index < 0 or source_index >= len(sources):
            return False
        
        # Обновляем статус прочтения
        sources[source_index]['read_status'] = read_status
        if read_status == 'read':
            sources[source_index]['read_timestamp'] = datetime.now().isoformat()
        else:
            sources[source_index]['read_timestamp'] = None
        
        # Сохраняем изменения
        StatsManager.save_stats()
        return True

    @staticmethod
    def get_filtered_sources(user_id: int, read_filter: str = 'all', page: int = 1, per_page: int = 5):
        """Получает отфильтрованные источники по статусу чтения"""
        if user_id not in user_stats:
            return [], 0, 0
        
        all_sources = user_stats[user_id].get('sources', [])
        
        # Применяем фильтр по статусу чтения
        if read_filter == 'read':
            filtered_sources = [s for s in all_sources if s.get('read_status') == 'read']
        elif read_filter == 'unread':
            filtered_sources = [s for s in all_sources if s.get('read_status', 'unread') == 'unread']
        else:  # 'all'
            filtered_sources = all_sources
        
        # Сортируем по времени (новые сначала)
        filtered_sources = sorted(filtered_sources, key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Пагинация
        total_sources = len(filtered_sources)
        total_pages = (total_sources + per_page - 1) // per_page if total_sources > 0 else 1
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_sources = filtered_sources[start_idx:end_idx]
        
        return page_sources, total_sources, total_pages

    @staticmethod
    def get_read_stats(user_id: int) -> Dict:
        """Получает статистику по прочитанным/непрочитанным источникам"""
        if user_id not in user_stats:
            return {'read': 0, 'unread': 0, 'total': 0}
        
        sources = user_stats[user_id].get('sources', [])
        read_count = len([s for s in sources if s.get('read_status') == 'read'])
        unread_count = len([s for s in sources if s.get('read_status', 'unread') == 'unread'])
        
        return {
            'read': read_count,
            'unread': unread_count,
            'total': len(sources)
        } 