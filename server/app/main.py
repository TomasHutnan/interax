from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import create_pool
from app.routers import (
    auth,
    health,
    interactions,
    medications,
    regimens,
    repo,
    scan,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = create_pool()
    pool.open()
    app.state.pool = pool
    try:
        yield
    finally:
        pool.close()


app = FastAPI(title="InteraX API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(health.router)
app.include_router(interactions.router)
app.include_router(medications.router)
app.include_router(regimens.router)
app.include_router(repo.router)
app.include_router(scan.router)

