from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.modules.inference.router import router as inference_router

app = FastAPI(title="Text Analysis")

# API routes
app.include_router(inference_router, prefix="/api/inference", tags=["inference"])

# Static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    return FileResponse(static_dir / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
