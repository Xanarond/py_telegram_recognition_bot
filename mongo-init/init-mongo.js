// Инициализационный скрипт для MongoDB
// Создает базу данных и пользователя для Telegram бота

// Подключаемся к базе данных admin для создания пользователя
db = db.getSiblingDB('admin');

// Создаем пользователя для работы с базой данных
db.createUser({
    user: "admin",
    pwd: "admin_password",
    roles: [
        { role: "userAdminAnyDatabase", db: "admin" },
        { role: "readWriteAnyDatabase", db: "admin" }
    ]
});

// Подключаемся к нашей базе данных
db = db.getSiblingDB('telegram_bot_analytics');

// Создаем коллекции
db.createCollection('synopses');
db.createCollection('user_sources');
db.createCollection('domain_stats');

// Создаем индексы для коллекции синопсисов
db.synopses.createIndex({ "user_id": 1, "created_at": -1 });
db.synopses.createIndex({ "url": 1 }, { unique: true });
db.synopses.createIndex({ "domain": 1 });
db.synopses.createIndex({ "category": 1 });
db.synopses.createIndex({ "priority_level": 1 });
db.synopses.createIndex({ "read_status": 1 });
db.synopses.createIndex({ "rating": -1 });
db.synopses.createIndex({ "user_id": 1, "rating": -1 });
db.synopses.createIndex({ "tags": 1 });
db.synopses.createIndex({ 
    "title": "text", 
    "summary": "text", 
    "key_points": "text" 
}, {
    weights: {
        "title": 10,
        "summary": 5,
        "key_points": 3
    },
    name: "content_search_index"
});

// Создаем индексы для коллекции источников пользователей
db.user_sources.createIndex({ "user_id": 1, "timestamp": -1 });
db.user_sources.createIndex({ "user_id": 1, "read_status": 1 });
db.user_sources.createIndex({ "source_id": 1 }, { unique: true });

// Создаем индексы для коллекции статистики по доменам
db.domain_stats.createIndex({ "domain": 1 }, { unique: true });
db.domain_stats.createIndex({ "total_analyses": -1 });

// Выводим сообщение об успешной инициализации
print("Инициализация MongoDB завершена успешно"); 