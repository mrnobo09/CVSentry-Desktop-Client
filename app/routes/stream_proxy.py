import os
import httpx
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import jwt

load_dotenv()

from dependencies.keys import get_public_key
from dependencies.state import _node_state

SRS_HTTP_PORT = os.getenv("SRS_HTTP_PORT", "8080")
SRS_BASE_URL = f"http://srs:{SRS_HTTP_PORT}/live"

router = APIRouter()


def _verify_stream_token(token: str):
    try:
        return jwt.decode(
            token,
            get_public_key(),
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Stream token expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid stream token.")


@router.get("/stream/{camera_id}.flv")
async def proxy_stream(
    camera_id: str,
    token: str = Query(..., description="Django JWT access token"),
):
    """
    Authenticated FLV stream proxy.
    Validates JWT token + node ownership, then streams FLV data from local SRS server.
    
    URL: GET /stream/{camera_id}.flv?token=<access_token>
    """
    payload = _verify_stream_token(token)
    node_user_id = _node_state.get("user_id")
    token_user_id = payload.get("user_id")
    if node_user_id and str(token_user_id) != str(node_user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    srs_url = f"{SRS_BASE_URL}/{camera_id}.flv"

    async def stream_generator():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("GET", srs_url) as response:
                    if response.status_code != 200:
                        raise HTTPException(status_code=response.status_code, detail="SRS stream not available")
                    async for chunk in response.aiter_bytes(chunk_size=4096):
                        yield chunk
        except (httpx.RemoteProtocolError, httpx.ReadError):
            pass

    return StreamingResponse(
        stream_generator(),
        media_type="video/x-flv",
        headers={
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
        },
    )
