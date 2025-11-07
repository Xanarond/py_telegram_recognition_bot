"""
Административные обработчики для управления авторизацией
"""

from storage.database_manager import database_manager
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from datetime import datetime

from config import ALLOWED_USERS, ADMIN_USERS, ENABLE_USER_AUTHORIZATION
from utils.auth import require_admin, is_user_authorized, get_authorization_status, get_user_info_text
from utils.logger import setup_logger

logger = setup_logger(__name__)


@require_admin
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Административная панель"""
    status = get_authorization_status()
    
    auth_status = "🟢 Включена" if status['enabled'] else "🔴 Отключена"
    users_count = status['allowed_users_count']
    admins_count = len(ADMIN_USERS)
    
    admin_text = f"""👑 **Административная панель**

🔐 **Статус авторизации:** {auth_status}
👥 **Разрешенных пользователей:** {users_count}
👑 **Администраторов:** {admins_count}

**Доступные команды:**
• `/admin` - эта панель
• `/users` - список пользователей
• `/add_user <ID>` - добавить пользователя
• `/remove_user <ID>` - удалить пользователя
• `/user_info <ID>` - информация о пользователе
• `/auth_status` - статус авторизации

**Получение ID пользователя:**
• Попросите пользователя написать @userinfobot
• Или найдите ID в логах бота"""

    keyboard = [
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users_list")],
        [InlineKeyboardButton("📊 Статус", callback_data="admin_auth_status")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        admin_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


@require_admin
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список авторизованных пользователей"""
    
    # Получаем пользователей из БД (включая неактивных для администраторов)
    db_users = await database_manager.get_all_users(include_inactive=True)
    
    # Объединяем с пользователями из старого списка для совместимости
    all_user_ids = set()
    
    # Добавляем пользователей из БД
    for db_user in db_users:
        all_user_ids.add(db_user['telegram_id'])
    
    # Добавляем пользователей из старого списка
    for user_id in ALLOWED_USERS:
        all_user_ids.add(user_id)
    
    if not all_user_ids:
        await update.message.reply_text(
            "👥 **Список пользователей пуст**\n\nИспользуйте `/add_user <ID>` для добавления пользователей.",
            parse_mode='Markdown'
        )
        return
    
    users_text = "👥 **Авторизованные пользователи:**\n\n"
    
    # Создаем словарь пользователей из БД для быстрого доступа
    db_users_dict = {user['telegram_id']: user for user in db_users}
    
    active_count = 0
    inactive_count = 0
    
    for i, user_id in enumerate(sorted(all_user_ids), 1):
        # Получаем информацию о пользователе из БД
        db_user = db_users_dict.get(user_id)
        
        if db_user:
            status_parts = []
            
            # Проверяем статус администратора
            if db_user['is_admin']:
                status_parts.append("👑 Админ")
            
            # Проверяем активность
            if db_user['is_active']:
                status_parts.append("✅ Активен")
                active_count += 1
            else:
                status_parts.append("🔴 Неактивен")
                inactive_count += 1
            
            # Добавляем имя пользователя если есть
            if db_user['username']:
                status_parts.append(f"@{db_user['username']}")
            elif db_user['first_name']:
                status_parts.append(f"{db_user['first_name']}")
            
            status_info = " | ".join(status_parts)
        else:
            # Пользователь только в старом списке
            status_info = get_user_info_text(user_id) + " | 🔄 Старый формат"
            active_count += 1
        
        users_text += f"{i}. `{user_id}` - {status_info}\n"
    
    users_text += f"\n**Статистика:**\n"
    users_text += f"• Всего пользователей: {len(all_user_ids)}\n"
    users_text += f"• Активных: {active_count}\n"
    users_text += f"• Неактивных: {inactive_count}\n"
    users_text += f"• В БД: {len(db_users)}\n"
    users_text += f"• В старом списке: {len(ALLOWED_USERS)}"
    
    await update.message.reply_text(users_text, parse_mode='Markdown')


