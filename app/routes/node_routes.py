import os
import socket
import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from dependencies.auth import verify_token
from dotenv import load_dotenv

load_dotenv()

DJANGO_URL = os.getenv("DJANGO_URL", "http://localhost:8000")
NODE_PORT = int(os.getenv("NODE_PORT", "8001"))
NODE_SRS_PORT = int(os.getenv("NODE_SRS_PORT", "8080"))

router = APIRouter()


def _get_local_ip() -> str:
    """
    Returns the machine's LAN IP (e.g. 192.168.x.x).
    Falls back to 127.0.0.1 if detection fails.
    """
    try:
        # Connect to an external address (doesn't actually send data)
        # to discover which local interface would be used
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


class RegisterPayload(BaseModel):
    label: str = ""
    access_token: str  # The Django JWT token to authenticate with Django backend


# In-memory node state
_node_state = {
    "node_id": None,
    "access_token": None,
    "local_ip": None,
}


@router.post("/register")
async def register_node(payload: RegisterPayload):
    """
    Called by the frontend after successful login.
    Registers this Desktop Client as a node in the Django backend.
    Uses the detected LAN IP so the Dashboard can reach SRS directly.
    """
    token = payload.access_token
    _node_state["access_token"] = token

    local_ip = _get_local_ip()
    _node_state["local_ip"] = local_ip
    base_url = f"http://{local_ip}"

    print(f"[node] 📡 Registering node with IP: {base_url}:{NODE_PORT}")

    try:
        response = requests.post(
            f"{DJANGO_URL}/nodes/register/",
            json={
                "label": payload.label or f"Node @ {local_ip}",
                "base_url": base_url,
                "port": NODE_PORT,
                "srs_port": NODE_SRS_PORT,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if response.status_code == 200:
            node_data = response.json()
            _node_state["node_id"] = node_data.get("id")
            print(f"[node] ✅ Registered as node #{node_data.get('id')} ({base_url})")
            return {"status": "registered", "node": node_data}
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Could not reach Django: {e}")


@router.post("/heartbeat")
async def send_heartbeat():
    """Called by startup background task every 30s."""
    token = _node_state.get("access_token")
    local_ip = _node_state.get("local_ip")
    if not token or not local_ip:
        return {"status": "not_registered"}
    try:
        requests.post(
            f"{DJANGO_URL}/nodes/heartbeat/",
            json={"base_url": f"http://{local_ip}", "port": NODE_PORT},
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
    except Exception:
        pass
    return {"status": "ok"}


@router.post("/cameras/update")
async def update_node_cameras(camera_ids: list[str], payload=Depends(verify_token)):
    """
    Called after camera analysis starts.
    Tells Django which cameras are now active on this node.
    """
    token = _node_state.get("access_token")
    local_ip = _node_state.get("local_ip")
    if not token or not local_ip:
        raise HTTPException(status_code=400, detail="Node not registered. Login first.")
    try:
        requests.post(
            f"{DJANGO_URL}/nodes/cameras/update/",
            json={
                "base_url": f"http://{local_ip}",
                "port": NODE_PORT,
                "camera_ids": camera_ids,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
    except Exception:
        pass
    return {"status": "cameras updated"}


@router.post("/offline")
async def mark_offline():
    """Called on shutdown."""
    token = _node_state.get("access_token")
    local_ip = _node_state.get("local_ip")
    if not token or not local_ip:
        return {"status": "not_registered"}
    try:
        requests.post(
            f"{DJANGO_URL}/nodes/offline/",
            json={"base_url": f"http://{local_ip}", "port": NODE_PORT},
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        _node_state["access_token"] = None
        _node_state["node_id"] = None
        _node_state["local_ip"] = None
    except Exception:
        pass
    return {"status": "offline"}


# ---------------------------------------------------------------------------
# Internal helper — importable by other modules (camera_routes, analyzer)
# ---------------------------------------------------------------------------
import asyncio as _asyncio

async def re_register_node(label: str = ""):
    """
    Re-registers this node with Django using the stored token + auto-detected IP.
    Safe to call at any point — NodeRegisterView uses update_or_create so it is idempotent.
    Call this on login AND every time analysis starts so the node is always visible
    in the dashboard even if it was pruned due to a missed heartbeat window.
    """
    token = _node_state.get("access_token")
    if not token:
        print("[node] ⚠️  re_register_node skipped — no access token stored")
        return

    local_ip = _get_local_ip()
    _node_state["local_ip"] = local_ip
    base_url = f"http://{local_ip}"

    def _post():
        return requests.post(
            f"{DJANGO_URL}/nodes/register/",
            json={
                "label": label or f"Node @ {local_ip}",
                "base_url": base_url,
                "port": NODE_PORT,
                "srs_port": NODE_SRS_PORT,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )

    try:
        await _asyncio.to_thread(_post)
        print(f"[node] 🔄 Node re-registered ({base_url}:{NODE_PORT})")
    except Exception as e:
        print(f"[node] ❌ Re-registration failed: {e}")


async def notify_cameras_active(camera_ids: list[str], reason: str = ""):
    """
    Pushes the active camera list to Django.
    Call this at two points:
      1. When camera analysis starts   → cameras are registered as starting.
      2. When the first frame arrives  → cameras are confirmed live.
    """
    token = _node_state.get("access_token")
    local_ip = _node_state.get("local_ip")
    if not token or not local_ip:
        print(f"[node] ⚠️  notify_cameras_active skipped — node not registered ({reason})")
        return

    def _post():
        return requests.post(
            f"{DJANGO_URL}/nodes/cameras/update/",
            json={
                "base_url": f"http://{local_ip}",
                "port": NODE_PORT,
                "camera_ids": camera_ids,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )

    try:
        await _asyncio.to_thread(_post)
        print(f"[node] 📋 Updated Django with active cameras: {camera_ids} ({reason})")
    except Exception as e:
        print(f"[node] ❌ Failed to update cameras: {e}")


async def send_threat_alert(camera_id: str, frame_id: int, identities: list, alert_type: str = "COMBINED_THREAT"):
    """
    POSTs a threat alert to Django.

    Django endpoint: POST /alerts/create/
    """
    token = _node_state.get("access_token")
    local_ip = _node_state.get("local_ip")
    if not token or not local_ip:
        print(f"[node] ⚠️  send_threat_alert skipped — node not registered")
        return

    import datetime
    payload = {
        "camera_id":  camera_id,
        "frame_id":   str(frame_id),
        "identities": identities,
        "alert_type": alert_type,
        "node_ip":    local_ip,
        "timestamp":  datetime.datetime.utcnow().isoformat() + "Z",
    }

    def _post():
        return requests.post(
            f"{DJANGO_URL}/alerts/create/",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )

    try:
        await _asyncio.to_thread(_post)
        print(f"[node] 🚨 Threat alert ({alert_type}) sent to Django | camera={camera_id} | identities={identities}")
    except Exception as e:
        print(f"[node] ❌ Failed to send threat alert: {e}")
