import re
from datetime import datetime
from typing import Dict

from config import PRIORITY_EMOJIS, READ_STATUS_EMOJIS


class TelegramFormatter:
    @staticmethod
    def escape_markdown(text: str) -> str:
        """Экранирует специальные символы для Markdown разметки Telegram"""
        if not text:
            return ""
        
        # Список символов, которые нужно экранировать в Markdown V2
        # Но мы используем обычный Markdown, поэтому экранируем только критичные
        escape_chars = ['\\', '`', '*', '_', '[', ']', '(', ')']
        
        escaped_text = text
        for char in escape_chars:
            escaped_text = escaped_text.replace(char, f'\\{char}')
        
        return escaped_text
    
    @staticmethod
    def safe_format_text(text: str, max_length: int = 4000) -> str:
        """Безопасно форматирует текст с ограничением длины"""
        if not text:
            return ""
        
        # Обрезаем текст если он слишком длинный
        if len(text) > max_length:
            text = text[:max_length-3] + "..."
        
        return text
    
    @staticmethod
    def format_rating(rating: int) -> str:
        """Форматирует рейтинг звездами"""
        if rating == 0:
            return "⭐ Не оценено"
        
        full_stars = "⭐" * rating
        empty_stars = "☆" * (5 - rating)
        return f"{full_stars}{empty_stars} ({rating}/5)"
    
    @staticmethod
    def validate_markdown(text: str) -> bool:
        """Проверяет корректность Markdown разметки"""
        if not text:
            return True
        
        # Проверяем парность символов форматирования
        bold_count = text.count('**')
        code_count = text.count('`')
        
        # Количество символов форматирования должно быть четным
        return bold_count % 2 == 0 and code_count % 2 == 0
    @staticmethod
    def format_analysis_message(analysis_data: Dict) -> str:
        """Форматирует сообщение с анализом"""
        if not analysis_data:
            return "❌ Не удалось проанализировать ссылку"
        
        analysis = analysis_data['analysis']
        emoji = analysis_data['domain_emoji']
        
        # Эмодзи для приоритета
        p_emoji = PRIORITY_EMOJIS.get(analysis.get('priority_level', 'medium'), '🟡')
        
        # Статус прочтения (по умолчанию непрочитано)
        read_emoji = READ_STATUS_EMOJIS.get('unread', '📖')
        
        message = f"""{read_emoji} {emoji} **{analysis_data['title']}**

📝 **Краткое резюме:**
{analysis.get('summary', 'Анализ недоступен')}

🎯 **Ключевые моменты:**"""
        
        for point in analysis.get('key_points', [])[:3]:
            message += f"\n• {point}"
        
        message += f"""

📊 **Метаданные:**
• Категория: {analysis.get('category', 'Не определена')}
• Сложность: {analysis.get('complexity_level', 'Не определена')}
• Время чтения: {analysis.get('estimated_reading_time', '?')} мин
• Релевантность: {analysis.get('relevance_score', '?')}/10
• Приоритет: {p_emoji} {analysis.get('priority_level', 'medium').upper()}
• Аудитория: {analysis.get('target_audience', 'Общая')}

🏷️ **Теги:** """
        
        for tag in analysis.get('tags', [])[:5]:
            message += f"`{tag}` "
        
        message += f"""

✅ **Рекомендуемые действия:**"""
        
        for action in analysis.get('action_items', [])[:3]:
            message += f"\n• {action}"
        
        message += f"""

🔗 **Источник:** {analysis_data['url']}

---
🤖 *Проанализировано ИИ* • ⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"""
        
        return message

    @staticmethod
    def format_stats_table(stats: Dict) -> str:
        """Форматирует таблицу статистики"""
        if not stats:
            return "📊 Статистика пока пуста"
        
        # Статистика по прочтению уже включена в stats
        read_stats = {
            'read': stats.get('read_count', 0),
            'unread': stats.get('unread_count', 0),
            'total': stats.get('read_count', 0) + stats.get('unread_count', 0)
        }
        
        # Рейтинги
        avg_rating = stats.get('avg_rating', 0)
        rated_count = stats.get('rated_count', 0)
        rating_line = ""
        if rated_count > 0:
            rating_stars = TelegramFormatter.format_rating(int(round(avg_rating)))
            rating_line = f"\n• Средний рейтинг: {rating_stars}"
        
        message = f"""📊 **СТАТИСТИКА АНАЛИЗА**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 **Общие показатели:**
• Всего проанализировано: {stats.get('total_analyzed', 0)}
• Средняя релевантность: {stats.get('avg_relevance', 0):.1f}/10
• Среднее время чтения: {stats.get('avg_reading_time', 0):.1f} мин{rating_line}

📖 **Статус прочтения:**
• ✅ Прочитано: {read_stats.get('read', 0)}
• 📖 Не прочитано: {read_stats.get('unread', 0)}
• 📊 Всего источников: {read_stats.get('total', 0)}

⭐ **Рейтинги:**
• Оценено статей: {rated_count} из {stats.get('total_analyzed', 0)}
• ⭐⭐⭐⭐⭐: {stats.get('rating_5', 0)}
• ⭐⭐⭐⭐: {stats.get('rating_4', 0)}
• ⭐⭐⭐: {stats.get('rating_3', 0)}
• ⭐⭐: {stats.get('rating_2', 0)}
• ⭐: {stats.get('rating_1', 0)}

🎯 **По приоритету:**
• 🔴 Высокий: {stats.get('priority_high', 0)}
• 🟡 Средний: {stats.get('priority_medium', 0)}
• 🟢 Низкий: {stats.get('priority_low', 0)}

📚 **По сложности:**
• Начальный: {stats.get('complexity_beginner', 0)}
• Средний: {stats.get('complexity_intermediate', 0)}
• Продвинутый: {stats.get('complexity_advanced', 0)}

🏷️ **Популярные категории:**"""
        
        categories = stats.get('categories', [])
        if isinstance(categories, list):
            for category in categories[:5]:
                message += f"\n• {category}"
        else:
            # Обратная совместимость со старым форматом
            for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]:
                message += f"\n• {category}: {count}"
        
        message += f"""

🌐 **По доменам:**"""
        
        domains = stats.get('domains', [])
        if isinstance(domains, list):
            for domain in domains[:5]:
                message += f"\n• {domain}"
        else:
            # Обратная совместимость со старым форматом
            for domain, count in sorted(domains.items(), key=lambda x: x[1], reverse=True)[:5]:
                message += f"\n• {domain}: {count}"
        
        message += f"""

⏰ Последнее обновление: {datetime.now().strftime('%d.%m.%Y %H:%M')}"""
        
        return message

    @staticmethod
    def format_sources_table(sources_data, read_filter: str = 'all', page: int = 1, total_sources: int = 0, total_pages: int = 1) -> str:
        """Форматирует таблицу источников с пагинацией и фильтрацией по статусу чтения"""
        if not sources_data:
            filter_text = ""
            if read_filter == 'read':
                filter_text = " прочитанных"
            elif read_filter == 'unread':
                filter_text = " непрочитанных"
            return f"📚 Список{filter_text} источников пуст"
        
        # Заголовок с фильтром
        filter_emoji = ""
        filter_text = ""
        if read_filter == 'read':
            filter_emoji = "✅"
            filter_text = " ПРОЧИТАННЫЕ"
        elif read_filter == 'unread':
            filter_emoji = "📖"
            filter_text = " НЕПРОЧИТАННЫЕ"
        else:
            filter_emoji = "📚"
            filter_text = ""
        
        message = f"""{filter_emoji} **ИСТОЧНИКИ{filter_text}** (стр. {page}/{total_pages})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        for i, source in enumerate(sources_data):
            # Эмодзи для приоритета и статуса прочтения
            p_emoji = PRIORITY_EMOJIS.get(source.get('priority_level', 'medium'), '🟡')
            read_emoji = READ_STATUS_EMOJIS.get(source.get('read_status', 'unread'), '📖')
            
            # Форматируем дату
            try:
                timestamp = datetime.fromisoformat(source.get('timestamp', ''))
                date_str = timestamp.strftime('%d.%m.%Y')
            except:
                try:
                    # Пробуем парсить created_at из MongoDB
                    timestamp = source.get('created_at', datetime.now())
                    if isinstance(timestamp, datetime):
                        date_str = timestamp.strftime('%d.%m.%Y')
                    else:
                        date_str = 'Неизвестно'
                except:
                    date_str = 'Неизвестно'
            
            # Сокращаем заголовок если слишком длинный
            title = source.get('title', 'Без названия')
            if len(title) > 35:
                title = title[:32] + '...'
            
            # Безопасно экранируем заголовок
            safe_title = TelegramFormatter.escape_markdown(title)
            
            # Теги - безопасно форматируем каждый тег
            tags = source.get('tags', [])
            safe_tags = []
            for tag in tags[:2]:
                if tag:  # Проверяем что тег не пустой
                    safe_tag = TelegramFormatter.escape_markdown(str(tag))
                    safe_tags.append(f"`{safe_tag}`")
            tags_str = ' '.join(safe_tags) if safe_tags else ''
            
            # Безопасно форматируем URL
            url = source.get('url', '')
            safe_url = TelegramFormatter.safe_format_text(url, 100)  # Ограничиваем длину URL
            
            # ID источника для callback'ов
            source_id = source.get('id', '')
            
            # Рейтинг
            rating = source.get('rating', 0)
            rating_str = ""
            if rating > 0:
                rating_str = f" • {TelegramFormatter.format_rating(rating)}"
            
            message += f"""{read_emoji} {source.get('domain_emoji', '📄')} **{safe_title}**
   📊 {source.get('relevance_score', '?')}/10 • {p_emoji} {source.get('priority_level', 'medium').upper()} • ⏱️ {source.get('estimated_reading_time', '?')} мин{rating_str}
   📅 {date_str} • 🏷️ {tags_str}
   🔗 {safe_url}

