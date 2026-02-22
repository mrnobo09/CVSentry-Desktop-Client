import os
import httpx
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import jwt

load_dotenv()

DJANGO_SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "crazysupersecretkey")
SRS_BASE_URL = f"http://localhost:{os.getenv('NODE_SRS_PORT', '8080')}/live"

router = APIRouter()


def _verify_stream_token(token: str):
    try:
        return jwt.decode(
            token,
            DJANGO_SECRET_KEY,
            algorithms=["HS256"],
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
    Validates JWT token then streams FLV data from local SRS server.
    
    URL: GET /stream/{camera_id}.flv?token=<access_token>
    """
    _verify_stream_token(token)

    srs_url = f"{SRS_BASE_URL}/{camera_id}.flv"

    async def stream_generator():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", srs_url) as response:
                if response.status_code != 200:
                    raise HTTPException(status_code=response.status_code, detail="SRS stream not available")
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    yield chunk

    return StreamingResponse(
        stream_generator(),
        media_type="video/x-flv",
        headers={
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
        },
    )
