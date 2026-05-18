from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import scheduler
from .config import settings
from .db import close_pool, get_pool
from .routers import faces, people, photos, search, suggestions


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await get_pool()
    scheduler.start()
    yield
    scheduler.stop()
    await close_pool()


app = FastAPI(title="Marist Time Machine — API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(photos.router)
app.include_router(people.router)
app.include_router(faces.router)
app.include_router(search.router)
app.include_router(suggestions.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
