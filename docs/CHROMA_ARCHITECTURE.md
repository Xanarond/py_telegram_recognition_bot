# 🏗️ Архитектура Chroma DB

## Обзор

Chroma DB теперь работает как **отдельный сервис** в Docker Compose, что обеспечивает:

- ✅ Лучшую изоляцию
- ✅ Независимое масштабирование
- ✅ Упрощенное обслуживание
- ✅ Меньшую нагрузку на контейнер бота

## Архитектура

```
┌─────────────────┐
│  Telegram Bot   │
│   (Python)      │
└────────┬────────┘
         │ HTTP Client
         ▼
┌─────────────────┐
│   Chroma DB     │
│   (Server)      │
│   Port: 8000    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Persistent     │
│  Storage        │
│  ./chroma_data  │
└─────────────────┘
```

## Docker Compose конфигурация

### Chroma DB сервис

```yaml
chromadb:
  image: chromadb/chroma:latest
  container_name: telegram-bot-chromadb
  restart: unless-stopped
  environment:
    - IS_PERSISTENT=TRUE
    - ANONYMIZED_TELEMETRY=FALSE
    - ALLOW_RESET=TRUE
  volumes:
    - ./chroma_data:/chroma/chroma
  ports:
    - "8000:8000"
  networks:
    - bot-network
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
    interval: 30s
    timeout: 10s
    retries: 3
```

### Telegram Bot конфигурация

```yaml
telegram-bot:
  environment:
    - CHROMA_HOST=chromadb
    - CHROMA_PORT=8000
    - EMBEDDING_PROVIDER=openai
    - OPENAI_API_KEY=${OPENAI_API_KEY}
  depends_on:
    chromadb:
      condition: service_healthy
```

## Режимы работы

### Client Mode (текущий)

**Используется когда:** `CHROMA_HOST` установлен

```python
# Автоматически определяется в vector_manager.py
if CHROMA_HOST:
    client = chromadb.HttpClient(
        host=CHROMA_HOST,
        port=CHROMA_PORT
    )
```

**Преимущества:**

- Отдельный процесс для Chroma
- Независимое масштабирование
- Меньше памяти для бота
- Можно использовать из нескольких клиентов

**Недостатки:**

- Дополнительный контейнер
- Сетевая задержка (минимальная)

### Embedded Mode (альтернатива)

**Используется когда:** `CHROMA_HOST` не установлен

```python
# Fallback на embedded режим
client = chromadb.PersistentClient(
    path="./data/chroma_db"
)
```

**Преимущества:**

- Проще для разработки
- Нет сетевых запросов
- Один контейнер

**Недостатки:**

- Больше памяти для бота
- Сложнее масштабировать

## Использование

### Запуск

```bash
# Запустить все сервисы
docker-compose up -d

# Проверить статус Chroma
docker-compose logs chromadb

# Проверить health
curl http://localhost:8000/api/v1/heartbeat
```

### Доступ к Chroma API

Chroma предоставляет REST API на порту 8000:

```bash
# Список коллекций
curl http://localhost:8000/api/v1/collections

# Heartbeat
curl http://localhost:8000/api/v1/heartbeat

# Версия
curl http://localhost:8000/api/v1/version
```

### Web UI (опционально)

Можно добавить Chroma Admin UI:

```yaml
chroma-admin:
  image: ghcr.io/amikos-tech/chromadb-admin:latest
  ports:
    - "3000:3000"
  environment:
    - CHROMA_SERVER_URL=http://chromadb:8000
  depends_on:
    - chromadb
  networks:
    - bot-network
```

## Мониторинг

### Логи

```bash
# Логи Chroma
docker-compose logs -f chromadb

# Логи бота (включая запросы к Chroma)
docker-compose logs -f telegram-bot
```

### Метрики

```bash
# Использование ресурсов
docker stats telegram-bot-chromadb

# Размер данных
du -sh ./chroma_data
```

### Health Check

```bash
# Проверка здоровья
docker-compose ps chromadb

# Должно быть: healthy
```

## Производительность

### Сравнение режимов

| Метрика | Embedded | Client (Server) |
|---------|----------|-----------------|
| Latency | ~10ms | ~15ms |
| Memory (Bot) | 2-4 GB | 512 MB |
| Memory (Chroma) | - | 1-2 GB |
| Scalability | Low | High |
| Isolation | None | Full |

### Оптимизация

**1. Кэширование на стороне клиента**

