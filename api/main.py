from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import configs, jobs, results
from api.ws.log_streamer import router as ws_router

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = PROJECT_ROOT / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="FanC(fd) Web API",
    description="FastAPI wrapper around the FanC(fd) CLI pipeline.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(configs.router)
app.include_router(jobs.router)
app.include_router(results.router)
app.include_router(ws_router)

app.mount(
    "/files/runs",
    StaticFiles(directory=str(RUNS_DIR), check_dir=False),
    name="runs",
)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

