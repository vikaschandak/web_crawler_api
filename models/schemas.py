from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class CrawlResponse(BaseModel):
    """Response model for crawled data"""

    id: Optional[str] = None
    url: str = Field(..., description="The crawled URL")
    title: str = Field(default="", description="Page title")
    description: str = Field(default="", description="Page meta description")
    body: str = Field(default="", description="Extracted body content (truncated)")
    keywords: List[str] = Field(default_factory=list, description="Meta keywords")
    topics: List[str] = Field(
        default_factory=list, description="Extracted topics from content"
    )
    og_data: Dict[str, str] = Field(
        default_factory=dict, description="Open Graph metadata"
    )
    word_count: int = Field(default=0, description="Word count of body content")
    page_type: str = Field(default="unknown", description="Classified page type")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "url": "https://www.amazon.com/product/B009GQ034C",
                "title": "Cuisinart CPT-122 Compact 2-Slice Toaster",
                "description": "Amazon.com: Cuisinart CPT-122 Compact 2-Slice Toaster",
                "body": "Cuisinart CPT-122 Compact 2-Slice Toaster features...",
                "keywords": ["toaster", "kitchen", "cuisinart"],
                "topics": ["e-commerce", "product", "toaster", "kitchen", "appliance"],
                "og_data": {"title": "Cuisinart Toaster", "type": "product"},
                "word_count": 450,
                "page_type": "amazon_product_page",
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00",
            }
        }


class CrawlHistoryResponse(BaseModel):
    """Response model for crawl history"""

    id: str
    url: str
    title: str
    page_type: str
    created_at: str
    updated_at: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "url": "https://www.amazon.com/product/B009GQ034C",
                "title": "Cuisinart CPT-122 Compact 2-Slice Toaster",
                "page_type": "amazon_product_page",
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00",
            }
        }


class BatchCrawlResponse(BaseModel):
    """Response model for batch crawl operation"""

    total_urls: int = Field(..., description="Total number of URLs in the file")
    successful: int = Field(..., description="Number of successfully crawled URLs")
    failed: int = Field(..., description="Number of failed crawl attempts")
    results: List[CrawlResponse] = Field(
        default_factory=list, description="List of crawl results"
    )
    errors: List[Dict[str, str]] = Field(
        default_factory=list, description="List of errors for failed URLs"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total_urls": 3,
                "successful": 2,
                "failed": 1,
                "results": [],
                "errors": [
                    {"url": "https://invalid-url.com", "error": "Invalid URL format"}
                ],
            }
        }


class ErrorResponse(BaseModel):
    """Error response model"""

    detail: str = Field(..., description="Error message")

    class Config:
        json_schema_extra = {"example": {"detail": "Invalid URL format"}}