```python
# В vector_manager.py можно добавить кэш
from functools import lru_cache

@lru_cache(maxsize=100)
def search_cached(query: str):
    return self.search_similar(query)
```

**2. Batch операции**

```python
# Векторизация пакетами
await vectorization_service.batch_vectorize(documents)
```

**3. Connection pooling**

```python
# Переиспользование HTTP соединений
client = chromadb.HttpClient(
    host=CHROMA_HOST,
    port=CHROMA_PORT,
    settings=Settings(
        chroma_client_auth_provider="token",
        chroma_client_auth_credentials="your-token"
    )
)
```

## Backup и восстановление

### Backup

```bash
# Остановить Chroma для консистентности
docker-compose stop chromadb

# Создать backup
tar -czf chroma_backup_$(date +%Y%m%d).tar.gz ./chroma_data

# Запустить снова
docker-compose start chromadb
```

### Восстановление

```bash
# Остановить Chroma
docker-compose stop chromadb

# Восстановить данные
rm -rf ./chroma_data
tar -xzf chroma_backup_20250108.tar.gz

# Запустить
docker-compose start chromadb
```

### Автоматический backup

Добавьте в cron:

```bash
# Ежедневный backup в 3:00
0 3 * * * cd /opt/projects/telegram_bot_analytic && \
  docker-compose stop chromadb && \
  tar -czf backups/chroma_$(date +\%Y\%m\%d).tar.gz ./chroma_data && \
  docker-compose start chromadb
```

## Масштабирование

### Вертикальное масштабирование

Увеличьте ресурсы для Chroma:

```yaml
chromadb:
  deploy:
    resources:
      limits:
        memory: 4G
        cpus: '2'
      reservations:
        memory: 2G
        cpus: '1'
```

### Горизонтальное масштабирование

Для больших нагрузок используйте Qdrant:

```yaml
qdrant:
  image: qdrant/qdrant:latest
  ports:
    - "6333:6333"
  volumes:
    - ./qdrant_data:/qdrant/storage
```

## Troubleshooting

### Chroma не запускается

**Проблема:** `unhealthy` статус

**Решение:**

```bash
# Проверьте логи
docker-compose logs chromadb

# Проверьте порт
netstat -tulpn | grep 8000

# Пересоздайте контейнер
docker-compose up -d --force-recreate chromadb
```

### Бот не подключается к Chroma

**Проблема:** Connection refused

**Решение:**

```bash
# Проверьте network
docker network inspect telegram_bot_analytic_bot-network

# Проверьте переменные окружения
docker-compose config | grep CHROMA

# Проверьте доступность
docker-compose exec telegram-bot curl http://chromadb:8000/api/v1/heartbeat
```

### Медленные запросы

**Проблема:** Поиск занимает >1 секунду

**Решение:**

1. Проверьте размер коллекции
2. Добавьте индексы
3. Увеличьте ресурсы Chroma
4. Используйте кэширование

### Ошибки памяти

**Проблема:** OOM killer убивает Chroma

**Решение:**

```yaml
chromadb:
  deploy:
    resources:
      limits:
        memory: 8G  # Увеличьте лимит
```

## Миграция с Embedded на Client

Если вы использовали embedded режим:

```bash
# 1. Остановите бота
docker-compose stop telegram-bot

# 2. Скопируйте данные
cp -r ./data/chroma_db/* ./chroma_data/

# 3. Обновите docker-compose.yml (уже сделано)

# 4. Запустите все сервисы
docker-compose up -d

# 5. Проверьте логи
docker-compose logs -f telegram-bot
```

## Production рекомендации

1. **Используйте authentication**

```yaml
chromadb:
  environment:
    - CHROMA_SERVER_AUTH_PROVIDER=token
    - CHROMA_SERVER_AUTH_CREDENTIALS=your-secure-token
```

1. **Настройте SSL/TLS**

```yaml
chromadb:
  environment:
    - CHROMA_SERVER_SSL_ENABLED=true
```

1. **Регулярные backups**

- Ежедневные автоматические backups
- Хранение в S3/облаке
- Тестирование восстановления

1. **Мониторинг**

- Prometheus метрики
- Grafana дашборды
- Алерты на ошибки

1. **Rate limiting**

```yaml
chromadb:
  environment:
    - CHROMA_SERVER_RATE_LIMIT=100
```

---

**Версия**: 2.0.0  
**Дата**: 2025-01-08  
**Режим**: Client (Server)
