"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
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

app.include_router(system.router)
app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(buyer.router)
app.include_router(approvals.router)
app.include_router(merchant.router)
app.include_router(audit.router)
app.include_router(webhooks.router)
app.include_router(drills.router)
