"""
FastAPI application factory.

Lifespan:
  startup  — warm up the DB connection pool
  shutdown — dispose the DB engine (closes all pooled connections)
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.database import engine


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: verify at least one connection can be established
    async with engine.connect():
        pass
    yield
    # Shutdown: release all pooled connections
    await engine.dispose()


app = FastAPI(title="FinPulse API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(v1_router)
