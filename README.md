# Web Crawler API

A scalable FastAPI-based web crawler service for extracting metadata, content, and topics from web pages. Designed to handle large-scale crawling operations with support for batch processing and efficient data storage.

## Features

- **Single URL Crawling**: Extract metadata from individual URLs
- **Batch Processing**: Process multiple URLs from text files
- **Metadata Extraction**: Title, description, keywords, Open Graph data
- **Topic Classification**: Automatic topic extraction from content
- **Crawl History**: Track and retrieve crawl history with pagination
- **Search Capabilities**: Search crawled pages by topic
- **MongoDB Storage**: Persistent storage with efficient indexing
- **Docker Support**: Easy deployment with Docker Compose

## Tech Stack

- **FastAPI**: Modern, fast web framework for building APIs
- **MongoDB**: Document database for storing crawl metadata
- **Motor**: Async MongoDB driver
- **httpx**: Async HTTP client for web requests
- **BeautifulSoup4**: HTML parsing and content extraction
- **Pydantic**: Data validation and serialization

## Installation

### Prerequisites

- Python 3.8+
- MongoDB (or use Docker Compose)
- pip

## Docker Setup

1. Build and run with Docker Compose:
```bash
docker-compose up -d
```

This will start:
- MongoDB on port 27017
- Web Crawler API on port 8000

2. View API documentation:
Visit `http://localhost:8000/docs` for interactive API documentation

## API Endpoints

### Single URL Crawl
```
GET /api/v1/crawl?url=<URL>&force_refresh=false
```

### Batch Crawl
```
POST /api/v1/crawl/batch
Content-Type: multipart/form-data
Body: file (text file with one URL per line)
```

### Crawl History
```
GET /api/v1/history?limit=10&skip=0
```

### Get Crawl by ID
```
GET /api/v1/crawl/{crawl_id}
```

### Search by Topic
```
GET /api/v1/search/topic?topic=<topic>&limit=10
```

### Statistics
```
GET /api/v1/stats
```

### Health Check
```
GET /health
```

## Project Structure

```
web_crawler_api/
├── controllers/          # API route handlers
├── services/            # Business logic
├── models/              # Pydantic schemas
├── database/            # Database connection and setup
├── docs/                # Design and implementation documentation
├── main.py              # FastAPI application entry point
├── requirements.txt     # Python dependencies
├── docker-compose.yml   # Docker Compose configuration
└── Dockerfile           # Docker image definition
```

## Documentation

- **Design Documentation**: See `docs/DESIGN.md` for architecture and scalability design
- **Implementation Plan**: See `docs/ENGINEERING_IMPLEMENTATION_PLAN.md` for detailed implementation guide
- **API Documentation**: Interactive docs available at `/docs` when the server is running

## License

[MIT]
