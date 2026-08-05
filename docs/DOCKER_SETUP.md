# 🐳 Docker Setup для RAG функциональности

## Обзор изменений

Docker Compose конфигурация обновлена для поддержки RAG и векторной базы данных.

## Новые возможности

### 1. Переменные окружения для RAG

```yaml
# RAG и векторная БД
- ENABLE_RAG=true
- ENABLE_VECTOR_DB=true
- VECTOR_DB_PATH=/app/data/chroma_db

# Эмбеддинги
- EMBEDDING_PROVIDER=sentence-transformers
- EMBEDDING_MODEL=intfloat/multilingual-e5-large

# Параметры RAG
- SEMANTIC_SEARCH_TOP_K=10
- RAG_CONTEXT_SOURCES=5
- RAG_MAX_CONTEXT_LENGTH=8000
```

### 2. Новый volume для кэша моделей

```yaml
volumes:
  - sentence-transformers-cache:/root/.cache/torch/sentence_transformers
```

Это ускоряет перезапуск контейнера - модель не нужно загружать заново.

### 3. Увеличенные ресурсы

```yaml
deploy:
  resources:
    limits:
      memory: 4G
    reservations:
      memory: 2G
```

Модель эмбеддингов требует ~2 ГБ RAM.

## Быстрый старт

### 1. Создайте файл с переменными окружения

Создайте `.env` файл в корне проекта:

```bash
# Обязательные переменные
BOT_TOKEN=your_telegram_bot_token
ANTHROPIC_API_KEY=your_anthropic_api_key

# Опционально: для облачных эмбеддингов
# OPENAI_API_KEY=your_openai_key
# COHERE_API_KEY=your_cohere_key
```

### 2. Запустите контейнеры

```bash
docker-compose up -d
```

### 3. Проверьте логи

```bash
docker-compose logs -f telegram-bot
```

Вы должны увидеть:
```
✅ Базы данных инициализированы
✅ Векторная база данных инициализирована
✅ Бот запущен!
```

## Конфигурация

### Использование локальных эмбеддингов (по умолчанию)

**Преимущества:**
- ✅ Бесплатно
- ✅ Работает офлайн
- ✅ Приватность данных

**Недостатки:**
- ❌ Требует 2-4 ГБ RAM
- ❌ Первый запуск медленный (~5-10 минут)

```yaml
environment:
  - EMBEDDING_PROVIDER=sentence-transformers
  - EMBEDDING_MODEL=intfloat/multilingual-e5-large
```

### Использование OpenAI эмбеддингов

**Преимущества:**
- ✅ Высокое качество
- ✅ Низкие требования к RAM
- ✅ Быстрый запуск

**Недостатки:**
- ❌ Требует API ключ
- ❌ Платно (~$0.10 за 1М токенов)

```yaml
environment:
  - EMBEDDING_PROVIDER=openai
  - EMBEDDING_MODEL=text-embedding-3-small
  - OPENAI_API_KEY=${OPENAI_API_KEY}
```

### Использование Cohere эмбеддингов

**Преимущества:**
- ✅ Оптимизировано для поиска
- ✅ Низкие требования к RAM

**Недостатки:**
- ❌ Требует API ключ
- ❌ Платно

```yaml
environment:
  - EMBEDDING_PROVIDER=cohere
  - EMBEDDING_MODEL=embed-multilingual-v3.0
  - COHERE_API_KEY=${COHERE_API_KEY}
```

## Отключение RAG

Если RAG не нужен или возникают проблемы:

```yaml
environment:
  - ENABLE_RAG=false
  - ENABLE_VECTOR_DB=false
```

И уменьшите лимиты памяти:

```yaml
deploy:
  resources:
    limits:
      memory: 1G
    reservations:
      memory: 512M
```

## Volumes

### Постоянные данные

```yaml
volumes:
  - ./data:/app/data              # Chroma DB, статистика
  - ./logs:/app/logs              # Логи
  - sentence-transformers-cache   # Кэш моделей
```

### Очистка кэша моделей

Если нужно освободить место:

```bash
docker volume rm telegram_bot_analytic_sentence-transformers-cache
```

При следующем запуске модель загрузится заново.

## Мониторинг

### Проверка использования ресурсов

```bash
docker stats telegram-content-analyzer
```

Ожидаемое потребление:
- **CPU**: 10-30% (пики при векторизации)
- **RAM**: 2-3 ГБ (с локальными эмбеддингами)
- **Disk**: ~3 ГБ (модель + данные)

### Логи

```bash
# Все логи
docker-compose logs -f

# Только бот
docker-compose logs -f telegram-bot

# Последние 100 строк
docker-compose logs --tail=100 telegram-bot
```

## Производительность

### Первый запуск

При первом запуске с локальными эмбеддингами:
1. Загрузка модели: 5-10 минут
2. Инициализация Chroma DB: 10-30 секунд
3. Готовность к работе: ~10 минут

### Последующие запуски

С кэшированной моделью:
1. Загрузка из кэша: 30-60 секунд
2. Инициализация: 10 секунд
3. Готовность: ~1 минута

### Векторизация

- Одна статья: 1-2 секунды
- 100 статей: 2-3 минуты
- 1000 статей: 20-30 минут

## Масштабирование

### Для больших баз (>10K статей)

Рассмотрите использование Qdrant вместо Chroma:

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: telegram-bot-qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    networks:
      - bot-network
```

И обновите конфигурацию:

```yaml
environment:
  - VECTOR_DB_PROVIDER=qdrant
  - QDRANT_URL=http://qdrant:6333
```

## Troubleshooting

### Проблема: Out of Memory

**Решение 1**: Увеличьте лимит памяти

```yaml
deploy:
  resources:
    limits:
      memory: 6G
```

**Решение 2**: Используйте облачные эмбеддинги

```yaml
environment:
  - EMBEDDING_PROVIDER=openai
```

### Проблема: Медленный запуск

**Причина**: Загрузка модели эмбеддингов

**Решение**: Используйте volume для кэша (уже настроено)

### Проблема: Ошибка "Chroma DB not initialized"

**Решение**: Проверьте права на директорию

```bash
chmod -R 777 ./data
docker-compose restart telegram-bot
```

### Проблема: Модель не загружается

**Решение**: Проверьте интернет и место на диске

```bash
df -h
docker system df
```

## Обновление

### Обновление образа

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Сохранение данных

Все данные сохраняются в volumes:
- Chroma DB: `./data/chroma_db`
- MongoDB: `./mongodb_data`
- PostgreSQL: `./postgres_data`

При обновлении они не удаляются.

## Backup

### Backup векторной БД

```bash
# Создать архив
tar -czf chroma_backup_$(date +%Y%m%d).tar.gz ./data/chroma_db

# Восстановить
tar -xzf chroma_backup_20250108.tar.gz -C ./data/
```

### Полный backup

```bash
docker-compose down
tar -czf full_backup_$(date +%Y%m%d).tar.gz \
  ./data \
  ./mongodb_data \
  ./postgres_data \
  ./logs
docker-compose up -d
```

## Production рекомендации

1. **Используйте secrets для API ключей**
```yaml
secrets:
  anthropic_key:
    external: true
```

2. **Настройте мониторинг**
- Prometheus + Grafana
- Health checks
- Alerts

3. **Регулярные backups**
- Автоматический backup раз в день
- Хранение в S3/облаке

4. **Reverse proxy**
- Nginx для Mongo Express
- SSL сертификаты

5. **Логирование**
- Централизованное логирование (ELK stack)
- Ротация логов

---

**Версия**: 1.0.0
**Дата**: 2025-01-08

