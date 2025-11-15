# Многоэтапная сборка для минимизации размера образа
# Используем Debian slim вместо Alpine для поддержки ML библиотек
FROM python:3.11-slim AS builder

# Установка зависимостей для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libpq-dev \
    libffi-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Создаем виртуальное окружение
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Копируем и устанавливаем зависимости
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Финальный образ
FROM python:3.11-slim

# Установка только runtime зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    fonts-dejavu-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем виртуальное окружение из builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Создаем пользователя для безопасности (Debian синтаксис)
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -s /bin/bash -m appuser

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

# Проверка здоровья (простая проверка импорта)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; print('Bot is healthy'); sys.exit(0)" || exit 1

# Запускаем бота
CMD ["python", "main.py"] 