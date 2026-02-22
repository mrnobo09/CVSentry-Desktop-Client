import os
import asyncio
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from routes.camera_routes import router as camera_routes
from routes.node_routes import router as node_routes, send_heartbeat, mark_offline
from routes.stream_proxy import router as stream_proxy
from dotenv import load_dotenv

load_dotenv()

NODE_BASE_URL = os.getenv("NODE_BASE_URL", "http://localhost")
NODE_PORT = int(os.getenv("NODE_PORT", "8001"))


async def _heartbeat_loop():
    """Sends a heartbeat to Django every 30 seconds to keep node online."""
    while True:
        await asyncio.sleep(30)
        try:
            await send_heartbeat()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch heartbeat background task
    task = asyncio.create_task(_heartbeat_loop())
    yield
    # Shutdown: cancel heartbeat, mark node offline
    task.cancel()
    try:
        await mark_offline()
    except Exception:
        pass


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Fine for a local desktop app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(camera_routes, prefix="/cameras")
app.include_router(node_routes, prefix="/node")
app.include_router(stream_proxy)   # /stream/{camera_id}.flv


@app.get("/")
async def read_root():
    return {"message": "CVSentry Desktop Client Node", "base_url": NODE_BASE_URL, "port": NODE_PORT}
