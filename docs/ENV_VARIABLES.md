# 🔧 Переменные окружения

## Обязательные переменные

```bash
# Telegram Bot
BOT_TOKEN=your_bot_token_from_botfather

# Anthropic Claude API
ANTHROPIC_API_KEY=your_anthropic_api_key
```

## Базы данных

### PostgreSQL (для пользователей)
```bash
POSTGRES_HOST=localhost          # или postgres (в Docker)
POSTGRES_PORT=5432
POSTGRES_DB=telegram_bot_users
POSTGRES_USER=bot_user
POSTGRES_PASSWORD=bot_password
```

### MongoDB (для контента)
```bash
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=telegram_bot_analytics
```

## RAG и векторная база данных

### Основные настройки
```bash
ENABLE_RAG=true                  # Включить RAG функциональность
ENABLE_VECTOR_DB=true            # Включить векторную БД
VECTOR_DB_PATH=data/chroma_db    # Путь к Chroma DB
```

### Провайдер эмбеддингов

**Вариант 1: Локальные эмбеддинги (по умолчанию)**
```bash
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=intfloat/multilingual-e5-large
```
- ✅ Бесплатно, работает офлайн
- ❌ Требует 2-4 ГБ RAM

**Вариант 2: OpenAI**
```bash
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=your_openai_api_key
```
- ✅ Высокое качество, низкие требования к RAM
- ❌ Платно (~$0.10 за 1М токенов)

**Вариант 3: Cohere**
```bash
EMBEDDING_PROVIDER=cohere
EMBEDDING_MODEL=embed-multilingual-v3.0
COHERE_API_KEY=your_cohere_api_key
```
- ✅ Оптимизировано для поиска
- ❌ Платно

### Параметры семантического поиска
```bash
SEMANTIC_SEARCH_TOP_K=10         # Количество результатов поиска
SEMANTIC_SEARCH_MIN_SCORE=0.5    # Минимальный порог схожести (0-1)
```

### Параметры RAG
```bash
RAG_CONTEXT_SOURCES=5            # Количество источников для контекста
RAG_MAX_CONTEXT_LENGTH=8000      # Максимальная длина контекста
RAG_TEMPERATURE=0.3              # Температура для генерации ответов
```

## TTS и пересказы

```bash
ENABLE_SUMMARY_AGENT=true        # Включить агент пересказа
ENABLE_TTS_AGENT=true            # Включить text-to-speech

TTS_DEFAULT_LANGUAGE=ru          # Язык по умолчанию
TTS_DEFAULT_ENGINE=gtts          # gtts или pyttsx3
TTS_MAX_TEXT_LENGTH=25000        # Максимальная длина для озвучивания
TTS_CLEANUP_HOURS=24             # Через сколько часов удалять аудио
```

## Поведение бота

```bash
DELETE_ORIGINAL_LINKS=true       # Удалять исходные ссылки после анализа
ENABLE_USER_AUTHORIZATION=true   # Включить авторизацию пользователей
```

## Логирование

```bash
LOG_LEVEL=INFO                   # DEBUG, INFO, WARNING, ERROR
LOG_DIR=logs
LOG_FILE=bot.log
```

## Примеры конфигураций

### Минимальная (без RAG)
```bash
BOT_TOKEN=xxx
ANTHROPIC_API_KEY=xxx
ENABLE_RAG=false
ENABLE_VECTOR_DB=false
```

### Стандартная (локальные эмбеддинги)
```bash
BOT_TOKEN=xxx
ANTHROPIC_API_KEY=xxx
ENABLE_RAG=true
ENABLE_VECTOR_DB=true
EMBEDDING_PROVIDER=sentence-transformers
```

### Продвинутая (OpenAI эмбеддинги)
```bash
BOT_TOKEN=xxx
ANTHROPIC_API_KEY=xxx
OPENAI_API_KEY=xxx
ENABLE_RAG=true
ENABLE_VECTOR_DB=true
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
```

### Production
```bash
BOT_TOKEN=xxx
ANTHROPIC_API_KEY=xxx
OPENAI_API_KEY=xxx
ENABLE_RAG=true
ENABLE_VECTOR_DB=true
EMBEDDING_PROVIDER=openai
LOG_LEVEL=WARNING
ENABLE_USER_AUTHORIZATION=true
```

## Как использовать

### Локальный запуск

Создайте `.env` файл в корне проекта:
```bash
cp .env.example .env
nano .env  # или любой редактор
```

Переменные автоматически загрузятся через `os.getenv()`.

### Docker

Переменные указываются в `docker-compose.yml`:
```yaml
environment:
  - BOT_TOKEN=${BOT_TOKEN}
  - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
```

Или создайте `.env` файл - Docker Compose автоматически его подхватит.

### Kubernetes

Используйте ConfigMap и Secrets:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: bot-secrets
data:
  bot-token: <base64>
  anthropic-key: <base64>
```

## Проверка конфигурации

Запустите бота и проверьте логи:
```bash
python main.py
```

Вы должны увидеть:
```
✅ Базы данных инициализированы
✅ Векторная база данных инициализирована  # если ENABLE_VECTOR_DB=true
✅ Бот запущен!
```

## Troubleshooting

### Переменная не загружается

**Проблема**: `BOT_TOKEN` не найден

**Решение**:
1. Проверьте `.env` файл
2. Убедитесь, что нет пробелов: `BOT_TOKEN=xxx` (не `BOT_TOKEN = xxx`)
3. Перезапустите бота

### RAG не работает

**Проблема**: RAG команды не отвечают

**Решение**:
```bash
# Проверьте настройки
ENABLE_RAG=true
ENABLE_VECTOR_DB=true
ANTHROPIC_API_KEY=xxx  # должен быть установлен
```

### Ошибка памяти при локальных эмбеддингах

**Решение**: Переключитесь на облачные
```bash
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=xxx
```

---

**Совет**: Храните `.env` файл в `.gitignore` и никогда не коммитьте API ключи!

