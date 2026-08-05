import os
from typing import Dict

# Токены и API ключи
BOT_TOKEN = os.getenv("BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Настройки бота
DELETE_ORIGINAL_LINKS = True  # Удалять исходные сообщения со ссылками после анализа

# Настройки авторизации
ENABLE_USER_AUTHORIZATION = True  # Включить проверку авторизации пользователей
ALLOWED_USERS = [
    # Добавьте ID пользователей, которым разрешено использовать бота
    # Получить ID можно через @userinfobot или в логах бота
    # Примеры:
    # 123456789,    # ID пользователя 1
    # 987654321,    # ID пользователя 2
    425447101
]

# ID администраторов (могут управлять списком пользователей)
ADMIN_USERS = [
    # Добавьте ID администраторов
    # Примеры:
    # 123456789,    # ID администратора
    425447101
]

# Сообщение для неавторизованных пользователей
UNAUTHORIZED_MESSAGE = """🚫 **Доступ запрещен**

К сожалению, вы не авторизованы для использования этого бота.

Для получения доступа обратитесь к администратору."""

# Настройки логирования
LOG_LEVEL = "INFO"
LOG_DIR = "logs"
LOG_FILE = "bot.log"

# Настройки хранения данных
DATA_DIR = "data"
TEMP_DIR = "data/temp"
STATS_FILE = "data/user_stats.json"

# Настройки PDF
PDF_METHOD = "reportlab"  # "weasyprint" или "reportlab"

# Настройки пагинации
SOURCES_PER_PAGE = 10
MAX_SOURCES_IN_STATS = 10

# Настройки анализа контента
MAX_CONTENT_LENGTH = 15000
AI_MODEL = "claude-haiku-4-5-20251001"
AI_MAX_TOKENS = 7500  # Безопасное значение для Claude 3.7 Sonnet (максимум 8000)
AI_TEMPERATURE = 0.3

# Настройки пересказа и TTS
ENABLE_SUMMARY_AGENT = True  # Включить агент пересказа
ENABLE_TTS_AGENT = True      # Включить text-to-speech агент

# Настройки TTS
TTS_DEFAULT_LANGUAGE = 'ru'
TTS_DEFAULT_ENGINE = 'gtts'  # 'gtts' или 'pyttsx3'
TTS_MAX_TEXT_LENGTH = 25000   # Максимальная длина текста для озвучивания
TTS_CLEANUP_HOURS = 24       # Через сколько часов удалять временные аудиофайлы

# Настройки баз данных
# MongoDB настройки (для синопсисов и контента)
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://localhost:27017')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'telegram_bot_analytics')

# PostgreSQL настройки (для пользователей и авторизации)
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'telegram_bot_users')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'bot_user')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'bot_password')

# Строка подключения к PostgreSQL
POSTGRES_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Настройки миграции данных
ENABLE_DATA_MIGRATION = True  # Включить миграцию из JSON в БД при первом запуске

# Настройки RAG и векторной базы данных
ENABLE_RAG = True  # Включить RAG функциональность
ENABLE_VECTOR_DB = True  # Включить векторную базу данных

# Векторная база данных
VECTOR_DB_PATH = "data/chroma_db"  # Путь к Chroma DB
VECTOR_DB_PROVIDER = "chroma"  # Провайдер векторной БД (chroma, qdrant)
CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = os.getenv("CHROMA_PORT", "8000")

# Настройки эмбеддингов
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")  # openai, sentence-transformers, cohere
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")  # Модель для эмбеддингов
OPENAI_EMBEDDING_API_KEY = os.getenv("OPENAI_API_KEY")  # API ключ для OpenAI embeddings
COHERE_API_KEY = os.getenv("COHERE_API_KEY")  # API ключ для Cohere

# Настройки семантического поиска
SEMANTIC_SEARCH_TOP_K = 10  # Количество результатов семантического поиска
SEMANTIC_SEARCH_MIN_SCORE = 0.5  # Минимальный порог схожести (0-1)

# Настройки RAG
RAG_CONTEXT_SOURCES = 5  # Количество источников для контекста RAG
RAG_MAX_CONTEXT_LENGTH = 8000  # Максимальная длина контекста для RAG
RAG_TEMPERATURE = 0.3  # Температура для генерации ответов RAG

# Поддерживаемые домены и их эмодзи
SUPPORTED_DOMAINS: Dict[str, str] = {
    'habr.com': '🔧',
    'youtube.com': '📺',
    'youtu.be': '📺',
    'arxiv.org': '🔬',
    'github.com': '💻',
    'medium.com': '📝',
    'dev.to': '👨‍💻',
    'stackoverflow.com': '❓',
    'docs.python.org': '📚',
    'reactjs.org': '⚛️'
}

# HTTP настройки
HTTP_TIMEOUT = 10
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# Селекторы для извлечения контента
CONTENT_SELECTORS = [
    'article', 'main', '.post-content', '.article-content',
    '.content', '#content', '.post-body', '.entry-content'
]

# Эмодзи для приоритетов
PRIORITY_EMOJIS = {
    'high': '🔴',
    'medium': '🟡',
    'low': '🟢'
}

# Эмодзи для статуса прочтения
READ_STATUS_EMOJIS = {
    'read': '✅',
    'unread': '📖'
}

# Настройки фильтрации по статусу чтения
READ_STATUS_FILTERS = ['all', 'read', 'unread']

# Пути к шрифтам для PDF
FONT_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans.ttf',
    '/System/Library/Fonts/Arial Unicode.ttf'  # macOS fallback
]

def ensure_directories():
    """Создает необходимые директории"""
    directories = [LOG_DIR, DATA_DIR, TEMP_DIR, VECTOR_DB_PATH]
    for directory in directories:
        os.makedirs(directory, exist_ok=True) 