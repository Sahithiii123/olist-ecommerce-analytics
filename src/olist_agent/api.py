"""Authenticated local API and Prometheus metrics."""

import hmac
import os
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from olist_agent.agent import answer

REQUESTS = Counter("olist_requests_total", "Agent requests", ["status"])
LATENCY = Histogram("olist_request_seconds", "Agent response latency")
app = FastAPI(title="Olist analytics agent")


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("OLIST_API_KEY")
    if not expected or not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid API key")


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    model: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics", dependencies=[Depends(require_key)])
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/ask", dependencies=[Depends(require_key)])
def ask(request: Question) -> dict:
    model = request.model or os.getenv("OLIST_MODEL", "gpt-4o-mini")
    allowed = os.getenv("OLIST_MODELS", os.getenv("OLIST_MODEL", "gpt-4o-mini")).split(",")
    if model not in allowed:
        raise HTTPException(status_code=400, detail="Model not permitted")
    base = Path(os.getenv("OLIST_OUTPUT_DIR", "artifacts"))
    if not (base / "olist.duckdb").is_file():
        raise HTTPException(status_code=503, detail="Run the pipeline before asking questions")
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not set on the server")
    start = time.perf_counter()
    try:
        result = answer(request.question, model, base / "olist.duckdb", base)
    except Exception:
        REQUESTS.labels(status="error").inc()
        raise
    else:
        REQUESTS.labels(status="ok").inc()
        return result
    finally:
        LATENCY.observe(time.perf_counter() - start)