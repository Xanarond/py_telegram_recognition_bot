# RAG (Retrieval-Augmented Generation) System

## Overview
Semantic search and knowledge retrieval system enabling users to query their analyzed content database using natural language.

## Core Components

### Vectorization Service (`vectorization_service.py`)
- **Purpose**: Manage vector embeddings and semantic search
- **Input**: Text content and queries
- **Output**: Similar content results with relevance scores
- **Capabilities**:
  - Text embedding generation
  - Vector similarity search
  - Content indexing and retrieval

### Embedding Generator (`embedding_generator.py`)
- **Purpose**: Generate vector embeddings for content
- **Supported Providers**:
  - OpenAI (text-embedding-3-small)
  - Sentence Transformers
  - Cohere
- **Configuration**:
  - Provider selection via `EMBEDDING_PROVIDER`
  - Model selection via `EMBEDDING_MODEL`
  - API key management

### RAG Agent (`rag_agent.py`)
- **Purpose**: Generate answers using retrieved context
- **Input**: User query and retrieved documents
- **Output**: Generated response with citations
- **Features**:
  - Context-aware response generation
  - Source attribution
  - Confidence scoring

### Vector Manager (`vector_manager.py`)
- **Purpose**: Manage ChromaDB vector database operations
- **Operations**:
  - Collection management
  - Document upsert and deletion
  - Similarity queries

## Search Capabilities

### Semantic Search
- **Endpoint**: `/search <query>`
- **Algorithm**: Cosine similarity with configurable threshold
- **Parameters**:
  - `top_k`: Number of results (default: 10)
  - `min_score`: Minimum similarity threshold (0-1)
- **Use Case**: Find articles by meaning, not exact keywords

### Question Answering
- **Endpoint**: `/ask <question>`
- **Process**:
  1. Query embedding generation
  2. Retrieve relevant documents
  3. Context assembly
  4. Response generation with Claude
- **Output**: Answer with source citations

### Content Comparison
- **Endpoint**: `/compare <url1> <url2>`
- **Analysis**: Similarities, differences, key themes
- **Output**: Structured comparison report

### Topic Synthesis
- **Endpoint**: `/synthesize <topic>`
- **Process**: Gather all related content, synthesize insights
- **Output**: Comprehensive topic overview

## Technical Architecture

### Vector Database (ChromaDB)
- **Path**: `data/chroma_db`
- **Collections**: Per-user content isolation
- **Operations**: Async CRUD with connection pooling

### Embedding Pipeline
```
Content → Chunking → Embedding → Vector DB → Query → Search → Context → Response
```

### Configuration
```python
EMBEDDING_PROVIDER = "openai"  # openai, sentence-transformers, cohere
EMBEDDING_MODEL = "text-embedding-3-small"
SEMANTIC_SEARCH_TOP_K = 10
SEMANTIC_SEARCH_MIN_SCORE = 0.5
RAG_CONTEXT_SOURCES = 5
RAG_MAX_CONTEXT_LENGTH = 8000
```

## Performance Considerations
- Batch embedding generation for large documents
- Caching of frequent queries
- Incremental indexing for new content
- Connection pooling for vector database

## Error Handling
- Embedding generation failures → fallback to keyword search
- Vector DB unavailability → graceful degradation
- Rate limiting for embedding APIs
- Timeout handling for large queries