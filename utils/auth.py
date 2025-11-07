"""
Утилиты для авторизации пользователей
"""

from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

from config import ENABLE_USER_AUTHORIZATION, ALLOWED_USERS, ADMIN_USERS, UNAUTHORIZED_MESSAGE
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def is_user_authorized(user_id: int) -> bool:
    """
    Проверяет, авторизован ли пользователь для использования бота
    
    Args:
        user_id: ID пользователя Telegram
        
    Returns:
        bool: True если пользователь авторизован или авторизация отключена
    """
    # Если авторизация отключена, разрешаем всем
    if not ENABLE_USER_AUTHORIZATION:
        return True
    
    # Проверяем в базе данных
    try:
        from storage.database_manager import database_manager
        is_authorized_in_db = await database_manager.is_user_authorized(user_id)
        
        # Если пользователь авторизован в БД, возвращаем True
        if is_authorized_in_db:
            return True
    except Exception as e:
        logger.error(f"❌ Ошибка проверки авторизации в БД для пользователя {user_id}: {e}")
    
    # Fallback: проверяем в старом списке для совместимости
    if user_id in ALLOWED_USERS:
        return True
    
    # Если список пуст, разрешаем всем (для обратной совместимости)
    if not ALLOWED_USERS:
        return True
    
    return False


def require_authorization(func):
    """
    Декоратор для проверки авторизации пользователя
    
    Использование:
        @require_authorization
        async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # код обработчика
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_id = user.id
        
        # Асинхронная проверка авторизации
        if not await is_user_authorized(user_id):
            username = user.username or user.first_name or "Unknown"
            logger.warning(f"Unauthorized access attempt from user {user_id} (@{username})")
            
            await update.message.reply_text(
                UNAUTHORIZED_MESSAGE,
                parse_mode='Markdown'
            )
            return
        
        # Обновляем активность пользователя в БД
        try:
            from storage.database_manager import database_manager
            await database_manager.update_user_activity(user_id)
        except Exception as e:
            logger.error(f"❌ Ошибка обновления активности пользователя {user_id}: {e}")
        
        # Пользователь авторизован, выполняем оригинальную функцию
        return await func(update, context)
    
    return wrapper


def log_user_access(user_id: int, username: str = None, command: str = None):
    """
    Логирует обращение пользователя к боту
    
    Args:
        user_id: ID пользователя
        username: Имя пользователя (опционально)
        command: Выполненная команда (опционально)
    """
    username_str = f"@{username}" if username else "Unknown"
    command_str = f" Command: {command}" if command else ""
    
    logger.info(f"User access: {user_id} ({username_str}){command_str}")


def get_authorization_status() -> dict:
    """
    Возвращает информацию о текущих настройках авторизации
    
    Returns:
        dict: Информация о настройках авторизации
    """
    return {
        'enabled': ENABLE_USER_AUTHORIZATION,
        'allowed_users_count': len(ALLOWED_USERS),
        'allowed_users': ALLOWED_USERS if ALLOWED_USERS else []
    }


async def is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором
    
    Args:
        user_id: ID пользователя Telegram
        
    Returns:
        bool: True если пользователь является администратором
    """
    # Проверяем в базе данных
    try:
        from storage.database_manager import database_manager
        is_admin_in_db = await database_manager.is_user_admin(user_id)
        
        # Если пользователь админ в БД, возвращаем True
        if is_admin_in_db:
            return True
    except Exception as e:
        logger.error(f"❌ Ошибка проверки прав администратора в БД для пользователя {user_id}: {e}")
    
    # Fallback: проверяем в старом списке для совместимости
    return user_id in ADMIN_USERS


def require_admin(func):
    """
    Декоратор для проверки прав администратора
    
    Использование:
        @require_admin
        async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # код для администраторов
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_id = user.id
        
        # Асинхронная проверка прав администратора
        if not await is_admin(user_id):
            username = user.username or user.first_name or "Unknown"
            logger.warning(f"Unauthorized admin access attempt from user {user_id} (@{username})")
            
            await update.message.reply_text(
                "🚫 **Недостаточно прав**\n\nЭта команда доступна только администраторам.",
                parse_mode='Markdown'
            )
            return
        
        # Обновляем активность администратора в БД
        try:
            from storage.database_manager import database_manager
            await database_manager.update_user_activity(user_id)
        except Exception as e:
            logger.error(f"❌ Ошибка обновления активности администратора {user_id}: {e}")
        
        # Пользователь является администратором, выполняем функцию
        return await func(update, context)
    
    return wrapper


def get_user_info_text(user_id: int) -> str:
    """
    Возвращает текстовую информацию о статусе пользователя
    
    Args:
        user_id: ID пользователя
        
    Returns:
        str: Информация о статусе пользователя
    """
    status_parts = []
    
    # Синхронная проверка через конфиг (для быстрого отображения)
    if user_id in ADMIN_USERS:
        status_parts.append("👑 Администратор")
    
    if user_id in ALLOWED_USERS or not ENABLE_USER_AUTHORIZATION:
        status_parts.append("✅ Авторизован")
    else:
        status_parts.append("🚫 Не авторизован")
    
    return " | ".join(status_parts) if status_parts else "❓ Неизвестный статус" 