import time
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from dependencies.auth import verify_token
from dependencies.keys import get_public_key
from dependencies.state import _node_state

from services.stream_service import _active_streams

router = APIRouter()


@router.post("/webrtc/{camera_id}/whep")
async def whep_local_signaling(
    camera_id: str,
    request: Request,
    token: str = None,
):
    if not token:
        raise HTTPException(status_code=401, detail="Token missing in query parameters.")

    try:
        payload = jwt.decode(
            token, get_public_key(), algorithms=["RS256"], options={"verify_aud": False}
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    node_user_id = _node_state.get("user_id")
    token_user_id = payload.get("user_id")
    if node_user_id and str(token_user_id) != str(node_user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    ws = _active_streams.get(camera_id)
    if not ws:
        raise HTTPException(status_code=503, detail=f"Stream '{camera_id}' is not active.")

    sdp_offer = await request.body()
    if not sdp_offer:
        raise HTTPException(status_code=400, detail="SDP offer body is required.")

    sdp_text = sdp_offer.decode("utf-8")

    try:
        session_id, answer_sdp = await ws.handle_local_client_offer(sdp_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"WebRTC signaling error: {e}")

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
async def whep_local_teardown(
    camera_id: str,
    session_id: str,
    payload=Depends(verify_token),
):
    ws = _active_streams.get(camera_id)
    if ws:
        await ws.remove_local_client(session_id)
    return {"status": "closed"}
