import cv2
import numpy as np
from pathlib import Path

try:
    from insightface.app import FaceAnalysis
except ImportError as e:
    raise ImportError(
        "insightface is not installed. Run: pip install insightface onnxruntime"
    ) from e

# ---------------------------------------------------------------------------
# Cosine similarity threshold for recognition.
# Lower = stricter match. Tune this if you get too many false positives/negatives.
# ---------------------------------------------------------------------------
RECOGNITION_THRESHOLD = 0.45

# Path to the known faces directory (relative to where the worker is launched)
FACES_DIR = Path("faces")


class FaceAnalyzer:
    """
    Detects and recognizes faces in a frame using InsightFace buffalo_s.

    Known faces are loaded from:
        faces/{Person_Name}/img1.jpg
        faces/{Person_Name}/img2.jpg
        ...
    Folder name (underscores replaced with spaces) becomes the identity.
    All images per person are encoded and averaged into a single embedding.
    """

    def __init__(self, skip_frames: int = 0):
        """
        skip_frames: Number of frames to skip between predictions.
                     e.g., skip_frames=2 means predict every 3rd frame.
        """
        self.skip_frames = skip_frames
        self.counter = 0

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

        # Dict: identity_name (str) -> averaged_embedding (np.ndarray, shape 512)
        self.known_embeddings: dict = self._load_known_faces()

    # ------------------------------------------------------------------
    # Known-face database loading
    # ------------------------------------------------------------------

    def _load_known_faces(self) -> dict:
        """
        Walks faces/{person_name}/ subdirectories.
        Encodes every image, averages embeddings per person.
        Returns: { "John Doe": np.ndarray(512,), ... }
        """
        db = {}

        if not FACES_DIR.exists():
            print(f"[face] ⚠️  faces/ directory not found at '{FACES_DIR.resolve()}'. No known faces loaded.")
            return db

        for person_dir in sorted(FACES_DIR.iterdir()):
            if not person_dir.is_dir():
                continue

            # Folder name → identity label (underscores → spaces)
            name = person_dir.name.replace("_", " ")
            embeddings = []

            image_files = list(person_dir.glob("*.[jJ][pP][gG]")) + \
                          list(person_dir.glob("*.[jJ][pP][eE][gG]")) + \
                          list(person_dir.glob("*.[pP][nN][gG]"))

            for img_path in sorted(image_files):
                img = cv2.imread(str(img_path))
                if img is None:
                    print(f"[face] ⚠️  Could not read image: {img_path}")
                    continue

                detected = self.app.get(img)
                if not detected:
                    print(f"[face] ⚠️  No face detected in: {img_path.name} — skipping")
                    continue

                # Use the highest-confidence face if multiple are found
                best_face = max(detected, key=lambda f: f.det_score)
                embeddings.append(best_face.embedding)

            if embeddings:
                avg_embedding = np.mean(embeddings, axis=0)
                # Normalize for cosine similarity
                avg_embedding /= np.linalg.norm(avg_embedding)
                db[name] = avg_embedding
                print(f"[face] 👤 Loaded '{name}' from {len(embeddings)} image(s)")
            else:
                print(f"[face] ⚠️  No valid face images found for '{name}' — skipping")

        print(f"[face] 📚 Known faces database: {len(db)} identit{'y' if len(db)==1 else 'ies'} loaded.")
        return db

    def reload_known_faces(self):
        """Hot-reload the known faces DB without restarting the worker."""
        print("[face] 🔄 Reloading known faces database...")
        self.known_embeddings = self._load_known_faces()

    # ------------------------------------------------------------------
    # Recognition helpers
    # ------------------------------------------------------------------

    def _recognize(self, embedding: np.ndarray):
        """
        Compares embedding against known_embeddings using cosine similarity.
        Returns: (identity: str | None, confidence: float)
        """
        if not self.known_embeddings:
            return None, 0.0

        # Normalize query embedding
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return None, 0.0
        query = embedding / norm

        best_name = None
        best_sim = -1.0

        for name, ref_emb in self.known_embeddings.items():
            sim = float(np.dot(query, ref_emb))  # cosine similarity (both normalized)
            if sim > best_sim:
                best_sim = sim
                best_name = name

        if best_sim >= RECOGNITION_THRESHOLD:
            return best_name, round(best_sim, 3)

        return None, round(best_sim, 3)

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
            return []
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

        return results