@require_admin
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить пользователя в список разрешенных"""
    if not context.args:
        await update.message.reply_text(
            "❌ **Ошибка**\n\nИспользование: `/add_user <ID_пользователя>`\n\nПример: `/add_user 123456789`",
            parse_mode='Markdown'
        )
        return
    
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ **Ошибка**\n\nID пользователя должен быть числом.",
            parse_mode='Markdown'
        )
        return
    
    # Проверяем, не авторизован ли уже пользователь в БД
    is_already_authorized = await database_manager.is_user_authorized(user_id)
    
    if is_already_authorized:
        await update.message.reply_text(
            f"ℹ️ **Пользователь уже авторизован**\n\nПользователь `{user_id}` уже находится в списке разрешенных.",
            parse_mode='Markdown'
        )
        return
    
    # Создаем пользователя в базе данных
    user_created = await database_manager.create_user(
        telegram_id=user_id,
        username=None,  # Будет обновлено при первом обращении
        first_name=None,
        last_name=None,
        is_admin=False
    )
    
    if not user_created:
        await update.message.reply_text(
            f"❌ **Ошибка**\n\nНе удалось добавить пользователя `{user_id}` в базу данных.",
            parse_mode='Markdown'
        )
        return
    
    # Также добавляем в старый список для совместимости
    if user_id not in ALLOWED_USERS:
        ALLOWED_USERS.append(user_id)
    
    # Логируем действие администратора
    await database_manager.log_admin_action(
        admin_telegram_id=update.effective_user.id,
        action_type="add_user",
        target_telegram_id=user_id,
        description=f"Пользователь {user_id} добавлен в список авторизованных"
    )
    
    logger.info(f"Admin {update.effective_user.id} added user {user_id} to authorized list")
    
    await update.message.reply_text(
        f"✅ **Пользователь добавлен**\n\nПользователь `{user_id}` добавлен в список разрешенных и создан в базе данных.\n\n"
        f"**Статус:** {get_user_info_text(user_id)}",
        parse_mode='Markdown'
    )


@require_admin
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить пользователя из списка разрешенных"""
    if not context.args:
        await update.message.reply_text(
            "❌ **Ошибка**\n\nИспользование: `/remove_user <ID_пользователя>`\n\nПример: `/remove_user 123456789`",
            parse_mode='Markdown'
        )
        return
    
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ **Ошибка**\n\nID пользователя должен быть числом.",
            parse_mode='Markdown'
        )
        return
    
    # Проверяем, авторизован ли пользователь в БД
    is_authorized = await database_manager.is_user_authorized(user_id)
    
    if not is_authorized and user_id not in ALLOWED_USERS:
        await update.message.reply_text(
            f"ℹ️ **Пользователь не найден**\n\nПользователь `{user_id}` не находится в списке разрешенных.",
            parse_mode='Markdown'
        )
        return
    
    # Проверяем, не является ли пользователь администратором
    is_admin_user = await database_manager.is_user_admin(user_id)
    if is_admin_user or user_id in ADMIN_USERS:
        await update.message.reply_text(
            f"❌ **Нельзя удалить администратора**\n\nПользователь `{user_id}` является администратором и не может быть удален из списка.",
            parse_mode='Markdown'
        )
        return
    
    # Деактивируем пользователя в БД (не удаляем, а деактивируем)
    deactivated = await database_manager.set_user_active_status(user_id, False)
    
    # Удаляем из старого списка для совместимости
    if user_id in ALLOWED_USERS:
        ALLOWED_USERS.remove(user_id)
    
    # Логируем действие администратора
    await database_manager.log_admin_action(
        admin_telegram_id=update.effective_user.id,
        action_type="remove_user",
        target_telegram_id=user_id,
        description=f"Пользователь {user_id} удален из списка авторизованных"
    )
    
    logger.info(f"Admin {update.effective_user.id} removed user {user_id} from authorized list")
    
    await update.message.reply_text(
        f"✅ **Пользователь удален**\n\nПользователь `{user_id}` удален из списка разрешенных и деактивирован в базе данных.",
        parse_mode='Markdown'
    )


