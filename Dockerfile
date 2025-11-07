# Многоэтапная сборка для минимизации размера образа
FROM python:3.11-alpine AS builder

# Установка зависимостей для сборки
RUN apk add --no-cache \
    gcc \
    musl-dev \
    postgresql-dev \
    libffi-dev

# Создаем виртуальное окружение
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Копируем и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Финальный образ
FROM python:3.11-alpine

# Установка только runtime зависимостей
RUN apk add --no-cache \
    postgresql-libs \
    libffi \
    ttf-dejavu

# Копируем виртуальное окружение из builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Создаем пользователя для безопасности
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

# Создаем директорию приложения
WORKDIR /app

# Копируем код приложения
COPY --chown=appuser:appgroup . .

# Создаем директории для данных
RUN mkdir -p data logs exports && \
    chown -R appuser:appgroup data logs exports

# Переключаемся на непривилегированного пользователя
USER appuser

# Создаем том для хранения данных
VOLUME ["/app/data", "/app/logs", "/app/exports"]

# Проверка здоровья
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; from storage.database_manager import database_manager; asyncio.run(database_manager.health_check())" || exit 1

# Запускаем бота
CMD ["python", "main.py"] 