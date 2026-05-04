import os
import asyncio
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from routes.camera_routes import router as camera_routes
from routes.node_routes import router as node_routes, send_heartbeat, mark_offline, _node_state
from routes.stream_proxy import router as stream_proxy
from routes.webrtc_routes import router as webrtc_routes
from services.face_sync import face_sync_loop, sync_state
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


def _get_access_token():
    """Returns the current access token from node state, or None."""
    return _node_state.get("access_token")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch heartbeat + face sync background tasks
    heartbeat_task = asyncio.create_task(_heartbeat_loop())
    sync_task = asyncio.create_task(face_sync_loop(_get_access_token))
    yield
    # Shutdown: cancel tasks, mark node offline
    heartbeat_task.cancel()
    sync_task.cancel()
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
app.include_router(webrtc_routes)  # /webrtc/{camera_id}/whep


@app.get("/")
async def read_root():
    return {"message": "CVSentry Desktop Client Node", "base_url": NODE_BASE_URL, "port": NODE_PORT}


@app.get("/sync/status")
async def get_sync_status():
    """Returns the current face sync status for the UI to poll."""
    return {
        "is_syncing": sync_state["is_syncing"],
        "last_sync": sync_state["last_sync"],
        "last_error": sync_state["last_error"],
        "faces_synced": sync_state["faces_synced"],
    }
