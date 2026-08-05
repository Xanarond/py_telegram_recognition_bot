
# Telegram Bot для анализа контента с ИИ и RAG

Модульный Telegram-бот для анализа веб-контента с помощью Claude, с семантическим поиском (RAG), пересказами, TTS-озвучиванием и персональной аналитикой.

## 🏗️ Архитектура проекта

```
telegram_bot_analytic/
├── main.py                        # Главный файл запуска бота
├── config.py                      # Конфигурация и настройки
│
├── analyzers/                     # Модули анализа контента и ИИ-агенты
│   ├── content_analyzer.py        # ИИ анализатор контента (Claude)
│   ├── content_analytics.py       # Аналитика интересов и трендов
│   ├── summary_agent.py           # Агент кратких/подробных пересказов
│   ├── rag_agent.py                # RAG-агент (поиск + генерация ответов)
│   ├── embedding_generator.py     # Генерация эмбеддингов (OpenAI/др.)
│   └── vectorization_service.py   # Векторизация и хранение в Chroma DB
│
├── formatters/                    # Модули форматирования сообщений
│   ├── telegram_formatter.py      # Форматтер основных сообщений
│   ├── summary_formatter.py       # Форматирование пересказов
│   └── rag_formatter.py           # Форматирование RAG-ответов
│
├── generators/                    # Модули генерации файлов
│   ├── pdf_generator.py           # Генератор PDF отчетов
│   └── tts_generator.py           # Text-to-Speech генератор аудио
│
├── handlers/                      # Обработчики команд и сообщений
│   ├── bot_handlers.py            # Основные обработчики (анализ, статистика)
│   ├── rag_handlers.py            # Обработчики RAG-команд
│   ├── analytics_handlers.py      # Обработчики аналитики
│   └── admin_handlers.py          # Обработчики администрирования
│
├── storage/                       # Модули управления данными
│   ├── database_manager.py        # Единая точка инициализации БД
│   ├── mongodb_manager.py         # MongoDB (контент, синопсисы, рейтинги)
│   ├── postgres_manager.py        # PostgreSQL (пользователи, авторизация)
│   ├── postgres_models.py         # ORM-модели PostgreSQL
│   ├── vector_manager.py          # Работа с Chroma DB (векторное хранилище)
│   ├── migration_manager.py       # Миграция данных
│   └── stats_manager.py           # Легаси-менеджер статистики (JSON)
│
├── utils/                         # Утилиты
│   ├── logger.py                  # Настройка логирования
│   ├── auth.py                    # Авторизация пользователей
│   ├── decorators.py              # Декораторы (проверка доступа и т.д.)
│   └── text_utils.py              # Вспомогательные функции для текста
│
├── scripts/                       # Служебные скрипты
│   ├── migrate_existing_content.py
│   └── add_rating_field.py
│
├── docs/                          # Документация проекта
│
├── data/                          # Данные и временные файлы
├── logs/                          # Логи
├── mongodb_data/                  # Данные MongoDB (volume)
├── postgres_data/                 # Данные PostgreSQL (volume)
├── chroma_data/                   # Данные Chroma DB (volume)
│
├── requirements.txt               # Основные зависимости Python
├── requirements-extras.txt        # Дополнительные зависимости (локальные эмбеддинги и т.д.)
├── Dockerfile                     # Docker конфигурация
├── docker-compose.yml             # Docker Compose (dev)
└── docker-compose.prod.yml        # Docker Compose (production)
```

## 🚀 Быстрый старт

### Локальный запуск

1. **Установка зависимостей:**
```bash
pip install -r requirements.txt
# для локальных эмбеддингов (sentence-transformers) и расширенной аналитики:
pip install -r requirements-extras.txt
```

2. **Настройка конфигурации:**
Скопируйте `.env.example` в `.env` и укажите переменные:
```bash
cp .env.example .env
```
```bash
BOT_TOKEN=your_telegram_bot_token
ANTHROPIC_API_KEY=your_anthropic_api_key
```
Подробный список переменных окружения — в [docs/ENV_VARIABLES.md](docs/ENV_VARIABLES.md).

