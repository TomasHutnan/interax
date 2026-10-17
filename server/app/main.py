import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import create_pool
from app.routers import (
    auth,
    dictate,
    health,
    interactions,
    medications,
    regimens,
    scan,
    uploads,
)
from app.upload_expiry import UploadExpiry


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = create_pool()
    pool.open()
    app.state.pool = pool
    upload_expiry = UploadExpiry(pool, settings.upload_ttl)
    upload_expiry.start()
    app.state.upload_expiry = upload_expiry
    try:
        yield
    finally:
        upload_expiry.stop()
        pool.close()


app = FastAPI(title="InteraX API", lifespan=lifespan)

log = logging.getLogger(__name__)


# Registered before CORS so it runs inside it: unhandled errors would otherwise
# reach Starlette's outermost error handler and go out without CORS headers,
# which the browser reports as a CORS failure instead of a 500.
@app.middleware("http")
async def catch_unhandled_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500, content={"detail": "internal server error"}
        )


app.add_middleware(
    CORSMiddleware,
    # Any origin may call the API. Credentials (cookies) stay disabled: browsers
    # reject `Access-Control-Allow-Origin: *` on credentialed requests.
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dictate.router)
app.include_router(health.router)
app.include_router(interactions.router)
app.include_router(medications.router)
app.include_router(regimens.router)
app.include_router(scan.router)
app.include_router(uploads.router)
