# Content Analytics with Claude AI

## Overview
AI-powered content analysis system using Anthropic Claude for extracting insights, summaries, and structured data from web content.

## Core Components

### Content Analyzer (`content_analyzer.py`)
- **Purpose**: Extract and analyze web content using Claude AI
- **Input**: URL or raw text content
- **Output**: Structured analysis with key insights
- **Capabilities**:
  - Web scraping with BeautifulSoup
  - Content extraction from HTML
  - AI-powered analysis and summarization
  - Domain-specific optimizations

### Summary Agent (`summary_agent.py`)
- **Purpose**: Generate concise summaries of analyzed content
- **Input**: Raw content or analysis results
- **Output**: Structured summary with key points
- **Features**:
  - Multiple summary lengths (brief, detailed)
  - Key points extraction
  - Readability scoring

### Content Analytics (`content_analytics.py`)
- **Purpose**: Analyze user interests and content patterns
- **Input**: User ID and historical data
- **Output**: Analytics insights and recommendations
- **Capabilities**:
  - Interest analysis
  - Trend detection
  - Content clustering

## AI Integration

### Claude API Configuration
- **Model**: claude-haiku-4-5-20251001
- **Temperature**: 0.3 (consistent outputs)
- **Max Tokens**: 7500
- **Timeout**: 30 seconds

### Prompt Engineering
- Structured analysis prompts
- Domain-specific optimizations
- Error handling for API failures
- Rate limiting compliance

## Supported Domains
- habr.com (tech articles)
- youtube.com (video content)
- arxiv.org (research papers)
- github.com (code repositories)
- medium.com (blog posts)
- dev.to (developer content)

## Technical Requirements
- Anthropic Python SDK
- BeautifulSoup4 for HTML parsing
- aiohttp for async HTTP requests
- Retry logic for API failures
- Caching for repeated analyses

## Output Format
```json
{
  "title": "Article Title",
  "summary": "Brief summary",
  "key_points": ["Point 1", "Point 2"],
  "topics": ["topic1", "topic2"],
  "readability_score": 0.85,
  "domain": "habr.com",
  "analyzed_at": "2024-01-01T00:00:00Z"
}
```