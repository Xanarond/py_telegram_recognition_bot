# Telegram Bot для анализа контента с ИИ

Модульный Telegram бот для анализа веб-контента с помощью Claude 3.5 Sonnet.

## 🏗️ Архитектура проекта

```
telegram_bot_analytic/
├── main.py                     # Главный файл запуска бота
├── config.py                   # Конфигурация и настройки
│
├── analyzers/                  # Модули анализа контента
│   ├── __init__.py
│   └── content_analyzer.py     # ИИ анализатор контента
│
├── formatters/                 # Модули форматирования сообщений
│   ├── __init__.py
│   └── telegram_formatter.py  # Форматтер для Telegram
│
├── generators/                 # Модули генерации файлов
│   ├── __init__.py
│   └── pdf_generator.py       # Генератор PDF отчетов
│
├── handlers/                   # Обработчики команд и сообщений
│   ├── __init__.py
│   └── bot_handlers.py        # Обработчики Telegram бота
│
├── storage/                    # Модули управления данными
│   ├── __init__.py
│   └── stats_manager.py       # Менеджер статистики
│
├── utils/                      # Утилиты
│   ├── __init__.py
│   └── logger.py              # Настройка логирования
│
├── data/                       # Данные и временные файлы
│   ├── temp/                  # Временные файлы
│   └── user_stats.json        # Статистика пользователей
│
├── logs/                       # Логи
│   └── bot.log
│
├── requirements.txt            # Зависимости Python
├── Dockerfile                  # Docker конфигурация
├── docker-compose.yml         # Docker Compose
```

## 🚀 Быстрый старт

### Локальный запуск

1. **Установка зависимостей:**
```bash
pip install -r requirements.txt
```

2. **Настройка конфигурации:**
Отредактируйте `config.py` и укажите ваши токены:
```python
BOT_TOKEN = "your_telegram_bot_token"
ANTHROPIC_API_KEY = "your_anthropic_api_key"
```

3. **Запуск бота:**
```bash
python main.py
```

### Docker запуск

```bash
docker-compose up -d
```

## 📋 Модули и их назначение

### 🔧 config.py
Центральный файл конфигурации содержит:
- Токены и API ключи
- Настройки бота и логирования
- Пути к файлам и директориям
- Поддерживаемые домены
- Настройки ИИ анализа

### 🤖 analyzers/content_analyzer.py
Класс `AIContentAnalyzer` отвечает за:
- Получение контента с веб-страниц
- Извлечение текста из HTML
- Анализ контента с помощью Claude 3.5 Sonnet
- Проверку поддерживаемых доменов

### 💬 formatters/telegram_formatter.py
Класс `TelegramFormatter` форматирует:
- Сообщения с результатами анализа
- Таблицы статистики
- Списки источников с пагинацией

### 📄 generators/pdf_generator.py
Класс `PDFGenerator` создает:
- PDF отчеты с таблицами источников
- Текстовые файлы как fallback
- Поддержка кириллицы в PDF

### 🎮 handlers/bot_handlers.py
Обработчики команд:
- `/start` - приветствие
- `/help` - справка
- `/stats` - статистика анализов
- `/sources` - таблица источников
- `/export` - экспорт в PDF
- `/clear` - очистка статистики
- Обработка ссылок и callback кнопок

### 💾 storage/stats_manager.py
Класс `StatsManager` управляет:
- Загрузкой и сохранением статистики
- Обновлением данных пользователей
- Вычислением средних значений

### 📝 utils/logger.py
Настройка логирования:
- Файловые и консольные логи
- Поддержка UTF-8
- Настраиваемый уровень логирования

## ⚙️ Конфигурация

Основные настройки в `config.py`:

```python
# Токены
BOT_TOKEN = "your_bot_token"
ANTHROPIC_API_KEY = "your_api_key"

# Поведение бота
DELETE_ORIGINAL_LINKS = True  # Удалять исходные ссылки

# Настройки ИИ
AI_MODEL = "claude-3-5-sonnet-20241022"
AI_MAX_TOKENS = 1500
AI_TEMPERATURE = 0.3

# Пагинация
SOURCES_PER_PAGE = 5
```

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
- Краткое резюме
- Ключевые моменты
- Категоризация
- Оценка сложности и релевантности
- Рекомендуемые действия
- Теги

### Статистика
- Общие показатели
- Распределение по приоритету
- Анализ по сложности
- Популярные категории и домены

### Экспорт данных
- PDF отчеты с таблицами
- Поддержка кириллицы
- Автоматическая очистка временных файлов

## 🔄 Миграция с монолитной версии

Старый файл `telegram_bot.py` сохранен для справки. Новая модульная архитектура:

1. **Разделена по функциональности** - каждый модуль отвечает за свою область
2. **Легко тестируется** - модули можно тестировать независимо
3. **Масштабируется** - легко добавлять новые анализаторы и форматтеры
4. **Поддерживается** - четкое разделение ответственности

## 🛠️ Разработка

### Добавление нового анализатора
1. Создайте класс в `analyzers/`
2. Реализуйте интерфейс анализа
3. Добавьте в `handlers/bot_handlers.py`

### Добавление нового форматтера
1. Создайте класс в `formatters/`
2. Реализуйте методы форматирования
3. Используйте в обработчиках

### Добавление новой команды
1. Создайте функцию в `handlers/bot_handlers.py`
2. Добавьте обработчик в `main.py`

## 📦 Зависимости

- `python-telegram-bot` - Telegram Bot API
- `anthropic` - Claude API
- `beautifulsoup4` - Парсинг HTML
- `requests` - HTTP запросы
- `reportlab` - Генерация PDF

## 🐳 Docker

Проект поддерживает контейнеризацию:

### Быстрый запуск с Docker Compose:
```bash
docker-compose up -d
```

### Ручная сборка и запуск:
```bash
# Сборка образа
docker build -t telegram-content-analyzer .

# Запуск контейнера
docker run -d \
  --name telegram-bot \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  telegram-content-analyzer
```

### Docker Compose конфигурация:
```yaml
# docker-compose.yml
version: '3.8'
services:
  telegram-bot:
    build: .
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
```


## 📄 Лицензия

MIT License - см. файл LICENSE для деталей. 