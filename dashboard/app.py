#!/usr/bin/env python3
"""
Web dashboard dla qwen-agent.
Uruchomienie: python3 dashboard/app.py
Otwórz: http://127.0.0.1:8080
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

AGENT_DIR = Path(__file__).parent.parent
TASKS_DIR = AGENT_DIR / "tasks"
LOGS_DIR = AGENT_DIR / "logs"
OLLAMA_URL = "http://localhost:11434"

app = FastAPI(title="qwen-agent dashboard")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


# ---------- helpers ----------

def _read_tasks(bucket: str) -> list[dict]:
    bucket_dir = TASKS_DIR / bucket
    if not bucket_dir.exists():
        return []
    tasks = []
    for f in sorted(bucket_dir.glob("*.txt"), reverse=True)[:50]:
        tasks.append({
            "name": f.name,
            "content": f.read_text(errors="replace").strip()[:200],
            "mtime": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return tasks


def _read_logs(n_lines: int = 100) -> str:
    log_files = sorted(LOGS_DIR.glob("*.log"), reverse=True)
    if not log_files:
        return "(brak logów)"
    return "\n".join(log_files[0].read_text(errors="replace").splitlines()[-n_lines:])


async def _ollama_models() -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            return r.json().get("models", [])
    except Exception:
        return []


async def _ollama_running() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


# ---------- routes ----------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    models = await _ollama_models()
    pending = _read_tasks("pending")
    done = _read_tasks("done")
    failed = _read_tasks("failed")
    logs = _read_logs(80)
    ollama_ok = await _ollama_running()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "ollama_ok": ollama_ok,
        "models": models,
        "pending": pending,
        "done": done,
        "failed": failed,
        "logs": logs,
        "counts": {"pending": len(list((TASKS_DIR / "pending").glob("*.txt")) if (TASKS_DIR / "pending").exists() else []),
                   "done": len(list((TASKS_DIR / "done").glob("*.txt")) if (TASKS_DIR / "done").exists() else []),
                   "failed": len(list((TASKS_DIR / "failed").glob("*.txt")) if (TASKS_DIR / "failed").exists() else [])},
    })


@app.post("/task/create")
async def create_task(task_text: str = Form(...), repo: str = Form("")):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"task_{ts}.txt"
    (TASKS_DIR / "pending").mkdir(parents=True, exist_ok=True)
    content = task_text
    if repo:
        content = f"REPO:{repo}\n{task_text}"
    (TASKS_DIR / "pending" / fname).write_text(content)
    return JSONResponse({"status": "ok", "task": fname})


@app.post("/task/run-agent")
async def run_agent(repo: str = Form(...)):
    """Uruchom agent_runner.py w tle."""
    runner = AGENT_DIR / "agent_runner.py"
    if not runner.exists():
        return JSONResponse({"status": "error", "msg": "agent_runner.py not found"}, status_code=404)
    subprocess.Popen(
        ["python3", str(runner), "--repo", repo],
        stdout=open(LOGS_DIR / f"dashboard_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", "w"),
        stderr=subprocess.STDOUT,
    )
    return JSONResponse({"status": "started", "repo": repo})


@app.get("/api/status")
async def api_status():
    ollama_ok = await _ollama_running()
    models = await _ollama_models()
    return {
        "ollama": ollama_ok,
        "models": [m["name"] for m in models],
        "tasks": {
            "pending": len(list((TASKS_DIR / "pending").glob("*.txt")) if (TASKS_DIR / "pending").exists() else []),
            "done": len(list((TASKS_DIR / "done").glob("*.txt")) if (TASKS_DIR / "done").exists() else []),
            "failed": len(list((TASKS_DIR / "failed").glob("*.txt")) if (TASKS_DIR / "failed").exists() else []),
        },
    }


@app.get("/api/logs")
async def api_logs(n: int = 100):
    return {"logs": _read_logs(n)}


@app.get("/api/tasks/{bucket}")
async def api_tasks(bucket: str):
    if bucket not in ("pending", "done", "failed"):
        return JSONResponse({"error": "invalid bucket"}, status_code=400)
    return {"tasks": _read_tasks(bucket)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8080, reload=True,
                app_dir=str(Path(__file__).parent))
