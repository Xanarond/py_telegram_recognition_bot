#!/usr/bin/env python3
"""
Telegram Bot для анализа контента с помощью ИИ
Модульная архитектура
"""

import asyncio
import signal

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

from config import BOT_TOKEN, ANTHROPIC_API_KEY, ensure_directories
from handlers.bot_handlers import (
    start, help_command, stats_command, sources_command, 
    export_command, clear_stats, handle_callback, handle_message,
    source_detail_command, clear_single_source_command
)
from handlers.admin_handlers import (
    admin_panel, list_users, add_user, remove_user, user_info, auth_status_command
)
from handlers.rag_handlers import (
    search_command, ask_command, compare_command, 
    synthesize_command, similar_command, rag_help_command
)
from handlers.analytics_handlers import (
    analytics_command, trends_command, clusters_command
)
from storage.database_manager import database_manager
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def initialize_databases():
    """Инициализация баз данных"""
    try:
        await database_manager.initialize()
        logger.info("✅ Базы данных инициализированы")
        
        # Инициализируем сервис векторизации
        from config import ENABLE_VECTOR_DB
        if ENABLE_VECTOR_DB:
            try:
                from analyzers.vectorization_service import vectorization_service
                await vectorization_service.initialize()
                logger.info("✅ Сервис векторизации инициализирован")
            except Exception as vec_error:
                logger.warning(f"⚠️ Сервис векторизации не инициализирован: {vec_error}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации баз данных: {e}")
        raise


async def main():
    """Главная функция"""
    if not BOT_TOKEN:
        print("❌ Ошибка: Не указан BOT_TOKEN!")
        print("Получите токен у @BotFather и добавьте его в переменную BOT_TOKEN")
        return
    
    if not ANTHROPIC_API_KEY:
        print("❌ Ошибка: Не указан ANTHROPIC_API_KEY!")
        return
    
    print("🤖 Запускаю Telegram бота для анализа контента...")
    
    # Создаем необходимые директории
    ensure_directories()
    
    # Инициализируем базы данных
    await initialize_databases()
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("sources", sources_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("clear", clear_stats))
    application.add_handler(CommandHandler("clear_source", clear_single_source_command))
    
    # RAG команды
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("ask", ask_command))
    application.add_handler(CommandHandler("compare", compare_command))
    application.add_handler(CommandHandler("synthesize", synthesize_command))
    application.add_handler(CommandHandler("similar", similar_command))
    application.add_handler(CommandHandler("rag_help", rag_help_command))
    
    # Аналитические команды
    application.add_handler(CommandHandler("analytics", analytics_command))
    application.add_handler(CommandHandler("trends", trends_command))
    application.add_handler(CommandHandler("clusters", clusters_command))
    
    # MessageHandler для команд типа /src_<id> (обрабатывается в handle_message)
    from telegram.ext import filters
    from telegram import MessageEntity
    import telegram.ext.filters as tg_filters
    
    # Создаем фильтр для команд /src_*
    class SourceCommandFilter(tg_filters.MessageFilter):
        def filter(self, message):
            if not message.text:
                return False
            return message.text.startswith('/src_')
    
    source_command_filter = SourceCommandFilter()
    application.add_handler(MessageHandler(source_command_filter, source_detail_command))
    
    # Административные команды
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("users", list_users))
    application.add_handler(CommandHandler("add_user", add_user))
    application.add_handler(CommandHandler("remove_user", remove_user))
    application.add_handler(CommandHandler("user_info", user_info))
    application.add_handler(CommandHandler("auth_status", auth_status_command))
    # Добавляем обработчики callback кнопок и сообщений
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Настраиваем обработчик сигналов завершения
    stop_event = asyncio.Event()
    
    async def cleanup():
        """Корректное завершение работы"""
        print("\n⚠️ Закрываю подключения к БД...")
        try:
            await database_manager.close()
            print("✅ Подключения закрыты.")
        except Exception as e:
            print(f"❌ Ошибка закрытия подключений: {e}")
    
    def signal_handler(signum, frame):
        """Обработчик сигналов завершения"""
        print("\n⚠️ Получен сигнал завершения. Останавливаю бота...")
        # Устанавливаем событие для остановки
        asyncio.get_event_loop().call_soon_threadsafe(stop_event.set)
    
    # Регистрируем обработчик для SIGINT (Ctrl+C) и SIGTERM
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запускаем бота
    print("✅ Бот запущен! Нажмите Ctrl+C для остановки.")
    
    try:
        # Инициализируем приложение
        await application.initialize()
        await application.start()
        
        # Запускаем updater
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES
        )
        
        # Ждем сигнала остановки
        await stop_event.wait()
        
    finally:
        # Корректно останавливаем приложение
        try:
            await application.updater.stop()
        except Exception as e:
            print(f"Ошибка остановки updater: {e}")
        
        try:
            await application.stop()
        except Exception as e:
            print(f"Ошибка остановки приложения: {e}")
        
        try:
            await application.shutdown()
        except Exception as e:
            print(f"Ошибка завершения приложения: {e}")
        
        await cleanup()


if __name__ == '__main__':
    try:
        # Запускаем асинхронную функцию main
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
    finally:
        print("👋 Завершение работы...") 