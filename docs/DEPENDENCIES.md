# 📦 Управление зависимостями

## Обзор оптимизации

Зависимости разделены на **базовые** и **дополнительные** для гибкой установки в зависимости от потребностей.

## Конфигурации установки

### 1. Минимальная (рекомендуется для Docker)

```bash
pip install -r requirements.txt
```

**Включает:**
- ✅ Telegram Bot API
- ✅ Claude API (Anthropic)
- ✅ PostgreSQL + MongoDB
- ✅ Chroma DB (client режим)
- ✅ OpenAI эмбеддинги
- ✅ Базовый TTS (gTTS)
- ✅ PDF генерация
- ✅ Базовая аналитика

**Размер:** ~200 МБ  
**RAM:** 512 МБ - 1 ГБ  
**Время установки:** 2-3 минуты

### 2. Полная (с локальными эмбеддингами)

```bash
pip install -r requirements.txt -r requirements-extras.txt
```

**Дополнительно включает:**
- ✅ Sentence-Transformers
- ✅ PyTorch + Transformers
- ✅ Локальные модели эмбеддингов
- ✅ Расширенный TTS (pyttsx3)
- ✅ Cohere API
- ✅ Расширенная аналитика
- ✅ ML библиотеки

**Размер:** ~2-3 ГБ  
**RAM:** 2-4 ГБ  
**Время установки:** 10-15 минут

### 3. Только для разработки

```bash
pip install -r requirements.txt
pip install pytest black flake8 mypy
```

**Для разработки и тестирования**

## Сравнение конфигураций

| Функция | Минимальная | Полная |
|---------|-------------|--------|
| Telegram Bot | ✅ | ✅ |
| RAG + Claude | ✅ | ✅ |
| OpenAI Embeddings | ✅ | ✅ |
| Локальные Embeddings | ❌ | ✅ |
| Chroma Client | ✅ | ✅ |
| Chroma Embedded | ❌ | ✅ |
| TTS (gTTS) | ✅ | ✅ |
| TTS (pyttsx3) | ❌ | ✅ |
| Базовая аналитика | ✅ | ✅ |
| ML аналитика | ❌ | ✅ |
| Cohere API | ❌ | ✅ |

## Docker конфигурации

### Минимальная (production)

```dockerfile
# В Dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

```yaml
# В docker-compose.yml
telegram-bot:
  environment:
    - EMBEDDING_PROVIDER=openai
    - CHROMA_HOST=chromadb
  deploy:
    resources:
      limits:
        memory: 1G
```

### Полная (development)

```dockerfile
# В Dockerfile
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-extras.txt
```

```yaml
# В docker-compose.yml
telegram-bot:
  environment:
    - EMBEDDING_PROVIDER=sentence-transformers
    - VECTOR_DB_PATH=/app/data/chroma_db
  deploy:
    resources:
      limits:
        memory: 4G
```

## Переменные окружения

### Для минимальной конфигурации

```bash
# Обязательные
BOT_TOKEN=your_token
ANTHROPIC_API_KEY=your_key
OPENAI_API_KEY=your_openai_key

# RAG
ENABLE_RAG=true
ENABLE_VECTOR_DB=true
CHROMA_HOST=chromadb
EMBEDDING_PROVIDER=openai
```

### Для полной конфигурации

```bash
# Дополнительно
EMBEDDING_PROVIDER=sentence-transformers
VECTOR_DB_PATH=/app/data/chroma_db
TTS_DEFAULT_ENGINE=pyttsx3
COHERE_API_KEY=your_cohere_key
```

## Оптимизация по размеру

### Исключение ненужных зависимостей

```bash
# Только для OpenAI эмбеддингов (без torch)
pip install --no-deps chromadb
pip install httpx numpy

# Без pandas (если не нужна аналитика)
pip uninstall pandas

# Без TTS (если не нужно озвучивание)
pip uninstall gTTS pyttsx3
```

### Использование slim образов

```dockerfile
FROM python:3.11-slim
# Вместо python:3.11 (экономия ~300 МБ)
```

## Версионирование

### Закрепленные версии (production)

```
# Точные версии для стабильности
chromadb==0.5.3
openai==1.12.0
anthropic==0.52.2
```

### Гибкие версии (development)

```
# Диапазоны для обновлений
chromadb>=0.5.0,<0.6.0
openai>=1.12.0,<2.0.0
anthropic>=0.50.0,<1.0.0
```

## Решение проблем совместимости

### ARM64 (Apple Silicon)

```bash
# Автоматически выбирается правильная версия
pip install -r requirements-extras.txt
# onnxruntime-silicon для M1/M2 Mac
```

### Linux x86_64

```bash
# Стандартная установка
pip install -r requirements-extras.txt
# onnxruntime для Intel/AMD
```

### Windows

```bash
# Может потребоваться Visual C++
pip install -r requirements.txt
# Для полной установки нужен Visual Studio Build Tools
```

## Мониторинг зависимостей

### Проверка уязвимостей

```bash
pip install safety
safety check -r requirements.txt
```

### Обновление зависимостей

```bash
pip install pip-tools
pip-compile --upgrade requirements.in
```

### Анализ размера

```bash
pip install pipdeptree
pipdeptree --packages chromadb
```

## Альтернативные конфигурации

### Только Qdrant (вместо Chroma)

```bash
pip install qdrant-client
# Вместо chromadb
```

### Только локальные модели

```bash
pip install sentence-transformers torch
# Без openai, cohere
```

### Только облачные API

```bash
pip install openai cohere
# Без sentence-transformers, torch
```

## Рекомендации

### Для production

1. **Используйте минимальную конфигурацию**
2. **Закрепите точные версии**
3. **Используйте OpenAI эмбеддинги**
4. **Отдельный контейнер для Chroma**

### Для development

1. **Используйте полную конфигурацию**
2. **Гибкие версии для обновлений**
3. **Локальные эмбеддинги для экспериментов**
4. **Embedded Chroma для простоты**

### Для CI/CD

1. **Кэшируйте зависимости**
2. **Используйте multi-stage builds**
3. **Проверяйте уязвимости**
4. **Тестируйте обе конфигурации**

## Troubleshooting

### Ошибка установки torch

```bash
# Используйте CPU версию
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### Ошибка onnxruntime

```bash
# Проверьте архитектуру
python -c "import platform; print(platform.machine())"
# Установите правильную версию
```

### Конфликт версий

```bash
# Создайте чистое окружение
python -m venv fresh_env
source fresh_env/bin/activate
pip install -r requirements.txt
```

---

**Рекомендация:** Начните с минимальной конфигурации и добавляйте зависимости по мере необходимости.
