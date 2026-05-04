"""
Face Sync Service — Cloud-to-Edge Qdrant Synchronization

Periodically pulls face identity embeddings from the Cloud Django backend
and upserts/deletes them in the Local Qdrant database to maintain a 1:1 copy.

Sync triggers:
  1. Immediately upon node registration (login).
  2. Every SYNC_INTERVAL_SECONDS (600s = 10 minutes).
"""

import os
import asyncio
import datetime
import requests
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance, PointStruct

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
DJANGO_URL = os.getenv("DJANGO_URL", "http://host.docker.internal:8000")
COLLECTION_NAME = "faces"
SYNC_INTERVAL_SECONDS = 600  # 10 minutes

# ── Sync State ────────────────────────────────────────────────
sync_state = {
    "is_syncing": False,
    "last_sync": None,       # ISO timestamp of last successful sync
    "last_error": None,
    "faces_synced": 0,
}


def _get_qdrant_client() -> QdrantClient:
    """Creates a Qdrant client and ensures the 'faces' collection exists."""
    client = QdrantClient(url=QDRANT_URL)
    try:
        client.get_collection(collection_name=COLLECTION_NAME)
    except Exception:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=512, distance=Distance.COSINE),
        )
    return client


async def sync_faces(access_token: str):
    """
    Pulls face identities from the Cloud and syncs them into the local Qdrant.

    - Fetches all identities modified since `last_sync` (delta sync).
    - Upserts active identities into local Qdrant.
    - Deletes soft-deleted identities from local Qdrant.
    """
    if sync_state["is_syncing"]:
        print("[face-sync] ⏳ Sync already in progress — skipping.")
        return

    sync_state["is_syncing"] = True
    sync_state["last_error"] = None

    since = sync_state["last_sync"] or ""
    url = f"{DJANGO_URL}/api/v1/faces/sync/"
    params = {}
    if since:
        params["since"] = since

    print(f"[face-sync] 🔄 Starting face sync (since={since or 'initial'})...")

    try:
        response = await asyncio.to_thread(
            requests.get,
            url,
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

        if response.status_code != 200:
            raise Exception(f"Cloud returned {response.status_code}: {response.text[:200]}")

        identities = response.json()
        
        # Always ensure collection exists, even if 0 identities are returned
        client = _get_qdrant_client()

        if not identities:
            print("[face-sync] ✅ No new updates from Cloud (Collection initialized).")
            sync_state["last_sync"] = datetime.datetime.utcnow().isoformat() + "Z"
            sync_state["is_syncing"] = False
            return

        upserted = 0
        deleted = 0

        for identity in identities:
            qdrant_id = identity["qdrant_id"]
            is_active = identity.get("is_active", True)
            embedding = identity.get("embedding")

            if not is_active:
                # Delete from local Qdrant
                try:
                    client.delete(
                        collection_name=COLLECTION_NAME,
                        points_selector=[qdrant_id],
                    )
                    deleted += 1
                except Exception:
                    pass
            elif embedding:
                # Upsert into local Qdrant
                payload = {
                    "name": identity.get("name", "Unknown"),
                    "is_global": identity.get("is_global", False),
                    "identity_id": str(identity.get("id", "")),
                }
                client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=[
                        PointStruct(
                            id=qdrant_id,
                            vector=embedding,
                            payload=payload,
                        )
                    ],
                )
                upserted += 1

        sync_state["last_sync"] = datetime.datetime.utcnow().isoformat() + "Z"
        sync_state["faces_synced"] = upserted
        print(f"[face-sync] ✅ Sync complete — upserted: {upserted}, deleted: {deleted}")

    except Exception as e:
        sync_state["last_error"] = str(e)
        print(f"[face-sync] ❌ Sync failed: {e}")
    finally:
        sync_state["is_syncing"] = False


async def face_sync_loop(get_token_fn):
    """
    Background loop: syncs faces every SYNC_INTERVAL_SECONDS.
    `get_token_fn` should return the current access_token or None.
    """
    print(f"[face-sync] 🔁 Periodic sync loop started (interval={SYNC_INTERVAL_SECONDS}s)")
    while True:
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)
        token = get_token_fn()
        if token:
            await sync_faces(token)
        else:
            print("[face-sync] ⏭️ Periodic sync skipped — no access token available.")
