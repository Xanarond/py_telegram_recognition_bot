#!/bin/bash
# Скрипт для запуска миграции контента в Docker контейнере

set -e

CONTAINER_NAME="telegram-content-analyzer"

echo "🔍 Проверяем статус контейнера..."
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Контейнер $CONTAINER_NAME не запущен!"
    echo "Запустите: docker-compose up -d"
    exit 1
fi

echo "✅ Контейнер найден"

# Проверяем аргументы
if [ "$1" == "--migrate" ]; then
    echo "🚀 Запускаем миграцию существующего контента..."
    docker exec "$CONTAINER_NAME" python scripts/migrate_existing_content.py --migrate
elif [ "$1" == "--check" ]; then
    echo "🔍 Проверяем статус векторизации..."
    docker exec "$CONTAINER_NAME" python scripts/migrate_existing_content.py --check
else
    echo "📊 Использование:"
    echo "  ./scripts/docker_migrate.sh --check    # Проверить статус"
    echo "  ./scripts/docker_migrate.sh --migrate  # Запустить миграцию"
    echo ""
    echo "🔍 Проверяем статус по умолчанию..."
    docker exec "$CONTAINER_NAME" python scripts/migrate_existing_content.py --check
fi

