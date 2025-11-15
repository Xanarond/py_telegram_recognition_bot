"""
Декораторы для обработчиков команд
"""

import functools
from typing import Callable, Any
from telegram import Update
from telegram.ext import ContextTypes
from utils.auth import is_user_authorized
from utils.logger import setup_logger

logger = setup_logger(__name__)


def require_authorization(func: Callable) -> Callable:
    """
    Декоратор для проверки авторизации пользователя
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs) -> Any:
        if not update.effective_user:
            logger.warning("❌ Получено обновление без пользователя")
            return
        
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        
        if not is_user_authorized(user_id):
            logger.warning(f"❌ Неавторизованный доступ: {username} (ID: {user_id})")
            await update.message.reply_text(
                "❌ У вас нет доступа к этому боту.\n"
                "Обратитесь к администратору для получения доступа."
            )
            return
        
        # Логируем успешный доступ
        command = func.__name__.replace('_command', '').replace('_', ' ').title()
        logger.info(f"✅ Авторизованный доступ: {username} (ID: {user_id}) -> {command}")
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


def log_user_access(func: Callable) -> Callable:
    """
    Декоратор для логирования доступа пользователей
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs) -> Any:
        if update.effective_user:
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            command = func.__name__.replace('_command', '').replace('_', ' ').title()
            
            logger.info(f"📊 Доступ пользователя: {username} (ID: {user_id}) -> {command}")
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


def handle_errors(func: Callable) -> Callable:
    """
    Декоратор для обработки ошибок в командах
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs) -> Any:
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            logger.error(f"❌ Ошибка в команде {func.__name__}: {e}", exc_info=True)
            
            if update.message:
                await update.message.reply_text(
                    "❌ Произошла ошибка при выполнении команды.\n"
                    "Попробуйте позже или обратитесь к администратору."
                )
    
    return wrapper


def typing_action(func: Callable) -> Callable:
    """
    Декоратор для показа индикатора печати
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs) -> Any:
        if update.message:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action="typing"
            )
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


def admin_only(func: Callable) -> Callable:
    """
    Декоратор для команд только для администраторов
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs) -> Any:
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        
        # Здесь можно добавить проверку на админа
        # Пока используем простую проверку авторизации
        if not is_user_authorized(user_id):
            logger.warning(f"❌ Попытка доступа к админ-команде: {username} (ID: {user_id})")
            await update.message.reply_text(
                "❌ Эта команда доступна только администраторам."
            )
            return
        
        logger.info(f"🔧 Админ-команда: {username} (ID: {user_id}) -> {func.__name__}")
        return await func(update, context, *args, **kwargs)
    
    return wrapper
