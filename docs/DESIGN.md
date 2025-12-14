# Design Documentation: Operationalizing Billion-URL Web Crawler

## Executive Summary

This document outlines the architecture, storage design, data schema, operational requirements (SLOs/SLAs), and monitoring strategy for scaling the web crawler API to process billions of URLs from text file inputs.

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Storage Design](#2-storage-design)
3. [Unified Data Schema](#3-unified-data-schema)
4. [Processing Pipeline for Billions of URLs](#4-processing-pipeline-for-billions-of-urls)
5. [SLOs and SLAs](#5-slos-and-slas)
6. [Monitoring Metrics and Tools](#6-monitoring-metrics-and-tools)
7. [Optimization Strategies](#7-optimization-strategies)

---

## 1. System Architecture

### 1.1 High-Level Architecture

The system will use a distributed, microservices-based architecture with the following components:

```
┌─────────────────┐
│  URL File Input │
│  (Billions)     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  URL Queue Manager                  │
│  - RabbitMQ/Kafka (URL ingestion)   │
│  - Deduplication layer              │
│  - Priority queue                   │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Crawler Workers (Horizontal Scale) │
│  - FastAPI workers (async)          │
│  - Rate limiting per domain         │
│  - Retry logic with exponential backoff│
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Data Processing Pipeline            │
│  - Metadata extraction               │
│  - Content analysis                  │
│  - Topic classification              │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Storage Layer                       │
│  ├─ MongoDB (Metadata + Indexes)    │
│  ├─ S3/GCS (Full HTML Content)      │
│  └─ Redis (Cache + Rate Limiting)   │
└─────────────────────────────────────┘
```

### 1.2 Component Breakdown

**URL Ingestion Service**

- Accepts large text files (billions of URLs)
- Validates and normalizes URLs
- Deduplicates using Bloom filters or Redis
- Distributes to message queue

**Crawler Workers**

- Horizontally scalable FastAPI instances
- Async HTTP clients (httpx) with connection pooling
- Domain-based rate limiting (respect robots.txt)
- Circuit breakers for failing domains

**Storage Services**

- MongoDB: Metadata, indexes, search capabilities
- Object Storage (S3/GCS): Full HTML content, compressed
- Redis: Caching, rate limiting, deduplication

## 2. Storage Design

### 2.1 Hybrid Storage Architecture

**MongoDB Collections:**

1. **crawls** (Metadata Collection)

   - Stores lightweight metadata
   - Indexed for fast queries
   - Estimated size: ~2-5KB per document
   - For 1B URLs: ~2-5TB

2. **crawl_history** (Time-series data)

   - Tracks crawl attempts, status, timestamps
   - Partitioned by date for efficient queries
   - Used for monitoring and analytics

3. **domains** (Domain metadata)

   - Rate limit tracking
   - robots.txt cache
   - Domain-level statistics

**Object Storage (S3/GCS):**

- **Full HTML Content**: Compressed (gzip) HTML files
- **Structure**: `s3://bucket/crawls/{year}/{month}/{day}/{url_hash}.html.gz`
- **Estimated size**: ~50-200KB per page (compressed)
- **For 1B URLs**: ~50-200TB

**Redis:**

- URL deduplication cache (TTL: 7 days)
- Rate limiting counters per domain
- Recent crawl results cache (TTL: 1 hour)

### 2.2 Data Lifecycle Management

- **Hot Data** (last 30 days): MongoDB + Object Storage
- **Warm Data** (30-90 days): Object Storage only, MongoDB metadata
- **Cold Data** (90+ days): Archive to Glacier/Archive storage, metadata in MongoDB

## 3. Unified Data Schema

### 3.1 MongoDB Document Schema

```python
{
    "_id": ObjectId,
    "url": str,  # Indexed, normalized
    "url_hash": str,  # SHA256 hash for deduplication
    "domain": str,  # Extracted domain, indexed
    "metadata": {
        "title": str,
        "description": str,
        "keywords": List[str],
        "og_data": Dict[str, str],
        "word_count": int,
        "page_type": str,  # article, product, general, etc.
        "language": str,  # ISO 639-1 code
        "content_type": str,  # text/html, application/json, etc.
    },
    "content": {
        "body_text": str,  # Truncated to 5000 chars
        "full_html_path": str,  # S3/GCS path
        "content_hash": str,  # SHA256 of full HTML
    },
    "topics": List[str],  # Extracted topics, indexed
    "crawl_metadata": {
        "status": str,  # success, failed, timeout, blocked
        "status_code": int,
        "response_time_ms": int,
        "crawl_duration_ms": int,
        "retry_count": int,
        "error_message": str,  # If failed
        "user_agent": str,
        "redirects": List[str],
    },
    "timestamps": {
        "created_at": datetime,
        "updated_at": datetime,
        "first_crawled_at": datetime,
        "last_crawled_at": datetime,
    },
    "version": int,  # Schema version for migrations
}
```

### 3.2 Indexes

```python
# Primary indexes
db.crawls.create_index("url", unique=True)
db.crawls.create_index("url_hash", unique=True)
db.crawls.create_index("domain")
db.crawls.create_index([("created_at", -1)])
db.crawls.create_index([("last_crawled_at", -1)])

# Search indexes
db.crawls.create_index("topics")
db.crawls.create_index([("metadata.title", "text"), ("metadata.description", "text")])
db.crawls.create_index("metadata.page_type")

# Compound indexes
db.crawls.create_index([("domain", 1), ("last_crawled_at", -1)])
db.crawls.create_index([("crawl_metadata.status", 1), ("created_at", -1)])
```

### 3.3 Object Storage Schema

**File Naming Convention:**

```
{url_hash}.html.gz
```

**Metadata File (JSON):**

```
{url_hash}.meta.json
{
    "url": "original_url",
    "crawled_at": "ISO8601",
    "content_type": "text/html",
    "content_length": 12345,
    "compressed_length": 4567,
    "encoding": "gzip"
}
```

## 4. Processing Pipeline for Billions of URLs

### 4.1 URL Ingestion Flow

1. **File Upload & Validation**

   - Accept text file via API or direct S3 upload
   - Stream processing (don't load entire file into memory)
   - Validate URLs in batches
   - Generate URL hashes for deduplication

2. **Deduplication**

   - Check Redis cache for recent crawls
   - Check MongoDB for existing URLs
   - Use Bloom filter for initial filtering (probabilistic)

3. **Queue Distribution**

   - Partition URLs by domain for rate limiting
   - Distribute to multiple queues (by domain hash)
   - Priority queues for high-value domains

### 4.2 Crawling Strategy

**Rate Limiting:**

- Per-domain rate limits (respect robots.txt)
- Global rate limit to prevent overwhelming infrastructure
- Adaptive rate limiting based on response times

**Retry Logic:**

- Exponential backoff: 1s, 2s, 4s, 8s, 16s
- Max 3 retries for transient errors
- Dead letter queue for permanent failures

**Parallelism:**

- Worker pool: 100-1000 concurrent workers
- Domain-based concurrency limits
- Connection pooling per worker

### 4.3 Data Processing

1. **HTML Parsing** (BeautifulSoup)
2. **Metadata Extraction** (existing logic)
3. **Content Compression** (gzip)
4. **Storage** (MongoDB + S3 in parallel)
5. **Indexing** (async index updates)

## 5. SLOs and SLAs

### 5.1 Service Level Objectives (SLOs)

**Availability:**

- **Target**: 99.9% uptime (8.76 hours downtime/year)
- **Measurement**: API health check endpoint availability

**Latency:**

- **P50**: < 2 seconds per URL crawl
- **P95**: < 10 seconds per URL crawl
- **P99**: < 30 seconds per URL crawl

**Throughput:**

- **Target**: 10,000 URLs/minute per worker
- **Scalable**: Add workers to increase throughput linearly

**Data Quality:**

- **Success Rate**: > 95% of valid URLs successfully crawled
- **Data Completeness**: > 98% of crawled pages have required metadata fields

**Storage:**

- **Durability**: 99.999999999% (11 nines) for object storage
- **Consistency**: Strong consistency for metadata, eventual for content

### 5.2 Service Level Agreements (SLAs)

**For API Consumers:**

- **Response Time**: 95% of requests complete within 10 seconds
- **Availability**: 99.5% uptime guarantee
- **Data Freshness**: URLs re-crawled within 7 days of last crawl (configurable)

**Error Handling:**

- **Transient Errors**: Automatic retry with exponential backoff
- **Permanent Errors**: Logged to dead letter queue, notification sent
- **Error Rate**: < 5% of total crawl attempts

## 6. Monitoring Metrics and Tools

### 6.1 Key Metrics

**System Metrics:**

- CPU, Memory, Disk I/O per worker
- Network bandwidth utilization
- Database connection pool usage
- Queue depth (messages waiting)

**Application Metrics:**

- Crawl success rate (%)
- Crawl failure rate by error type
- Average response time per domain
- URLs processed per minute/hour/day
- Queue processing rate
- Retry rate

**Business Metrics:**

- Total URLs crawled (cumulative)
- Unique URLs crawled
- Duplicate rate
- Storage growth rate (GB/day)
- Cost per URL crawled

**Error Metrics:**

- HTTP error codes (4xx, 5xx) distribution
- Timeout rate
- Rate limit hits
- DNS resolution failures
- SSL/TLS errors

### 6.2 Monitoring Tools Stack

**Metrics Collection:**

- **Prometheus**: Time-series metrics storage
- **Grafana/Datadog**: Visualization and dashboards

**Logging:**

- **Datadog**/**ELK Stack**/**Loki**
- Structured logging (JSON format)
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL


**Alerting:**

- **Alertmanager** (Prometheus) or **PagerDuty** or **Datadog Alerts**
- Alert on: High error rate, queue backlog, storage capacity, SLA violations

**APM (Application Performance Monitoring):**

- **Datadog** or **Sentry**
- Real-time performance monitoring
- Error tracking and alerting

### 6.3 Dashboard Requirements

**Operational Dashboard:**

- Real-time crawl rate (URLs/second)
- Success/failure rate
- Queue depth
- Worker health status
- Top error types

**Business Dashboard:**

- Total URLs processed (cumulative)
- Storage usage (MongoDB + Object Storage)
- Cost tracking
- Domain distribution
- Page type distribution

**Performance Dashboard:**

- P50/P95/P99 latency
- Response time by domain
- Throughput trends
- Resource utilization

## 7. Optimization Strategies

### 7.1 Cost Optimization

**Infrastructure:**

- Use spot instances for non-critical workers (70% cost savings)
- Auto-scaling based on queue depth
- Reserved instances for MongoDB (40% savings)
- Object storage lifecycle policies (move to Glacier after 90 days)

**Data Storage:**

- Compress HTML content (gzip: 70-80% reduction)
- Store only metadata in MongoDB, full content in object storage
- Implement data retention policies
- Use columnar storage for analytics (Parquet format)

**Network:**

- CDN for frequently accessed content
- Regional data processing (reduce cross-region transfer costs)
- Batch API calls where possible

**Estimated Costs (1B URLs):**

- Compute: $50,000-100,000 (spot instances)
- MongoDB: $20,000-40,000 (managed cluster)
- Object Storage: $1,000-2,000/month (S3 Standard)
- Network: $5,000-10,000
- **Total First Year**: ~$100,000-150,000

### 7.2 Reliability Optimization

**High Availability:**

- Multi-AZ deployment (MongoDB replica set, workers across zones)
- Health checks and automatic failover
- Circuit breakers for failing services
- Graceful degradation

**Data Durability:**

- MongoDB replica set (3+ nodes)
- Object storage with versioning enabled
- Regular backups (daily snapshots)
- Cross-region replication for critical data

**Error Handling:**

- Comprehensive retry logic
- Dead letter queue for failed URLs
- Error classification (transient vs permanent)
- Automatic recovery from common failures

### 7.3 Performance Optimization

**Crawling:**

- Connection pooling (reuse HTTP connections)
- Async/await for I/O operations
- Batch processing where possible
- Domain-based sharding for parallel processing

**Database:**

- Proper indexing (as defined in schema)
- Read replicas for query load
- Connection pooling
- Query optimization (use projections, limit fields)

**Caching:**

- Redis cache for recent crawls (1 hour TTL)
- CDN for frequently accessed metadata
- In-memory cache for robots.txt

**Processing:**

- Stream processing (don't load entire files)
- Parallel processing with asyncio
- Worker specialization (dedicated workers for specific domains)

### 7.4 Scale Optimization

**Horizontal Scaling:**

- Stateless workers (easy to scale)
- Message queue for decoupling
- Load balancer for API requests
- Auto-scaling based on metrics

**Database Scaling:**

- MongoDB sharding by domain or URL hash
- Read replicas for analytics queries
- Partitioning by date for time-series data

**Storage Scaling:**

- Object storage scales automatically
- Implement partitioning strategy early
- Use content-addressable storage (hash-based)

**Capacity Planning:**

- Monitor queue depth trends
- Predict storage growth
- Plan for 10x scale (design for 10B URLs)
