import os
import asyncio
import requests
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from dependencies.auth import verify_node_ownership, optional_token
from dependencies.keys import get_public_key
from dependencies.state import _node_state
from routes.node_routes import _get_local_ip
from services.face_sync import sync_faces
from dotenv import load_dotenv

load_dotenv()

DJANGO_URL = os.getenv("DJANGO_URL", "http://localhost:8000")

router = APIRouter(prefix="/api/auth")

NODE_PORT = int(os.getenv("NODE_PORT", "8001"))
NODE_SRS_PORT = int(os.getenv("NODE_SRS_PORT", "8080"))


class LoginPayload(BaseModel):
    email: str
    password: str


class VerifyOTPPayload(BaseModel):
    email: str
    otp: str


class RefreshPayload(BaseModel):
    refresh: str


def _unwrap_django_error(resp):
    try:
        data = resp.json()
    except Exception:
        return resp.text or str(resp.status_code)
    detail = data.get("detail", data.get("non_field_errors", ""))
    if isinstance(detail, list):
        detail = detail[0] if detail else ""
    if isinstance(detail, dict):
        detail = str(detail)
    return str(detail) if detail else str(data)


def _register_node_with_django(token: str, label: str = ""):
    local_ip = _get_local_ip()
    _node_state["local_ip"] = local_ip
    base_url = f"http://{local_ip}"

    print(f"[auth] Registering node with Django: {base_url}:{NODE_PORT}")

    resp = requests.post(
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
    if resp.status_code == 200:
        node_data = resp.json()
        _node_state["node_id"] = node_data.get("id")
        print(f"[auth] Node registered as #{node_data.get('id')}")
    else:
        print(f"[auth] Node registration returned {resp.status_code}: {resp.text}")


@router.post("/login")
async def login(payload: LoginPayload):
    resp = requests.post(
        f"{DJANGO_URL}/auth/login/",
        json={"email": payload.email, "password": payload.password},
        timeout=10,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=_unwrap_django_error(resp))
    return resp.json()


@router.post("/verify-otp")
async def verify_otp(payload: VerifyOTPPayload):
    resp = requests.post(
        f"{DJANGO_URL}/auth/desktop/verify-otp/",
        json={"email": payload.email, "otp": payload.otp},
        timeout=10,
    )
    if resp.status_code != 200 or "access" not in resp.json():
        raise HTTPException(status_code=resp.status_code, detail=_unwrap_django_error(resp))

    data = resp.json()
    access_token = data["access"]
    refresh_token = data.get("refresh", "")

    _node_state["access_token"] = access_token
    if refresh_token:
        _node_state["refresh_token"] = refresh_token

    try:
        public_key = get_public_key()
        print(f"[auth] Decoding token with public key (len={len(public_key)}, "
              f"starts={public_key[:30].replace(chr(10), ' ')}...)")
        token_payload = jwt.decode(
            access_token, public_key, algorithms=["RS256"], options={"verify_aud": False}
        )
        _node_state["user_id"] = token_payload.get("user_id")
        _node_state["user_email"] = token_payload.get("email")
        print(f"[auth] Token verified for user_id={token_payload.get('user_id')}")
    except Exception as e:
        print(f"[auth] Token decode failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=401,
            detail=f"Token verification failed: {type(e).__name__}",
        )

    _register_node_with_django(access_token)

    asyncio.create_task(sync_faces(access_token))

    return {
        "access": access_token,
        "refresh": refresh_token,
        "user_id": _node_state.get("user_id"),
        "email": _node_state.get("user_email"),
    }


@router.post("/refresh")
async def refresh(payload: RefreshPayload):
    resp = requests.post(
        f"{DJANGO_URL}/auth/desktop/token/refresh/",
        json={"refresh": payload.refresh},
        timeout=10,
    )
    if resp.status_code != 200 or "access" not in resp.json():
        raise HTTPException(status_code=resp.status_code, detail=_unwrap_django_error(resp))

    data = resp.json()
    _node_state["access_token"] = data["access"]
    return {"access": data["access"]}


@router.get("/me")
async def me(payload: dict = Depends(optional_token)):
    if payload is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    await verify_node_ownership(payload)
    token = _node_state.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    resp = requests.get(
        f"{DJANGO_URL}/auth/users/me/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=_unwrap_django_error(resp))
    return resp.json()


@router.get("/alerts")
async def alerts(request: Request, payload: dict = Depends(optional_token)):
    if payload is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    await verify_node_ownership(payload)
    token = _node_state.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    query_string = ""
    if request.query_params:
        query_string = "?" + "&".join(f"{k}={v}" for k, v in request.query_params.items())
    resp = requests.get(
        f"{DJANGO_URL}/alerts/{query_string}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=_unwrap_django_error(resp))
    return resp.json()
