"""
Обработчики RAG команд для Telegram бота
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ENABLE_RAG, SEMANTIC_SEARCH_TOP_K
from analyzers.rag_agent import rag_agent
from analyzers.vectorization_service import vectorization_service
from formatters.rag_formatter import rag_formatter
from utils.decorators import require_authorization
from storage.database_manager import database_manager
from utils.logger import setup_logger

logger = setup_logger(__name__)


def log_user_access(user_id: int, username: str, command: str):
    """Логирует доступ пользователя к команде"""
    logger.info(f"👤 Пользователь {username} (ID: {user_id}) выполнил команду: {command}")


@require_authorization
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /search - семантический поиск"""
    user = update.effective_user
    log_user_access(user.id, user.username, "/search")
    
    if not ENABLE_RAG:
        await update.message.reply_text(
            "⚠️ RAG функциональность отключена",
            parse_mode='Markdown'
        )
        return
    
    # Проверяем наличие запроса
    if not context.args:
        await update.message.reply_text(
            "❌ **Использование:** `/search <запрос>`\n\n"
            "**Пример:** `/search машинное обучение`\n\n"
            "Семантический поиск найдет статьи по смыслу, а не только по точным словам.",
            parse_mode='Markdown'
        )
        return
    
    query = " ".join(context.args)
    
    # Отправляем сообщение о процессе
    processing_msg = await update.message.reply_text(
        f"🔍 Ищу в вашей базе знаний: _{query}_...",
        parse_mode='Markdown'
    )
    
    try:
        # Выполняем семантический поиск
        results = await vectorization_service.search_similar_content(
            query=query,
            user_id=user.id,
            top_k=SEMANTIC_SEARCH_TOP_K
        )
        
        # Форматируем результаты
        formatted_results = rag_formatter.format_search_results(results, query)
        
        # Удаляем сообщение о процессе
        await processing_msg.delete()
        
        # Отправляем результаты
        await update.message.reply_text(
            formatted_results,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        logger.info(f"✅ Поиск выполнен для пользователя {user.id}: {len(results)} результатов")
        
    except Exception as e:
        logger.error(f"❌ Ошибка поиска для пользователя {user.id}: {e}")
        await processing_msg.edit_text(
            rag_formatter.format_error(f"Произошла ошибка при поиске: {str(e)}")
        )


@require_authorization
async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /ask - вопрос к базе знаний"""
    user = update.effective_user
    log_user_access(user.id, user.username, "/ask")
    
    if not ENABLE_RAG:
        await update.message.reply_text(
            "⚠️ RAG функциональность отключена",
            parse_mode='Markdown'
        )
        return
    
    # Проверяем наличие вопроса
    if not context.args:
        await update.message.reply_text(
            "❌ **Использование:** `/ask <вопрос>`\n\n"
            "**Примеры:**\n"
            "• `/ask Что говорят статьи о микросервисах?`\n"
            "• `/ask Какие подходы к тестированию упоминаются?`\n"
            "• `/ask Сравни React и Vue по моим статьям`\n\n"
            "Я отвечу на основе ваших сохраненных материалов.",
            parse_mode='Markdown'
        )
        return
    
    question = " ".join(context.args)
    
    # Отправляем сообщение о процессе
    processing_msg = await update.message.reply_text(
        f"🤔 Анализирую вашу базу знаний...\n\n_Вопрос: {question}_",
        parse_mode='Markdown'
    )
    
    try:
        # Получаем ответ от RAG агента
        result = await rag_agent.ask_question(
            question=question,
            user_id=user.id
        )
        
        # Форматируем ответ
        formatted_answer = rag_formatter.format_answer(result)
        
        # Удаляем сообщение о процессе
        await processing_msg.delete()
        
        # Отправляем ответ
        await update.message.reply_text(
            formatted_answer,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        logger.info(f"✅ Ответ сгенерирован для пользователя {user.id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации ответа для пользователя {user.id}: {e}")
        await processing_msg.edit_text(
            rag_formatter.format_error(f"Произошла ошибка при генерации ответа: {str(e)}")
        )


@require_authorization
async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /compare - сравнение источников"""
    user = update.effective_user
    log_user_access(user.id, user.username, "/compare")
    
    if not ENABLE_RAG:
        await update.message.reply_text(
            "⚠️ RAG функциональность отключена",
            parse_mode='Markdown'
        )
        return
    
    # Проверяем наличие темы
    if not context.args:
        await update.message.reply_text(
            "❌ **Использование:** `/compare <тема>`\n\n"
            "**Примеры:**\n"
            "• `/compare блокчейн`\n"
            "• `/compare микросервисы vs монолит`\n"
            "• `/compare подходы к тестированию`\n\n"
            "Я сравню разные источники из вашей базы по заданной теме.",
            parse_mode='Markdown'
        )
        return
    
    topic = " ".join(context.args)
    
    # Отправляем сообщение о процессе
    processing_msg = await update.message.reply_text(
        f"📊 Сравниваю источники по теме: _{topic}_...",
        parse_mode='Markdown'
    )
    
    try:
        # Получаем сравнительный анализ
        result = await rag_agent.compare_sources(
            topic=topic,
            user_id=user.id,
            num_sources=5
        )
        
        # Форматируем результат
        formatted_comparison = rag_formatter.format_comparison(result)
        
        # Удаляем сообщение о процессе
        await processing_msg.delete()
        
        # Отправляем результат
        await update.message.reply_text(
            formatted_comparison,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        logger.info(f"✅ Сравнение выполнено для пользователя {user.id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка сравнения для пользователя {user.id}: {e}")
        await processing_msg.edit_text(
            rag_formatter.format_error(f"Произошла ошибка при сравнении: {str(e)}")
        )


@require_authorization
async def synthesize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /synthesize - синтез информации"""
    user = update.effective_user
    log_user_access(user.id, user.username, "/synthesize")
    
    if not ENABLE_RAG:
        await update.message.reply_text(
            "⚠️ RAG функциональность отключена",
            parse_mode='Markdown'
        )
        return
    
    # Проверяем наличие темы
    if not context.args:
        await update.message.reply_text(
            "❌ **Использование:** `/synthesize <тема>`\n\n"
            "**Примеры:**\n"
            "• `/synthesize искусственный интеллект`\n"
            "• `/synthesize веб-разработка`\n"
            "• `/synthesize DevOps практики`\n\n"
            "Я создам обзор по теме на основе всех ваших материалов.",
            parse_mode='Markdown'
        )
        return
    
    topic = " ".join(context.args)
    
    # Отправляем сообщение о процессе
    processing_msg = await update.message.reply_text(
        f"📚 Синтезирую информацию по теме: _{topic}_...",
        parse_mode='Markdown'
    )
    
    try:
        # Получаем синтез
        result = await rag_agent.synthesize_topic(
            topic=topic,
            user_id=user.id,
            synthesis_type="summary"
        )
        
        # Форматируем результат
        formatted_synthesis = rag_formatter.format_synthesis(result)
        
        # Удаляем сообщение о процессе
        await processing_msg.delete()
        
        # Отправляем результат
        await update.message.reply_text(
            formatted_synthesis,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        logger.info(f"✅ Синтез выполнен для пользователя {user.id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка синтеза для пользователя {user.id}: {e}")
        await processing_msg.edit_text(
            rag_formatter.format_error(f"Произошла ошибка при синтезе: {str(e)}")
        )


@require_authorization
async def similar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /similar - поиск похожих статей"""
    user = update.effective_user
    log_user_access(user.id, user.username, "/similar")
    
    if not ENABLE_RAG:
        await update.message.reply_text(
            "⚠️ RAG функциональность отключена",
            parse_mode='Markdown'
        )
        return
    
    # Проверяем наличие ID
    if not context.args:
        await update.message.reply_text(
            "❌ **Использование:** `/similar <ID статьи>`\n\n"
            "**Пример:** `/similar 507f1f77bcf86cd799439011`\n\n"
            "ID статьи можно найти в списке источников (`/sources`).",
            parse_mode='Markdown'
        )
        return
    
    synopsis_id = context.args[0]
    
    # Отправляем сообщение о процессе
    processing_msg = await update.message.reply_text(
        "🔍 Ищу похожие статьи...",
        parse_mode='Markdown'
    )
    
    try:
        # Получаем информацию о статье
        synopsis = await database_manager.get_synopsis_by_id(synopsis_id)
        
        if not synopsis:
            await processing_msg.edit_text(
                "❌ Статья не найдена. Проверьте ID."
            )
            return
        
        source_title = synopsis.get('title', 'Без названия')
        
        # Получаем рекомендации
        recommendations = await vectorization_service.get_recommendations(
            synopsis_id=synopsis_id,
            top_k=5,
            user_id=user.id
        )
        
        # Форматируем результат
        formatted_recommendations = rag_formatter.format_recommendations(
            recommendations,
            source_title
        )
        
        # Удаляем сообщение о процессе
        await processing_msg.delete()
        
        # Отправляем результат
        await update.message.reply_text(
            formatted_recommendations,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        logger.info(f"✅ Рекомендации получены для пользователя {user.id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения рекомендаций для пользователя {user.id}: {e}")
        await processing_msg.edit_text(
            rag_formatter.format_error(f"Произошла ошибка: {str(e)}")
        )


@require_authorization
async def rag_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /rag_help - справка по RAG"""
    user = update.effective_user
    log_user_access(user.id, user.username, "/rag_help")
    
    help_text = rag_formatter.format_help_rag()
    
    await update.message.reply_text(
        help_text,
        parse_mode='Markdown'
    )

