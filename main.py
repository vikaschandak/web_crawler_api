import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from controllers.crawler_controller import router as crawler_router
from database.database import init_db

app = FastAPI(
    title="Web Crawler API",
    description="A scalable web crawler API for extracting metadata and topics from URLs",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize database
@app.on_event("startup")
async def startup_event():
    await init_db()


@app.on_event("shutdown")
async def shutdown_event():
    from database.database import close_db

    await close_db()


# Include routers
app.include_router(crawler_router, prefix="/api/v1", tags=["crawler"])


@app.get("/")
async def root():
    return {"message": "Web Crawler API", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
