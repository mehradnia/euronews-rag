import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from src.config.database import Base, engine
from src.modules.conversation.router import router as conversation_router
from src.modules.inference.router import router as inference_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import src.modules.conversation.models  # noqa: F401 — register ORM models

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables synced")
    yield
    await engine.dispose()


app = FastAPI(title="Text Analysis", lifespan=lifespan)

# API routes
app.include_router(inference_router, prefix="/api/inference", tags=["inference"])
app.include_router(conversation_router, prefix="/api/conversation", tags=["conversation"])

# Static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    return FileResponse(static_dir / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
