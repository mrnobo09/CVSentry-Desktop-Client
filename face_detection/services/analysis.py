import os
import numpy as np

try:
    from insightface.app import FaceAnalysis
except ImportError as e:
    raise ImportError(
        "insightface is not installed. Run: pip install insightface onnxruntime"
    ) from e

from qdrant_client import QdrantClient

# ---------------------------------------------------------------------------
# Cosine similarity threshold for recognition.
# Lower = stricter match. Tune this if you get too many false positives/negatives.
# ---------------------------------------------------------------------------
RECOGNITION_THRESHOLD = 0.45

# Qdrant connection — points to the local edge Qdrant container
QDRANT_URL = os.getenv("QDRANT_URL", "http://cvsentry-qdrant:6333")
COLLECTION_NAME = "faces"


class FaceAnalyzer:
    """
    Detects and recognizes faces in a frame using InsightFace buffalo_s.

    Known faces are looked up from the local Qdrant vector database,
    which is kept in sync with the Cloud by the orchestrator's face_sync service.
    """

    def __init__(self, skip_frames: int = 0):
        """
        skip_frames: Number of frames to skip between predictions.
                     e.g., skip_frames=2 means predict every 3rd frame.
        """
        self.skip_frames = skip_frames
        self.counter = 0
        self.last_detections = []

        print("[face] 🚀 Loading InsightFace buffalo_s model...")
        self.app = FaceAnalysis(
            name="buffalo_s",
            providers=["CUDAExecutionProvider", "OpenVINOExecutionProvider", "CPUExecutionProvider"]
        )
        self.app.prepare(ctx_id=0, det_size=(640, 640))
        
        # Determine the active executor used by the underlying ONNXSession
        try:
            model_name = list(self.app.models.keys())[0]
            providers = self.app.models[model_name].session.get_providers()
            active_provider = providers[0] if providers else "UnknownProvider"
            
            # Make the log friendly
            if "CUDA" in active_provider:
                print(f"[face] ✅ InsightFace model ready. Executor: CUDA")
            elif "OpenVINO" in active_provider:
                print(f"[face] ✅ InsightFace model ready. Executor: OpenVINO")
            else:
                print(f"[face] ✅ InsightFace model ready. Executor: CPU ({active_provider})")
        except Exception:
            print("[face] ✅ InsightFace model ready.")

        # Connect to local Qdrant
        self.qdrant = None
        self._connect_qdrant()

    # ------------------------------------------------------------------
    # Qdrant connection
    # ------------------------------------------------------------------

    def _connect_qdrant(self):
        """Connects to the local Qdrant instance."""
        try:
            self.qdrant = QdrantClient(url=QDRANT_URL)
            # Check if the collection exists
            try:
                info = self.qdrant.get_collection(collection_name=COLLECTION_NAME)
                count = info.points_count
                print(f"[face] 📚 Connected to local Qdrant — {count} known face(s) in database.")
            except Exception:
                print(f"[face] ⚠️ Qdrant collection '{COLLECTION_NAME}' not found. "
                      "Waiting for orchestrator sync to create it.")
                self.qdrant = None
        except Exception as e:
            print(f"[face] ⚠️ Could not connect to Qdrant at {QDRANT_URL}: {e}")
            self.qdrant = None

    # ------------------------------------------------------------------
    # Recognition via Qdrant vector search
    # ------------------------------------------------------------------

    def _recognize(self, embedding: np.ndarray):
        """
        Searches the local Qdrant database for the nearest known face.
        Returns: (identity: str | None, confidence: float)
        """
        if self.qdrant is None:
            # Try to reconnect lazily
            self._connect_qdrant()
            if self.qdrant is None:
                return None, 0.0

        # Normalize query embedding
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return None, 0.0
        query_vector = (embedding / norm).tolist()

        try:
            # query_points is the new standard API for qdrant-client 1.16.0+
            results = self.qdrant.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                limit=1,
                score_threshold=RECOGNITION_THRESHOLD,
            ).points

            if results:
                best = results[0]
                identity = best.payload.get("name")
                confidence = round(best.score, 3)
                return identity, confidence

        except Exception as e:
            print(f"[face] ⚠️ Qdrant search error ({type(self.qdrant)}): {e}")
            # Invalidate connection so we retry next time
            self.qdrant = None

        return None, 0.0

    # ------------------------------------------------------------------
    # Main inference
    # ------------------------------------------------------------------

    def analyze_frame(self, frame) -> list:
        """
        Detect and recognize faces in a frame.

        Returns list of dicts:
            {
                "class_name": "known_face" | "face",
                "box":        [x1, y1, x2, y2],
                "score":      float,          # detection confidence
                "identity":   str | None,     # recognized name
                "recognized": bool,
                "rec_confidence": float       # cosine similarity score
            }
        """
        if frame is None:
            return []

        # Skip frame logic
        if self.counter < self.skip_frames:
            self.counter += 1
            return self.last_detections
        self.counter = 0

        try:
            faces = self.app.get(frame)
        except Exception as e:
            print(f"[face] ❌ InsightFace inference error: {e}")
            return []

        results = []
        for face in faces:
            identity, rec_conf = self._recognize(face.embedding)

            bbox = face.bbox.tolist()   # [x1, y1, x2, y2] as floats
            bbox = [round(v) for v in bbox]  # snap to int pixels

            results.append({
                "class_name": "known_face" if identity else "face",
                "box":            bbox,
                "score":          round(float(face.det_score), 3),
                "identity":       identity,
                "recognized":     identity is not None,
                "rec_confidence": rec_conf,
            })

        self.last_detections = results
        return results
