# Data Storage Architecture

## Overview
Multi-database storage system combining MongoDB, PostgreSQL, and ChromaDB for different data types and access patterns.

## Database Components

### MongoDB (`mongodb_manager.py`)
- **Purpose**: Store content data, synopses, and analysis results
- **Connection**: Async with Motor driver
- **Collections**:
  - `content`: Analyzed web content
  - `synopses`: Generated summaries
  - `analyses`: AI analysis results
- **Features**:
  - TTL indexes for data expiration
  - Aggregation pipelines for analytics
  - Full-text search capabilities

### PostgreSQL (`postgres_manager.py`)
- **Purpose**: Store user data, authorization, and relational data
- **Connection**: Async with SQLAlchemy
- **Models**:
  - `users`: User accounts and preferences
  - `authorizations`: Access control lists
  - `sessions`: User session data
- **Features**:
  - ACID compliance
  - Complex queries and joins
  - Data integrity constraints

### ChromaDB (`vector_manager.py`)
- **Purpose**: Store vector embeddings for semantic search
- **Type**: Vector database
- **Collections**: Per-user content isolation
- **Features**:
  - Cosine similarity search
  - Metadata filtering
  - Incremental updates

## Database Manager (`database_manager.py`)
- **Purpose**: Unified interface for all database operations
- **Features**:
  - Connection pooling
  - Health monitoring
  - Graceful shutdown
  - Migration support

## Data Models

### Content Document (MongoDB)
```json
{
  "_id": " ObjectId",
  "user_id": 123456789,
  "url": "https://example.com/article",
  "title": "Article Title",
  "content": "Full text content...",
  "summary": "AI-generated summary",
  "topics": ["topic1", "topic2"],
  "analyzed_at": "2024-01-01T00:00:00Z",
  "domain": "example.com"
}
```

### User Model (PostgreSQL)
```sql
CREATE TABLE users (
  id BIGINT PRIMARY KEY,
  username VARCHAR(255),
  first_name VARCHAR(255),
  last_name VARCHAR(255),
  is_authorized BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_active TIMESTAMP
);
```

### Vector Document (ChromaDB)
- **ID**: Content hash or UUID
- **Embedding**: Vector representation
- **Metadata**: User ID, URL, title, timestamp
- **Document**: Original text content

## Migration System (`migration_manager.py`)
- **Purpose**: Data migration from JSON to databases
- **Triggers**: First run or version upgrade
- **Process**:
  1. Detect existing JSON data
  2. Transform to database format
  3. Batch insert with transactions
  4. Validate migration success
  5. Archive original files

## Configuration
```python
# MongoDB
MONGODB_URL = "mongodb://localhost:27017"
MONGODB_DATABASE = "telegram_bot_analytics"

# PostgreSQL
POSTGRES_HOST = "localhost"
POSTGRES_PORT = "5432"
POSTGRES_DB = "telegram_bot_users"
POSTGRES_USER = "bot_user"
POSTGRES_PASSWORD = "bot_password"

# ChromaDB
VECTOR_DB_PATH = "data/chroma_db"
VECTOR_DB_PROVIDER = "chroma"
```

## Performance Optimizations
- Connection pooling for all databases
- Async/await for non-blocking operations
- Batch operations for bulk data
- Index optimization for query patterns
- Caching layer for frequent queries

## Backup and Recovery
- MongoDB: mongodump/mongorestore
- PostgreSQL: pg_dump/pg_restore
- ChromaDB: Directory backup
- Automated backup scripts
- Data retention policies

## Monitoring
- Health check endpoints
- Connection pool metrics
- Query performance logging
- Error rate tracking
- Storage usage monitoring