@require_admin
async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о пользователе"""
    if not context.args:
        # Показываем информацию о текущем пользователе
        user_id = update.effective_user.id
    else:
        try:
            user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text(
                "❌ **Ошибка**\n\nID пользователя должен быть числом.",
                parse_mode='Markdown'
            )
            return
    
    # Получаем информацию из базы данных
    
    db_user = await database_manager.get_user(user_id)
    
    # Проверяем статусы
    is_authorized_db = await database_manager.is_user_authorized(user_id)
    is_admin_db = await database_manager.is_user_admin(user_id)
    is_authorized_old = await is_user_authorized(user_id)
    is_admin_old = user_id in ADMIN_USERS
    
    info_text = f"""👤 **Информация о пользователе**

**ID:** `{user_id}`

**База данных:**"""
    
    if db_user:
        info_text += f"""
• Существует в БД: ✅ Да
• Имя пользователя: {db_user.username or 'Не указано'}
• Имя: {db_user.first_name or 'Не указано'}
• Активен: {'✅ Да' if db_user.is_active else '❌ Нет'}
• Администратор: {'✅ Да' if db_user.is_admin else '❌ Нет'}
• Последняя активность: {db_user.last_activity.strftime('%Y-%m-%d %H:%M:%S') if db_user.last_activity else 'Никогда'}
• Создан: {db_user.created_at.strftime('%Y-%m-%d %H:%M:%S')}"""
    else:
        info_text += "\n• Существует в БД: ❌ Нет"
    
    info_text += f"""

**Авторизация:**
• Авторизован (БД): {'✅ Да' if is_authorized_db else '❌ Нет'}
• Авторизован (общий): {'✅ Да' if is_authorized_old else '❌ Нет'}
• Администратор (БД): {'✅ Да' if is_admin_db else '❌ Нет'}
• Администратор (конфиг): {'✅ Да' if is_admin_old else '❌ Нет'}

