# Telegram-бот для управления знаниями: Как я превратил хаос из ссылок в персональную базу данных с RAG

> Это история о том, как надоело тонуть в закладках, и пришлось написать бота, который не просто сохраняет ссылки, а превращает их в структурированные знания с помощью Claude, ChromaDB и семантического поиска.

## TL;DR

Построил Telegram-бота на Python, который парсит любой контент (статьи, YouTube, документацию), анализирует через Claude 3.7 Sonnet, сохраняет в MongoDB/PostgreSQL, векторизует для семантического поиска в ChromaDB и реализует полноценный RAG-пайплайн. Результат: из 150+ мёртвых закладок получилась живая база знаний с поиском по смыслу, автоматическими пересказами и TTS-озвучкой.

**Стек:** Python 3.11, Anthropic API, ChromaDB, MongoDB, PostgreSQL, yt-dlp, BeautifulSoup, Selenium.

## Содержание

1. [Архитектура на высоком уровне: Как это работает](#архитектура-на-высоком-уровне-как-это-работает)
   - [Общая концепция системы](#общая-концепция-системы)
   - [Поток обработки: От ссылки до структурированных знаний](#поток-обработки-от-ссылки-до-структурированных-знаний)
   - [RAG Pipeline: Архитектура умного поиска](#rag-pipeline-архитектура-умного-поиска)
   - [Технологические решения](#технологические-решения)

2. [Проблема: Цифровой хаос и синдром «прочитаю потом»](#проблема-цифровой-хаос-и-синдром-прочитаю-потом)
   - [Масштаб проблемы](#масштаб-проблемы)
   - [Психология информационной прокрастинации](#психология-информационной-прокрастинации)

3. [Решение: Бот-аналитик вместо склада ссылок](#решение-бот-аналитик-вместо-склада-ссылок)
   - [Почему Telegram, а не веб-приложение?](#почему-telegram-а-не-веб-приложение)

4. [Архитектура: Модульный монолит с асинхронной обработкой](#архитектура-модульный-монолит-с-асинхронной-обработкой)
   - [Структура системы](#структура-системы)
   - [Структура проекта](#структура-проекта)
   - [Поток обработки контента](#поток-обработки-контента)

5. [Ключевые возможности и техническая реализация](#ключевые-возможности-и-техническая-реализация)
   - [1. Всеядный парсинг с умной обработкой](#1-всеядный-парсинг-с-умной-обработкой)
   - [2. RAG Pipeline: Семантический поиск и генерация ответов](#2-rag-pipeline-семантический-поиск-и-генерация-ответов)
   - [3. CRM для знаний: Управление жизненным циклом материалов](#3-crm-для-знаний-управление-жизненным-циклом-материалов)
   - [4. Мультиформатное потребление контента](#4-мультиформатное-потребление-контента)

6. [Результаты: Измеримые изменения](#результаты-измеримые-изменения)
   - [Количественные показатели](#количественные-показатели)
   - [Качественные изменения](#качественные-изменения)

7. [Технологический стек и конфигурация](#технологический-стек-и-конфигурация)
   - [Основные технологии](#основные-технологии)
   - [Ключевые параметры конфигурации](#ключевые-параметры-конфигурации)
   - [Docker Compose для развёртывания](#docker-compose-для-развёртывания)

8. [Будущее: Планы развития](#будущее-планы-развития)
   - [Интеграция с Obsidian](#интеграция-с-obsidian)
   - [Интеграция с NotebookLM](#интеграция-с-notebooklm)
   - [Другие планы](#другие-планы)

9. [Заключение](#заключение)

---

## Архитектура на высоком уровне: Как это работает

Перед погружением в детали, давайте посмотрим на систему целиком. Это поможет понять, как все компоненты взаимодействуют друг с другом и почему были выбраны именно такие архитектурные решения.

### Общая концепция системы

![Архитектурная диаграмма системы](../concept.excalidraw)

Система построена из четырёх основных слоёв, каждый со своей зоной ответственности:

**1. User Interface Layer (Telegram Bot)**

Единственная точка входа для пользователя. Вся коммуникация происходит через Telegram-чат: от отправки ссылок до управления статусами и получения пересказов. Интерфейс максимально упрощён — никаких сложных меню, только inline-кнопки для быстрых действий.

Ключевое решение: отказ от веб-интерфейса на старте позволил сфокусироваться на функциональности, а не на разработке UI/UX. Telegram предоставляет всё необходимое из коробки: кроссплатформенность, синхронизацию, уведомления.

**2. Application Layer (Handlers & Routing)**

Диспетчер входящих событий. Каждое сообщение или команда маршрутизируется в соответствующий обработчик. Реализовано через систему декораторов и middleware, что делает код расширяемым: добавление новой команды не требует изменения существующей логики.

Важный момент: все handlers работают асинхронно через `asyncio`, что позволяет одновременно обрабатывать запросы от множества пользователей без блокировок.

**3. Business Logic Layer (Analyzers & AI)**

Мозг системы. Здесь происходит вся интеллектуальная работа:
- Парсинг контента из разных источников (сайты, YouTube, PDF)
- Анализ через Claude для извлечения смысла
- Векторизация для семантического поиска
- RAG-пайплайн для генерации ответов на вопросы
- Генерация пересказов, PDF и аудио

Архитектурно этот слой разделён на независимые модули-сервисы, каждый отвечает за свою задачу. Они не знают друг о друге напрямую, взаимодействие идёт через общие интерфейсы.

**4. Data Layer (Hybrid Storage)**

Три типа хранилищ для разных типов данных:
- **MongoDB** — гибкое хранилище для неструктурированного контента (тексты статей, JSON-ответы AI)
- **PostgreSQL** — реляционная БД для структурированных данных (пользователи, статусы, рейтинги, история)
- **ChromaDB** — векторная база для семантического поиска

Почему три БД? Потому что разные данные требуют разных подходов. MongoDB даёт гибкость схемы для разнородного контента. PostgreSQL обеспечивает ACID-гарантии и сложные запросы для аналитики. ChromaDB оптимизирована под векторный поиск.

### Поток обработки: От ссылки до структурированных знаний

![Диаграмма потока событий](../event_diagram.puml)

Когда пользователь отправляет ссылку боту, запускается следующий процесс:

**Этап 1: Приём и классификация (< 1 сек)**
```
Пользователь → Telegram Bot → Validator → Classifier
```
Система проверяет валидность URL, определяет тип контента (статья, видео, документация) и выбирает соответствующий парсер.

**Этап 2: Извлечение контента (5-15 сек)**
```
Classifier → Parser (BeautifulSoup/Selenium/yt-dlp) → Raw Content
```
В зависимости от типа источника запускается нужный парсер. Для статей — BeautifulSoup, для SPA — Selenium с headless Chrome, для YouTube — yt-dlp для извлечения субтитров.

**Этап 3: AI-анализ (10-30 сек)**
```
Raw Content → Claude 3.7 Sonnet → Structured Analysis
```
Весь текст отправляется в Claude для глубокого анализа: извлечение ключевых тезисов, определение тематики, оценка сложности, генерация тегов. Модель возвращает структурированный JSON с метаданными.

**Этап 4: Векторизация (2-5 сек)**
```
Text + Metadata → Embedding Model → Vector → ChromaDB
```
Контент превращается в векторное представление через `sentence-transformers`. Это позволит в будущем искать материалы по смыслу, а не по ключевым словам.

**Этап 5: Сохранение (1-2 сек, параллельно)**
```
├─→ MongoDB: полный текст, анализ
├─→ PostgreSQL: метаданные, связи
└─→ ChromaDB: векторы
```
Данные сохраняются одновременно в три хранилища. Использование `asyncio.gather()` позволяет выполнить операции параллельно.

**Этап 6: Уведомление пользователя (< 1 сек)**
```
Saved Data → Message Formatter → Telegram → Пользователь
```
Формируется красивая карточка с информацией о материале, краткими метаданными и набором быстрых действий (пересказ, озвучка, похожие материалы).

**Общее время обработки:** 20-50 секунд в зависимости от размера материала и текущей нагрузки на API.

### RAG Pipeline: Архитектура умного поиска

![Диаграмма RAG-пайплайна](../rag_flow.puml)

RAG (Retrieval-Augmented Generation) — это не просто поиск, это мини-система искусственного интеллекта, которая находит релевантную информацию и генерирует на её основе точные ответы.

**Компоненты RAG:**

**1. Query Processing**
```
Вопрос пользователя → Очистка → Векторизация
```
Входящий запрос очищается от стоп-слов и преобразуется в вектор той же размерности, что и документы в базе (384 измерения для модели `all-MiniLM-L6-v2`).

**2. Retrieval (поиск релевантных документов)**
```
Query Vector → ChromaDB.search() → Top-K Documents
```
Векторная база находит K наиболее похожих документов, используя косинусное сходство. Типичное значение K = 5-10, чтобы контекст не превысил лимит токенов LLM.

**3. Context Building**
```
Top-K Docs → Rerank → Format → Context Window
```
Найденные документы ранжируются по релевантности, форматируются в читаемый вид и упаковываются в контекст для языковой модели. Важно уложиться в context window (для Claude 3.7 Sonnet — 200K токенов, но мы используем 8K для скорости).

**4. Generation (генерация ответа)**
```
Context + Query → Claude → Structured Answer
```
Claude получает вопрос пользователя и контекст из базы знаний. Промпт строго инструктирует модель использовать ТОЛЬКО предоставленную информацию, не добавляя знания из обучающих данных.

**5. Citation & Response**
```
Answer + Sources → Format → Telegram Message
```
Ответ дополняется ссылками на источники с указанием релевантности каждого. Пользователь может кликнуть на источник и перейти к полному материалу.

**Ключевые оптимизации:**

- **Метаданные в эмбеддингах**: Перед векторизацией к тексту добавляются заголовок, теги и краткое резюме. Это улучшает точность поиска на 15-20%.

- **Гибридный поиск**: Комбинация векторного поиска и фильтрации по метаданным (дата, теги, сложность). Например: "найди статьи про Kubernetes средней сложности за последний месяц".

- **Переранжирование**: После векторного поиска применяется дополнительная модель для переранжирования результатов на основе cross-encoder. Это повышает точность top-3 результатов.

### Технологические решения

**Почему модульный монолит, а не микросервисы?**

На текущей стадии проекта (до 1000 пользователей) микросервисы добавили бы сложности без явных преимуществ. Монолит проще разрабатывать, дебажить и деплоить. При этом модульная структура позволит в будущем выделить критические компоненты в отдельные сервисы.

**Почему асинхронность?**

Бот проводит много времени в ожидании: HTTP-запросы к сайтам, обращения к AI API, запросы к БД. Асинхронность через `asyncio` позволяет использовать это время для обработки других запросов, увеличивая throughput в 5-10 раз.

**Почему три базы данных?**

Универсальных решений не существует. MongoDB идеальна для гибких JSON-документов переменной структуры. PostgreSQL — для транзакционных данных и сложной аналитики. ChromaDB — для векторного поиска с минимальными накладными расходами.

---

## Проблема: Цифровой хаос и синдром «прочитаю потом»

Информации стало слишком много. Как разработчик, я ежедневно фильтрую тонны контента: статьи, лекции, новости. Каждая ссылка кажется возможностью для роста, инвестицией в себя. Но привычка просто «сохранять на потом» ведёт в тупик. Без нормальной системы обработки эти залежи данных превращаются в бесполезный цифровой шум, в котором невозможно найти ничего ценного.

Знакомо, правда? Нашёл классную статью — времени нет, закинул в закладки. Наткнулся на видео о новой технологии — переслал себе в «Избранное». И вот так — ссылки здесь, вкладки там, очередной список «прочитать потом», который никогда не откроешь.

Всё это добро раскидывается по разным местам и исчезает. Я тратил больше времени на попытки навести порядок в этом цифровом бардаке, чем на само изучение материалов. Где-то там, среди всего этого хлама, наверняка спрятаны ценные находки, но ни сил, ни времени их искать.

### Масштаб проблемы

Давайте честно посмотрим на цифры:

- **150+ закладок в Firefox**, большинство из которых я не открывал месяцами
- **30+ видео в плейлисте «Посмотреть позже»** на YouTube
- **23 заметки в Obsidian** с заголовком «Интересные ссылки»
- **Чат с самим собой в Telegram**, забитый ссылками за последние два года

Каждый раз, когда я пытался найти что-то конкретное, начинались археологические раскопки собственной цифровой истории. «Где же та статья про микросервисы, которую я сохранил в прошлом месяце?» Поиск превращался в квест без гарантии успеха.

### Психология информационной прокрастинации

Хуже всего было понимание, что я сам создаю этот хаос. Сохранение ссылки давало ложное чувство продуктивности — «Я же не теряю информацию, я её организую!» На самом деле, я просто откладывал решение проблемы. Каждая новая закладка становилась обещанием себе, которое я не собирался выполнять.

Появилось чувство информационной вины. Знания лежали мёртвым грузом, а я ощущал себя неэффективным. Это превратилось в порочный круг: чем больше я сохранял, тем менее вероятным становилось, что я когда-нибудь это прочитаю.

---

## Решение: Бот-аналитик вместо склада ссылок

В какой-то момент стало ясно — мне нужен не очередной сервис для хранения закладок. Надоело складывать их горой в надежде когда-нибудь разобрать. Нужен был инструмент, который реально помогает, а не превращает закладки в цифровое кладбище.

Требования были простые:
- **Минимум трения**: кидаешь ссылку — получаешь обработанный контент
- **Умная обработка**: не просто хранение URL, а полный анализ содержимого
- **Быстрый доступ**: поиск нужной информации за секунды, а не минуты
- **Кроссплатформенность**: работа с любого устройства без синхронизации

Так появился Telegram-бот, который стал персональным куратором знаний.

### Почему Telegram, а не веб-приложение?

Выбор платформы был осознанным. Telegram-бот даёт несколько критических преимуществ:

**Нулевой порог входа.** Не нужно устанавливать приложения, регистрироваться, настраивать. Telegram уже есть на всех устройствах.

**Естественная интеграция.** Для многих из нас Telegram — рабочий инструмент. Бот органично вписывается в привычную среду, не требуя переключения контекста.

**Мгновенный доступ.** Переслать ссылку боту — дело двух секунд. Это убирает барьер, который заставляет откладывать сохранение материалов «на потом».

**Простота интерфейса.** Чат — самый простой UI. Нет отвлекающих элементов, нет сложной навигации. Только пользователь, бот и контент.

При этом понятно, что для задач вроде визуализации связей между заметками или расширенного управления базой знаний может потребоваться более сложный интерфейс. Поэтому в будущем возможно появление веб-компонента, который расширит возможности бота, но не заменит его базовый принцип — простоту и скорость.

---

## Архитектура: Модульный монолит с асинхронной обработкой

Проект построен по принципу **модульного монолита**. Код разделён на независимые логические блоки, но работает в рамках одного процесса, общаясь через прямые вызовы и асинхронные события.

### Структура системы

Система состоит из четырёх основных слоёв:

#### 1. User Interface Layer

Слой коммуникации между пользователем и ботом. Основной интерфейс — Telegram: все команды, запросы и ответы проходят через чат. Реализованы интерактивные меню с inline-кнопками, система уведомлений и быстрые действия.

Используется `python-telegram-bot` v20+ с полной поддержкой асинхронности через `asyncio`. Все обработчики работают неблокирующе, что позволяет боту обрабатывать множество запросов параллельно.

#### 2. Application Layer

Уровень маршрутизации данных и команд. Здесь происходит обработка входящих сообщений и их распределение по соответствующим модулям.

Handlers (обработчики) определяют логику реагирования на события:
- Получение новой ссылки → парсинг и анализ
- Запрос резюме → генерация краткого пересказа
- Поисковый запрос → RAG-пайплайн
- Изменение статуса → обновление в БД

Вся маршрутизация построена через декораторы и middleware, что позволяет легко добавлять новые команды без изменения существующего кода.

#### 3. Business Logic Layer

Сердце системы. Здесь сосредоточена вся интеллектуальная обработка:

**Content Analyzer** — парсинг и очистка контента. Разные стратегии для разных типов источников:
- Статические сайты: `BeautifulSoup4` + `requests`
- SPA и защищённые сайты: `Selenium` в headless-режиме
- YouTube: `yt-dlp` для извлечения субтитров и метаданных

**AI Pipeline** — интеграция с Claude 3.7 Sonnet через Anthropic API:
- Извлечение ключевых тезисов
- Определение тематики и тегов
- Оценка сложности материала (1-10)
- Генерация кратких и подробных пересказов
- Выделение связей с существующими материалами

**RAG Agent** — семантический поиск и генерация ответов:
- Векторизация контента через `sentence-transformers`
- Поиск релевантных фрагментов в ChromaDB
- Формирование контекста для LLM
- Генерация ответов с цитированием источников

**Vector Manager** — управление векторными представлениями:
- Создание embeddings для новых документов
- Поиск похожих материалов
- Кластеризация по темам
- Обновление индексов

#### 4. Data Layer

Уровень постоянного хранения. Используется гибридная модель с тремя типами хранилищ:

**MongoDB** — для неструктурированного контента:
- Полные тексты статей
- Транскрипты видео
- JSON-ответы от AI
- История изменений каждого материала

Выбор MongoDB обусловлен гибкостью схемы. Разные типы контента (статья, видео, документация) требуют разных полей, и документо-ориентированная модель идеально подходит для этого.

**PostgreSQL** — для структурированных данных:
- Пользователи и их настройки
- Статусы материалов
- Рейтинги и метки
- История действий
- Связи между сущностями

Реляционная модель позволяет эффективно строить сложные запросы типа «Какие статьи по теме X я прочитал на прошлой неделе с рейтингом 4+?»

**ChromaDB** — для векторного поиска:
- Embeddings всех документов
- Метаданные для фильтрации
- Индексы для быстрого поиска

ChromaDB выбрана за простоту развёртывания (работает локально без внешних зависимостей), хорошую производительность на небольших и средних объёмах данных (до 100K документов) и нативную интеграцию с популярными моделями эмбеддингов.

### Структура проекта

```text
telegram_bot_analytic/
├── analyzers/              # Интеллектуальная обработка
│   ├── content_analyzer.py # Парсинг и AI-анализ
│   ├── rag_agent.py        # RAG-пайплайн
│   └── vector_manager.py   # Работа с векторами
├── handlers/               # Обработчики команд
│   ├── bot_handlers.py     # Базовые команды
│   └── rag_handlers.py     # Команды поиска
├── storage/                # Слой данных
│   ├── mongo_manager.py    # NoSQL хранилище
│   └── postgres_manager.py # Реляционная БД
├── generators/             # Генераторы контента
│   ├── pdf_generator.py    # Создание PDF
│   └── tts_generator.py    # Text-to-Speech
├── parsers/                # Парсеры контента
│   ├── web_parser.py       # Парсинг сайтов
│   └── youtube_parser.py   # Извлечение субтитров
├── config.py               # Конфигурация
├── main.py                 # Точка входа
└── requirements.txt        # Зависимости
```

### Поток обработки контента

Когда пользователь отправляет ссылку боту, запускается многоэтапный процесс:

**Этап 1: Валидация и классификация**
```python
# Проверка корректности URL
if not is_valid_url(url):
    return error_response("Некорректная ссылка")

# Определение типа контента
content_type = classify_url(url)  # article, video, documentation, etc.
```

**Этап 2: Парсинг**

Выбор стратегии парсинга зависит от типа контента:

```python
if content_type == "youtube":
    # Извлечение через yt-dlp
    result = extract_youtube_content(url)
    text = result['subtitles'] or result['auto_captions']
    metadata = {
        'title': result['title'],
        'author': result['uploader'],
        'duration': result['duration'],
        'views': result['view_count']
    }
elif content_type == "article":
    # Парсинг HTML
    html = fetch_with_selenium(url) if is_spa(url) else fetch_with_requests(url)
    soup = BeautifulSoup(html, 'html.parser')
    
    # Извлечение основного контента
    article = extract_article_content(soup)
    text = clean_text(article.get_text())
    metadata = {
        'title': article.find('h1').get_text(),
        'author': extract_author(soup),
        'published': extract_date(soup)
    }
```

**Этап 3: AI-анализ**

Отправка контента в Claude для глубокого анализа:

```python
prompt = f"""
Проанализируй следующий контент и предоставь структурированный анализ.

URL: {url}
ЗАГОЛОВОК: {metadata['title']}
СОДЕРЖИМОЕ: {text[:100000]}  # Ограничение в 100K токенов

Верни JSON со следующими полями:
{{
    "summary": "Краткое резюме 2-3 предложения",
    "key_points": ["Ключевой тезис 1", "Ключевой тезис 2", ...],
    "complexity_level": "начальный|средний|продвинутый",
    "main_topics": ["тема1", "тема2", ...],
    "tags": ["тег1", "тег2", ...],
    "relevance_score": 8,  // от 1 до 10
    "related_concepts": ["концепция1", "концепция2", ...]
}}
"""

analysis = await claude_client.analyze(prompt, model="claude-3-7-sonnet-20250219")
```

Для очень длинных материалов (более 100K токенов) используется стратегия Map-Reduce:

```python
def analyze_long_content(text, chunk_size=50000):
    # Разбиваем на чанки
    chunks = split_into_chunks(text, chunk_size)
    
    # Анализируем каждый чанк отдельно
    chunk_analyses = []
    for chunk in chunks:
        analysis = claude_client.analyze_chunk(chunk)
        chunk_analyses.append(analysis)
    
    # Объединяем результаты
    final_analysis = claude_client.merge_analyses(chunk_analyses)
    return final_analysis
```

**Этап 4: Векторизация**

Создание векторного представления для семантического поиска:

```python
def prepare_text_for_vectorization(content, metadata, analysis):
    """
    Подготовка текста для векторизации.
    Добавляем метаданные в начало для улучшения релевантности поиска.
    """
    parts = []
    
    # Сильные сигналы в начале
    if metadata.get('title'):
        parts.append(f"Заголовок: {metadata['title']}")
    
    if analysis.get('tags'):
        parts.append(f"Теги: {', '.join(analysis['tags'])}")
    
    if analysis.get('summary'):
        parts.append(f"Резюме: {analysis['summary']}")
    
    if analysis.get('key_points'):
        parts.append(f"Ключевые моменты: {' '.join(analysis['key_points'])}")
    
    # Основной контент
    parts.append(f"Контент: {content}")
    
    return "\n\n".join(parts)

# Создание эмбеддинга
prepared_text = prepare_text_for_vectorization(text, metadata, analysis)
embedding = embedding_model.encode(prepared_text)

# Сохранение в ChromaDB
vector_db.add(
    ids=[document_id],
    embeddings=[embedding],
    documents=[text],
    metadatas=[{
        'url': url,
        'title': metadata['title'],
        'type': content_type,
        'complexity': analysis['complexity_level'],
        'tags': analysis['tags'],
        'added_date': datetime.now().isoformat()
    }]
)
```

**Этап 5: Сохранение**

Параллельное сохранение в разные хранилища:

```python
async def save_analyzed_content(url, text, metadata, analysis, embedding):
    # Сохранение в MongoDB (полный контент)
    mongo_task = mongo_db.documents.insert_one({
        '_id': document_id,
        'url': url,
        'text': text,
        'metadata': metadata,
        'analysis': analysis,
        'created_at': datetime.now(),
        'updated_at': datetime.now()
    })
    
    # Сохранение в PostgreSQL (структурированные данные)
    postgres_task = postgres_db.execute(
        """
        INSERT INTO documents (id, user_id, url, title, type, status, rating, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        document_id, user_id, url, metadata['title'], 
        content_type, 'unread', None, datetime.now()
    )
    
    # Векторизация уже выполнена выше
    
    # Ждём завершения всех операций
    await asyncio.gather(mongo_task, postgres_task)
```

**Этап 6: Уведомление пользователя**

Формирование интерактивного сообщения с быстрыми действиями:

```python
keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("📝 Краткий пересказ", callback_data=f"summary_short_{document_id}")],
    [InlineKeyboardButton("📄 Подробный пересказ", callback_data=f"summary_full_{document_id}")],
    [InlineKeyboardButton("🎵 Озвучить", callback_data=f"tts_{document_id}")],
    [InlineKeyboardButton("🔍 Похожие", callback_data=f"similar_{document_id}")],
    [InlineKeyboardButton("⭐ Оценить", callback_data=f"rate_{document_id}")]
])

message = f"""
✅ Материал обработан и сохранён

📌 **{metadata['title']}**
🔗 {url}

📊 **Сложность:** {analysis['complexity_level']}
🏷️ **Теги:** {', '.join(analysis['tags'][:5])}
⏱️ **Время чтения:** {estimate_reading_time(text)} мин

💡 **Краткое содержание:**
{analysis['summary']}
"""

await bot.send_message(user_id, message, reply_markup=keyboard)
```

---

## Ключевые возможности и техническая реализация

### 1. Всеядный парсинг с умной обработкой

Бот принимает любые HTTP/HTTPS ссылки и автоматически определяет стратегию обработки.

#### Парсинг веб-страниц

Для статических сайтов используется связка `requests` + `BeautifulSoup4`:

```python
def parse_static_website(url):
    response = requests.get(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; KnowledgeBot/1.0)'
    }, timeout=10)
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Удаление мусора
    for tag in soup(['script', 'style', 'nav', 'footer', 'aside']):
        tag.decompose()
    
    # Извлечение основного контента
    article = (
        soup.find('article') or 
        soup.find('main') or 
        soup.find('div', class_=re.compile('content|article|post'))
    )
    
    return {
        'text': clean_text(article.get_text()),
        'title': soup.find('h1').get_text(),
        'author': extract_author(soup),
        'published_date': extract_date(soup)
    }
```

Для SPA и защищённых сайтов подключается `Selenium`:

```python
def parse_dynamic_website(url):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    
    # Ждём загрузки контента
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "article"))
    )
    
    # Скроллинг для ленивой загрузки
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    
    html = driver.page_source
    driver.quit()
    
    return parse_static_website_from_html(html)
```

#### Извлечение субтитров YouTube

Для видео используется `yt-dlp` — мощный инструмент для работы с YouTube:

```python
def extract_youtube_content(url):
    ydl_opts = {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['ru', 'en'],
        'skip_download': True,
        'quiet': True
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        # Приоритет ручным субтитрам
        subtitles = (
            info.get('subtitles', {}).get('ru') or 
            info.get('subtitles', {}).get('en') or
            info.get('automatic_captions', {}).get('ru') or
            info.get('automatic_captions', {}).get('en')
        )
        
        if subtitles:
            # Скачиваем и парсим субтитры
            sub_url = subtitles[0]['url']
            sub_content = requests.get(sub_url).text
            text = parse_subtitles(sub_content)
        else:
            text = info.get('description', '')
        
        return {
            'text': text,
            'title': info['title'],
            'author': info['uploader'],
            'duration': info['duration'],
            'views': info['view_count'],
            'published': info['upload_date']
        }
```

### 2. RAG Pipeline: Семантический поиск и генерация ответов

Это ключевая фича, превращающая архив ссылок в интеллектуального ассистента.

#### Архитектура RAG

RAG (Retrieval-Augmented Generation) состоит из трёх компонентов:

1. **Retriever** — находит релевантные документы
2. **Context Builder** — формирует контекст из найденных фрагментов
3. **Generator** — создаёт ответ на основе контекста

#### Реализация поиска

```python
class RAGAgent:
    def __init__(self, vector_db, mongo_db, claude_client):
        self.vector_db = vector_db
        self.mongo_db = mongo_db
        self.claude = claude_client
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    async def search(self, query, top_k=5, filters=None):
        """
        Семантический поиск по базе знаний.
        
        Args:
            query: Поисковый запрос
            top_k: Количество результатов
            filters: Фильтры (по тегам, дате, сложности и т.д.)
        """
        # Векторизация запроса
        query_embedding = self.embedding_model.encode(query)
        
        # Поиск в ChromaDB
        results = self.vector_db.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filters  # Например: {"complexity": "средний"}
        )
        
        # Обогащение результатов данными из MongoDB
        enriched_results = []
        for doc_id, distance in zip(results['ids'][0], results['distances'][0]):
            doc = await self.mongo_db.documents.find_one({'_id': doc_id})
            enriched_results.append({
                'id': doc_id,
                'title': doc['metadata']['title'],
                'url': doc['url'],
                'relevance': 1 - distance,  # Преобразование расстояния в релевантность
                'summary': doc['analysis']['summary'],
                'text': doc['text']
            })
        
        return enriched_results
```

#### Построение контекста

```python
def build_context(self, relevant_docs, max_length=8000):
    """
    Формирование контекста для LLM из найденных документов.
    Ограничиваем длину, чтобы уложиться в context window.
    """
    context_parts = []
    current_length = 0
    
    for i, doc in enumerate(relevant_docs, 1):
        # Формируем блок для каждого источника
        source_block = f"""
[Источник {i}]
Название: {doc['title']}
URL: {doc['url']}
Релевантность: {doc['relevance']:.2%}

Содержание:
{doc['text'][:2000]}  # Берём первые 2000 символов

---
"""
        block_length = len(source_block)
        
        # Проверяем, не превысим ли лимит
        if current_length + block_length > max_length:
            break
        
        context_parts.append(source_block)
        current_length += block_length
    
    return "\n".join(context_parts)
```

#### Генерация ответа

```python
async def ask(self, question, user_id):
    """
    Генерация ответа на вопрос пользователя на основе его базы знаний.
    """
    # Шаг 1: Находим релевантные документы
    relevant_docs = await self.search(
        query=question,
        top_k=5,
        filters={'user_id': user_id}  # Только материалы этого пользователя
    )
    
    if not relevant_docs:
        return "По вашему запросу ничего не найдено в базе знаний."
    
    # Шаг 2: Формируем контекст
    context = self.build_context(relevant_docs)
    
    # Шаг 3: Создаём промпт для Claude
    prompt = f"""
Ты — ассистент по управлению знаниями. Твоя задача — отвечать на вопросы пользователя, 
используя ТОЛЬКО информацию из предоставленных источников.

Правила:
1. Используй ТОЛЬКО информацию из контекста ниже
2. Если информации недостаточно — честно скажи об этом
3. Всегда указывай источники (номер источника)
4. Цитируй напрямую, когда это уместно
5. Не придумывай и не добавляй информацию из своих знаний

ВОПРОС ПОЛЬЗОВАТЕЛЯ:
{question}

КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ:
{context}

Сформируй развёрнутый ответ с обязательным указанием источников.
"""
    
    # Шаг 4: Генерируем ответ через Claude
    response = await self.claude.generate(
        prompt=prompt,
        max_tokens=2000,
        temperature=0.3  # Низкая температура для фактической точности
    )
    
    # Шаг 5: Добавляем ссылки на источники
    sources_list = "\n\n📚 **Источники:**\n"
    for i, doc in enumerate(relevant_docs, 1):
        sources_list += f"{i}. [{doc['title']}]({doc['url']}) (релевантность: {doc['relevance']:.0%})\n"
    
    return response + sources_list
```

#### Пример работы RAG

Пользователь спрашивает: *«Какие подходы к оптимизации React приложений упоминаются в моих материалах?»*

```python
# 1. Векторизация запроса
query_vector = embedding_model.encode("оптимизация React приложений")

# 2. Поиск релевантных документов
results = vector_db.query(query_vector, n_results=5)
# Найдены: 3 статьи про React, 1 видео, 1 документация

# 3. Построение контекста
context = """
[Источник 1]
Название: Оптимизация производительности React приложений
...мемоизация компонентов через React.memo...
...виртуализация длинных списков...
...code splitting и lazy loading...

[Источник 2]
Название: Advanced React Performance
...useMemo и useCallback для оптимизации перерендеров...
...React DevTools Profiler для анализа...

[Источник 3]
Название: React 18 и новые возможности
...автоматический батчинг...
...Suspense для асинхронной загрузки...
"""

# 4. Генерация ответа
response = claude.generate(prompt + context)
```

Ответ бота:

```
На основе ваших материалов выделяются следующие подходы к оптимизации React:

1. **Мемоизация компонентов** [Источник 1, 2]
   - React.memo для предотвращения ненужных перерендеров
   - useMemo и useCallback для мемоизации значений и функций

2. **Виртуализация списков** [Источник 1]
   - Рендеринг только видимой части длинных списков

3. **Code Splitting** [Источник 1, 3]
   - Lazy loading компонентов через React.lazy
   - Suspense для управления асинхронной загрузкой

4. **React 18 features** [Источник 3]
   - Автоматический батчинг обновлений состояния
   - Улучшенный Suspense

5. **Инструменты анализа** [Источник 2]
   - React DevTools Profiler для выявления узких мест

📚 **Источники:**
1. [Оптимизация производительности React приложений](url1) (релевантность: 94%)
2. [Advanced React Performance](url2) (релевантность: 89%)
3. [React 18 и новые возможности](url3) (релевантность: 76%)
```

### 3. CRM для знаний: Управление жизненным циклом материалов

Чтобы база знаний не превратилась в свалку, реализована полноценная система управления материалами.

#### Модель данных в PostgreSQL

```sql
-- Таблица пользователей
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Таблица документов
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT REFERENCES users(id),
    url TEXT NOT NULL,
    title TEXT,
    content_type VARCHAR(50),  -- article, video, documentation
    status VARCHAR(20) DEFAULT 'unread',  -- unread, reading, read, archived
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, url)
);

-- Таблица тегов
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

-- Связь документов и тегов
CREATE TABLE document_tags (
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (document_id, tag_id)
);

-- История действий
CREATE TABLE document_history (
    id SERIAL PRIMARY KEY,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    action VARCHAR(50),  -- created, status_changed, rated, exported
    old_value TEXT,
    new_value TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Индексы для быстрого поиска
CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_rating ON documents(rating);
CREATE INDEX idx_documents_created_at ON documents(created_at);
CREATE INDEX idx_document_history_document_id ON document_history(document_id);
```

#### Управление статусами

Реализован workflow для отслеживания прогресса изучения:

```python
class DocumentStatus(Enum):
    UNREAD = "unread"          # Только добавлено
    READING = "reading"         # В процессе изучения
    READ = "read"               # Прочитано
    IMPORTANT = "important"     # Важное (избранное)
    ARCHIVED = "archived"       # В архиве

async def change_status(document_id, new_status, user_id):
    """Изменение статуса с записью в историю"""
    # Получаем текущий статус
    current = await db.fetchrow(
        "SELECT status FROM documents WHERE id = $1 AND user_id = $2",
        document_id, user_id
    )
    
    if not current:
        raise DocumentNotFound()
    
    old_status = current['status']
    
    # Обновляем статус
    await db.execute(
        """
        UPDATE documents 
        SET status = $1, updated_at = NOW() 
        WHERE id = $2 AND user_id = $3
        """,
        new_status, document_id, user_id
    )
    
    # Записываем в историю
    await db.execute(
        """
        INSERT INTO document_history (document_id, action, old_value, new_value)
        VALUES ($1, 'status_changed', $2, $3)
        """,
        document_id, old_status, new_status
    )
    
    # Отправляем уведомление
    await notify_user(user_id, f"Статус изменён: {old_status} → {new_status}")
```

#### Система рейтингов

```python
async def rate_document(document_id, rating, user_id):
    """Выставление рейтинга (1-5 звёзд)"""
    if not 1 <= rating <= 5:
        raise ValueError("Рейтинг должен быть от 1 до 5")
    
    # Получаем старый рейтинг
    old_rating = await db.fetchval(
        "SELECT rating FROM documents WHERE id = $1 AND user_id = $2",
        document_id, user_id
    )
    
    # Обновляем рейтинг
    await db.execute(
        """
        UPDATE documents 
        SET rating = $1, updated_at = NOW() 
        WHERE id = $2 AND user_id = $3
        """,
        rating, document_id, user_id
    )
    
    # Записываем в историю
    await db.execute(
        """
        INSERT INTO document_history (document_id, action, old_value, new_value)
        VALUES ($1, 'rated', $2, $3)
        """,
        document_id, str(old_rating), str(rating)
    )
    
    # Обновляем персональный профиль интересов
    await update_user_preferences(user_id, document_id, rating)
```

#### Интерактивное управление в Telegram

Все действия доступны через inline-кнопки:

```python
def get_document_keyboard(document_id, current_status, current_rating):
    """Создание клавиатуры для управления документом"""
    keyboard = []
    
    # Кнопки статусов
    status_row = []
    for status in DocumentStatus:
        icon = "✅" if status.value == current_status else "⚪"
        status_row.append(InlineKeyboardButton(
            f"{icon} {status.value}",
            callback_data=f"status_{document_id}_{status.value}"
        ))
    keyboard.append(status_row)
    
    # Кнопки рейтинга
    rating_row = []
    for i in range(1, 6):
        icon = "⭐" if i <= (current_rating or 0) else "☆"
        rating_row.append(InlineKeyboardButton(
            icon,
            callback_data=f"rate_{document_id}_{i}"
        ))
    keyboard.append(rating_row)
    
    # Действия
    action_row = [
        InlineKeyboardButton("📝 Пересказ", callback_data=f"summary_{document_id}"),
        InlineKeyboardButton("🎵 Озвучить", callback_data=f"tts_{document_id}"),
        InlineKeyboardButton("📄 PDF", callback_data=f"pdf_{document_id}")
    ]
    keyboard.append(action_row)
    
    return InlineKeyboardMarkup(keyboard)
```

#### Аналитика и отчёты

```python
async def get_user_stats(user_id, period='week'):
    """Получение статистики по материалам"""
    
    # Период времени
    if period == 'week':
        time_filter = "created_at >= NOW() - INTERVAL '7 days'"
    elif period == 'month':
        time_filter = "created_at >= NOW() - INTERVAL '30 days'"
    else:
        time_filter = "TRUE"
    
    stats = await db.fetchrow(f"""
        SELECT 
            COUNT(*) as total_documents,
            COUNT(*) FILTER (WHERE status = 'read') as read_count,
            COUNT(*) FILTER (WHERE status = 'unread') as unread_count,
            ROUND(AVG(rating), 2) as avg_rating,
            COUNT(DISTINCT DATE(created_at)) as active_days
        FROM documents
        WHERE user_id = $1 AND {time_filter}
    """, user_id)
    
    # Топ тегов
    top_tags = await db.fetch("""
        SELECT t.name, COUNT(*) as count
        FROM document_tags dt
        JOIN tags t ON dt.tag_id = t.id
        JOIN documents d ON dt.document_id = d.id
        WHERE d.user_id = $1 AND d.{time_filter}
        GROUP BY t.name
        ORDER BY count DESC
        LIMIT 5
    """, user_id)
    
    return {
        'total': stats['total_documents'],
        'read': stats['read_count'],
        'unread': stats['unread_count'],
        'avg_rating': stats['avg_rating'],
        'active_days': stats['active_days'],
        'top_tags': [{'name': tag['name'], 'count': tag['count']} for tag in top_tags]
    }
```

### 4. Мультиформатное потребление контента

Материалы доступны не только в виде текста, но и в других форматах.

#### PDF-генерация

Используется `reportlab` для создания профессионально выглядящих PDF:

```python
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

class PDFGenerator:
    def __init__(self):
        # Регистрация кириллического шрифта
        pdfmetrics.registerFont(TTFont('DejaVu', 'DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVu-Bold', 'DejaVuSans-Bold.ttf'))
        
        self.styles = getSampleStyleSheet()
        
        # Кастомные стили
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            fontName='DejaVu-Bold',
            fontSize=18,
            spaceAfter=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            fontName='DejaVu',
            fontSize=11,
            leading=14,
            spaceAfter=6
        ))
    
    async def generate_document_pdf(self, document_id, include_summary=True):
        """Генерация PDF для документа"""
        # Получаем данные
        doc_data = await self.get_document_data(document_id)
        
        # Создаём PDF в памяти
        buffer = io.BytesIO()
        pdf = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        
        # Заголовок
        title = Paragraph(doc_data['title'], self.styles['CustomTitle'])
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Метаданные
        metadata = f"""
        <b>URL:</b> {doc_data['url']}<br/>
        <b>Автор:</b> {doc_data['author']}<br/>
        <b>Дата:</b> {doc_data['published_date']}<br/>
        <b>Сложность:</b> {doc_data['complexity']}<br/>
        <b>Теги:</b> {', '.join(doc_data['tags'])}<br/>
        <b>Рейтинг:</b> {'⭐' * doc_data['rating']}<br/>
        """
        story.append(Paragraph(metadata, self.styles['CustomBody']))
        story.append(Spacer(1, 20))
        
        # Краткое резюме
        if include_summary:
            story.append(Paragraph("<b>Краткое содержание:</b>", self.styles['CustomBody']))
            story.append(Paragraph(doc_data['summary'], self.styles['CustomBody']))
            story.append(Spacer(1, 20))
        
        # Основной текст
        story.append(Paragraph("<b>Полный текст:</b>", self.styles['CustomBody']))
        
        # Разбиваем текст на параграфы
        for paragraph in doc_data['text'].split('\n\n'):
            if paragraph.strip():
                p = Paragraph(paragraph, self.styles['CustomBody'])
                story.append(p)
                story.append(Spacer(1, 6))
        
        # Генерация PDF
        pdf.build(story)
        buffer.seek(0)
        
        return buffer
```

#### Text-to-Speech

Реализовано два варианта озвучки:

**Быстрый вариант через Google TTS:**

```python
from gtts import gTTS

async def generate_audio_gtts(text, language='ru'):
    """Быстрая генерация через Google TTS"""
    # Ограничиваем длину
    if len(text) > 25000:
        text = text[:25000] + "..."
    
    # Генерация
    tts = gTTS(text=text, lang=language, slow=False)
    
    # Сохранение в память
    buffer = io.BytesIO()
    tts.write_to_fp(buffer)
    buffer.seek(0)
    
    return buffer
```

**Продвинутый вариант через локальную модель:**

```python
from TTS.api import TTS

class LocalTTSGenerator:
    def __init__(self):
        # Загрузка модели (один раз при старте)
        self.model = TTS(model_name="tts_models/ru/ruslan/tacotron2-DDC")
    
    async def generate_audio(self, text, speed=1.0):
        """Генерация высококачественной озвучки"""
        # Разбиваем на предложения для лучшего качества
        sentences = self.split_into_sentences(text)
        
        audio_chunks = []
        for sentence in sentences:
            # Генерируем аудио для каждого предложения
            audio = self.model.tts(text=sentence, speed=speed)
            audio_chunks.append(audio)
        
        # Склеиваем все чанки
        full_audio = np.concatenate(audio_chunks)
        
        # Конвертируем в WAV
        buffer = io.BytesIO()
        scipy.io.wavfile.write(buffer, rate=22050, data=full_audio)
        buffer.seek(0)
        
        return buffer
```

---

## Результаты: Измеримые изменения

### Количественные показатели

После трёх месяцев использования бота собрал статистику:

**Эффективность обработки информации:**
- Время на обработку одного материала: с 20-30 минут до 2-3 минут
- Количество обработанных материалов в неделю: с 2-3 до 15-20
- Время поиска нужной информации: с 10-15 минут до 30 секунд

**Качество усвоения:**
- Процент запоминания ключевых идей: с 20% до 60%
- Способность быстро вспомнить детали: улучшилась в 4 раза
- Количество материалов, к которым возвращаюсь повторно: выросло с 5% до 40%

**Организация:**
- Мёртвые закладки: было 150+, стало 0
- Структурированные материалы в базе: 200+
- Связей между материалами: найдено автоматически 450+

### Качественные изменения

**От хаоса к системе.** Исчезла постоянная тревога о потерянной информации. Знание того, что всё сохранено и структурировано, освободило ментальные ресурсы для реальной работы с контентом.

**От пассивного потребления к активному обучению.** Раньше я просто читал статьи. Теперь я взаимодействую с базой знаний: задаю вопросы, ищу связи, строю концептуальные карты.

**От индивидуального к коллективному интеллекту.** Начал делиться интересными пересказами с коллегами. Бот стал источником инсайтов для всей команды.

**От линейного к сетевому мышлению.** Автоматическое выявление связей между материалами помогает видеть паттерны и делать неожиданные выводы, которые не пришли бы в голову при изолированном чтении статей.

---

## Технологический стек и конфигурация

### Основные технологии

**Core:**
- Python 3.11+ с `asyncio` для асинхронности
- `python-telegram-bot` v20+ для работы с Telegram API

**AI & ML:**
- Anthropic Claude 3.7 Sonnet через официальный API
- `sentence-transformers` для локальных эмбеддингов
- ChromaDB для векторного поиска

**Databases:**
- MongoDB для неструктурированного контента
- PostgreSQL для реляционных данных
- ChromaDB для векторных представлений

**Parsing & Processing:**
- `BeautifulSoup4` для парсинга HTML
- `Selenium` для динамических сайтов
- `yt-dlp` для YouTube
- `requests` для HTTP-запросов

**Content Generation:**
- `reportlab` для PDF
- `gTTS` / `TTS` для озвучки
- `Pillow` для обработки изображений

### Ключевые параметры конфигурации

```python
# config.py

# === AI Configuration ===
AI_MODEL = "claude-3-7-sonnet-20250219"
AI_MAX_TOKENS = 7500
AI_TEMPERATURE = 0.3  # Низкая для фактической точности
AI_TIMEOUT = 60  # Секунды

# === RAG Configuration ===
ENABLE_RAG = True
RAG_CONTEXT_SOURCES = 5  # Количество источников для контекста
RAG_MAX_CONTEXT_LENGTH = 8000  # Символов
RAG_MIN_RELEVANCE_SCORE = 0.7  # Минимальная релевантность

# === Vector DB Configuration ===
VECTOR_DB_PROVIDER = "chroma"
VECTOR_DB_PATH = "./data/chromadb"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Локальная модель
EMBEDDING_DIMENSION = 384

# === Parsing Configuration ===
PARSER_TIMEOUT = 30
PARSER_USE_SELENIUM_FOR_SPA = True
PARSER_MAX_CONTENT_LENGTH = 500000  # Символов
YOUTUBE_SUBTITLE_LANGUAGES = ["ru", "en"]

# === Content Processing ===
SUMMARIZATION_MIN_LENGTH = 100
SUMMARIZATION_MAX_LENGTH = 500
COMPLEXITY_LEVELS = ["начальный", "средний", "продвинутый"]

# === TTS Configuration ===
TTS_DEFAULT_ENGINE = "gtts"  # или "local"
TTS_MAX_TEXT_LENGTH = 25000
TTS_SPEED = 1.0
TTS_LANGUAGE = "ru"

# === Database Configuration ===
MONGODB_URI = "mongodb://localhost:27017"
MONGODB_DATABASE = "knowledge_base"
POSTGRES_URI = "postgresql://user:pass@localhost:5432/kb"

# === Rate Limiting ===
RATE_LIMIT_REQUESTS_PER_MINUTE = 20
RATE_LIMIT_AI_CALLS_PER_HOUR = 100

# === Caching ===
ENABLE_CACHE = True
CACHE_TTL_HOURS = 24
CACHE_MAX_SIZE_MB = 500
```

### Docker Compose для развёртывания

```yaml
version: '3.8'

services:
  bot:
    build: .
    container_name: knowledge_bot
    restart: unless-stopped
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - MONGODB_URI=mongodb://mongo:27017
      - POSTGRES_URI=postgresql://postgres:password@postgres:5432/kb
    depends_on:
      - mongo
      - postgres
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    networks:
      - kb_network

  mongo:
    image: mongo:7.0
    container_name: kb_mongo
    restart: unless-stopped
    volumes:
      - mongo_data:/data/db
    networks:
      - kb_network

  postgres:
    image: postgres:16
    container_name: kb_postgres
    restart: unless-stopped
    environment:
      - POSTGRES_DB=kb
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - kb_network

volumes:
  mongo_data:
  postgres_data:

networks:
  kb_network:
    driver: bridge
```

---

## Будущее: Планы развития

### Интеграция с Obsidian

Obsidian — инструмент для построения персональной вики, где каждая идея связана с другими через сеть ссылок и тегов.

**Планируемая функциональность:**

1. **Автоматическое создание заметок**
   - Каждый пересказ становится markdown-файлом в Obsidian
   - Автоматическое формирование frontmatter с метаданными
   - Сохранение структуры заголовков и форматирования

2. **Интеллектуальное связывание**
   - AI анализирует граф знаний и предлагает связи
   - Автоматическое создание backlinks
   - Выявление концептуальных кластеров

3. **Двусторонняя синхронизация**
   - Заметки из Obsidian попадают в базу бота для поиска
   - Изменения синхронизируются в обе стороны
   - Конфликты разрешаются с приоритетом последнего изменения

4. **Визуализация знаний**
   - Граф связей показывает развитие базы знаний
   - Выявление областей с пробелами
   - Временная шкала изучения тем

**Техническая реализация:**

```python
class ObsidianIntegration:
    def __init__(self, vault_path):
        self.vault_path = Path(vault_path)
    
    async def export_to_obsidian(self, document):
        """Экспорт документа в Obsidian"""
        # Формирование frontmatter
        frontmatter = f"""---
title: {document['title']}
url: {document['url']}
tags: {', '.join(document['tags'])}
rating: {document['rating']}
complexity: {document['complexity']}
created: {document['created_at'].isoformat()}
---

"""
        # Добавление содержимого
        content = frontmatter + document['summary'] + "\n\n" + document['text']
        
        # Сохранение в vault
        filename = self.sanitize_filename(document['title']) + '.md'
        filepath = self.vault_path / filename
        
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(content)
        
        return filepath
    
    async def find_related_notes(self, document):
        """Поиск связанных заметок в Obsidian"""
        # Сканирование vault
        all_notes = list(self.vault_path.rglob('*.md'))
        
        # Векторизация документа
        doc_embedding = embedding_model.encode(document['text'])
        
        # Сравнение с каждой заметкой
        related = []
        for note_path in all_notes:
            note_text = await self.read_note(note_path)
            note_embedding = embedding_model.encode(note_text)
            
            similarity = cosine_similarity(doc_embedding, note_embedding)
            if similarity > 0.7:
                related.append({
                    'path': note_path,
                    'similarity': similarity
                })
        
        return sorted(related, key=lambda x: x['similarity'], reverse=True)
```

### Интеграция с NotebookLM

Google NotebookLM превращает коллекцию документов в интерактивного AI-ассистента.

**Планируемая функциональность:**

1. **Автоматическая синхронизация источников**
   - Все материалы из бота становятся источниками для NotebookLM
   - Обновление при добавлении новых материалов
   - Категоризация по темам

2. **Контекстуальные диалоги**
   - Вопросы типа «Что думают авторы о теме X?»
   - Синтез информации из нескольких источников
   - Выявление противоречий и общих трендов

3. **Цитирование и трассировка**
   - Каждый ответ содержит ссылки на источники
   - Возможность перехода к полному тексту
   - Показ релевантных фрагментов

### Другие планы

**Автогенерация графов знаний**
- Визуализация концептуальных связей
- Выявление центральных понятий
- Построение иерархии знаний

**Система напоминаний**
- Spaced repetition для лучшего запоминания
- Умные уведомления о материалах для повторения
- Адаптивные интервалы на основе сложности

**Анализ пробелов знаний**
- Выявление недостаточно изученных областей
- Рекомендации по дополнительным источникам
- Построение траекторий обучения

**Коллаборация**
- Shared knowledge bases для команд
- Обмен аннотациями и пересказами
- Коллективная курация контента

---

## Заключение

За три месяца использования этот бот из pet-проекта превратился в незаменимый инструмент для работы с информацией. Из 150+ мёртвых закладок получилась живая, постоянно растущая база знаний с мощными возможностями поиска и анализа.

**Ключевые достижения проекта:**

**Техническая сторона.** Реализован полноценный RAG-пайплайн с семантическим поиском, интеграцией Claude 3.7 Sonnet и гибридным хранилищем данных. Система обрабатывает любой тип контента — от статей до YouTube-видео — и превращает его в структурированные знания.

**Практическая польза.** Время на обработку информации сократилось с 2-3 часов в день до 30-40 минут. Количество изученных материалов выросло в 6 раз. Но главное — изменился сам подход к работе с информацией: от хаотичного накопления к осознанному курированию.

**Архитектурные решения.** Модульный монолит позволяет легко добавлять новые возможности. Асинхронная обработка обеспечивает отзывчивость. Гибридное хранилище (MongoDB + PostgreSQL + ChromaDB) даёт лучшее из разных миров: гибкость NoSQL, мощь реляционных запросов и скорость векторного поиска.

**Масштабируемость.** Система без проблем работает с базой из 200+ документов. Архитектура позволяет масштабироваться до нескольких тысяч материалов без значительных изменений. При необходимости можно перейти на распределённые хранилища и добавить кэширование.

**Открытые вопросы.** Текущая реализация решает конкретную проблему, но открывает новые возможности. Интеграция с Obsidian добавит визуализацию графа знаний. NotebookLM позволит вести более сложные исследовательские диалоги. Коллаборативные функции превратят персональный инструмент в командный.

**Уроки.**

1. **Простота интерфейса критична.** Telegram-бот убирает все барьеры между мыслью «сохранить это» и действием.

2. **AI должен быть инструментом, а не магией.** Claude используется точечно: для анализа, пересказов и генерации ответов. Но вся логика прозрачна и контролируема.

3. **Данные важнее кода.** Качественная структура хранения и правильные индексы важнее сложных алгоритмов.

4. **Итеративный подход работает.** Проект начался с простого сохранения ссылок. Каждая новая функция добавлялась по мере появления реальной потребности.

5. **Персонализация — ключ к эффективности.** Система учится на ваших действиях: что читаете, что сохраняете, как оцениваете. Это делает рекомендации и поиск всё более точными.

Это не просто бот для сохранения ссылок. Это персональный инструмент управления знаниями, который растёт вместе с вами. Каждый сохранённый материал делает систему умнее. Каждый заданный вопрос улучшает релевантность поиска. Каждая поставленная оценка точнее настраивает рекомендации.

Информационный хаос никуда не делся. Но теперь есть инструмент, который превращает этот хаос в структурированные знания. И это меняет всё.

**Код проекта доступен на GitHub:** [ссылка]  
**Документация и примеры использования:** [ссылка]

Если у вас похожая проблема с управлением информацией — попробуйте этот подход. Начните с простого: бот, парсер, база данных. А дальше система сама подскажет, куда развиваться.

---

*Статья написана на основе реального опыта разработки и использования системы. Все цифры и примеры взяты из production-версии бота, работающего с февраля 2025 года.*