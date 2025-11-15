"""
Форматтер для RAG ответов в Telegram
"""

from typing import Dict, List, Any


class RAGFormatter:
    """Форматирует RAG ответы для отображения в Telegram"""
    
    @staticmethod
    def format_answer(result: Dict[str, Any]) -> str:
        """
        Форматирует ответ RAG агента
        
        Args:
            result: Результат от RAG агента
        
        Returns:
            str: Отформатированное сообщение для Telegram
        """
        if not result.get('success'):
            error = result.get('error', 'Неизвестная ошибка')
            return f"❌ **Ошибка**\n\n{error}"
        
        answer = result.get('answer', '')
        sources = result.get('sources', [])
        context_used = result.get('context_used', 0)
        
        # Формируем сообщение
        message_parts = [
            "🤖 **Ответ на основе вашей базы знаний:**\n",
            answer,
            "\n\n---\n"
        ]
        
        # Добавляем информацию об источниках
        if sources:
            message_parts.append(f"📚 **Использовано источников:** {context_used}\n")
            message_parts.append("\n**Источники:**\n")
            
            for i, source in enumerate(sources[:5], 1):  # Показываем до 5 источников
                title = source.get('title', 'Без названия')
                relevance = source.get('relevance', 0)
                relevance_percent = int(relevance * 100)
                
                message_parts.append(
                    f"{i}. [{title}]({source.get('url', '#')}) "
                    f"(релевантность: {relevance_percent}%)\n"
                )
            
            if len(sources) > 5:
                message_parts.append(f"\n_...и еще {len(sources) - 5} источников_\n")
        else:
            message_parts.append("ℹ️ Источники не найдены\n")
        
        return "".join(message_parts)
    
    @staticmethod
    def format_comparison(result: Dict[str, Any]) -> str:
        """Форматирует сравнительный анализ"""
        if not result.get('success'):
            error = result.get('error', 'Неизвестная ошибка')
            return f"❌ **Ошибка**\n\n{error}"
        
        topic = result.get('topic', '')
        analysis = result.get('analysis', '')
        sources = result.get('sources', [])
        
        message_parts = [
            f"📊 **Сравнительный анализ по теме:** {topic}\n\n",
            analysis,
            "\n\n---\n"
        ]
        
        # Добавляем список источников
        if sources:
            message_parts.append(f"📚 **Проанализировано источников:** {len(sources)}\n\n")
            
            for i, source in enumerate(sources, 1):
                title = source.get('title', 'Без названия')
                category = source.get('category', '')
                
                message_parts.append(
                    f"{i}. [{title}]({source.get('url', '#')}) "
                    f"({category})\n"
                )
        
        return "".join(message_parts)
    
    @staticmethod
    def format_synthesis(result: Dict[str, Any]) -> str:
        """Форматирует синтез информации"""
        if not result.get('success'):
            error = result.get('error', 'Неизвестная ошибка')
            return f"❌ **Ошибка**\n\n{error}"
        
        topic = result.get('topic', '')
        synthesis = result.get('synthesis', '')
        sources_count = result.get('sources_count', 0)
        synthesis_type = result.get('type', 'summary')
        
        type_emoji = {
            'summary': '📝',
            'detailed': '📚',
            'outline': '📋'
        }
        
        type_names = {
            'summary': 'Краткий обзор',
            'detailed': 'Подробный конспект',
            'outline': 'Структурированный план'
        }
        
        emoji = type_emoji.get(synthesis_type, '📝')
        type_name = type_names.get(synthesis_type, 'Синтез')
        
        message_parts = [
            f"{emoji} **{type_name} по теме:** {topic}\n\n",
            synthesis,
            "\n\n---\n",
            f"📚 **Источников использовано:** {sources_count}\n"
        ]
        
        return "".join(message_parts)
    
    @staticmethod
    def format_search_results(results: List[Dict[str, Any]], query: str) -> str:
        """Форматирует результаты семантического поиска"""
        if not results:
            return f"🔍 **Поиск:** {query}\n\n❌ Ничего не найдено"
        
        message_parts = [
            f"🔍 **Результаты поиска:** {query}\n",
            f"📊 **Найдено:** {len(results)} результатов\n\n"
        ]
        
        for i, result in enumerate(results[:10], 1):  # Показываем до 10 результатов
            metadata = result.get('metadata', {})
            title = metadata.get('title', 'Без названия')
            category = metadata.get('category', '')
            distance = result.get('distance', 1.0)
            relevance = int((1 - distance) * 100)
            
            message_parts.append(
                f"{i}. **{title}**\n"
                f"   📁 {category} | 🎯 {relevance}%\n"
            )
            
            # Добавляем краткое описание если есть
            summary = metadata.get('summary', '')
            if summary:
                summary_short = summary[:150] + "..." if len(summary) > 150 else summary
                message_parts.append(f"   _{summary_short}_\n")
            
            message_parts.append("\n")
        
        if len(results) > 10:
            message_parts.append(f"_...и еще {len(results) - 10} результатов_\n")
        
        return "".join(message_parts)
    
    @staticmethod
    def format_recommendations(
        recommendations: List[Dict[str, Any]],
        source_title: str
    ) -> str:
        """Форматирует рекомендации похожих статей"""
        if not recommendations:
            return f"💡 **Похожие статьи для:** {source_title}\n\n❌ Похожие статьи не найдены"
        
        message_parts = [
            f"💡 **Похожие статьи для:** {source_title}\n",
            f"📊 **Найдено:** {len(recommendations)} рекомендаций\n\n"
        ]
        
        for i, rec in enumerate(recommendations, 1):
            metadata = rec.get('metadata', {})
            title = metadata.get('title', 'Без названия')
            category = metadata.get('category', '')
            distance = rec.get('distance', 1.0)
            similarity = int((1 - distance) * 100)
            
            message_parts.append(
                f"{i}. **{title}**\n"
                f"   📁 {category} | 🔗 Схожесть: {similarity}%\n"
            )
            
            # Добавляем теги если есть
            tags = metadata.get('tags', [])
            if tags:
                if isinstance(tags, str):
                    tags_str = tags
                else:
                    tags_str = ", ".join(tags[:3])
                message_parts.append(f"   🏷️ {tags_str}\n")
            
            message_parts.append("\n")
        
        return "".join(message_parts)
    
    @staticmethod
    def format_error(error_message: str) -> str:
        """Форматирует сообщение об ошибке"""
        return f"❌ **Ошибка**\n\n{error_message}"
    
    @staticmethod
    def format_help_rag() -> str:
        """Форматирует справку по RAG командам"""
        return """🤖 **Справка по RAG функциям**

**Семантический поиск:**
`/search <запрос>` - поиск по смыслу в вашей базе знаний
Пример: `/search машинное обучение`

**Вопросы к базе знаний:**
`/ask <вопрос>` - задать вопрос вашей базе знаний
Пример: `/ask Что говорят статьи о микросервисах?`

**Сравнение источников:**
`/compare <тема>` - сравнить разные источники по теме
Пример: `/compare блокчейн`

**Синтез информации:**
`/synthesize <тема>` - создать обзор по теме
Пример: `/synthesize искусственный интеллект`

**Похожие статьи:**
`/similar <ID>` - найти похожие статьи
Пример: `/similar 507f1f77bcf86cd799439011`

**Особенности:**
• Поиск работает по смыслу, а не по точным словам
• Система учитывает контекст и связи между материалами
• Ответы основаны только на ваших сохраненных статьях
• Указываются источники для каждого ответа

💡 **Совет:** Чем больше статей в вашей базе, тем точнее и полезнее ответы!"""


# Глобальный экземпляр форматтера
rag_formatter = RAGFormatter()