3. **Запуск бота:**
```bash
python main.py
```

### Docker запуск

```bash
docker-compose up -d
```

Поднимает PostgreSQL, MongoDB, Chroma DB, сам бот и Mongo Express (UI для MongoDB). Подробности — в [docs/DOCKER_SETUP.md](docs/DOCKER_SETUP.md).

## 📋 Модули и их назначение

### 🔧 config.py
Центральный файл конфигурации содержит:
- Токены и API ключи
- Настройки авторизации пользователей
- Параметры БД (PostgreSQL, MongoDB), векторной БД (Chroma) и эмбеддингов
- Параметры RAG, пересказов и TTS
- Поддерживаемые домены и настройки ИИ-анализа

### 🤖 analyzers/content_analyzer.py
Класс `AIContentAnalyzer`:
- Получение контента с веб-страниц
- Извлечение текста из HTML
- Анализ контента с помощью Claude
- Проверка поддерживаемых доменов

### 📄 analyzers/summary_agent.py
Класс `SummaryAgent`:
- Краткий и подробный пересказ статьи
- Пересказ напрямую по URL (свежий контент со страницы)
- Оценка качества пересказа

### 🔍 analyzers/rag_agent.py, embedding_generator.py, vectorization_service.py
RAG-конвейер:
- Векторизация сохранённых материалов (эмбеддинги + Chroma DB)
- Семантический поиск по базе знаний
- Генерация ответов с цитированием источников

### 📊 analyzers/content_analytics.py
- Персональная аналитика интересов
- Тренды по периодам
- Кластеризация по темам

### 💬 formatters/
- `telegram_formatter.py` — сообщения с анализом, статистика, списки источников
- `summary_formatter.py` — форматирование пересказов
- `rag_formatter.py` — форматирование RAG-ответов

### 📄 generators/
- `pdf_generator.py` — PDF отчеты с таблицами источников, fallback в текст
- `tts_generator.py` — озвучивание пересказов (gTTS / pyttsx3)

### 🎮 handlers/
- `bot_handlers.py` — `/start`, `/help`, `/stats`, `/sources`, `/export`, `/clear`, `/clear_source`, обработка ссылок и callback-кнопок
- `rag_handlers.py` — `/search`, `/ask`, `/compare`, `/synthesize`, `/similar`, `/rag_help`
- `analytics_handlers.py` — `/analytics`, `/trends`, `/clusters`
- `admin_handlers.py` — `/admin`, `/users`, `/add_user`, `/remove_user`, `/user_info`, `/auth_status`

### 💾 storage/
- `database_manager.py` — единая инициализация всех БД при старте
- `mongodb_manager.py` — синопсисы, контент, рейтинги статей
- `postgres_manager.py` / `postgres_models.py` — пользователи и авторизация
- `vector_manager.py` — Chroma DB (client или embedded режим)
- `migration_manager.py` — миграция легаси-данных из JSON в БД

### 📝 utils/
- `logger.py` — файловые и консольные логи, UTF-8, настраиваемый уровень
- `auth.py`, `decorators.py` — авторизация и ограничение доступа к командам

## ⚙️ Конфигурация

Основные настройки в `config.py` (переопределяются через `.env` / переменные окружения):

```python
# Токены
BOT_TOKEN = os.getenv("BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Поведение бота
DELETE_ORIGINAL_LINKS = True         # Удалять исходные ссылки
ENABLE_USER_AUTHORIZATION = True     # Проверка авторизации пользователей

# Настройки ИИ
AI_MODEL = "claude-haiku-4-5-20251001"
AI_MAX_TOKENS = 7500
AI_TEMPERATURE = 0.3

# RAG и векторная БД
ENABLE_RAG = True
ENABLE_VECTOR_DB = True
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")

# Пересказы и TTS
ENABLE_SUMMARY_AGENT = True
ENABLE_TTS_AGENT = True
TTS_MAX_TEXT_LENGTH = 25000

# Пагинация
SOURCES_PER_PAGE = 10
```

