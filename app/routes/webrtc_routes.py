import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from dependencies.auth import verify_token, verify_node_ownership
from dependencies.keys import get_public_key
from dependencies.state import _node_state
from dotenv import load_dotenv

load_dotenv()

SRS_API_PORT = os.getenv("SRS_API_PORT", "1985")
SRS_HOST = os.getenv("SRS_HOST", "srs")
SRS_API_USER = os.getenv("SRS_API_USERNAME", "cvsentry_srs")
SRS_API_PASS = os.getenv("SRS_API_PASSWORD", "")
SRS_HTTP_URL = f"http://{SRS_HOST}:{SRS_API_PORT}"

router = APIRouter()


def _srs_auth():
    if SRS_API_PASS:
        return httpx.BasicAuth(SRS_API_USER, SRS_API_PASS)
    return None


@router.post("/webrtc/{camera_id}/whep")
async def whep_offer(
    camera_id: str,
    request: Request,
    token: str = None,
):
    """
    JWT-authenticated WHEP proxy.

    The cloud dashboard (or any client) sends a WebRTC SDP offer here.
    We forward it to the local SRS WHEP endpoint for the given camera stream.
    SRS returns the SDP answer which we relay back.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Token missing in query parameters.")
    
    import jwt
    try:
        payload = jwt.decode(token, get_public_key(), algorithms=["RS256"], options={"verify_aud": False})
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    node_user_id = _node_state.get("user_id")
    token_user_id = payload.get("user_id")
    if node_user_id and str(token_user_id) != str(node_user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    sdp_offer = await request.body()
    if not sdp_offer:
        raise HTTPException(status_code=400, detail="SDP offer body is required.")

    sdp_text = sdp_offer.decode("utf-8")
    
    srs_whep_url = f"{SRS_HTTP_URL}/rtc/v1/play/"

    payload = {
        "api": srs_whep_url,
        "streamurl": f"webrtc://localhost/live/{camera_id}",
        "clientip": None,
        "sdp": sdp_text
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            srs_response = await client.post(
                srs_whep_url,
                json=payload,
                auth=_srs_auth(),
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not reach SRS for WebRTC signaling: {exc}",
        )

    if srs_response.status_code not in (200, 201):
        raise HTTPException(
            status_code=srs_response.status_code,
            detail=f"SRS WebRTC error: {srs_response.text}",
        )
        
    # SRS returns JSON: { "code": 0, "sdp": "v=0\r\n...", "sessionid": "..." }
    srs_data = srs_response.json()
    if srs_data.get("code", 0) != 0:
        raise HTTPException(
            status_code=500,
            detail=f"SRS WebRTC API error: {srs_data}",
        )
        
    answer_sdp = srs_data.get("sdp", "")

    # Relay SRS SDP answer back to the client as raw SDP
    return Response(
        content=answer_sdp,
        status_code=200,
        media_type="application/sdp",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
        },
    )


@router.delete("/webrtc/{camera_id}/whep/{session_id}")
async def whep_teardown(
    camera_id: str,
    session_id: str,
    payload=Depends(verify_token),
):
    """
    Teardown a WHEP session (WebRTC connection cleanup).
    Forwards the DELETE to SRS.
    """
    srs_delete_url = (
        f"{SRS_HTTP_URL}/rtc/v1/whep/{session_id}?app=live&stream={camera_id}"
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.delete(srs_delete_url, auth=_srs_auth())
    except Exception:
        pass  # Best-effort teardown

    return {"status": "closed"}
