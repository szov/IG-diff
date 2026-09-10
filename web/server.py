import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse
from filelock import FileLock
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from igdiff import exporter
from igdiff.config import DATA_FILE, parse_args, resolve_headless, resolve_profile_dir
from igdiff.log_config import setup_logging

setup_logging()
load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = str(DATA_FILE)
LOCK_PATH = DATA_PATH + ".lock"
TEMPLATE = ROOT_DIR / "web" / "templates" / "index.html"
API_KEY = os.getenv("IG_API_KEY")
if not API_KEY:
    raise RuntimeError(
        "IG_API_KEY is not set. Copy .env.example to .env and set IG_API_KEY "
        "(refusing to start: without it /data and /trigger would be unauthenticated)."
    )

# CLI overrides, set in __main__. Defaults to headed.
SERVER_PROFILE_DIR: Path | None = None
SERVER_HEADLESS: bool | None = None


def current_profile() -> Path:
    if SERVER_PROFILE_DIR is not None:
        return SERVER_PROFILE_DIR
    return resolve_profile_dir()


def current_headless() -> bool:
    if SERVER_HEADLESS is not None:
        return SERVER_HEADLESS
    return resolve_headless()


def reset_stale_state():
    if not os.path.exists(DATA_PATH):
        return
    try:
        with FileLock(LOCK_PATH):
            with open(DATA_PATH, "r") as f:
                data = json.load(f)
            if data.get("status") == "running":
                logger.warning("Found stale 'running' state, resetting to idle")
                data["status"] = "idle"
                data["stage"] = "idle"
                data["message"] = "Ready"
                with open(DATA_PATH, "w") as f:
                    json.dump(data, f)
    except Exception as e:
        logger.error(f"Failed to reset stale state: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up: resetting stale state...")
    reset_stale_state()
    yield
    logger.info("Shutting down...")


app = FastAPI(lifespan=lifespan)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/":
            return await call_next(request)
        key = request.query_params.get("key") or request.headers.get("X-API-Key")
        if key != API_KEY:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


app.add_middleware(AuthMiddleware)


@app.get("/")
def home():
    return FileResponse(str(TEMPLATE))


@app.get("/data")
def get_data():
    if not os.path.exists(DATA_PATH):
        return {"status": "idle"}
    with FileLock(LOCK_PATH):
        with open(DATA_PATH, "r") as f:
            data = json.load(f)
    return data


def set_stage(stage, message):
    with FileLock(LOCK_PATH):
        data = {}
        if os.path.exists(DATA_PATH):
            try:
                with open(DATA_PATH, "r") as f:
                    data = json.load(f)
            except Exception:
                pass
        data["status"] = "running"
        data["stage"] = stage
        data["message"] = message
        with open(DATA_PATH, "w") as f:
            json.dump(data, f)


def run_export_task():
    logger.info("Export task started")
    logger.info(f"Profile: {current_profile()} | headless={current_headless()}")
    try:
        set_stage("starting", "Starting browser...")
        logger.info("Running Instagram automation...")
        set_stage("processing", "Processing export data...")
        not_following_back, fans = asyncio.run(
            exporter.run_export_flow(current_profile(), current_headless())
        )
        set_stage("analyzing", "Computing results...")
        result = {
            "status": "done",
            "stage": "complete",
            "message": "Updated just now",
            "not_following_back": not_following_back,
            "fans": fans,
            "updated_at": datetime.now().isoformat(),
        }
        logger.info("Export completed successfully")
        logger.info(f"  - Not following back: {len(not_following_back)}")
        logger.info(f"  - Fans: {len(fans)}")
    except Exception as e:
        logger.error(f"Export failed: {str(e)[:200]}")
        result = {"status": "error", "stage": "error", "message": str(e)}
    with FileLock(LOCK_PATH):
        with open(DATA_PATH, "w") as f:
            json.dump(result, f)
    logger.info("Export task finished")


@app.post("/trigger")
def trigger(background_tasks: BackgroundTasks):
    logger.info("Trigger received, starting export task")
    set_stage("starting", "Initializing...")
    background_tasks.add_task(run_export_task)
    return {"message": "Started"}


if __name__ == "__main__":
    import sys

    args = parse_args(sys.argv[1:])
    SERVER_PROFILE_DIR = args.profile_dir
    SERVER_HEADLESS = args.headless
    logger.info(f"Profile: {SERVER_PROFILE_DIR} | headless={SERVER_HEADLESS}")
    logger.info("Starting server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
