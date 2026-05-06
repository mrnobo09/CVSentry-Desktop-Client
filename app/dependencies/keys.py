import os
import requests
from dotenv import load_dotenv

load_dotenv()

DJANGO_URL = os.getenv("DJANGO_URL", "http://host.docker.internal:8000")

_public_key: str | None = None
_fetch_attempted: bool = False


def fetch_public_key() -> str:
    global _public_key, _fetch_attempted
    if _public_key:
        return _public_key
    _fetch_attempted = True
    try:
        response = requests.get(f"{DJANGO_URL}/auth/public-key/", timeout=5)
        response.raise_for_status()
        _public_key = response.json()["public_key"]
        print(f"[auth] Public key fetched from {DJANGO_URL}")
    except Exception as e:
        print(f"[auth] WARNING: Could not fetch public key from {DJANGO_URL}: {e}")
        raise
    return _public_key


def preload_public_key():
    try:
        fetch_public_key()
    except Exception:
        pass


def get_public_key() -> str:
    return fetch_public_key()