"""
        
        # Информация о пагинации
        if total_pages > 1:
            message += f"📄 Показано {len(sources_data)} из {total_sources} источников"
        else:
            message += f"📄 Всего источников: {total_sources}"
        
        # Проверяем и обрезаем сообщение если оно слишком длинное
        message = TelegramFormatter.safe_format_text(message, 4000)
        
        return message
    
    @staticmethod
    def format_single_source_details(source: Dict) -> str:
        """Форматирует детальную информацию об одном источнике"""
        if not source:
            return "❌ Источник не найден"
        
        # Эмодзи для приоритета и статуса прочтения
        p_emoji = PRIORITY_EMOJIS.get(source.get('priority_level', 'medium'), '🟡')
        read_emoji = READ_STATUS_EMOJIS.get(source.get('read_status', 'unread'), '📖')
        
        # Форматируем дату
        try:
            timestamp = source.get('created_at', datetime.now())
            if isinstance(timestamp, datetime):
                date_str = timestamp.strftime('%d.%m.%Y %H:%M')
            else:
                date_str = 'Неизвестно'
        except:
            date_str = 'Неизвестно'
        
        # Безопасно форматируем заголовок
        safe_title = TelegramFormatter.escape_markdown(source.get('title', 'Без названия'))
        
        # Безопасно форматируем резюме
        summary = source.get('summary', 'Анализ недоступен')
        safe_summary = TelegramFormatter.safe_format_text(summary, 1000)
        
        message = f"""{read_emoji} {source.get('domain_emoji', '📄')} **{safe_title}**

