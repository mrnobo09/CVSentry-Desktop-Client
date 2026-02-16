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
            # Keypoint Connections (COCO format subset)
            # 5-7 (L S-E), 7-9 (L E-W)
            # 6-8 (R S-E), 8-10 (R E-W)
            # 5-6 (Shoulders), 11-12 (Hips)
            SKELETON = [
                (5,7), (7,9), (6,8), (8,10), 
                (5,6), (5,11), (6,12), (11,12),
                (11,13), (13,15), (12,14), (14,16)
            ]
            
            # Extract formatted keys
            box = det.get("box") # Expected [x1, y1, x2, y2]
            label = det.get("class_name", "Unknown")
            score = det.get("score", 0.0)
            keypoints = det.get("keypoints") # List of [x, y]
            is_aiming = det.get("is_aiming", False)
            aiming_vec = det.get("aiming_vec")
            aiming_at = det.get("aiming_at")

            # COLOR LOGIC
            color = (0, 255, 0) # Green (Safe)
            
            if label == "THREAT_AIMING":
                color = (0, 0, 255) # Red
                label = "⚠️ WEAPON THREAT ⚠️"
            elif label == "person_pose":
                if is_aiming:
                    color = (0, 0, 255) # Red for shooter
                elif det.get("has_weapon"):
                    color = (0, 165, 255) # Orange for holding weapon
                else: 
                    color = (255, 255, 0) # Cyan/Yellow for normal person
            elif label in ["pistol", "rifle", "knife", "weapon"]: # Check your model class names
                color = (0, 0, 255) # Red for weapon itself
            
            # DRAW SKELETON
            if keypoints:
                # Iterate connections
                for p1_idx, p2_idx in SKELETON:
                    if p1_idx < len(keypoints) and p2_idx < len(keypoints):
                        pt1 = keypoints[p1_idx]
                        pt2 = keypoints[p2_idx]
                        # Check confidence or if 0,0
                        if pt1[0] > 0 and pt2[0] > 0:
                            cv2.line(frame, (int(pt1[0]), int(pt1[1])), (int(pt2[0]), int(pt2[1])), color, 2)
                
                # Draw Keypoints (Wrists red if holding)
                for idx, kp in enumerate(keypoints):
                     if kp[0] > 0:
                        c = color
                        if idx in [9,10] and det.get("has_weapon"): c = (0,0,255)
                        cv2.circle(frame, (int(kp[0]), int(kp[1])), 3, c, -1)
                        
                # Draw Aiming Line
                if is_aiming and aiming_vec:
                    # Find wrist (active one?) - simplistic: from center of box or just use vec
                    # We stored vec, let's just draw a long line from the wrist in that direction
                    # We need the wrist point again.
                    # Let's approximate start point from the person center or iterate wrists
                    # Since we don't know which wrist is aiming here easily without re-calc, 
                    # let's just use the person center or keypoint 9/10 if avail.
                    start_pt = (int(keypoints[9][0]), int(keypoints[9][1])) if len(keypoints) > 9 and keypoints[9][0]>0 else (int(keypoints[0][0]), int(keypoints[0][1]))
                    
                    end_x = start_pt[0] + aiming_vec[0] * 200
                    end_y = start_pt[1] + aiming_vec[1] * 200
                    cv2.arrowedLine(frame, start_pt, (int(end_x), int(end_y)), (0, 0, 255), 4)

            # DRAW BOX
            if box and len(box) == 4:
                # Cast to int for OpenCV
                x1, y1, x2, y2 = map(int, box)

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