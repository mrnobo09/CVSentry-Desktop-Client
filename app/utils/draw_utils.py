import cv2
import numpy as np
from typing import List, Dict, Any, Optional

def draw_detections(frame_bytes: bytes, detections: List[Dict[str, Any]]) -> Optional[bytes]:
    """
    Decodes a frame, draws bounding boxes/labels based on worker format, 
    and re-encodes to JPEG bytes.
    """
    if not frame_bytes:
        return None

    try:
        # 1. Decode Bytes -> Numpy Array (OpenCV Image)
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return None

        # 2. Iterate and Draw
        for det in detections:
            # Extract formatted keys
            box = det.get("box") # Expected [x1, y1, x2, y2]
            label = det.get("class_name", "Unknown")
            score = det.get("score", 0.0)

            if not box or len(box) != 4:
                continue

            # Cast to int for OpenCV
            x1, y1, x2, y2 = map(int, box)

            # Colors (BGR): Red for high confidence/threat, Green otherwise
            # You can add logic here to change color based on class_name
            color = (0, 0, 255) 

            # Draw Rectangle (using x1, y1, x2, y2 directly)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Prepare Label
            label_text = f"{label} {score:.2f}"
            
            # Calculate Text Size for background box
            (text_w, text_h), baseline = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            
            # Draw Text Background (Filled Rectangle)
            # Ensure background doesn't go off-screen if y1 is near top
            text_y_start = max(y1 - 20, 0)
            cv2.rectangle(frame, (x1, text_y_start), (x1 + text_w, text_y_start + 20), color, -1)
            
            # Draw Text
            # Align text inside the background box
            cv2.putText(frame, label_text, (x1, text_y_start + 15), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # 3. Encode Numpy Array -> Bytes (JPEG)
        # Quality 70 keeps streams fast and light
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        return buffer.tobytes()

    except Exception as e:
        print(f"⚠️ Error drawing detections: {e}")
        return frame_bytes # Fail safe: return original image if drawing errors out