# Telegram Bot Interface

## Overview
Telegram bot providing AI-powered content analysis, RAG-based knowledge retrieval, and analytics for web content.

## Core Commands

### Basic Commands
- `/start` - Welcome message and bot introduction
- `/help` - Usage instructions and command list
- `/stats` - User analysis statistics
- `/sources` - List of analyzed sources with pagination
- `/export` - Export statistics to PDF
- `/clear` - Clear user statistics
- `/clear_source <id>` - Clear specific source data

### RAG Commands
- `/search <query>` - Semantic search across knowledge base
- `/ask <question>` - Ask questions to knowledge base
- `/compare <url1> <url2>` - Compare two articles
- `/synthesize <topic>` - Synthesize information on topic
- `/similar <url>` - Find similar articles
- `/rag_help` - RAG command help

### Analytics Commands
- `/analytics` - Analyze user interests and patterns
- `/trends [days]` - Trending topics over time period
- `/clusters` - Content clustering analysis

### Admin Commands
- `/admin` - Admin panel
- `/users` - List all users
- `/add_user <id>` - Add user to allowed list
- `/remove_user <id>` - Remove user from allowed list
- `/user_info <id>` - Get user information
- `/auth_status` - Check authorization status

## Message Handling
- URL detection and automatic content analysis
- Callback button handling for pagination and actions
- Source detail commands via `/src_<id>` pattern

## Technical Requirements
- Python 3.8+
- python-telegram-bot library
- Async/await pattern for all handlers
- Markdown formatting for messages
- Error handling with user-friendly messages
- Pagination for large data sets

## User Experience
- Processing indicators during AI operations
- Inline keyboard navigation
- Confirmation dialogs for destructive actions
- Responsive design for different screen sizes