"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    approvals,
    audit,
    auth,
    buyer,
    catalog,
    drills,
    merchant,
    system,
    webhooks,
)
from app.config import settings
from app.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

DESCRIPTION = """
A bounded AI commerce network: an autonomous Buyer Agent discovers, evaluates and
purchases from an AI-powered Merchant Growth Agent over Razorpay test-mode rails,
with every financial action gated by a deterministic Policy Engine.

**The architectural rule this whole API is built around:** the LLM has no tool,
function or route that reaches the payment gateway. The only interfaces between
the AI layer and money are the Permission Check and the Policy Engine, both of
which are plain Python with no model in the loop.
"""

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    logging.getLogger(__name__).info(
        "%s ready (db=%s)", settings.app_name, settings.database_url.split("://")[0]
    )
    yield


app = FastAPI(
    title=settings.app_name,
    description=DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
@app.head("/")
def root():
    return {
        "status": "ok",
        "app": settings.app_name,
        "docs": "/docs",
        "health": "/health",
    }


ROUTERS = [
    system.router,
    auth.router,
    catalog.router,
    buyer.router,
    approvals.router,
    merchant.router,
    audit.router,
    webhooks.router,
    drills.router,
]

# Include routers at both root and /api prefix so direct calls (/api/...) and standard calls (/...) work seamlessly
api_router = APIRouter(prefix="/api")
for router in ROUTERS:
    app.include_router(router)
    api_router.include_router(router)

app.include_router(api_router)

