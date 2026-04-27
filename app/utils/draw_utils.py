import cv2
import numpy as np
import math
from typing import List, Dict, Any, Optional
from turbojpeg import TurboJPEG

def draw_detections(frame_bytes: bytes, detections: List[Dict[str, Any]]) -> Optional[bytes]:
    """
    Decodes a frame, draws bounding boxes/labels based on worker format, 
    and re-encodes to JPEG bytes.
    """
    if not frame_bytes:
        return None

    try:
        jpeg = TurboJPEG()
        
        # 1. Decode Bytes -> Numpy Array (OpenCV Image) using TurboJPEG
        frame = jpeg.decode(frame_bytes)

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
            elif label.lower() in ["pistol", "rifle", "knife", "weapon"]: # Check your model class names
                color = (0, 0, 255) # Red for weapon itself
            # ---- Face detection labels ----
            elif label == "COMBINED_THREAT":
                color = (0, 0, 220) # Deep red — armed recognized suspect
                identity = det.get("identity") or "Unknown"
                label = f"⚠️ ARMED SUSPECT: {identity}"
            elif label == "known_face":
                color = (0, 220, 100) # Green — recognized face
                identity = det.get("identity") or "?"
                rec_conf = det.get("rec_confidence", 0.0)
                label = f"{identity} ({rec_conf:.2f})"
            elif label == "face":
                color = (200, 200, 0) # Cyan-grey — unknown face
            
            # DRAW SKELETON
            if keypoints:
                # Iterate connections
                for p1_idx, p2_idx in SKELETON:
                    if p1_idx < len(keypoints) and p2_idx < len(keypoints):
                        pt1 = keypoints[p1_idx]
                        pt2 = keypoints[p2_idx]
                        # Check confidence or if 0,0 and avoid NaN before int cast
                        if not math.isnan(pt1[0]) and not math.isnan(pt2[0]) and pt1[0] > 0 and pt2[0] > 0:
                            cv2.line(frame, (int(pt1[0]), int(pt1[1])), (int(pt2[0]), int(pt2[1])), color, 2)
                
                # Draw Keypoints (Wrists red if holding)
                for idx, kp in enumerate(keypoints):
                     if not math.isnan(kp[0]) and kp[0] > 0:
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
                    start_pt = None
                    if len(keypoints) > 9 and not math.isnan(keypoints[9][0]) and keypoints[9][0]>0:
                        start_pt = (int(keypoints[9][0]), int(keypoints[9][1]))
                    elif len(keypoints) > 0 and not math.isnan(keypoints[0][0]) and keypoints[0][0]>0:
                        start_pt = (int(keypoints[0][0]), int(keypoints[0][1]))
                    
                    if start_pt and not math.isnan(aiming_vec[0]) and not math.isnan(aiming_vec[1]):
                        end_x = start_pt[0] + aiming_vec[0] * 200
                        end_y = start_pt[1] + aiming_vec[1] * 200
                        cv2.arrowedLine(frame, start_pt, (int(end_x), int(end_y)), (0, 0, 255), 4)

            # DRAW BOX
            if box and len(box) == 4 and not any(math.isnan(b) for b in box):
                # Cast to int for OpenCV
                x1, y1, x2, y2 = map(int, box)

                # Combined threat: draw thicker, flashing-style double border
                if det.get("class_name") == "COMBINED_THREAT":
                    cv2.rectangle(frame, (x1 - 4, y1 - 4), (x2 + 4, y2 + 4), (0, 0, 180), 4)

                # Draw Rectangle
                thickness = 3 if det.get("class_name") in ("COMBINED_THREAT", "known_face") else 2
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

                # Prepare Label — face/known_face labels are already formatted above
                if det.get("class_name") in ("face", "known_face", "COMBINED_THREAT"):
                    label_text = label  # already includes identity / score
                else:
                    label_text = f"{label} {score:.2f}"
                
                # Calculate Text Size for background box
                font_scale = 0.55 if det.get("class_name") == "COMBINED_THREAT" else 0.5
                (text_w, text_h), baseline = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
                
                # Draw Text Background
                text_y_start = max(y1 - 20, 0)
                cv2.rectangle(frame, (x1, text_y_start), (x1 + text_w, text_y_start + 20), color, -1)
                
                # Draw Text
                cv2.putText(frame, label_text, (x1, text_y_start + 15), 
                            cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1)

        # 3. Encode Numpy Array -> Bytes (JPEG) using TurboJPEG
        # Quality 70 keeps streams fast and light
        return jpeg.encode(frame, quality=70)

    except Exception as e:
        print(f"⚠️ Error drawing detections: {e}")
        return frame_bytes # Fail safe: return original image if drawing errors out