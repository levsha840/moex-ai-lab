"""MOEX AI Terminal — FastAPI backend.

Thin API layer over existing project services.
Reads from: data/, reports/, hypotheses/, services/
Writes nothing. No broker API. No real trading.

Run from project root:
    python -m terminal.backend.main
or:
    uvicorn terminal.backend.main:app --reload --port 8000
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(
    title="MOEX AI Terminal API",
    version="1.0.0",
    description="Research terminal for MOEX AI LAB — read-only, no real trading.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from terminal.backend.routers import dashboard, research, strategies, paper, knowledge, scientist

app.include_router(dashboard.router,   prefix="/api/dashboard",  tags=["Dashboard"])
app.include_router(research.router,    prefix="/api/research",   tags=["Research"])
app.include_router(strategies.router,  prefix="/api/strategies", tags=["Strategies"])
app.include_router(paper.router,       prefix="/api/paper",      tags=["Paper"])
app.include_router(knowledge.router,   prefix="/api/knowledge",  tags=["Knowledge"])
app.include_router(scientist.router,   prefix="/api/scientist",  tags=["Scientist"])


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0", "lab": "MOEX AI LAB"}


if __name__ == "__main__":
    uvicorn.run(
        "terminal.backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(ROOT / "terminal" / "backend")],
    )
