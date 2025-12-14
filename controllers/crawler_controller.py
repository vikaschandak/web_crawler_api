from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from models.schemas import BatchCrawlResponse, CrawlHistoryResponse, CrawlResponse
from services.crawler_service import CrawlerService

router = APIRouter()
crawler_service = CrawlerService()


@router.get("/crawl", response_model=CrawlResponse)
async def crawl_url(
    url: str = Query(..., description="URL to crawl and extract metadata from"),
    force_refresh: bool = Query(False, description="Force re-crawl even if cached"),
):
    """
    Crawl a given URL and extract metadata including title, description, body content, and topics.

    - **url**: The URL to crawl (e.g., Amazon product page)
    - **force_refresh**: If True, bypass cache and perform fresh crawl
    """
    try:
        result = await crawler_service.crawl_and_analyze(url, force_refresh)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/history", response_model=list[CrawlHistoryResponse])
async def get_crawl_history(
    limit: int = Query(10, ge=1, le=100, description="Number of records to return"),
    skip: int = Query(0, ge=0, description="Number of records to skip (pagination)"),
):
    """
    Get crawl history with pagination.

    - **limit**: Maximum number of records to return (1-100)
    - **skip**: Number of records to skip for pagination
    """
    try:
        history = await crawler_service.get_history(limit, skip)
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/crawl/{crawl_id}", response_model=CrawlResponse)
async def get_crawl_by_id(crawl_id: str):
    """
    Retrieve a specific crawl result by MongoDB ObjectId.

    - **crawl_id**: The MongoDB ObjectId of the crawl record
    """
    try:
        result = await crawler_service.get_by_id(crawl_id)
        if not result:
            raise HTTPException(status_code=404, detail="Crawl record not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/search/topic", response_model=list[CrawlResponse])
async def search_by_topic(
    topic: str = Query(..., description="Topic to search for"),
    limit: int = Query(10, ge=1, le=100, description="Number of results to return"),
):
    """
    Search crawled pages by topic.

    - **topic**: Topic keyword to search for
    - **limit**: Maximum number of results (1-100)
    """
    try:
        results = await crawler_service.search_by_topic(topic, limit)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/stats")
async def get_stats():
    """
    Get database statistics including total crawls and page types.
    """
    try:
        stats = await crawler_service.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/crawl/batch", response_model=BatchCrawlResponse)
async def batch_crawl_urls(
    file: UploadFile = File(
        ..., description="Text file containing line-separated URLs"
    ),
    force_refresh: bool = Query(False, description="Force re-crawl even if cached"),
):
    """
    Crawl multiple URLs from a text file containing line-separated URLs.

    - **file**: Text file with one URL per line
    - **force_refresh**: If True, bypass cache and perform fresh crawl for all URLs
    """
    try:
        # Validate file type
        if not file.filename.endswith((".txt", ".text")):
            raise HTTPException(
                status_code=400, detail="File must be a text file (.txt or .text)"
            )

        # Read file content
        content = await file.read()
        urls_text = content.decode("utf-8")

        # Parse URLs from file (one per line)
        urls = [
            url.strip()
            for url in urls_text.split("\n")
            if url.strip() and not url.strip().startswith("#")
        ]

        if not urls:
            raise HTTPException(
                status_code=400, detail="No valid URLs found in the file"
            )

        # Perform batch crawl
        result = await crawler_service.batch_crawl_urls(urls, force_refresh)
        return result

    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400, detail="File must be UTF-8 encoded text file"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
