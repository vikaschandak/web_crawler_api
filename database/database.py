import os
from datetime import datetime
from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from models.schemas import CrawlHistoryResponse, CrawlResponse

# MongoDB Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "web_crawler")
COLLECTION_NAME = "crawls"


class DatabaseManager:
    """MongoDB Database Manager for crawler operations"""

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.collection = None

    async def connect(self):
        """Connect to MongoDB and setup indexes"""
        self.client = AsyncIOMotorClient(MONGODB_URL)
        self.db = self.client[DATABASE_NAME]
        self.collection = self.db[COLLECTION_NAME]

        # Create indexes for performance
        await self.collection.create_index("url")  # For quick URL lookups
        await self.collection.create_index([("created_at", -1)])  # For history queries
        await self.collection.create_index(
            [("url", 1), ("created_at", -1)]
        )  # Compound index

        print(f"✅ Connected to MongoDB: {DATABASE_NAME}")

    async def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("✅ Disconnected from MongoDB")

    async def save_crawl(self, crawl_data: CrawlResponse) -> str:
        """
        Save or update crawl data
        Returns the document ID
        """
        document = {
            "url": crawl_data.url,
            "title": crawl_data.title,
            "description": crawl_data.description,
            "body": crawl_data.body,
            "keywords": crawl_data.keywords,
            "topics": crawl_data.topics,
            "og_data": crawl_data.og_data,
            "word_count": crawl_data.word_count,
            "page_type": crawl_data.page_type,
            "updated_at": datetime.utcnow(),
        }

        # Check if URL already exists
        existing = await self.collection.find_one(
            {"url": crawl_data.url}, sort=[("created_at", -1)]
        )

        if existing:
            # Update existing document
            result = await self.collection.update_one(
                {"_id": existing["_id"]}, {"$set": document}
            )
            return str(existing["_id"])
        else:
            # Insert new document
            document["created_at"] = datetime.utcnow()
            result = await self.collection.insert_one(document)
            return str(result.inserted_id)

    async def get_by_url(self, url: str) -> Optional[CrawlResponse]:
        """Get most recent crawl data by URL"""
        document = await self.collection.find_one(
            {"url": url}, sort=[("created_at", -1)]
        )

        if document:
            return self._document_to_crawl_response(document)
        return None

    async def get_by_id(self, crawl_id: str) -> Optional[CrawlResponse]:
        """Get crawl data by MongoDB ObjectId"""
        from bson import ObjectId

        try:
            document = await self.collection.find_one({"_id": ObjectId(crawl_id)})
            if document:
                return self._document_to_crawl_response(document)
        except Exception as e:
            print(f"Error fetching by ID: {e}")

        return None

    async def get_history(
        self, limit: int = 10, skip: int = 0
    ) -> List[CrawlHistoryResponse]:
        """
        Get crawl history with pagination
        Supports offset-based pagination for better scaling
        """
        cursor = (
            self.collection.find(
                {},
                {
                    "_id": 1,
                    "url": 1,
                    "title": 1,
                    "page_type": 1,
                    "created_at": 1,
                    "updated_at": 1,
                },
            )
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        documents = await cursor.to_list(length=limit)

        return [
            CrawlHistoryResponse(
                id=str(doc["_id"]),
                url=doc.get("url", ""),
                title=doc.get("title", ""),
                page_type=doc.get("page_type", "unknown"),
                created_at=doc.get("created_at", datetime.utcnow()).isoformat(),
                updated_at=doc.get("updated_at", datetime.utcnow()).isoformat(),
            )
            for doc in documents
        ]

    async def search_by_topic(self, topic: str, limit: int = 10) -> List[CrawlResponse]:
        """
        Search crawls by topic
        Uses MongoDB text search for better performance
        """
        cursor = (
            self.collection.find({"topics": {"$regex": topic, "$options": "i"}})
            .sort("created_at", -1)
            .limit(limit)
        )

        documents = await cursor.to_list(length=limit)
        return [self._document_to_crawl_response(doc) for doc in documents]

    async def get_stats(self) -> dict:
        """Get database statistics"""
        total_crawls = await self.collection.count_documents({})
        unique_domains = await self.collection.distinct("page_type")

        return {
            "total_crawls": total_crawls,
            "unique_page_types": len(unique_domains),
            "page_types": unique_domains,
        }

    def _document_to_crawl_response(self, document: dict) -> CrawlResponse:
        """Convert MongoDB document to CrawlResponse"""
        return CrawlResponse(
            id=str(document["_id"]),
            url=document.get("url", ""),
            title=document.get("title", ""),
            description=document.get("description", ""),
            body=document.get("body", ""),
            keywords=document.get("keywords", []),
            topics=document.get("topics", []),
            og_data=document.get("og_data", {}),
            word_count=document.get("word_count", 0),
            page_type=document.get("page_type", "unknown"),
            created_at=document.get("created_at", datetime.utcnow()).isoformat(),
            updated_at=document.get("updated_at", datetime.utcnow()).isoformat(),
        )


# Global database instance
db_manager = DatabaseManager()


async def init_db():
    """Initialize database connection"""
    await db_manager.connect()


async def close_db():
    """Close database connection"""
    await db_manager.disconnect()


def get_db() -> DatabaseManager:
    """Get database manager instance"""
    return db_manager
