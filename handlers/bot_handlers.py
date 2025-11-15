import re
import os
from datetime import datetime

from storage.stats_manager import StatsManager
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import Conflict, BadRequest, TelegramError

from config import DELETE_ORIGINAL_LINKS, SOURCES_PER_PAGE, ENABLE_SUMMARY_AGENT, ENABLE_TTS_AGENT
from analyzers.content_analyzer import AIContentAnalyzer
from analyzers.summary_agent import SummaryAgent
from formatters.telegram_formatter import TelegramFormatter
from formatters.summary_formatter import SummaryFormatter
from generators.pdf_generator import PDFGenerator
from generators.tts_generator import TTSGenerator
from storage.database_manager import database_manager
from utils.logger import setup_logger
from utils.auth import require_authorization, log_user_access
from utils.text_utils import clean_text_for_telegram, validate_telegram_message, safe_truncate_at_word

logger = setup_logger(__name__)

# Инициализация компонентов
analyzer = AIContentAnalyzer()
formatter = TelegramFormatter()


async def safe_edit_message_text(query, message: str, reply_markup=None, disable_web_page_preview=True):
    """Безопасно редактирует сообщение с обработкой ошибок форматирования"""
    try:
        # Очищаем текст от потенциально проблемных символов
        message = clean_text_for_telegram(message)
        
        # Валидируем сообщение
        is_valid, error_msg = validate_telegram_message(message)
        if not is_valid:
            logger.warning(f"⚠️ Проблема с сообщением: {error_msg}")
            
            # Пытаемся исправить обрезанием
            if "слишком длинное" in error_msg:
                message = safe_truncate_at_word(message, 4000)
            else:
                # Проблема с разметкой - убираем все форматирование
                message = message.replace('**', '').replace('`', '').replace('*', '')
        
        # Дополнительная проверка Markdown
        if not formatter.validate_markdown(message):
            logger.warning("⚠️ Некорректная Markdown разметка, исправляем...")
            # Пытаемся исправить сообщение, убрав потенциально проблемные символы
            message = message.replace('**', '*').replace('`', "'")
        
        # Финальная проверка длины
        if len(message) > 4096:
            logger.warning(f"⚠️ Сообщение все еще слишком длинное: {len(message)} символов")
            message = safe_truncate_at_word(message, 4000)
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview
        )
        return True
        
    except BadRequest as e:
        # Если сообщение идентично, просто показываем уведомление
        if "message is not modified" in str(e).lower():
            await query.answer("🔄 Данные уже актуальны")
            return True
        elif "can't parse entities" in str(e).lower():
            logger.error(f"❌ Ошибка разбора Markdown: {e}")
            # Отправляем сообщение без Markdown разметки
            try:
                plain_message = message.replace('**', '').replace('`', '').replace('*', '')
                await query.edit_message_text(
                    plain_message,
                    reply_markup=reply_markup,
                    disable_web_page_preview=disable_web_page_preview
                )
                return True
            except Exception as fallback_error:
                logger.error(f"❌ Ошибка fallback отправки: {fallback_error}")
                await query.answer("❌ Ошибка форматирования сообщения")
                return False
        else:
            logger.info(f"ℹ️ Не удалось обновить сообщение: {e}")
            await query.answer("❌ Не удалось обновить сообщение")
            return False
    except Conflict as e:
        logger.info(f"ℹ️ Конфликт при обновлении сообщения: {e}")
        await query.answer("🔄 Попробуйте снова")
        return False
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при обновлении сообщения: {e}")
        await query.answer("❌ Произошла ошибка")
        return False

# Инициализация новых агентов
summary_agent = SummaryAgent() if ENABLE_SUMMARY_AGENT else None
summary_formatter = SummaryFormatter()
tts_generator = TTSGenerator() if ENABLE_TTS_AGENT else None


