import jwt
from fastapi import Header, HTTPException, Depends
from dependencies.keys import get_public_key
from dependencies.state import _node_state


async def verify_token(authorization: str = Header(...)):
    """
    Dependency that validates a Django RS256 JWT access token.
    Usage in route: async def my_route(payload=Depends(verify_token)): ...
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format.")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = jwt.decode(
            token,
            get_public_key(),
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired.")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


async def optional_token(authorization: str = Header(default="")):
    """
    Optional token verify — for stream proxy using query param.
    """
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return jwt.decode(token, get_public_key(), algorithms=["RS256"], options={"verify_aud": False})
    except Exception:
        return None


async def verify_node_ownership(payload: dict):
    token_user_id = payload.get("user_id")
    node_user_id = _node_state.get("user_id")
    if not node_user_id or not token_user_id:
        raise HTTPException(status_code=401, detail="Node not registered or token lacks user_id")
    if str(token_user_id) != str(node_user_id):
        raise HTTPException(status_code=403, detail="You do not own this node")
    return payload
