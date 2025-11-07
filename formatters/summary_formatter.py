from typing import Dict
from datetime import datetime

from config import PRIORITY_EMOJIS


class SummaryFormatter:
    """Форматтер для пересказов контента"""
    
    @staticmethod
    def format_brief_summary(summary_data: Dict, original_title: str = "", source_url: str = "") -> str:
        """Форматирует краткий пересказ"""
        if not summary_data:
            return "❌ Не удалось создать пересказ"
        
        # Эмодзи для сложности
        difficulty_emojis = {
            'легко': '🟢',
            'средне': '🟡', 
            'сложно': '🔴',
            'неопределено': '⚪'
        }
        
        difficulty = summary_data.get('reading_difficulty', 'неопределено')
        difficulty_emoji = difficulty_emojis.get(difficulty, '⚪')
        
        # Компрессия
        compression = summary_data.get('compression_ratio', 'неизвестно')
        
        message = f"""📄 **КРАТКИЙ ПЕРЕСКАЗ**

🎯 **Суть:** {summary_data.get('brief_summary', 'Не удалось создать пересказ')}

💡 **Главная идея:**
{summary_data.get('main_thesis', 'Не определена')}

🔍 **Ключевые факты:**"""
        
        # Добавляем ключевые факты
        key_facts = summary_data.get('key_facts', [])
        for i, fact in enumerate(key_facts[:3], 1):
            message += f"\n{i}. {fact}"
        
        # Добавляем выводы
        conclusions = summary_data.get('conclusions', [])
        if conclusions:
            message += f"\n\n🎯 **Выводы:**"
            for conclusion in conclusions[:2]:
                message += f"\n• {conclusion}"
        
        message += f"""

💼 **Практическая ценность:**
{summary_data.get('practical_value', 'Не определена')}

👥 **Целевая аудитория:** {summary_data.get('who_should_read', 'Общая')}

📊 **Характеристики:**
• Сложность: {difficulty_emoji} {difficulty}
• Сжатие: {compression}
• Слов в пересказе: {summary_data.get('summary_length', '?')}

💭 **Запоминающаяся мысль:**
_{summary_data.get('memorable_quote', 'Не выделена')}_

🏷️ **Связанные темы:**"""
        
        # Добавляем связанные темы
        related_topics = summary_data.get('related_topics', [])
        for topic in related_topics[:3]:
            message += f" `{topic}`"
        
        # Добавляем метаданные
        created_at = summary_data.get('created_at', '')
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                time_str = dt.strftime('%H:%M')
                message += f"\n\n⏰ Создан: {time_str}"
            except:
                pass
        
        return message
    
    @staticmethod
    def format_detailed_summary(summary_data: Dict, original_title: str = "", source_url: str = "") -> str:
        """Форматирует подробный пересказ"""
        if not summary_data:
            return "❌ Не удалось создать подробный пересказ"
        
        message = f"""📚 **ПОДРОБНЫЙ ПЕРЕСКАЗ**

🎯 **Резюме:** {summary_data.get('executive_summary', 'Не создано')}

📖 **Введение:**
{summary_data.get('introduction', 'Не определено')}

📋 **Основные разделы:**"""
        
        # Добавляем основные разделы
        main_sections = summary_data.get('main_sections', [])
        for i, section in enumerate(main_sections[:4], 1):
            section_title = section.get('section_title', f'Раздел {i}')
            section_content = section.get('content', 'Содержание недоступно')
            
            message += f"\n\n**{i}. {section_title}**\n{section_content}"
            
            # Добавляем ключевые моменты раздела
            key_points = section.get('key_points', [])
            if key_points:
                message += "\n*Ключевые моменты:*"
                for point in key_points[:2]:
                    message += f"\n  • {point}"
        
        # Методология
        methodology = summary_data.get('methodology', '')
        if methodology and methodology != 'Автоматический анализ с помощью ИИ':
            message += f"\n\n🔬 **Методология:** {methodology}"
        
        # Основные открытия
        findings = summary_data.get('findings', [])
        if findings:
            message += f"\n\n🔍 **Основные открытия:**"
            for finding in findings[:3]:
                message += f"\n• {finding}"
        
        # Значение и последствия
        implications = summary_data.get('implications', '')
        if implications:
            message += f"\n\n🎯 **Значение:** {implications}"
        
        # Рекомендации
        recommendations = summary_data.get('recommendations', [])
        if recommendations:
            message += f"\n\n💡 **Рекомендации:**"
            for rec in recommendations[:3]:
                message += f"\n• {rec}"
        
        # Ограничения
        limitations = summary_data.get('limitations', '')
        if limitations and limitations != 'Техническая недоступность контента':
            message += f"\n\n⚠️ **Ограничения:** {limitations}"
        
        # Будущие направления
        future_directions = summary_data.get('future_directions', '')
        if future_directions and future_directions != 'Устранение технических проблем':
            message += f"\n\n🚀 **Перспективы:** {future_directions}"
        
        # Позиция автора
        author_perspective = summary_data.get('author_perspective', '')
        if author_perspective and author_perspective != 'Системное сообщение':
            message += f"\n\n👤 **Позиция автора:** {author_perspective}"
        
        # Критический анализ
        critical_analysis = summary_data.get('critical_analysis', '')
        if critical_analysis and 'Невозможно провести анализ' not in critical_analysis:
            message += f"\n\n🎭 **Критический анализ:** {critical_analysis}"
        
        # Метаданные
        created_at = summary_data.get('created_at', '')
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                time_str = dt.strftime('%H:%M')
                message += f"\n\n⏰ Создан: {time_str}"
            except:
                pass
        
        return message
    
    @staticmethod
    def format_summary_stats(stats_data: Dict) -> str:
        """Форматирует статистику пересказа"""
        if not stats_data:
            return "📊 Статистика недоступна"
        
        word_count = stats_data.get('word_count', 0)
        char_count = stats_data.get('character_count', 0)
        read_time = stats_data.get('estimated_read_time_seconds', 0)
        compression = stats_data.get('compression_achieved', 'неизвестно')
        difficulty = stats_data.get('difficulty_level', 'неопределено')
        quality_score = stats_data.get('summary_quality_score', 5)
        
        # Конвертируем время чтения
        if read_time >= 60:
            read_time_str = f"{read_time // 60}м {read_time % 60}с"
        else:
            read_time_str = f"{read_time}с"
        
        # Эмодзи для качества
        quality_emoji = "⭐" * min(max(quality_score // 2, 1), 5)
        
        message = f"""📊 **СТАТИСТИКА ПЕРЕСКАЗА**

📝 **Объем:**
• Слов: {word_count}
• Символов: {char_count}
• Время чтения: ~{read_time_str}

🎯 **Характеристики:**
• Сжатие: {compression}
• Сложность: {difficulty}
• Качество: {quality_emoji} ({quality_score}/10)

📈 **Эффективность сжатия:** Исходный контент сокращен в соответствии с заданными параметрами."""
        
        return message
    
    @staticmethod
    def format_tts_result(tts_result: Dict, summary_type: str = "краткий") -> str:
        """Форматирует результат генерации аудио"""
        if not tts_result or not tts_result.get('success'):
            error = tts_result.get('error', 'Неизвестная ошибка') if tts_result else 'Нет данных'
            return f"❌ **Ошибка создания аудио:** {error}"
        
        filename = tts_result.get('filename', 'Неизвестно')
        duration = tts_result.get('estimated_duration_seconds', 0)
        engine = tts_result.get('engine_used', 'неизвестно')
        file_size = tts_result.get('file_size', 0)
        audio_format = tts_result.get('audio_format', 'неизвестно')
        
        # Конвертируем длительность
        if duration >= 60:
            duration_str = f"{duration // 60}м {duration % 60}с"
        else:
            duration_str = f"{duration}с"
        
        # Конвертируем размер файла
        if file_size >= 1024 * 1024:
            size_str = f"{file_size / 1024 / 1024:.1f} МБ"
        elif file_size >= 1024:
            size_str = f"{file_size / 1024:.1f} КБ"
        else:
            size_str = f"{file_size} байт"
        
        message = f"""🎵 **АУДИО ПЕРЕСКАЗ ГОТОВ**

📻 **Тип:** {summary_type.title()} пересказ
⏱️ **Длительность:** ~{duration_str}
📁 **Размер:** {size_str}
🎧 **Формат:** {audio_format.upper()}
🤖 **Движок:** {engine.upper()}

💡 Используйте встроенный плеер Telegram для прослушивания."""
        
        return message 