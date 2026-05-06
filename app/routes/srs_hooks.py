from fastapi import APIRouter, Request, HTTPException

router = APIRouter(prefix="/internal/srs")

INTERNAL_DOCKER_PREFIXES = ("172.", "10.", "192.168.", "127.")


def _is_internal(client_ip: str) -> bool:
    return client_ip.startswith(INTERNAL_DOCKER_PREFIXES)


@router.post("/on_play")
async def on_play(request: Request):
    client_ip = request.client.host if request.client else ""
    if not _is_internal(client_ip):
        raise HTTPException(status_code=403, detail="Access denied")
    return {"code": 0}


@router.post("/on_publish")
async def on_publish(request: Request):
    client_ip = request.client.host if request.client else ""
    if not _is_internal(client_ip):
        raise HTTPException(status_code=403, detail="Access denied")
    return {"code": 0}


@router.post("/on_stop")
async def on_stop(request: Request):
    return {"code": 0}
