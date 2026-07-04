import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from .config import settings
from .routers import analytics, audit, auth, cameras, events, gates, health, notifications, parking, reports, sites, system, tariffs, users, visitor_passes, watchlists, alerts, ws, webhooks
from .routers import stream

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(sites.router, prefix="/sites", tags=["sites"])
app.include_router(cameras.router, prefix="/cameras", tags=["cameras"])
app.include_router(events.router, prefix="/events", tags=["events"])
app.include_router(watchlists.router, prefix="/watchlists", tags=["watchlists"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(parking.router, prefix="/parking-sessions", tags=["parking"])
app.include_router(tariffs.router, prefix="/tariffs", tags=["tariffs"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(gates.router, prefix="/gates", tags=["gates"])
app.include_router(visitor_passes.router, prefix="/visitor-passes", tags=["visitor-passes"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(stream.router, prefix="/stream", tags=["stream"])
app.include_router(system.router, prefix="/system", tags=["system"])
app.include_router(audit.router, prefix="/audit-logs", tags=["audit"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(ws.router, prefix="/ws", tags=["websocket"])

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"
    return response
