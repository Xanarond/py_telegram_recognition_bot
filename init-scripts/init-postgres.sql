-- Инициализационный скрипт для PostgreSQL
-- Создает базу данных и пользователя для Telegram бота

-- Создаем пользователя, если он не существует
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'bot_user') THEN
        CREATE USER bot_user WITH PASSWORD 'bot_password';
    END IF;
END
$$;

-- Создаем базу данных, если она не существует
CREATE DATABASE telegram_bot_users WITH OWNER bot_user;

-- Подключаемся к созданной базе данных
\c telegram_bot_users

-- Предоставляем все привилегии пользователю
GRANT ALL PRIVILEGES ON DATABASE telegram_bot_users TO bot_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO bot_user;

-- Создаем расширение для работы с UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Создаем расширение для полнотекстового поиска на русском языке
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Комментарий для проверки успешного выполнения скрипта
SELECT 'Инициализация PostgreSQL завершена успешно' as result; 