import os
import jwt
from fastapi import Header, HTTPException, Depends
from dotenv import load_dotenv

load_dotenv()

DJANGO_SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "crazysupersecretkey")


async def verify_token(authorization: str = Header(...)):
    """
    Dependency that validates a Django HS256 JWT access token.
    Usage in route: async def my_route(payload=Depends(verify_token)): ...
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format.")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = jwt.decode(
            token,
            DJANGO_SECRET_KEY,
            algorithms=["HS256"],
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
        return jwt.decode(token, DJANGO_SECRET_KEY, algorithms=["HS256"], options={"verify_aud": False})
    except Exception:
        return None
