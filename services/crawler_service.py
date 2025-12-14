import re
from collections import Counter
from typing import List, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from database.database import get_db
from models.schemas import BatchCrawlResponse, CrawlHistoryResponse, CrawlResponse


class CrawlerService:
    def __init__(self):
        self.db = get_db()
        self.timeout = httpx.Timeout(30.0, connect=10.0)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    async def crawl_and_analyze(
        self, url: str, force_refresh: bool = False
    ) -> CrawlResponse:
        """Main method to crawl URL and extract metadata"""
        # Validate URL
        if not self._is_valid_url(url):
            raise ValueError("Invalid URL format")

        # Check cache if not forcing refresh
        if not force_refresh:
            cached = await self.db.get_by_url(url)
            if cached:
                return cached

        # Perform crawl
        html_content = await self._fetch_page(url)
        metadata = self._extract_metadata(html_content, url)
        topics = self._classify_and_extract_topics(html_content, metadata)

        # Prepare response
        response = CrawlResponse(
            url=url,
            title=metadata.get("title", ""),
            description=metadata.get("description", ""),
            body=metadata.get("body", ""),
            keywords=metadata.get("keywords", []),
            topics=topics,
            og_data=metadata.get("og_data", {}),
            word_count=metadata.get("word_count", 0),
            page_type=metadata.get("page_type", "unknown"),
        )

        # Save to database
        id = await self.db.save_crawl(response)
        response.id = id

        return response

    async def _fetch_page(self, url: str) -> str:
        """Fetch HTML content from URL using httpx (async, scalable)"""
        async with httpx.AsyncClient(
            timeout=self.timeout, headers=self.headers, follow_redirects=True
        ) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
            except httpx.HTTPStatusError as e:
                raise ValueError(f"HTTP error occurred: {e.response.status_code}")
            except httpx.RequestError as e:
                raise ValueError(f"Request error occurred: {str(e)}")

    def _extract_metadata(self, html: str, url: str) -> dict:
        """Extract metadata from HTML using BeautifulSoup4"""
        soup = BeautifulSoup(html, "lxml")

        # Extract title
        title = ""
        if soup.title:
            title = soup.title.string.strip() if soup.title.string else ""
        if not title:
            h1 = soup.find("h1")
            title = h1.get_text(strip=True) if h1 else ""

        # Extract meta description
        description = ""
        meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find(
            "meta", attrs={"property": "og:description"}
        )
        if meta_desc:
            description = meta_desc.get("content", "")

        # Extract keywords
        keywords = []
        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        if meta_keywords:
            keywords = [k.strip() for k in meta_keywords.get("content", "").split(",")]

        # Extract body content (removing scripts, styles, etc.)
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        body_text = soup.get_text(separator=" ", strip=True)
        body_text = re.sub(r"\s+", " ", body_text)[:5000]  # Limit to 5000 chars

        # Extract Open Graph data
        og_data = {}
        og_tags = soup.find_all("meta", property=re.compile(r"^og:"))
        for tag in og_tags:
            prop = tag.get("property", "").replace("og:", "")
            og_data[prop] = tag.get("content", "")

        # Word count
        word_count = len(body_text.split())

        # Detect page type
        page_type = self._detect_page_type(url, soup, title)

        return {
            "title": title,
            "description": description,
            "body": body_text,
            "keywords": keywords,
            "og_data": og_data,
            "word_count": word_count,
            "page_type": page_type,
        }

    def _classify_and_extract_topics(self, html: str, metadata: dict) -> List[str]:
        """Classify page and extract relevant topics"""
        soup = BeautifulSoup(html, "lxml")

        # Combine all text for analysis
        all_text = f"{metadata.get('title', '')} {metadata.get('description', '')} {metadata.get('body', '')}"
        all_text = all_text.lower()

        # Extract headings
        headings = []
        for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
            text = tag.get_text(strip=True)
            if text:
                headings.append(text)

        # Topic extraction based on frequency and relevance
        words = re.findall(r"\b[a-z]{3,}\b", all_text)

        # Filter out common stop words
        stop_words = {
            "the",
            "and",
            "for",
            "with",
            "this",
            "that",
            "from",
            "have",
            "been",
            "are",
            "was",
            "were",
            "but",
            "not",
            "you",
            "all",
            "can",
            "her",
            "his",
            "they",
            "she",
            "what",
            "when",
            "where",
            "who",
            "how",
            "why",
        }

        words = [w for w in words if w not in stop_words and len(w) > 3]

        # Count frequency
        word_freq = Counter(words)

        # Get top words as topics
        topics = [word for word, count in word_freq.most_common(15) if count > 1]

        # Add headings as topics if relevant
        for heading in headings[:5]:
            heading_lower = heading.lower()
            if heading_lower not in topics and len(heading_lower.split()) <= 3:
                topics.append(heading_lower)

        return topics[:10]  # Return top 10 topics

    def _detect_page_type(self, url: str, soup: BeautifulSoup, title: str) -> str:
        """Detect the type of page"""

        # Check for common patterns
        if soup.find("article"):
            return "article"
        if soup.find("form", class_=re.compile("search")):
            return "search_page"

        return "general_page"

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    async def get_history(
        self, limit: int = 10, skip: int = 0
    ) -> List[CrawlHistoryResponse]:
        """Get crawl history with pagination"""
        return await self.db.get_history(limit, skip)

    async def get_by_id(self, crawl_id: str) -> Optional[CrawlResponse]:
        """Get crawl by MongoDB ObjectId"""
        return await self.db.get_by_id(crawl_id)

    async def search_by_topic(self, topic: str, limit: int = 10) -> List[CrawlResponse]:
        """Search crawls by topic"""
        return await self.db.search_by_topic(topic, limit)

    async def full_text_search(
        self, query: str, limit: int = 10
    ) -> List[CrawlResponse]:
        """Full-text search across content"""
        return await self.db.full_text_search(query, limit)

    async def get_stats(self) -> dict:
        """Get database statistics"""
        return await self.db.get_stats()

    async def batch_crawl_urls(
        self, urls: List[str], force_refresh: bool = False
    ) -> BatchCrawlResponse:
        """
        Crawl multiple URLs from a list
        Returns a batch response with all results and errors
        """
        import asyncio

        results = []
        errors = []
        successful = 0
        failed = 0

        # Create tasks for all URLs to crawl in parallel
        async def crawl_single_url(url: str):
            try:
                result = await self.crawl_and_analyze(url, force_refresh)
                return {"success": True, "url": url, "result": result}
            except Exception as e:
                return {"success": False, "url": url, "error": str(e)}

        # Execute all crawls in parallel
        tasks = [crawl_single_url(url.strip()) for url in urls if url.strip()]
        crawl_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for crawl_result in crawl_results:
            if isinstance(crawl_result, Exception):
                failed += 1
                errors.append({"url": "unknown", "error": str(crawl_result)})
            elif crawl_result.get("success"):
                results.append(crawl_result["result"])
                successful += 1
            else:
                failed += 1
                errors.append(
                    {"url": crawl_result["url"], "error": crawl_result["error"]}
                )

        return BatchCrawlResponse(
            total_urls=len(urls),
            successful=successful,
            failed=failed,
            results=results,
            errors=errors,
        )
