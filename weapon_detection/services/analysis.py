from ultralytics import YOLO
import cv2

model = YOLO('weights/last_2.pt')
model.to('cuda')

class FrameAnalyzer:
    def __init__(self, skip_frames: int = 0):
        """
        skip_frames: Number of frames to skip between predictions
                     e.g., skip_frames=2 means predict every 3rd frame
        """
        self.skip_frames = skip_frames
        self.counter = 0

    def analyze_frame(self, frame):
        """
        Analyze frame using YOLOv12n and optionally skip frames for performance.
        
        Returns:
            frame_out: The frame (drawn with boxes if prediction applied)
            detections: list of dicts with:
                        {
                          "class_id": int,
                          "class_name": str,
                          "score": float,
                          "box": [x1, y1, x2, y2]
                        }
                        Empty list if frame was skipped
        """
        if frame is None:
            return None, []

        # Skip frame logic
        if self.counter < self.skip_frames:
            self.counter += 1
            return frame, []  # skipped, return original frame without predictions

        # Reset counter
        self.counter = 0

        # Run YOLO prediction
        results = model.predict(source=frame, verbose=False,device='cuda')

        detections = []
        frame_out = frame.copy()

        for r in results:
            for b in r.boxes:
                x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
                conf = float(b.conf[0])
                cls = int(b.cls[0])
                name = model.names[cls]

                detections.append({
                    "class_id": cls,
                    "class_name": name,
                    "score": conf,
                    "box": [x1, y1, x2, y2]
                })

                # Draw bounding box + label on the frame
                cv2.rectangle(frame_out, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame_out, f"{name} {conf:.2f}",
                            (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (0, 255, 0), 2)
                
                print(f"Detected {name} with confidence {conf:.2f} at [{x1}, {y1}, {x2}, {y2}]")

        return frame_out, detections
