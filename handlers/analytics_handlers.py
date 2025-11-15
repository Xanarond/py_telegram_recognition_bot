"""
Обработчики команд аналитики контента
"""

from telegram import Update
from telegram.ext import ContextTypes

from analyzers.content_analytics import content_analytics
from utils.decorators import require_authorization
from utils.logger import setup_logger

logger = setup_logger(__name__)


def log_user_access(user_id: int, username: str, command: str):
    """Логирует доступ пользователя к команде"""
    logger.info(f"👤 Пользователь {username} (ID: {user_id}) выполнил команду: {command}")


@require_authorization
async def analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /analytics - аналитика интересов"""
    user = update.effective_user
    log_user_access(user.id, user.username, "/analytics")
    
    # Отправляем сообщение о процессе
    processing_msg = await update.message.reply_text(
        "📊 Анализирую вашу базу знаний...",
        parse_mode='Markdown'
    )
    
    try:
        # Получаем аналитику
        analytics = await content_analytics.analyze_user_interests(user.id)
        
        if 'error' in analytics:
            await processing_msg.edit_text(
                f"❌ Ошибка: {analytics['error']}"
            )
            return
        
        # Форматируем результат
        formatted_analytics = format_analytics(analytics)
        
        # Удаляем сообщение о процессе
        await processing_msg.delete()
        
        # Отправляем результат
        await update.message.reply_text(
            formatted_analytics,
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ Аналитика отправлена пользователю {user.id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка аналитики для пользователя {user.id}: {e}")
        await processing_msg.edit_text(
            f"❌ Произошла ошибка: {str(e)}"
        )


@require_authorization
async def trends_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /trends - трендовые темы"""
    user = update.effective_user
    log_user_access(user.id, user.username, "/trends")
    
    # Определяем период
    days = 30
    if context.args and context.args[0].isdigit():
        days = int(context.args[0])
        days = min(days, 365)  # Максимум год
    
    # Отправляем сообщение о процессе
    processing_msg = await update.message.reply_text(
        f"📈 Анализирую тренды за последние {days} дней...",
        parse_mode='Markdown'
    )
    
    try:
        # Получаем тренды
        trends = await content_analytics.get_trending_topics(user.id, days)
        
        if 'error' in trends:
            await processing_msg.edit_text(
                f"❌ Ошибка: {trends['error']}"
            )
            return
        
        # Форматируем результат
        formatted_trends = format_trends(trends)
        
        # Удаляем сообщение о процессе
        await processing_msg.delete()
        
        # Отправляем результат
        await update.message.reply_text(
            formatted_trends,
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ Тренды отправлены пользователю {user.id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка трендов для пользователя {user.id}: {e}")
        await processing_msg.edit_text(
            f"❌ Произошла ошибка: {str(e)}"
        )


@require_authorization
async def clusters_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /clusters - кластеризация контента"""
    user = update.effective_user
    log_user_access(user.id, user.username, "/clusters")
    
    # Отправляем сообщение о процессе
    processing_msg = await update.message.reply_text(
        "🗂️ Кластеризую ваш контент...",
        parse_mode='Markdown'
    )
    
    try:
        # Получаем кластеры
        clusters = await content_analytics.cluster_content(user.id, num_clusters=5)
        
        if 'error' in clusters:
            await processing_msg.edit_text(
                f"❌ Ошибка: {clusters['error']}"
            )
            return
        
        # Форматируем результат
        formatted_clusters = format_clusters(clusters)
        
        # Удаляем сообщение о процессе
        await processing_msg.delete()
        
        # Отправляем результат
        await update.message.reply_text(
            formatted_clusters,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        logger.info(f"✅ Кластеры отправлены пользователю {user.id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка кластеризации для пользователя {user.id}: {e}")
        await processing_msg.edit_text(
            f"❌ Произошла ошибка: {str(e)}"
        )


def format_analytics(analytics: dict) -> str:
    """Форматирует аналитику для отображения"""
    if analytics.get('total_sources', 0) == 0:
        return "📊 **Аналитика интересов**\n\n❌ Недостаточно данных для анализа"
    
    parts = [
        "📊 **Аналитика ваших интересов**\n",
        f"📚 **Всего источников:** {analytics['total_sources']}\n"
    ]
    
    # Топ категории
    top_categories = analytics.get('top_categories', {})
    if top_categories:
        parts.append("\n🎯 **Топ категории:**\n")
        for category, count in list(top_categories.items())[:5]:
            percentage = (count / analytics['total_sources']) * 100
            parts.append(f"• {category}: {count} ({percentage:.1f}%)\n")
    
    # Топ теги
    top_tags = analytics.get('top_tags', {})
    if top_tags:
        parts.append("\n🏷️ **Популярные теги:**\n")
        tags_list = [f"#{tag}" for tag in list(top_tags.keys())[:10]]
        parts.append(", ".join(tags_list) + "\n")
    
    # Разнообразие
    diversity_score = analytics.get('diversity_score', 0)
    diversity_emoji = "🌈" if diversity_score > 0.7 else "📊" if diversity_score > 0.4 else "📌"
    parts.append(f"\n{diversity_emoji} **Разнообразие интересов:** {diversity_score:.0%}\n")
    
    # Прогресс чтения
    reading_progress = analytics.get('reading_progress', {})
    if reading_progress:
        parts.append(f"\n📖 **Прогресс чтения:**\n")
        parts.append(f"• Прочитано: {reading_progress.get('read', 0)} из {reading_progress.get('total', 0)}\n")
        parts.append(f"• Процент: {reading_progress.get('read_percentage', 0):.1f}%\n")
        
        if reading_progress.get('rated', 0) > 0:
            parts.append(f"• Средний рейтинг: ⭐ {reading_progress.get('avg_rating', 0):.1f}/5\n")
    
    # Топ домены
    top_domains = analytics.get('top_domains', {})
    if top_domains:
        parts.append("\n🌐 **Любимые источники:**\n")
        for domain, count in list(top_domains.items())[:3]:
            parts.append(f"• {domain}: {count}\n")
    
    return "".join(parts)


def format_trends(trends: dict) -> str:
    """Форматирует тренды для отображения"""
    if trends.get('sources_count', 0) == 0:
        return f"📈 **Тренды за {trends.get('period_days', 30)} дней**\n\n❌ Нет данных за указанный период"
    
    parts = [
        f"📈 **Тренды за последние {trends['period_days']} дней**\n",
        f"📚 **Сохранено источников:** {trends['sources_count']}\n",
        f"📊 **Средняя активность:** {trends.get('growth_rate', 0):.1f} источников/день\n"
    ]
    
    # Трендовые категории
    trending_categories = trends.get('trending_categories', {})
    if trending_categories:
        parts.append("\n🔥 **Трендовые категории:**\n")
        for category, count in list(trending_categories.items())[:5]:
            parts.append(f"• {category}: {count}\n")
    
    # Трендовые теги
    trending_tags = trends.get('trending_tags', {})
    if trending_tags:
        parts.append("\n🏷️ **Горячие темы:**\n")
        tags_list = [f"#{tag}" for tag in list(trending_tags.keys())[:8]]
        parts.append(", ".join(tags_list) + "\n")
    
    return "".join(parts)


def format_clusters(clusters: dict) -> str:
    """Форматирует кластеры для отображения"""
    if clusters.get('num_clusters', 0) == 0:
        return "🗂️ **Кластеризация контента**\n\n❌ Недостаточно данных для кластеризации"
    
    parts = [
        "🗂️ **Кластеры вашего контента**\n",
        f"📊 **Всего источников:** {clusters['total_sources']}\n",
        f"🎯 **Найдено кластеров:** {clusters['num_clusters']}\n\n"
    ]
    
    for i, cluster in enumerate(clusters.get('clusters', []), 1):
        parts.append(f"**{i}. {cluster['name']}** ({cluster['count']} источников)\n")
        
        # Топ теги кластера
        top_tags = cluster.get('top_tags', {})
        if top_tags:
            tags_list = [f"#{tag}" for tag in list(top_tags.keys())[:3]]
            parts.append(f"   Теги: {', '.join(tags_list)}\n")
        
        # Сложность
        complexity = cluster.get('dominant_complexity', 'средний')
        parts.append(f"   Сложность: {complexity}\n")
        
        parts.append("\n")
    
    return "".join(parts)