Полный и актуальный список переменных окружения — [docs/ENV_VARIABLES.md](docs/ENV_VARIABLES.md).

## 🌐 Поддерживаемые сайты

- Habr.com 🔧
- YouTube 📺
- GitHub 💻
- Medium 📝
- Dev.to 👨‍💻
- ArXiv 🔬
- Stack Overflow ❓
- Python Docs 📚
- React.js ⚛️

## 📊 Функции

### Анализ контента
- Краткое резюме, ключевые моменты, категоризация
- Оценка сложности и релевантности
- Рекомендуемые действия, теги

### Пересказы и озвучивание
- Краткий и подробный пересказ (в т.ч. по свежему контенту URL)
- Озвучивание пересказа (gTTS / pyttsx3)

### RAG и семантический поиск
- `/search` — семантический поиск по смыслу
- `/ask` — вопросы к базе знаний с цитированием источников
- `/compare`, `/synthesize`, `/similar` — сравнение, синтез, поиск похожих материалов

### Аналитика
- Общие показатели, распределение по приоритету и сложности
- Тренды за период, кластеризация по темам
- Рейтинг статей (1–5 звёзд) и статистика по рейтингам

### Экспорт данных
- PDF отчеты с таблицами, поддержка кириллицы
- Автоматическая очистка временных файлов

## 🐳 Docker

Проект поддерживает контейнеризацию через `docker-compose.yml` (dev) и `docker-compose.prod.yml` (production). Сервисы: PostgreSQL, MongoDB, Chroma DB, сам бот, Mongo Express.

### Быстрый запуск:
```bash
docker-compose up -d
```

Подробности, лимиты ресурсов, backup/restore и troubleshooting — в [docs/DOCKER_SETUP.md](docs/DOCKER_SETUP.md) и [docs/CHROMA_ARCHITECTURE.md](docs/CHROMA_ARCHITECTURE.md).

## 📦 Управление зависимостями

Зависимости разделены на базовые (`requirements.txt`) и дополнительные (`requirements-extras.txt` — локальные эмбеддинги, расширенный TTS, ML-аналитика). Подробное сравнение конфигураций — в [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md).

## 📚 Дополнительная документация

Вся подробная документация находится в каталоге [`docs/`](docs/):

- [ENV_VARIABLES.md](docs/ENV_VARIABLES.md) — переменные окружения
- [DEPENDENCIES.md](docs/DEPENDENCIES.md) — управление зависимостями
- [DOCKER_SETUP.md](docs/DOCKER_SETUP.md) — Docker и RAG-инфраструктура
- [CHROMA_ARCHITECTURE.md](docs/CHROMA_ARCHITECTURE.md) — архитектура векторной БД
- [RAG_IMPLEMENTATION.md](docs/RAG_IMPLEMENTATION.md) — реализация RAG-конвейера
- [RAG_QUICK_START.md](docs/RAG_QUICK_START.md) — быстрый старт с RAG-командами
- [RATING_FEATURE.md](docs/RATING_FEATURE.md) — функция рейтинга статей
- [RATING_QUICK_START.md](docs/RATING_QUICK_START.md) — быстрый старт с рейтингами
- [SUMMARY_TTS_README.md](docs/SUMMARY_TTS_README.md) — пересказы и TTS
- [BOT_ARTICLE.md](docs/BOT_ARTICLE.md) — подробная статья об архитектуре и мотивации проекта

## 🛠️ Разработка

### Добавление нового анализатора
1. Создайте класс в `analyzers/`
2. Реализуйте интерфейс анализа
3. Подключите в соответствующем `handlers/*.py`

### Добавление нового форматтера
1. Создайте класс в `formatters/`
2. Реализуйте методы форматирования
3. Используйте в обработчиках

### Добавление новой команды
1. Создайте функцию-обработчик в подходящем `handlers/*.py`
2. Зарегистрируйте `CommandHandler` в `main.py`

## 📄 Лицензия

MIT License - см. файл LICENSE для деталей.