**Совместимость:**
• В списке ALLOWED_USERS: {'✅ Да' if user_id in ALLOWED_USERS else '❌ Нет'}
• В списке ADMIN_USERS: {'✅ Да' if user_id in ADMIN_USERS else '❌ Нет'}"""

    await update.message.reply_text(info_text, parse_mode='Markdown')


def _get_auth_behavior_text() -> str:
    """Возвращает описание поведения системы авторизации"""
    if not ENABLE_USER_AUTHORIZATION:
        return "• Все пользователи имеют доступ (авторизация отключена)"
    
    if not ALLOWED_USERS:
        return "• Все пользователи имеют доступ (список пуст)"
    
    return f"• Доступ только для {len(ALLOWED_USERS)} разрешенных пользователей"


@require_admin
async def auth_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статус системы авторизации"""
    
    # Получаем статистику из базы данных
    db_users = await database_manager.get_all_users(include_inactive=True)
    active_users = [user for user in db_users if user['is_active']]
    admin_users = [user for user in db_users if user['is_admin']]
    
    # Старая система
    old_allowed_count = len(ALLOWED_USERS)
    old_admin_count = len(ADMIN_USERS)
    
    status_text = f"""🔐 **Статус системы авторизации**

**Текущие настройки:**
• Авторизация: {'🟢 Включена' if ENABLE_USER_AUTHORIZATION else '🔴 Отключена'}

**База данных (новая система):**
• Всего пользователей в БД: {len(db_users)}
• Активных пользователей: {len(active_users)}
• Администраторов в БД: {len(admin_users)}

**Конфигурация (старая система):**
• В списке ALLOWED_USERS: {old_allowed_count}
• В списке ADMIN_USERS: {old_admin_count}

**Рекомендации:**
• Используйте команды `/add_user` и `/remove_user` для управления пользователями
• Все новые пользователи создаются в базе данных"""

    keyboard = [
        [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users_list")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_auth_status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        status_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback для обновления административной панели"""
    query = update.callback_query
    
    status = get_authorization_status()
    
    auth_status = "🟢 Включена" if status['enabled'] else "🔴 Отключена"
    users_count = status['allowed_users_count']
    admins_count = len(ADMIN_USERS)
    
    # Добавляем временную метку для принудительного обновления
    current_time = datetime.now().strftime("%H:%M:%S")
    
    admin_text = f"""👑 **Административная панель**

🔐 **Статус авторизации:** {auth_status}
👥 **Разрешенных пользователей:** {users_count}
👑 **Администраторов:** {admins_count}

**Доступные команды:**
• `/admin` - эта панель
• `/users` - список пользователей
• `/add_user <ID>` - добавить пользователя
• `/remove_user <ID>` - удалить пользователя
• `/user_info <ID>` - информация о пользователе
• `/auth_status` - статус авторизации

**Получение ID пользователя:**
• Попросите пользователя написать @userinfobot
• Или найдите ID в логах бота

_Обновлено: {current_time}_"""

    keyboard = [
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users_list")],
        [InlineKeyboardButton("📊 Статус", callback_data="admin_auth_status")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            admin_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except BadRequest as e:
        if "message is not modified" in str(e).lower():
            # Если сообщение не изменилось, просто отвечаем на callback
            logger.info("Admin panel content unchanged, skipping update")
        else:
            raise e


async def admin_users_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback для кнопки списка пользователей"""
    query = update.callback_query
    
    # Получаем пользователей из БД (включая неактивных для администраторов)
    db_users = await database_manager.get_all_users(include_inactive=True)
    
    # Объединяем с пользователями из старого списка для совместимости
    all_user_ids = set()
    
    # Добавляем пользователей из БД
    for db_user in db_users:
        all_user_ids.add(db_user['telegram_id'])
    
    # Добавляем пользователей из старого списка
    for user_id in ALLOWED_USERS:
        all_user_ids.add(user_id)
    
    if not all_user_ids:
        await query.edit_message_text(
            "👥 **Список пользователей пуст**\n\nИспользуйте `/add_user <ID>` для добавления пользователей.",
            parse_mode='Markdown'
        )
        return
    
    users_text = "👥 **Авторизованные пользователи:**\n\n"
    
    # Создаем словарь пользователей из БД для быстрого доступа
    db_users_dict = {user['telegram_id']: user for user in db_users}
    
    active_count = 0
    inactive_count = 0
    
    for i, user_id in enumerate(sorted(all_user_ids), 1):
        # Получаем информацию о пользователе из БД
        db_user = db_users_dict.get(user_id)
        
        if db_user:
            status_parts = []
            
            # Проверяем статус администратора
            if db_user['is_admin']:
                status_parts.append("👑 Админ")
            
            # Проверяем активность
            if db_user['is_active']:
                status_parts.append("✅ Активен")
                active_count += 1
            else:
                status_parts.append("🔴 Неактивен")
                inactive_count += 1
            
            # Добавляем имя пользователя если есть
            if db_user['username']:
                status_parts.append(f"@{db_user['username']}")
            elif db_user['first_name']:
                status_parts.append(f"{db_user['first_name']}")
            
            status_info = " | ".join(status_parts)
        else:
            # Пользователь только в старом списке
            status_info = get_user_info_text(user_id) + " | 🔄 Старый формат"
            active_count += 1
        
        users_text += f"{i}. `{user_id}` - {status_info}\n"
    
    users_text += f"\n**Статистика:**\n"
    users_text += f"• Всего пользователей: {len(all_user_ids)}\n"
    users_text += f"• Активных: {active_count}\n"
    users_text += f"• Неактивных: {inactive_count}\n"
    users_text += f"• В БД: {len(db_users)}\n"
    users_text += f"• В старом списке: {len(ALLOWED_USERS)}"
    
    # Добавляем временную метку
    current_time = datetime.now().strftime("%H:%M:%S")
    users_text += f"\n\n_Обновлено: {current_time}_"
    
    # Добавляем кнопку возврата
    keyboard = [
        [InlineKeyboardButton("🔙 Назад в админ панель", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(users_text, parse_mode='Markdown', reply_markup=reply_markup)
    except BadRequest as e:
        if "message is not modified" in str(e).lower():
            # Если сообщение не изменилось, просто отвечаем на callback
            logger.info("Users list content unchanged, skipping update")
        else:
            raise e


async def admin_auth_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback для кнопки статуса авторизации"""
    query = update.callback_query
    
    # Получаем статистику из базы данных
    db_users = await database_manager.get_all_users(include_inactive=True)
    active_users = [user for user in db_users if user['is_active']]
    admin_users = [user for user in db_users if user['is_admin']]
    
    # Старая система
    old_allowed_count = len(ALLOWED_USERS)
    old_admin_count = len(ADMIN_USERS)
    
    # Добавляем временную метку для принудительного обновления
    current_time = datetime.now().strftime("%H:%M:%S")
    
    status_text = f"""🔐 **Статус системы авторизации**

**Текущие настройки:**
• Авторизация: {'🟢 Включена' if ENABLE_USER_AUTHORIZATION else '🔴 Отключена'}

**База данных (новая система):**
• Всего пользователей в БД: {len(db_users)}
• Активных пользователей: {len(active_users)}
• Администраторов в БД: {len(admin_users)}

**Конфигурация (старая система):**
• В списке ALLOWED_USERS: {old_allowed_count}
• В списке ADMIN_USERS: {old_admin_count}

**Рекомендации:**
• Используйте команды `/add_user` и `/remove_user` для управления пользователями
• Все новые пользователи создаются в базе данных

_Обновлено: {current_time}_"""

    keyboard = [
        [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users_list")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_auth_status")],
        [InlineKeyboardButton("🔙 Назад в админ панель", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(status_text, parse_mode='Markdown', reply_markup=reply_markup)
    except BadRequest as e:
        if "message is not modified" in str(e).lower():
            # Если сообщение не изменилось, просто отвечаем на callback
            logger.info("Auth status content unchanged, skipping update")
        else:
            raise e


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback-кнопок административной панели"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        logger.info(f"Admin callback from user {user_id}: {query.data}")
        
        # Проверяем права администратора через новую систему и fallback на конфиг
        is_admin_user = await database_manager.is_user_admin(user_id)
        is_admin_config = user_id in ADMIN_USERS
        
        if not is_admin_user and not is_admin_config:
            logger.warning(f"Non-admin user {user_id} tried to access admin callback")
            await query.edit_message_text("🚫 Недостаточно прав для доступа к административной панели.")
            return
        
        # Если пользователь админ по конфигу, но не в БД, создаем его
        if is_admin_config and not is_admin_user:
            logger.info(f"Creating admin user {user_id} in database")
            await database_manager.create_user(
                telegram_id=user_id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name,
                last_name=update.effective_user.last_name,
                is_admin=True
            )
        
        callback_data = query.data
        logger.info(f"Processing admin callback: {callback_data}")
        
        if callback_data == "admin_panel":
            # Обновляем главную панель - создаем callback версию
            await admin_panel_callback(update, context)
        elif callback_data == "admin_users_list":
            await admin_users_list_callback(update, context)
        elif callback_data == "admin_auth_status":
            await admin_auth_status_callback(update, context)
        else:
            logger.warning(f"Unknown admin callback: {callback_data}")
            await query.edit_message_text("❌ Неизвестная команда")
            
    except BadRequest as e:
        if "message is not modified" in str(e).lower():
            logger.info("Admin callback: message content unchanged")
        else:
            logger.error(f"BadRequest in admin callback handler: {e}")
            try:
                await query.edit_message_text("❌ Произошла ошибка при обработке команды")
            except:
                pass
    except Exception as e:
        logger.error(f"Error in admin callback handler: {e}")
        try:
            await query.edit_message_text("❌ Произошла ошибка при обработке команды")
        except:
            pass 