📝 **Краткое резюме:**
{safe_summary}

🎯 **Ключевые моменты:**"""
        
        key_points = source.get('key_points', [])
        if key_points:
            for point in key_points[:5]:
                if point:  # Проверяем что пункт не пустой
                    safe_point = TelegramFormatter.escape_markdown(str(point))
                    safe_point = TelegramFormatter.safe_format_text(safe_point, 200)
                    message += f"\n• {safe_point}"
        else:
            message += "\n• Ключевые моменты не определены"
        
        message += f"""

📊 **Метаданные:**
• Категория: {source.get('category', 'Не определена')}
• Сложность: {source.get('complexity_level', 'Не определена')}
• Время чтения: {source.get('estimated_reading_time', '?')} мин
• Релевантность: {source.get('relevance_score', '?')}/10
• Приоритет: {p_emoji} {source.get('priority_level', 'medium').upper()}

🏷️ **Теги:** """
        
        tags = source.get('tags', [])
        if tags:
            safe_tags = []
            for tag in tags[:5]:
                if tag:  # Проверяем что тег не пустой
                    safe_tag = TelegramFormatter.escape_markdown(str(tag))
                    safe_tags.append(f"`{safe_tag}`")
            if safe_tags:
                message += ' '.join(safe_tags)
            else:
                message += "Нет тегов"
        else:
            message += "Нет тегов"
        
        read_status_text = "Прочитан" if source.get('read_status') == 'read' else "Не прочитан"
        
        # Рейтинг
        rating = source.get('rating', 0)
        rating_str = TelegramFormatter.format_rating(rating)
        
        # Безопасно форматируем URL
        url = source.get('url', '')
        safe_url = TelegramFormatter.safe_format_text(url, 150)
        
        message += f"""

📖 **Статус:** {read_status_text}
⭐ **Рейтинг:** {rating_str}
🔗 **Источник:** {safe_url}

---
📅 Создано: {date_str}"""
        
        # Проверяем и обрезаем сообщение если оно слишком длинное
        message = TelegramFormatter.safe_format_text(message, 4000)
        
        return message 