def create_source_management_buttons(page_sources, read_filter, page, total_pages):
    """Создает кнопки управления источниками"""
    keyboard = []
    
    # Кнопки фильтрации по статусу чтения
    filter_buttons = []
    if read_filter != 'all':
        filter_buttons.append(InlineKeyboardButton("📚 Все", callback_data=f"sources_filter_all_1"))
    if read_filter != 'unread':
        filter_buttons.append(InlineKeyboardButton("📖 Непрочитанные", callback_data=f"sources_filter_unread_1"))
    if read_filter != 'read':
        filter_buttons.append(InlineKeyboardButton("✅ Прочитанные", callback_data=f"sources_filter_read_1"))
    
    if filter_buttons:
        # Разбиваем кнопки фильтров на строки по 2
        for i in range(0, len(filter_buttons), 2):
            keyboard.append(filter_buttons[i:i+2])
    
    # Кнопки навигации по страницам
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Пред", callback_data=f"sources_nav_{read_filter}_{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("След ➡️", callback_data=f"sources_nav_{read_filter}_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Индивидуальные кнопки управления для каждого источника
    if page_sources:
        keyboard.append([InlineKeyboardButton("⚙️ УПРАВЛЕНИЕ ИСТОЧНИКАМИ", callback_data=f"sources_nav_{read_filter}_{page}")])
        
        for i, source in enumerate(page_sources):
            source_id = source.get('id', '')
            source_title = source.get('title', 'Без названия')
            if len(source_title) > 25:
                source_title = source_title[:22] + '...'
            
            # Кнопки для каждого источника
            source_buttons = []
            
            # Кнопка статуса прочтения
            if source.get('read_status') == 'read':
                source_buttons.append(InlineKeyboardButton("📖", callback_data=f"mark_synopsis_unread_{source_id}"))
            else:
                source_buttons.append(InlineKeyboardButton("✅", callback_data=f"mark_synopsis_read_{source_id}"))
            
            # Кнопка просмотра деталей
            source_buttons.append(InlineKeyboardButton(f"📋 {source_title}", callback_data=f"show_source_{source_id}"))
            
            # Кнопка удаления
            source_buttons.append(InlineKeyboardButton("🗑️", callback_data=f"delete_source_{source_id}"))
            
            keyboard.append(source_buttons)
    
    # Кнопки управления статусом прочтения для текущей страницы
    read_control_buttons = []
    if page_sources:
        if read_filter != 'read':
            read_control_buttons.append(InlineKeyboardButton("✅ Отметить страницу прочитанной", callback_data=f"mark_page_read_{read_filter}_{page}"))
        if read_filter != 'unread':
            read_control_buttons.append(InlineKeyboardButton("📖 Отметить страницу непрочитанной", callback_data=f"mark_page_unread_{read_filter}_{page}"))
    
    if read_control_buttons:
        for button in read_control_buttons:
            keyboard.append([button])
    
    # Кнопки управления
    management_buttons = [
        InlineKeyboardButton("🔄 Обновить", callback_data=f"sources_nav_{read_filter}_{page}"),
        InlineKeyboardButton("📄 PDF", callback_data="generate_pdf")
    ]
    keyboard.append(management_buttons)
    
    keyboard.append([
        InlineKeyboardButton("📊 Статистика", callback_data="refresh_stats")
    ])
    
    return InlineKeyboardMarkup(keyboard)


@require_authorization
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    log_user_access(user.id, user.username, "/start")
    
    welcome_message = """🤖 **Добро пожаловать в ИИ Анализатор Контента!**

Я помогу вам анализировать ссылки и получать структурированную информацию о контенте.

✨ **Как это работает:**
• Отправьте ссылку → Получите красивый пост с анализом
• Отмечайте статус прочтения ✅📖
• Оценивайте статьи рейтингом ⭐ (1-5 звезд)
• Исходная ссылка автоматически удаляется
• Ведется персональная статистика анализов и прочтения

📋 **Доступные команды:**
• Просто отправьте ссылку - получите анализ
• /stats - посмотреть статистику
• /sources - таблица источников (с фильтрацией по статусу)
• /export - экспорт в PDF
• /help - справка
• /clear - очистить всю статистику
• /clear_source <ID> - удалить один источник

🆕 **Функционал пересказа:**
• 📄 Краткий пересказ - сжатая суть статьи
• 📚 Подробный пересказ - структурированное изложение
• 🎵 Озвучивание пересказа - аудио для прослушивания

🤖 **RAG и семантический поиск:**
• 🔍 `/search` - поиск по смыслу в вашей базе
• 💬 `/ask` - задавайте вопросы вашим статьям
• 📊 `/compare` - сравнивайте разные источники
• 📝 `/synthesize` - создавайте обзоры по темам
• 🔗 `/similar` - находите похожие материалы

🌐 **Поддерживаемые источники:**
• Любые веб-сайты и статьи
• Блоги и новостные порталы  
• Техническая документация
• Образовательные ресурсы
• Коммерческие сайты
• Форумы и социальные сети
• И многое другое...

📖 **Отслеживание и оценка:**
• ✅ Отмечайте источники как прочитанные
• ⭐ Оценивайте статьи от 1 до 5 звезд
• 📖 Фильтруйте по статусу (все/прочитанные/непрочитанные)
• 📊 Смотрите прогресс и средний рейтинг в статистике

🔧 **Управление источниками:**
• 🗑️ Удаляйте отдельные источники через /clear_source
• 📋 Детальный просмотр через кнопки в списке источников
• ⚙️ Индивидуальные кнопки управления для каждого источника

Отправьте любую ссылку, чтобы начать анализ! 🚀"""
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


@require_authorization
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    user = update.effective_user
    log_user_access(user.id, user.username, "/help")
    
    help_text = """📖 **Справка по использованию**

🔗 **Анализ ссылок:**
Просто отправьте любую HTTP/HTTPS ссылку в чат, и я проанализирую контент с помощью ИИ.

🌐 **Поддерживаемые источники:**
• Любые веб-сайты и статьи
• Блоги и новостные порталы  
• Техническая документация
• Образовательные ресурсы
• Коммерческие сайты
• Форумы и социальные сети

📊 **Что вы получите:**
• Краткое резюме содержимого
• Ключевые моменты
• Категорию и сложность
• Время чтения и релевантность
• Рекомендуемые действия
• Теги для категоризации

🆕 **Функции пересказа:**
• **📄 Краткий пересказ** - сжатая суть в нескольких предложениях
• **📚 Подробный пересказ** - структурированное изложение по разделам
• **🎵 Озвучивание** - аудио для прослушивания пересказа
• **📊 Статистика** - анализ качества и эффективности пересказа

📖 **Статус прочтения:**
• ✅ Отмечайте источники как прочитанные
• 📖 Фильтруйте по статусу (все/прочитанные/непрочитанные)
• 📊 Просматривайте статистику прочтения
• 🔄 Массово меняйте статус целой страницы

⭐ **Рейтинг статей:**
• Оценивайте статьи от 1 до 5 звезд
• Интерактивные кнопки в детальном просмотре
• Средний рейтинг и распределение в статистике
• Быстрый сброс рейтинга кнопкой 🔄

📈 **Статистика:**
Используйте `/stats` для просмотра детальной статистики ваших анализов, прогресса чтения и рейтингов.

⚙️ **Основные команды:**
• `/start` - начать работу
• `/stats` - показать статистику
• `/sources [all/read/unread]` - таблица источников с фильтрацией
• `/export` - экспорт в PDF
• `/help` - эта справка
• `/clear` - очистить всю статистику
• `/clear_source <ID>` - удалить один источник

🤖 **RAG и семантический поиск:**
• `/search <запрос>` - семантический поиск по базе
• `/ask <вопрос>` - задать вопрос базе знаний
• `/compare <тема>` - сравнить источники по теме
• `/synthesize <тема>` - создать обзор по теме
• `/similar <ID>` - найти похожие статьи
• `/rag_help` - подробная справка по RAG

🔧 **Управление источниками:**
• В списке источников используйте кнопки управления для каждого источника
• В детальном режиме доступны кнопки для изменения статуса, рейтинга и удаления
• Массовые операции доступны через кнопки в списке источников

🎯 **Примеры команд:**
• Все источники: `/sources`
• Только непрочитанные: `/sources unread`
• Только прочитанные: `/sources read`
• Удалить источник: `/clear_source 507f1f77bcf86cd799439011`

🤖 Анализ выполняется с помощью Claude 3.7 Sonnet"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')


@require_authorization
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stats"""
    user = update.effective_user
    log_user_access(user.id, user.username, "/stats")
    
    user_id = update.effective_user.id
    stats = await database_manager.get_user_stats(user_id)
    
    if not stats or stats.get('total_analyzed', 0) == 0:
        await update.message.reply_text(
            "📊 У вас пока нет статистики.\nОтправьте несколько ссылок для анализа!",
            parse_mode='Markdown'
        )
        return
    
    stats_message = formatter.format_stats_table(stats)
    
    # Добавляем кнопки
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_stats")],
        [InlineKeyboardButton("🗑️ Очистить", callback_data="clear_stats")],
        [InlineKeyboardButton("📚 К источникам", callback_data="sources_filter_all_1")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        stats_message, 
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


@require_authorization
async def sources_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /sources"""
    user = update.effective_user
    log_user_access(user.id, user.username, "/sources")
    
    user_id = update.effective_user.id
    
    # Получаем фильтр и номер страницы из аргументов
    read_filter = 'all'  # по умолчанию показываем все
    page = 1
    
    if context.args:
        for arg in context.args:
            if arg in ['all', 'read', 'unread']:
                read_filter = arg
            else:
                try:
                    page = int(arg)
                except (ValueError, IndexError):
                    pass
    
    # Получаем отфильтрованные источники из MongoDB
    sources_data = await database_manager.get_user_sources(
        user_id=user_id,
        page=page,
        per_page=SOURCES_PER_PAGE,
        read_filter=read_filter
    )
    
    page_sources = sources_data.get('synopses', [])
    total_sources = sources_data.get('total_count', 0)
    total_pages = sources_data.get('total_pages', 0)
    
    if not page_sources:
        filter_text = ""
        if read_filter == 'read':
            filter_text = " прочитанных"
        elif read_filter == 'unread':
            filter_text = " непрочитанных"
        await update.message.reply_text(
            f"📚 У вас нет{filter_text} источников.",
            parse_mode='Markdown'
        )
        return
    
    sources_message = formatter.format_sources_table(
        page_sources, read_filter, page, total_sources, total_pages
    )
    
    # Создаем кнопки управления источниками
    reply_markup = create_source_management_buttons(page_sources, read_filter, page, total_pages)
    
    await update.message.reply_text(
        sources_message,
        parse_mode='Markdown',
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )


@require_authorization
async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /export"""
    user = update.effective_user
    log_user_access(user.id, user.username, "/export")
    
    user_id = update.effective_user.id
    
    # Проверяем наличие источников в MongoDB
    sources_data = await database_manager.get_user_sources(user_id=user_id, page=1, per_page=1)
    
    if sources_data.get('total_count', 0) == 0:
        await update.message.reply_text(
            "📚 У вас пока нет источников для экспорта.\nОтправьте несколько ссылок для анализа!",
            parse_mode='Markdown'
        )
        return
    
    # Создаем клавиатуру с опциями экспорта
    keyboard = []
    
    # Опции сортировки
    sort_options = [
        ('По дате (новые)', 'export_sort_timestamp_desc'),
        ('По дате (старые)', 'export_sort_timestamp_asc'),
        ('По релевантности ⬆️', 'export_sort_relevance_desc'),
        ('По релевантности ⬇️', 'export_sort_relevance_asc'),
        ('По времени чтения ⬆️', 'export_sort_reading_desc'),
        ('По времени чтения ⬇️', 'export_sort_reading_asc'),
        ('По приоритету ⬆️', 'export_sort_priority_desc'),
        ('По приоритету ⬇️', 'export_sort_priority_asc'),
    ]
    
    for name, callback_data in sort_options:
        keyboard.append([InlineKeyboardButton(name, callback_data=callback_data)])
    
    # Фильтры
    filter_options = [
        ('📖 Все источники', 'export_filter_all'),
        ('✅ Только прочитанные', 'export_filter_read'),
        ('📖 Только непрочитанные', 'export_filter_unread'),
        ('🔴 Высокий приоритет', 'export_filter_priority_high'),
        ('🟡 Средний приоритет', 'export_filter_priority_medium'),
        ('🟢 Низкий приоритет', 'export_filter_priority_low'),
    ]
    
    for name, callback_data in filter_options:
        keyboard.append([InlineKeyboardButton(name, callback_data=callback_data)])
    
    # Кнопка экспорта с текущими настройками
    keyboard.append([InlineKeyboardButton("📄 Экспортировать с текущими настройками", callback_data="export_current")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📊 *Настройки экспорта PDF*\n\n"
        "Выберите опции сортировки и фильтрации:\n\n"
        "*Сортировка:*\n"
        "• По умолчанию: по дате (новые сверху)\n\n"
        "*Фильтры:*\n"
        "• По умолчанию: все источники\n\n"
        "Выберите нужные опции или экспортируйте с текущими настройками:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


@require_authorization
async def clear_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /clear"""
    user = update.effective_user
    log_user_access(user.id, user.username, "/clear")
    
    user_id = update.effective_user.id
    
    # Проверяем наличие данных
    stats = await database_manager.get_user_stats(user_id)
    if stats and stats.get('total_analyzed', 0) > 0:
        # Очищаем данные пользователя из обеих БД
        await database_manager.clear_user_data(user_id)
        await update.message.reply_text("🗑️ Статистика очищена!")
    else:
        await update.message.reply_text("📊 Статистика уже пуста!")


@require_authorization
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline кнопки"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    await query.answer()
    
    # Проверяем административные callback
    if query.data.startswith("admin_"):
        logger.info(f"Routing admin callback {query.data} to admin handler")
        from handlers.admin_handlers import handle_admin_callback
        return await handle_admin_callback(update, context)
    
    if query.data == "refresh_stats":
        stats = await database_manager.get_user_stats(user_id)
        if stats and stats.get('total_analyzed', 0) > 0:
            # Добавляем user_id для статистики прочтения
            stats['user_id'] = user_id
            stats_message = formatter.format_stats_table(stats)
            
            # Добавляем кнопки
            keyboard = [
                [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_stats")],
                [InlineKeyboardButton("🗑️ Очистить", callback_data="clear_stats")],
                [InlineKeyboardButton("📚 К источникам", callback_data="sources_filter_all_1")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(
                    stats_message,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except (Conflict, BadRequest) as e:
                logger.info(f"ℹ️ Не удалось обновить сообщение: {e}")
                # Отправляем новое сообщение вместо редактирования
                await query.message.reply_text(
                    stats_message,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
        else:
            await query.edit_message_text("📊 Статистика пуста!")
    
    elif query.data == "clear_stats":
        stats = await database_manager.get_user_stats(user_id)
        if stats and stats.get('total_analyzed', 0) > 0:
            await database_manager.clear_user_data(user_id)
            await query.edit_message_text("🗑️ Статистика очищена!")
        else:
            await query.edit_message_text("📊 Статистика уже пуста!")
    
    elif query.data.startswith("sources_filter_"):
        # Обработка фильтрации источников по статусу чтения
        parts = query.data.split("_")
        if len(parts) >= 4:
            read_filter = parts[2]  # all, read, unread
            page = int(parts[3]) if parts[3].isdigit() else 1
            
            sources_data = await database_manager.get_user_sources(
                user_id=user_id,
                page=page,
                per_page=SOURCES_PER_PAGE,
                read_filter=read_filter
            )
            page_sources = sources_data.get('synopses', [])
            total_sources = sources_data.get('total_count', 0)
            total_pages = sources_data.get('total_pages', 0)
            
            if page_sources:
                sources_message = formatter.format_sources_table(
                    page_sources, read_filter, page, total_sources, total_pages
                )
                
                # Создаем полные кнопки управления источниками
                reply_markup = create_source_management_buttons(page_sources, read_filter, page, total_pages)
                
                await safe_edit_message_text(query, sources_message, reply_markup)
            else:
                filter_text = ""
                if read_filter == 'read':
                    filter_text = " прочитанных"
                elif read_filter == 'unread':
                    filter_text = " непрочитанных"
                await query.edit_message_text(f"📚 Список{filter_text} источников пуст!")

    elif query.data.startswith("sources_nav_"):
        # Обработка навигации по страницам источников с фильтром
        parts = query.data.split("_")
        if len(parts) >= 4:
            read_filter = parts[2]
            page = int(parts[3]) if parts[3].isdigit() else 1
            
            sources_data = await database_manager.get_user_sources(
                user_id=user_id,
                page=page,
                per_page=SOURCES_PER_PAGE,
                read_filter=read_filter
            )
            page_sources = sources_data.get('synopses', [])
            total_sources = sources_data.get('total_count', 0)
            total_pages = sources_data.get('total_pages', 0)
            
            if page_sources:
                sources_message = formatter.format_sources_table(
                    page_sources, read_filter, page, total_sources, total_pages
                )
                
                # Создаем полные кнопки управления источниками
                reply_markup = create_source_management_buttons(page_sources, read_filter, page, total_pages)
                
                await safe_edit_message_text(query, sources_message, reply_markup)
            else:
                await query.edit_message_text("📚 Список источников пуст!")

    elif query.data.startswith("mark_page_"):
        # Обработка массового изменения статуса прочтения для страницы
        parts = query.data.split("_")
        if len(parts) >= 5:
            action = parts[2]  # read или unread
            read_filter = parts[3]
            page = int(parts[4]) if parts[4].isdigit() else 1
            
            # Получаем источники текущей страницы
            sources_data = await database_manager.get_user_sources(
                user_id=user_id,
                page=page,
                per_page=SOURCES_PER_PAGE,
                read_filter=read_filter
            )
            page_sources = sources_data.get('synopses', [])
            
            if page_sources:
                # Массово обновляем статус всех синопсисов на странице
                success_count = 0
                
                for source in page_sources:
                    synopsis_id = source.get('id')
                    if synopsis_id:
                        if await database_manager.mark_source_as_read(synopsis_id, action):
                            success_count += 1
                
                if success_count > 0:
                    status_text = "прочитанными" if action == "read" else "непрочитанными"
                    await query.answer(f"✅ Отмечено {success_count} источников как {status_text}")
                    
                    # Обновляем отображение
                    sources_data = await database_manager.get_user_sources(
                        user_id=user_id,
                        page=page,
                        per_page=SOURCES_PER_PAGE,
                        read_filter=read_filter
                    )
                    page_sources = sources_data.get('synopses', [])
                    total_sources = sources_data.get('total_count', 0)
                    total_pages = sources_data.get('total_pages', 0)
                    
                    if page_sources:
                        sources_message = formatter.format_sources_table(
                            page_sources, read_filter, page, total_sources, total_pages
                        )
                        
                        # Создаем полные кнопки управления источниками
                        reply_markup = create_source_management_buttons(page_sources, read_filter, page, total_pages)
                        
                        try:
                            await query.edit_message_text(
                                sources_message,
                                parse_mode='Markdown',
                                reply_markup=reply_markup,
                                disable_web_page_preview=True
                            )
                        except BadRequest as e:
                            # Если сообщение идентично, это нормально
                            if "message is not modified" in str(e).lower():
                                pass  # Не показываем уведомление, так как изменение статуса уже подтверждено выше
                            else:
                                logger.info(f"ℹ️ Не удалось обновить сообщение: {e}")
                        except Conflict as e:
                            logger.info(f"ℹ️ Конфликт при обновлении сообщения: {e}")
                    else:
                        # Если страница стала пустой после фильтрации, переходим на первую страницу
                        await query.edit_message_text("✅ Статус обновлен! Перезагрузите источники.")
                else:
                    await query.answer("❌ Не удалось обновить статус источников")

    elif query.data.startswith("mark_single_"):
        # Обработка изменения статуса прочтения для отдельного источника
        parts = query.data.split("_")
        if len(parts) >= 4:
            action = parts[2]  # read или unread
            source_index = int(parts[3]) if parts[3].isdigit() else -1
            
            if source_index >= 0:
                success = StatsManager.mark_source_as_read(user_id, source_index, action)
                if success:
                    status_text = "прочитанным" if action == "read" else "непрочитанным"
                    await query.answer(f"✅ Источник отмечен как {status_text}")
                    
                    # Обновляем кнопки в сообщении
                    new_keyboard = []
                    if action == "read":
                        new_keyboard.append([
                            InlineKeyboardButton("✅ Прочитано", callback_data=f"mark_single_read_{source_index}"),
                            InlineKeyboardButton("📖 Отметить не прочитанным", callback_data=f"mark_single_unread_{source_index}")
                        ])
                    else:
                        new_keyboard.append([
                            InlineKeyboardButton("✅ Отметить прочитанным", callback_data=f"mark_single_read_{source_index}"),
                            InlineKeyboardButton("📖 Не прочитано", callback_data=f"mark_single_unread_{source_index}")
                        ])
                    
                    new_keyboard.extend([
                        [InlineKeyboardButton("📊 Статистика", callback_data="refresh_stats")],
                        [InlineKeyboardButton("📚 Источники", callback_data="sources_filter_all_1")]
                    ])
                    
                    new_reply_markup = InlineKeyboardMarkup(new_keyboard)
                    
                    try:
                        await query.edit_message_reply_markup(reply_markup=new_reply_markup)
                    except (Conflict, BadRequest) as e:
                        logger.info(f"ℹ️ Не удалось обновить кнопки: {e}")
                else:
                    await query.answer("❌ Не удалось обновить статус источника")
            else:
                await query.answer("❌ Неверный индекс источника")

    elif query.data.startswith("mark_synopsis_"):
        # Обработка изменения статуса прочтения для синопсиса по ID
        parts = query.data.split("_")
        if len(parts) >= 3:
            action = parts[2]  # read или unread
            synopsis_id = "_".join(parts[3:])  # ID может содержать подчеркивания
            
            if synopsis_id:
                success = await database_manager.mark_source_as_read(synopsis_id, action)
                if success:
                    status_text = "прочитанным" if action == "read" else "непрочитанным"
                    await query.answer(f"✅ Источник отмечен как {status_text}")
                    
                    # Получаем обновленную информацию об источнике
                    source = await database_manager.get_synopsis_by_id(synopsis_id)
                    if source:
                        # Проверяем, это детальный просмотр или список источников
                        current_message = query.message.text
                        
                        if "📋 **Детальная информация**" in current_message:
                            # Это детальный просмотр - обновляем полностью
                            source_message = formatter.format_single_source_details(source)
                            
                            # Создаем кнопки управления для детального просмотра
                            keyboard = []
                            
                            # Кнопки статуса прочтения
                            if source.get('read_status') == 'read':
                                keyboard.append([
                                    InlineKeyboardButton("✅ Прочитано", callback_data=f"mark_synopsis_read_{synopsis_id}"),
                                    InlineKeyboardButton("📖 Отметить не прочитанным", callback_data=f"mark_synopsis_unread_{synopsis_id}")
                                ])
                            else:
                                keyboard.append([
                                    InlineKeyboardButton("✅ Отметить прочитанным", callback_data=f"mark_synopsis_read_{synopsis_id}"),
                                    InlineKeyboardButton("📖 Не прочитано", callback_data=f"mark_synopsis_unread_{synopsis_id}")
                                ])
                            
                            # Кнопки управления
                            keyboard.extend([
                                [InlineKeyboardButton("🗑️ Удалить источник", callback_data=f"delete_source_{synopsis_id}")],
                                [InlineKeyboardButton("📚 К источникам", callback_data="sources_filter_all_1"),
                                 InlineKeyboardButton("📊 Статистика", callback_data="refresh_stats")]
                            ])
                            
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            
                            try:
                                await query.edit_message_text(
                                    source_message,
                                    parse_mode='Markdown',
                                    reply_markup=reply_markup,
                                    disable_web_page_preview=True
                                )
                            except (Conflict, BadRequest) as e:
                                logger.info(f"ℹ️ Не удалось обновить детальное сообщение: {e}")
                        else:
                            # Это список источников или другое сообщение - просто показываем уведомление
                            # Пользователь может обновить список кнопкой "Обновить"
                            pass
                else:
                    await query.answer("❌ Не удалось обновить статус источника")
            else:
                await query.answer("❌ Неверный ID синопсиса")

    elif query.data.startswith("delete_source_"):
        # Обработка удаления источника
        source_id = query.data[14:]  # Убираем "delete_source_"
        
        if source_id:
            # Получаем источник для проверки принадлежности
            source = await database_manager.get_synopsis_by_id(source_id)
            
            if not source:
                await query.answer("❌ Источник не найден")
                return
            
            # Проверяем, что источник принадлежит пользователю
            if source.get('user_id') != user_id:
                await query.answer("❌ У вас нет доступа к этому источнику")
                return
            
            # Отправляем подтверждение
            source_title = source.get('title', 'Без названия')
            if len(source_title) > 50:
                source_title = source_title[:47] + '...'
            
            keyboard = [
                [InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_{source_id}")],
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_delete")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(
                    f"🗑️ **Подтверждение удаления**\n\n"
                    f"Вы действительно хотите удалить источник?\n\n"
                    f"📄 **{source_title}**\n"
                    f"🔗 {source.get('url', '')}\n\n"
                    f"⚠️ Это действие нельзя отменить!",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except (Conflict, BadRequest) as e:
                logger.info(f"ℹ️ Не удалось обновить сообщение: {e}")
        else:
            await query.answer("❌ Неверный ID источника")

    elif query.data.startswith("confirm_delete_"):
        # Подтверждение удаления источника
        source_id = query.data[15:]  # Убираем "confirm_delete_"
        
        if source_id:
            # Получаем источник для проверки принадлежности
            source = await database_manager.get_synopsis_by_id(source_id)
            
            if not source:
                await query.answer("❌ Источник не найден")
                return
            
            # Проверяем, что источник принадлежит пользователю
            if source.get('user_id') != user_id:
                await query.answer("❌ У вас нет доступа к этому источнику")
                return
            
            # Удаляем источник
            success = await database_manager.mongodb.delete_synopsis(source_id, user_id)
            
            if success:
                source_title = source.get('title', 'Без названия')
                if len(source_title) > 50:
                    source_title = source_title[:47] + '...'
                
                await query.edit_message_text(
                    f"✅ **Источник удален**\n\n"
                    f"📄 **{source_title}** успешно удален из вашей коллекции.\n\n"
                    f"📊 Статистика автоматически обновлена.",
                    parse_mode='Markdown'
                )
                
                logger.info(f"✅ Пользователь {user_id} удалил источник {source_id}")
            else:
                await query.edit_message_text("❌ Не удалось удалить источник. Попробуйте позже.")
        else:
            await query.answer("❌ Неверный ID источника")

    elif query.data == "cancel_delete":
        # Отмена удаления
        await query.edit_message_text("❌ Удаление отменено")

    elif query.data.startswith("show_source_"):
        # Показать детали источника
        source_id = query.data[12:]  # Убираем "show_source_"
        
        if source_id:
            # Получаем источник из базы данных
            source = await database_manager.get_synopsis_by_id(source_id)
            
            if not source:
                await query.answer("❌ Источник не найден")
                return
            
            # Проверяем, что источник принадлежит пользователю
            if source.get('user_id') != user_id:
                await query.answer("❌ У вас нет доступа к этому источнику")
                return
            
            # Форматируем детальную информацию
            source_message = formatter.format_single_source_details(source)
            
            # Создаем кнопки управления
            keyboard = []
            
            # Кнопки рейтинга
            rating_buttons_row1 = []
            rating_buttons_row2 = []
            current_rating = source.get('rating', 0)
            for i in range(1, 6):
                emoji = "⭐" if i <= current_rating else "☆"
                rating_buttons_row1.append(InlineKeyboardButton(
                    f"{emoji} {i}",
                    callback_data=f"set_rating_{i}_{source_id}"
                ))
            
            keyboard.append(rating_buttons_row1[:3])
            keyboard.append(rating_buttons_row1[3:5] + [InlineKeyboardButton("🔄 Сброс", callback_data=f"set_rating_0_{source_id}")])
            
            # Кнопки статуса прочтения
            if source.get('read_status') == 'read':
                keyboard.append([
                    InlineKeyboardButton("✅ Прочитано", callback_data=f"mark_synopsis_read_{source_id}"),
                    InlineKeyboardButton("📖 Отметить не прочитанным", callback_data=f"mark_synopsis_unread_{source_id}")
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton("✅ Отметить прочитанным", callback_data=f"mark_synopsis_read_{source_id}"),
                    InlineKeyboardButton("📖 Не прочитано", callback_data=f"mark_synopsis_unread_{source_id}")
                ])
            
            # Кнопки пересказа (если агент включен)
            if ENABLE_SUMMARY_AGENT:
                keyboard.extend([
                    [InlineKeyboardButton("📄 Краткий пересказ", callback_data=f"create_brief_summary_{source_id}"),
                     InlineKeyboardButton("📚 Подробный пересказ", callback_data=f"create_detailed_summary_{source_id}")],
                ])
            
            # Кнопки озвучивания (если агент включен)
            if ENABLE_TTS_AGENT:
                keyboard.append([
                    InlineKeyboardButton("🎵 Краткий аудио", callback_data=f"create_brief_audio_{source_id}"),
                    InlineKeyboardButton("🎙️ Подробный аудио", callback_data=f"create_detailed_audio_{source_id}")
                ])
            
            # Кнопки управления
            keyboard.extend([
                [InlineKeyboardButton("🗑️ Удалить источник", callback_data=f"delete_source_{source_id}")],
                [InlineKeyboardButton("📚 К источникам", callback_data="sources_filter_all_1"),
                 InlineKeyboardButton("📊 Статистика", callback_data="refresh_stats")]
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(
                    source_message,
                    parse_mode='Markdown',
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
            except (Conflict, BadRequest) as e:
                logger.info(f"ℹ️ Не удалось обновить сообщение: {e}")
                # Отправляем новое сообщение
                await query.message.reply_text(
                    source_message,
                    parse_mode='Markdown',
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
        else:
            await query.answer("❌ Неверный ID источника")

    elif query.data.startswith("sources_page_"):
        # Старая система навигации - перенаправляем на новую
        try:
            page = int(query.data.split("_")[-1])
        except ValueError:
            page = 1
        
        # Используем новую систему с фильтром 'all'
        sources_data = await database_manager.get_user_sources(
            user_id=user_id,
            page=page,
            per_page=SOURCES_PER_PAGE,
            read_filter='all'
        )
        page_sources = sources_data.get('synopses', [])
        total_sources = sources_data.get('total_count', 0)
        total_pages = sources_data.get('total_pages', 0)
        
        if page_sources:
            sources_message = formatter.format_sources_table(
                page_sources, 'all', page, total_sources, total_pages
            )
            
            # Создаем кнопки для совместимости
            keyboard = []
            
            # Кнопки фильтрации
            filter_buttons = [
                InlineKeyboardButton("📖 Непрочитанные", callback_data=f"sources_filter_unread_1"),
                InlineKeyboardButton("✅ Прочитанные", callback_data=f"sources_filter_read_1")
            ]
            keyboard.append(filter_buttons)
            
            # Навигация
            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⬅️ Пред", callback_data=f"sources_nav_all_{page-1}"))
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton("След ➡️", callback_data=f"sources_nav_all_{page+1}"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            # Кнопки управления статусом прочтения
            read_control_buttons = [
                InlineKeyboardButton("✅ Отметить страницу прочитанной", callback_data=f"mark_page_read_all_{page}"),
                InlineKeyboardButton("📖 Отметить страницу непрочитанной", callback_data=f"mark_page_unread_all_{page}")
            ]
            for button in read_control_buttons:
                keyboard.append([button])
            
            # Управление
            management_buttons = [
                InlineKeyboardButton("🔄 Обновить", callback_data=f"sources_nav_all_{page}"),
                InlineKeyboardButton("📄 PDF", callback_data="generate_pdf")
            ]
            keyboard.append(management_buttons)
            keyboard.append([InlineKeyboardButton("📊 Статистика", callback_data="refresh_stats")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            success = await safe_edit_message_text(query, sources_message, reply_markup)
            if not success:
                # Если редактирование не удалось, отправляем новое сообщение
                try:
                    await query.message.reply_text(
                        sources_message,
                        parse_mode='Markdown',
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки нового сообщения: {e}")
                    # Отправляем без разметки как последний вариант
                    plain_message = sources_message.replace('**', '').replace('`', '').replace('*', '')
                    await query.message.reply_text(plain_message, reply_markup=reply_markup)
        else:
            await query.edit_message_text("📚 Список источников пуст!")
    
    elif query.data == "generate_pdf":
        # Генерация PDF с таблицей источников
        sources_data = await database_manager.get_user_sources(user_id=user_id, page=1, per_page=1000)
        
        if sources_data.get('total_count', 0) == 0:
            await query.edit_message_text("📚 Нет источников для экспорта в PDF!")
            return
        
        # Показываем прогресс
        await query.edit_message_text("📄 Создаю PDF с таблицей источников...")
        
        try:
            # Адаптируем данные для PDFGenerator (ожидает stats с полем sources)
            adapted_stats = {
                'sources': sources_data.get('synopses', [])
            }
            
            # Генерируем PDF с базовыми настройками
            pdf_path = PDFGenerator.create_sources_pdf(adapted_stats, user_id)
            
            if pdf_path and os.path.exists(pdf_path):
                # Отправляем PDF файл с правильным именем
                pdf_filename = os.path.basename(pdf_path)
                with open(pdf_path, 'rb') as pdf_file:
                    await query.message.reply_document(
                        document=pdf_file,
                        filename=pdf_filename,
                        caption=f"📚 **Таблица источников**\n\n📊 Всего источников: {sources_data.get('total_count', 0)}\n📅 Создано: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                        parse_mode='Markdown'
                    )
                
                # Удаляем временный файл
                try:
                    os.remove(pdf_path)
                except:
                    pass
                
                await query.edit_message_text("✅ PDF файл создан и отправлен!")
            else:
                await query.edit_message_text("❌ Ошибка при создании PDF файла")
                
        except Exception as e:
            logger.error(f"Ошибка при создании PDF: {e}")
            await query.edit_message_text("❌ Произошла ошибка при создании PDF файла")
            
    elif query.data.startswith("export_sort_") or query.data.startswith("export_filter_"):
        # Обработка выбора опций экспорта
        parts = query.data.split('_')
        if len(parts) >= 3:
            option_type = parts[1]  # sort или filter
            option_value = '_'.join(parts[2:])  # значение опции
            
            # Сохраняем выбранную опцию в контексте пользователя
            if not context.user_data.get('export_options'):
                context.user_data['export_options'] = {
                    'sort_by': 'created_at',
                    'sort_order': 'desc',
                    'read_filter': 'all',
                    'priority_filter': 'all',
                    'category_filter': 'all'
                }
            
            if option_type == 'sort':
                # Парсим опцию сортировки
                field = option_value.rsplit('_', 1)[0]  # timestamp, relevance, reading, priority
                order = option_value.rsplit('_', 1)[1]  # asc или desc
                
                # Преобразуем названия полей
                field_mapping = {
                    'timestamp': 'created_at',  # В новой системе используем created_at
                    'relevance': 'relevance_score',
                    'reading': 'estimated_reading_time',
                    'priority': 'priority_level'
                }
                
                context.user_data['export_options']['sort_by'] = field_mapping.get(field, 'timestamp')
                context.user_data['export_options']['sort_order'] = order
                
            elif option_type == 'filter':
                # Обрабатываем фильтры
                if option_value in ['all', 'read', 'unread']:
                    # Фильтр по статусу чтения
                    context.user_data['export_options']['read_filter'] = option_value
                    # Сбрасываем фильтр по приоритету при выборе фильтра по статусу
                    context.user_data['export_options']['priority_filter'] = 'all'
                elif option_value.startswith('priority_'):
                    # Фильтр по приоритету
                    priority = option_value.replace('priority_', '')
                    context.user_data['export_options']['priority_filter'] = priority
                    # Сбрасываем фильтр по статусу при выборе фильтра по приоритету
                    context.user_data['export_options']['read_filter'] = 'all'
            
            # Логируем выбранные опции для отладки
            logger.info(f"Выбраны опции экспорта: {context.user_data.get('export_options')}")
            
            # Обновляем сообщение с текущими настройками
            current_options = context.user_data.get('export_options', {})
            
            # Форматируем текст с текущими настройками
            sort_names = {
                'created_at': 'дате',
                'timestamp': 'дате',  # Для совместимости со старой системой
                'relevance_score': 'релевантности',
                'estimated_reading_time': 'времени чтения',
                'priority_level': 'приоритету'
            }
            
            sort_orders = {
                'desc': '(по убыванию)',
                'asc': '(по возрастанию)'
            }
            
            filter_names = {
                'all': 'все источники',
                'read': 'только прочитанные',
                'unread': 'только непрочитанные',
                'high': 'высокий приоритет',
                'medium': 'средний приоритет',
                'low': 'низкий приоритет'
            }
            
            settings_text = (
                "📊 *Настройки экспорта PDF*\n\n"
                "*Текущие настройки:*\n"
                f"• Сортировка: по {sort_names.get(current_options.get('sort_by'), 'дате')} "
                f"{sort_orders.get(current_options.get('sort_order'), '')}\n"
                f"• Статус: {filter_names.get(current_options.get('read_filter'), 'все источники')}\n"
                f"• Приоритет: {filter_names.get(current_options.get('priority_filter'), 'все')}\n\n"
                "Выберите дополнительные опции или экспортируйте с текущими настройками:"
            )
            
            # Обновляем сообщение с сохранением клавиатуры
            await query.edit_message_text(
                settings_text,
                parse_mode='Markdown',
                reply_markup=query.message.reply_markup
            )
            
    elif query.data == "export_current":
        # Экспорт с текущими настройками
        sources_data = await database_manager.get_user_sources(user_id=user_id, page=1, per_page=1000)
        
        if sources_data.get('total_count', 0) == 0:
            await query.edit_message_text("📚 Нет источников для экспорта в PDF!")
            return
        
        # Получаем текущие настройки
        export_options = context.user_data.get('export_options', {
            'sort_by': 'created_at',
            'sort_order': 'desc',
            'read_filter': 'all',
            'priority_filter': 'all',
            'category_filter': 'all'
        })
        
        # Логируем параметры перед созданием PDF
        logger.info(f"Создание PDF с параметрами: {export_options}")
        
        # Показываем прогресс
        await query.edit_message_text("📄 Создаю PDF с таблицей источников...")
        
        try:
            # Адаптируем данные для PDFGenerator (ожидает stats с полем sources)
            adapted_stats = {
                'sources': sources_data.get('synopses', [])
            }
            
            # Генерируем PDF с выбранными настройками
            pdf_path = PDFGenerator.create_sources_pdf(
                stats=adapted_stats,
                user_id=user_id,
                sort_by=export_options.get('sort_by', 'timestamp'),
                sort_order=export_options.get('sort_order', 'desc'),
                read_filter=export_options.get('read_filter', 'all'),
                priority_filter=export_options.get('priority_filter', 'all'),
                category_filter=export_options.get('category_filter', 'all')
            )
            
            if pdf_path and os.path.exists(pdf_path):
                # Отправляем PDF файл с правильным именем
                pdf_filename = os.path.basename(pdf_path)
                with open(pdf_path, 'rb') as pdf_file:
                    await query.message.reply_document(
                        document=pdf_file,
                        filename=pdf_filename,
                        caption=f"📚 **Таблица источников**\n\n📊 Всего источников: {sources_data.get('total_count', 0)}\n📅 Создано: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                        parse_mode='Markdown'
                    )
                
                # Удаляем временный файл
                try:
                    os.remove(pdf_path)
                except:
                    pass
                
                await query.edit_message_text("✅ PDF файл создан и отправлен!")
            else:
                await query.edit_message_text("❌ Ошибка при создании PDF файла")
                
        except Exception as e:
            logger.error(f"Ошибка при создании PDF: {e}")
            await query.edit_message_text("❌ Произошла ошибка при создании PDF файла")

    elif query.data.startswith("create_brief_summary_"):
        # Создание краткого пересказа
        if not ENABLE_SUMMARY_AGENT or not summary_agent:
            await query.answer("❌ Сервис пересказа отключен")
            return
            
        source_id = query.data[21:]  # Убираем "create_brief_summary_"
        
        if source_id:
            # Получаем источник из базы данных
            source = await database_manager.get_synopsis_by_id(source_id)
            
            if not source or source.get('user_id') != user_id:
                await query.answer("❌ Источник не найден или нет доступа")
                return
            
            # Показываем прогресс
            await query.edit_message_text("📄 Создаю краткий пересказ...")
            
            try:
                # Создаем краткий пересказ напрямую с URL источника
                if source.get('url'):
                    summary_data = await summary_agent.create_brief_summary_from_url(source.get('url'))
                else:
                    # Fallback к старому методу
                    content_data = {
                        'title': source.get('title', ''),
                        'content': source.get('summary', ''),
                        'analysis': source
                    }
                    summary_data = await summary_agent.create_brief_summary(
                        content_data, source.get('url', '')
                    )
                
                if summary_data:
                    # Форматируем пересказ
                    summary_message = summary_formatter.format_brief_summary(
                        summary_data, source.get('title', ''), source.get('url', '')
                    )
                    
                    # Создаем кнопки
                    keyboard = [
                        [InlineKeyboardButton("🎵 Озвучить краткий", callback_data=f"create_brief_audio_from_summary_{source_id}")],
                        [InlineKeyboardButton("📚 Подробный пересказ", callback_data=f"create_detailed_summary_{source_id}")],
                        [InlineKeyboardButton("📊 Статистика пересказа", callback_data=f"summary_stats_{source_id}")],
                        [InlineKeyboardButton("🔙 К источнику", callback_data=f"show_source_{source_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await query.edit_message_text(
                        summary_message,
                        parse_mode='Markdown',
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                    
                    logger.info(f"✅ Создан краткий пересказ для источника {source_id}")
                else:
                    await query.edit_message_text("❌ Не удалось создать пересказ")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка создания краткого пересказа: {e}")
                await query.edit_message_text("❌ Произошла ошибка при создании пересказа")
        else:
            await query.answer("❌ Неверный ID источника")

    elif query.data.startswith("create_detailed_summary_"):
        # Создание подробного пересказа
        if not ENABLE_SUMMARY_AGENT or not summary_agent:
            await query.answer("❌ Сервис пересказа отключен")
            return
            
        source_id = query.data[24:]  # Убираем "create_detailed_summary_"
        
        if source_id:
            # Получаем источник из базы данных
            source = await database_manager.get_synopsis_by_id(source_id)
            
            if not source or source.get('user_id') != user_id:
                await query.answer("❌ Источник не найден или нет доступа")
                return
            
            # Показываем прогресс
            await query.edit_message_text("📚 Создаю подробный пересказ...")
            
            try:
                # Создаем подробный пересказ напрямую с URL источника
                if source.get('url'):
                    summary_data = await summary_agent.create_detailed_summary_from_url(source.get('url'))
                else:
                    # Fallback к старому методу
                    content_data = {
                        'title': source.get('title', ''),
                        'content': source.get('summary', ''),
                        'analysis': source
                    }
                    summary_data = await summary_agent.create_detailed_summary(
                        content_data, source.get('url', '')
                    )
                
                if summary_data:
                    # Форматируем пересказ
                    summary_message = summary_formatter.format_detailed_summary(
                        summary_data, source.get('title', ''), source.get('url', '')
                    )
                    
                    # Создаем кнопки
                    keyboard = [
                        [InlineKeyboardButton("🎙️ Озвучить подробный", callback_data=f"create_detailed_audio_from_summary_{source_id}")],
                        [InlineKeyboardButton("📄 Краткий пересказ", callback_data=f"create_brief_summary_{source_id}")],
                        [InlineKeyboardButton("📊 Статистика пересказа", callback_data=f"summary_stats_{source_id}")],
                        [InlineKeyboardButton("🔙 К источнику", callback_data=f"show_source_{source_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await query.edit_message_text(
                        summary_message,
                        parse_mode='Markdown',
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                    
                    logger.info(f"✅ Создан подробный пересказ для источника {source_id}")
                else:
                    await query.edit_message_text("❌ Не удалось создать подробный пересказ")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка создания подробного пересказа: {e}")
                await query.edit_message_text("❌ Произошла ошибка при создании подробного пересказа")
        else:
            await query.answer("❌ Неверный ID источника")

    elif query.data.startswith("create_audio_summary_") or query.data.startswith("create_audio_from_summary_"):
        # Создание аудио из пересказа
        if not ENABLE_TTS_AGENT or not tts_generator:
            await query.answer("❌ Сервис озвучивания отключен")
            return
            
        # Определяем source_id в зависимости от типа callback
        if query.data.startswith("create_audio_summary_"):
            source_id = query.data[21:]  # Убираем "create_audio_summary_"
        else:
            source_id = query.data[27:]  # Убираем "create_audio_from_summary_"
        
        # Логируем полученный source_id для отладки
        logger.info(f"🔍 Получен source_id: '{source_id}' (длина: {len(source_id)})")
        
        if source_id:
            # Получаем источник из базы данных
            source = await database_manager.get_synopsis_by_id(source_id)
            
            if not source or source.get('user_id') != user_id:
                await query.answer("❌ Источник не найден или нет доступа")
                logger.warning(f"⚠️ Источник {source_id} не найден или нет доступа для пользователя {user_id}")
                
                # Если source_id выглядит как обрезанный ObjectId, информируем об этом
                if len(source_id) == 23:
                    await query.edit_message_text(
                        "❌ **Ошибка данных**\n\n"
                        "Произошла техническая ошибка с идентификатором источника. "
                        "Попробуйте вернуться к списку источников и выбрать источник заново.\n\n"
                        "📚 Перейти к источникам:",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("📚 К источникам", callback_data="sources_filter_all_1")]
                        ])
                    )
                
                return
            
            # Показываем прогресс
            await query.edit_message_text("🎵 Создаю аудио пересказ...")
            
            try:
                # Создаем краткий пересказ напрямую с URL источника
                if source.get('url'):
                    summary_data = await summary_agent.create_brief_summary_from_url(source.get('url'))
                else:
                    # Fallback к старому методу
                    content_data = {
                        'title': source.get('title', ''),
                        'content': source.get('summary', ''),
                        'analysis': source
                    }
                    summary_data = await summary_agent.create_brief_summary(
                        content_data, source.get('url', '')
                    )
                
                if summary_data:
                    # Создаем аудио из пересказа
                    audio_result = await tts_generator.create_summary_audio(summary_data)
                    
                    if audio_result.get('success'):
                        # Отправляем аудиофайл
                        file_path = audio_result.get('file_path')
                        if file_path and os.path.exists(file_path):
                            # Форматируем сообщение с результатом
                            result_message = summary_formatter.format_tts_result(audio_result, "краткий")
                            
                            with open(file_path, 'rb') as audio_file:
                                await query.message.reply_audio(
                                    audio=audio_file,
                                    title=f"Пересказ: {source.get('title', 'Без названия')[:50]}",
                                    caption=result_message,
                                    parse_mode='Markdown'
                                )
                            
                            # Создаем кнопки для возврата
                            keyboard = [
                                [InlineKeyboardButton("🔙 К источнику", callback_data=f"show_source_{source_id}")],
                                [InlineKeyboardButton("📚 Источники", callback_data="sources_filter_all_1")]
                            ]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            
                            await query.edit_message_text(
                                "✅ Аудио пересказ создан и отправлен!",
                                reply_markup=reply_markup
                            )
                            
                            logger.info(f"✅ Создано аудио для источника {source_id}")
                        else:
                            await query.edit_message_text("❌ Не удалось создать аудиофайл")
                    else:
                        error_msg = audio_result.get('error', 'Неизвестная ошибка')
                        await query.edit_message_text(f"❌ Ошибка создания аудио: {error_msg}")
                else:
                    await query.edit_message_text("❌ Не удалось создать пересказ для озвучивания")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка создания аудио: {e}")
                await query.edit_message_text("❌ Произошла ошибка при создании аудио")
        else:
            await query.answer("❌ Неверный ID источника")
            logger.error(f"❌ Пустой source_id в create_audio_summary callback")
            await query.edit_message_text(
                "❌ **Ошибка**\n\n"
                "Не удалось определить источник для озвучивания. "
                "Попробуйте вернуться к списку источников.\n\n"
                "📚 Перейти к источникам:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📚 К источникам", callback_data="sources_filter_all_1")]
                ]                )
            )

    elif query.data.startswith("create_brief_audio_") or query.data.startswith("create_brief_audio_from_summary_"):
        # Создание краткого аудиопересказа
        if not ENABLE_TTS_AGENT or not tts_generator:
            await query.answer("❌ Сервис озвучивания отключен")
            return
            
        # Определяем source_id в зависимости от типа callback
        if query.data.startswith("create_brief_audio_"):
            source_id = query.data[19:]  # Убираем "create_brief_audio_"
        else:
            source_id = query.data[32:]  # Убираем "create_brief_audio_from_summary_"
        
        # Логируем полученный source_id для отладки
        logger.info(f"🔍 Получен source_id для краткого аудио: '{source_id}' (длина: {len(source_id)})")
        
        if source_id:
            # Получаем источник из базы данных
            source = await database_manager.get_synopsis_by_id(source_id)
            
            if not source or source.get('user_id') != user_id:
                await query.answer("❌ Источник не найден или нет доступа")
                logger.warning(f"⚠️ Источник {source_id} не найден или нет доступа для пользователя {user_id}")
                
                # Если source_id выглядит как обрезанный ObjectId, информируем об этом
                if len(source_id) == 23:
                    await query.edit_message_text(
                        "❌ **Ошибка данных**\n\n"
                        "Произошла техническая ошибка с идентификатором источника. "
                        "Попробуйте вернуться к списку источников и выбрать источник заново.\n\n"
                        "📚 Перейти к источникам:",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("📚 К источникам", callback_data="sources_filter_all_1")]
                        ])
                    )
                
                return
            
            # Показываем прогресс
            await query.edit_message_text("🎵 Создаю краткий аудиопересказ...")
            
            try:
                # Создаем краткий пересказ напрямую с URL источника
                if source.get('url'):
                    summary_data = await summary_agent.create_brief_summary_from_url(source.get('url'))
                else:
                    # Fallback к старому методу
                    content_data = {
                        'title': source.get('title', ''),
                        'content': source.get('summary', ''),
                        'analysis': source
                    }
                    summary_data = await summary_agent.create_brief_summary(
                        content_data, source.get('url', '')
                    )
                
                if summary_data:
                    # Создаем аудио из пересказа
                    audio_result = await tts_generator.create_summary_audio(summary_data)
                    
                    if audio_result.get('success'):
                        # Отправляем аудиофайл
                        file_path = audio_result.get('file_path')
                        if file_path and os.path.exists(file_path):
                            # Форматируем сообщение с результатом
                            result_message = summary_formatter.format_tts_result(audio_result, "краткий")
                            
                            with open(file_path, 'rb') as audio_file:
                                await query.message.reply_audio(
                                    audio=audio_file,
                                    title=f"Краткий пересказ: {source.get('title', 'Без названия')[:50]}",
                                    caption=result_message,
                                    parse_mode='Markdown'
                                )
                            
                            # Создаем кнопки для возврата
                            keyboard = [
                                [InlineKeyboardButton("🎙️ Подробный аудио", callback_data=f"create_detailed_audio_{source_id}")],
                                [InlineKeyboardButton("🔙 К источнику", callback_data=f"show_source_{source_id}")],
                                [InlineKeyboardButton("📚 Источники", callback_data="sources_filter_all_1")]
                            ]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            
                            await query.edit_message_text(
                                "✅ Краткий аудиопересказ создан и отправлен!",
                                reply_markup=reply_markup
                            )
                            
                            logger.info(f"✅ Создано краткое аудио для источника {source_id}")
                        else:
                            await query.edit_message_text("❌ Не удалось создать аудиофайл")
                    else:
                        error_msg = audio_result.get('error', 'Неизвестная ошибка')
                        await query.edit_message_text(f"❌ Ошибка создания аудио: {error_msg}")
                else:
                    await query.edit_message_text("❌ Не удалось создать пересказ для озвучивания")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка создания краткого аудио: {e}")
                await query.edit_message_text("❌ Произошла ошибка при создании краткого аудио")
        else:
            await query.answer("❌ Неверный ID источника")
            logger.error(f"❌ Пустой source_id в create_brief_audio callback")

    elif query.data.startswith("create_detailed_audio_") or query.data.startswith("create_detailed_audio_from_summary_"):
        # Создание подробного аудиопересказа
        if not ENABLE_TTS_AGENT or not tts_generator:
            await query.answer("❌ Сервис озвучивания отключен")
            return
            
        # Определяем source_id в зависимости от типа callback
        if query.data.startswith("create_detailed_audio_"):
            source_id = query.data[22:]  # Убираем "create_detailed_audio_"
        else:
            source_id = query.data[35:]  # Убираем "create_detailed_audio_from_summary_"
        
        # Логируем полученный source_id для отладки
        logger.info(f"🔍 Получен source_id для подробного аудио: '{source_id}' (длина: {len(source_id)})")
        
        if source_id:
            # Получаем источник из базы данных
            source = await database_manager.get_synopsis_by_id(source_id)
            
            if not source or source.get('user_id') != user_id:
                await query.answer("❌ Источник не найден или нет доступа")
                logger.warning(f"⚠️ Источник {source_id} не найден или нет доступа для пользователя {user_id}")
                
                # Если source_id выглядит как обрезанный ObjectId, информируем об этом
                if len(source_id) == 23:
                    await query.edit_message_text(
                        "❌ **Ошибка данных**\n\n"
                        "Произошла техническая ошибка с идентификатором источника. "
                        "Попробуйте вернуться к списку источников и выбрать источник заново.\n\n"
                        "📚 Перейти к источникам:",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("📚 К источникам", callback_data="sources_filter_all_1")]
                        ])
                    )
                
                return
            
            # Показываем прогресс
            await query.edit_message_text("🎙️ Создаю подробный аудиопересказ...")
            
            try:
                # Создаем подробный пересказ напрямую с URL источника
                if source.get('url'):
                    summary_data = await summary_agent.create_detailed_summary_from_url(source.get('url'))
                else:
                    # Fallback к старому методу
                    content_data = {
                        'title': source.get('title', ''),
                        'content': source.get('summary', ''),
                        'analysis': source
                    }
                    summary_data = await summary_agent.create_detailed_summary(
                        content_data, source.get('url', '')
                    )
                
                if summary_data:
                    # Создаем аудио из подробного пересказа
                    audio_result = await tts_generator.create_summary_audio(summary_data)
                    
                    if audio_result.get('success'):
                        # Отправляем аудиофайл
                        file_path = audio_result.get('file_path')
                        if file_path and os.path.exists(file_path):
                            # Форматируем сообщение с результатом
                            result_message = summary_formatter.format_tts_result(audio_result, "подробный")
                            
                            with open(file_path, 'rb') as audio_file:
                                await query.message.reply_audio(
                                    audio=audio_file,
                                    title=f"Подробный пересказ: {source.get('title', 'Без названия')[:50]}",
                                    caption=result_message,
                                    parse_mode='Markdown'
                                )
                            
                            # Создаем кнопки для возврата
                            keyboard = [
                                [InlineKeyboardButton("🎵 Краткий аудио", callback_data=f"create_brief_audio_{source_id}")],
                                [InlineKeyboardButton("🔙 К источнику", callback_data=f"show_source_{source_id}")],
                                [InlineKeyboardButton("📚 Источники", callback_data="sources_filter_all_1")]
                            ]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            
                            await query.edit_message_text(
                                "✅ Подробный аудиопересказ создан и отправлен!",
                                reply_markup=reply_markup
                            )
                            
                            logger.info(f"✅ Создано подробное аудио для источника {source_id}")
                        else:
                            await query.edit_message_text("❌ Не удалось создать аудиофайл")
                    else:
                        error_msg = audio_result.get('error', 'Неизвестная ошибка')
                        await query.edit_message_text(f"❌ Ошибка создания аудио: {error_msg}")
                else:
                    await query.edit_message_text("❌ Не удалось создать подробный пересказ для озвучивания")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка создания подробного аудио: {e}")
                await query.edit_message_text("❌ Произошла ошибка при создании подробного аудио")
        else:
            await query.answer("❌ Неверный ID источника")
            logger.error(f"❌ Пустой source_id в create_detailed_audio callback")

    elif query.data.startswith("summary_stats_"):
        # Показать статистику пересказа
        source_id = query.data[14:]  # Убираем "summary_stats_"
        
        if source_id:
            await query.edit_message_text(
                "📊 **Статистика пересказа**\n\n"
                "🔧 Функция в разработке...\n\n"
                "Скоро здесь будет детальная статистика по качеству и эффективности пересказа.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data=f"show_source_{source_id}")]
                ])
            )
        else:
            await query.answer("❌ Неверный ID источника")
    
    elif query.data.startswith("set_rating_"):
        # Обработка установки рейтинга
        parts = query.data.split("_")
        if len(parts) >= 4:
            rating = int(parts[2]) if parts[2].isdigit() else 0
            source_id = "_".join(parts[3:])  # ID может содержать подчеркивания
            
            if source_id and 0 <= rating <= 5:
                # Получаем источник для проверки принадлежности
                source = await database_manager.get_synopsis_by_id(source_id)
                
                if not source or source.get('user_id') != user_id:
                    await query.answer("❌ Источник не найден или нет доступа")
                    return
                
                # Обновляем рейтинг
                success = await database_manager.update_source_rating(source_id, rating)
                
                if success:
                    rating_text = "сброшен" if rating == 0 else f"установлен на {rating} {'звезду' if rating == 1 else 'звезды' if rating < 5 else 'звезд'}"
                    await query.answer(f"⭐ Рейтинг {rating_text}")
                    
                    # Обновляем отображение источника
                    updated_source = await database_manager.get_synopsis_by_id(source_id)
                    if updated_source:
                        source_message = formatter.format_single_source_details(updated_source)
                        
                        # Создаем обновленные кнопки управления
                        keyboard = []
                        
                        # Кнопки рейтинга
                        rating_buttons_row1 = []
                        rating_buttons_row2 = []
                        for i in range(1, 6):
                            emoji = "⭐" if i <= updated_source.get('rating', 0) else "☆"
                            rating_buttons_row1.append(InlineKeyboardButton(
                                f"{emoji} {i}",
                                callback_data=f"set_rating_{i}_{source_id}"
                            ))
                        
                        keyboard.append(rating_buttons_row1[:3])
                        keyboard.append(rating_buttons_row1[3:5] + [InlineKeyboardButton("🔄 Сброс", callback_data=f"set_rating_0_{source_id}")])
                        
                        # Кнопки статуса прочтения
                        if updated_source.get('read_status') == 'read':
                            keyboard.append([
                                InlineKeyboardButton("✅ Прочитано", callback_data=f"mark_synopsis_read_{source_id}"),
                                InlineKeyboardButton("📖 Отметить не прочитанным", callback_data=f"mark_synopsis_unread_{source_id}")
                            ])
                        else:
                            keyboard.append([
                                InlineKeyboardButton("✅ Отметить прочитанным", callback_data=f"mark_synopsis_read_{source_id}"),
                                InlineKeyboardButton("📖 Не прочитано", callback_data=f"mark_synopsis_unread_{source_id}")
                            ])
                        
                        # Кнопки пересказа (если агент включен)
                        if ENABLE_SUMMARY_AGENT:
                            keyboard.extend([
                                [InlineKeyboardButton("📄 Краткий пересказ", callback_data=f"create_brief_summary_{source_id}"),
                                 InlineKeyboardButton("📚 Подробный пересказ", callback_data=f"create_detailed_summary_{source_id}")],
                            ])
                        
                        # Кнопки озвучивания (если агент включен)
                        if ENABLE_TTS_AGENT:
                            keyboard.append([
                                InlineKeyboardButton("🎵 Краткий аудио", callback_data=f"create_brief_audio_{source_id}"),
                                InlineKeyboardButton("🎙️ Подробный аудио", callback_data=f"create_detailed_audio_{source_id}")
                            ])
                        
                        # Кнопки управления
                        keyboard.extend([
                            [InlineKeyboardButton("🗑️ Удалить источник", callback_data=f"delete_source_{source_id}")],
                            [InlineKeyboardButton("📚 К источникам", callback_data="sources_filter_all_1"),
                             InlineKeyboardButton("📊 Статистика", callback_data="refresh_stats")]
                        ])
                        
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        try:
                            await query.edit_message_text(
                                source_message,
                                parse_mode='Markdown',
                                reply_markup=reply_markup,
                                disable_web_page_preview=True
                            )
                        except (Conflict, BadRequest) as e:
                            logger.info(f"ℹ️ Не удалось обновить сообщение: {e}")
                else:
                    await query.answer("❌ Не удалось обновить рейтинг")
            else:
                await query.answer("❌ Неверные параметры рейтинга")
        else:
            await query.answer("❌ Неверный формат данных")


@require_authorization
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user = update.effective_user
    log_user_access(user.id, user.username, "message")
    
    text = update.message.text
    user_id = update.effective_user.id
    original_message = update.message
    
    # Ищем URL в сообщении
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, text)
    
    if not urls:
        await update.message.reply_text(
            "🔗 Отправьте ссылку для анализа!\n\nПример: https://habr.com/ru/articles/123456/"
        )
        return
    
    for url in urls:
        # Проверяем валидность URL
        if not analyzer.is_supported_url(url):
            await update.message.reply_text(
                f"❌ Некорректный URL: {url}\n\n"
                "🔗 Убедитесь, что ссылка начинается с http:// или https://"
            )
            continue
        
        # Отправляем сообщение о начале анализа
        processing_msg = await update.message.reply_text(
            f"🔍 Анализирую ссылку...\n{url}",
            parse_mode='Markdown'
        )
        
        try:
            # Анализируем URL
            analysis_data = await analyzer.analyze_url(url)
            
            if analysis_data:
                # Сохраняем анализ в базы данных
                synopsis_id = await database_manager.save_analysis(user_id, analysis_data)
                
                # Форматируем и отправляем результат
                result_message = formatter.format_analysis_message(analysis_data)
                
                # Добавляем кнопки для статистики, источников и статуса прочтения
                keyboard = []
                
                # Кнопки статуса прочтения (если синопсис сохранен)
                if synopsis_id:
                    keyboard.append([
                        InlineKeyboardButton("✅ Прочитано", callback_data=f"mark_synopsis_read_{synopsis_id}"),
                        InlineKeyboardButton("📖 Не прочитано", callback_data=f"mark_synopsis_unread_{synopsis_id}")
                    ])
                
                # Кнопки пересказа (если агент включен)
                if synopsis_id and ENABLE_SUMMARY_AGENT:
                    keyboard.append([
                        InlineKeyboardButton("📄 Краткий пересказ", callback_data=f"create_brief_summary_{synopsis_id}"),
                        InlineKeyboardButton("📚 Подробный пересказ", callback_data=f"create_detailed_summary_{synopsis_id}")
                    ])
                
                # Кнопки озвучивания (если агент включен)
                if synopsis_id and ENABLE_TTS_AGENT:
                    keyboard.append([
                        InlineKeyboardButton("🎵 Краткий аудио", callback_data=f"create_brief_audio_{synopsis_id}"),
                        InlineKeyboardButton("🎙️ Подробный аудио", callback_data=f"create_detailed_audio_{synopsis_id}")
                    ])
                
                # Основные кнопки
                keyboard.extend([
                    [InlineKeyboardButton("📊 Статистика", callback_data="refresh_stats")],
                    [InlineKeyboardButton("📚 Источники", callback_data="sources_filter_all_1")]
                ])
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await processing_msg.edit_text(
                    result_message,
                    parse_mode='Markdown',
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
                
                # Удаляем исходное сообщение со ссылкой после успешного анализа
                if DELETE_ORIGINAL_LINKS:
                    try:
                        await original_message.delete()
                        logger.info(f"✅ Удалено исходное сообщение со ссылкой: {url}")
                    except (Conflict, BadRequest) as delete_error:
                        logger.info(f"ℹ️ Сообщение уже удалено или недоступно: {delete_error}")
                    except TelegramError as delete_error:
                        logger.warning(f"⚠️ Не удалось удалить исходное сообщение: {delete_error}")
                        # Не прерываем работу, если удаление не удалось
                
            else:
                await processing_msg.edit_text(
                    f"❌ Не удалось проанализировать ссылку: {url}"
                )
                
        except Exception as e:
            logger.error(f"Ошибка при анализе {url}: {e}")
            await processing_msg.edit_text(
                f"❌ Произошла ошибка при анализе: {url}\n\nПопробуйте позже."
            )


@require_authorization
async def source_detail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /src_<id> для просмотра деталей источника"""
    user = update.effective_user
    user_id = user.id
    
    # Извлекаем ID источника из команды
    command_text = update.message.text
    if not command_text.startswith('/src_'):
        await update.message.reply_text("❌ Неверный формат команды")
        return
    
    source_id = command_text[5:]  # Убираем '/src_'
    
    if not source_id:
        await update.message.reply_text("❌ Не указан ID источника")
        return
    
    log_user_access(user_id, user.username, f"/src_{source_id}")
    
    # Получаем источник из базы данных
    source = await database_manager.get_synopsis_by_id(source_id)
    
    if not source:
        await update.message.reply_text("❌ Источник не найден")
        return
    
    # Проверяем, что источник принадлежит пользователю
    if source.get('user_id') != user_id:
        await update.message.reply_text("❌ У вас нет доступа к этому источнику")
        return
    
    # Форматируем детальную информацию
    source_message = formatter.format_single_source_details(source)
    
    # Создаем кнопки управления
    keyboard = []
    
    # Кнопки рейтинга
    rating_buttons_row1 = []
    current_rating = source.get('rating', 0)
    for i in range(1, 6):
        emoji = "⭐" if i <= current_rating else "☆"
        rating_buttons_row1.append(InlineKeyboardButton(
            f"{emoji} {i}",
            callback_data=f"set_rating_{i}_{source_id}"
        ))
    
    keyboard.append(rating_buttons_row1[:3])
    keyboard.append(rating_buttons_row1[3:5] + [InlineKeyboardButton("🔄 Сброс", callback_data=f"set_rating_0_{source_id}")])
    
    # Кнопки статуса прочтения
    if source.get('read_status') == 'read':
        keyboard.append([
            InlineKeyboardButton("✅ Прочитано", callback_data=f"mark_synopsis_read_{source_id}"),
            InlineKeyboardButton("📖 Отметить не прочитанным", callback_data=f"mark_synopsis_unread_{source_id}")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("✅ Отметить прочитанным", callback_data=f"mark_synopsis_read_{source_id}"),
            InlineKeyboardButton("📖 Не прочитано", callback_data=f"mark_synopsis_unread_{source_id}")
        ])
    
    # Кнопки управления
    keyboard.extend([
        [InlineKeyboardButton("🗑️ Удалить источник", callback_data=f"delete_source_{source_id}")],
        [InlineKeyboardButton("📚 К источникам", callback_data="sources_filter_all_1"),
         InlineKeyboardButton("📊 Статистика", callback_data="refresh_stats")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        source_message,
        parse_mode='Markdown',
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )


@require_authorization 
async def clear_single_source_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /clear_source <id> для удаления одного источника"""
    user = update.effective_user
    user_id = user.id
    
    if not context.args:
        await update.message.reply_text(
            "❌ **Неверный формат команды**\n\n"
            "Использование: `/clear_source <ID_источника>`\n\n"
            "Пример: `/clear_source 507f1f77bcf86cd799439011`",
            parse_mode='Markdown'
        )
        return
    
    source_id = context.args[0]
    log_user_access(user_id, user.username, f"/clear_source {source_id}")
    
    # Получаем источник для проверки принадлежности
    source = await database_manager.get_synopsis_by_id(source_id)
    
    if not source:
        await update.message.reply_text("❌ Источник не найден")
        return
    
    # Проверяем, что источник принадлежит пользователю
    if source.get('user_id') != user_id:
        await update.message.reply_text("❌ У вас нет доступа к этому источнику")
        return
    
    # Отправляем подтверждение
    source_title = source.get('title', 'Без названия')
    if len(source_title) > 50:
        source_title = source_title[:47] + '...'
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_{source_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_delete")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🗑️ **Подтверждение удаления**\n\n"
        f"Вы действительно хотите удалить источник?\n\n"
        f"📄 **{source_title}**\n"
        f"🔗 {source.get('url', '')}\n\n"
        f"⚠️ Это действие нельзя отменить!",
        parse_mode='Markdown',
        reply_markup=reply_markup
    ) 