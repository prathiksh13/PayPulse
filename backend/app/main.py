# -*- coding: utf-8 -*-
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .routers import (
    agent,
    analytics,
    anomalies,
    cache,
    checkout,
    health,
    mandates,
    notifications,
    payments,
    recovery,
    reports,
    settings_api,
    webhooks,
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Merchant payment operations intelligence API — real data, live detection, safe automated recovery.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


app.include_router(health.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(mandates.router, prefix="/api/mandates")
app.include_router(mandates.router, prefix="/api/upi-mandates")
app.include_router(checkout.router, prefix="/api")
app.include_router(anomalies.router, prefix="/api")
app.include_router(recovery.router, prefix="/api/recovery")
app.include_router(recovery.router, prefix="/api/recovery-actions")
app.include_router(reports.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")
app.include_router(agent.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(cache.router, prefix="/api")