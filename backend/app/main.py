import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.clients.coindcx import CoinDCXError
from app.config import get_settings
from app.market_data.runtime import MarketDataRuntime


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    runtime = MarketDataRuntime(settings)
    application.state.market_data_runtime = runtime
    await runtime.start()
    try:
        yield
    finally:
        await runtime.stop()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Read-only CoinDCX USDT futures market-data service",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(CoinDCXError)
async def coindcx_error_handler(_: Request, exc: CoinDCXError) -> JSONResponse:
    structlog.get_logger().warning("coindcx_public_request_failed", error=str(exc))
    return JSONResponse(status_code=502, content={"detail": "CoinDCX market data is unavailable"})


app.include_router(router)
