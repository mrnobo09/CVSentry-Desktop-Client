from ultralytics import YOLO
import cv2
import math
import numpy as np
import torch
import os
import time

MODEL_PATH = "weights/weapon/best.onnx"
MODEL_PATH_OPENVINO = "weights/weapon/best_2_openvino_model"

# Load Models
try:
    if torch.cuda.is_available():
        print("[weapon] 🚀 CUDA is available. Executor: CUDA")
        weapon_model = YOLO(MODEL_PATH, task="detect")
        pose_model = YOLO('weights/pose/yolo11s-pose.onnx', task="pose")
        INFERENCE_DEVICE = 0
    else:
        print("[weapon] ⚡ CUDA not found. Attempting to load OpenVINO optimized models. Executor: OpenVINO")
        # Note: Ultralytics uses the format of the loaded model path to trigger OpenVINO. 
        # When an OpenVINO model is loaded, passing device="cpu" tells the OpenVINO backend to run on the CPU.
        weapon_model = YOLO('weights/weapon/best_2_openvino_model', task="detect")
        pose_model = YOLO('weights/pose/yolo11s-pose_openvino_model', task="pose") 
        INFERENCE_DEVICE = "cpu"
except Exception as e:
    print(f"[weapon] 💻 Primary models failed to load. Loading fallback ONNX models. Executor: CPU ({e})")
    # Fallback to standard ONNX models (runs on CPU)
    weapon_model = YOLO(MODEL_PATH, task="detect")
    pose_model = YOLO("weights/pose/yolo11s-pose.onnx", task="pose")
    INFERENCE_DEVICE = "cpu"

class FrameAnalyzer:
    def __init__(self, skip_frames: int = 0):
        """
        skip_frames: Number of frames to skip between predictions
                     e.g., skip_frames=2 means predict every 3rd frame
        """
        self.skip_frames = skip_frames
        self.counter = 0
        self.last_detections = []

    def analyze_frame(self, frame):
        """
        Analyze frame using YOLO models for Weapon and Pose.
        
        Returns:
            detections: list of dicts with weapon info, pose info, and threat status.
        """
        if frame is None:
            return []
            
        # Skip frame logic
        if self.counter < self.skip_frames:
            self.counter += 1
            return self.last_detections  # return cached detections on skipped frame

        self.counter = 0

        # 1. Run Weapon Detection
        weapon_results = weapon_model.predict(source=frame, verbose=False, conf=0.6, iou=0.5, max_det=50, device=INFERENCE_DEVICE)
        
        # 2. Run Pose Estimation
        # Using a lower conf for pose to ensure we catch people even if partially occluded
        pose_results = pose_model.predict(source=frame, verbose=False, conf=0.5, device=INFERENCE_DEVICE)

        detections = []
        
        # Extract Weapon Boxes
        weapons = []
        for r in weapon_results:
            for b in r.boxes:
                x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
                conf = float(b.conf[0])
                cls = int(b.cls[0])
                name = weapon_model.names[cls]
                weapons.append({
                    "box": [x1, y1, x2, y2],
                    "score": conf,
                    "class_name": name,
                    "center": [(x1+x2)/2, (y1+y2)/2]
                })

        # Extract Action/Pose Data
        # We need to map weapons to people
        people = []
        if pose_results and len(pose_results) > 0:
            for r in pose_results:
                if r.keypoints is not None:
                    # r.keypoints.xy is (N, 17, 2)
                    # We iterate through each person detected
                    for idx, kpts in enumerate(r.keypoints.xy.cpu().numpy()):
                        box = r.boxes.xyxy[idx].tolist() if r.boxes else [0,0,0,0]
                        people.append({
                            "id": idx, # Index in this frame's results
                            "box": box,
                            "keypoints": kpts, # Array of [x, y]
                            "has_weapon": False,
                            "weapon_data": None,
                            "is_aiming": False,
                            "aiming_at": None
                        })

        # 3. Logic: Match Weapon to Person (Wrist)
        # COCO Keypoints: 9: Left Wrist, 10: Right Wrist, 7: Left Elbow, 8: Right Elbow
        # We use a distance threshold.
        max_dist =  max(frame.shape[0], frame.shape[1]) * 0.15 # 15% of screen dimension

        for p in people:
            kpts = p['keypoints']
            # Check wrists (indices 9 and 10)
            # kpts structure: [[x,y], [x,y], ...]
            # Some models return [x,y,conf] or just [x,y]. Ultralytics .xy is [x,y].
            
            # Filter valid keypoints (0,0 is usually invalid)
            valid_wrists = []
            if kpts[9][0] > 0 and kpts[9][1] > 0: valid_wrists.append(('left', kpts[9], kpts[7])) # wrist, elbow
            if kpts[10][0] > 0 and kpts[10][1] > 0: valid_wrists.append(('right', kpts[10], kpts[8]))

            best_weapon = None
            min_dist = float('inf')
            active_wrist = None
            active_elbow = None

            for w in weapons:
                w_center = w['center']
                for side, wrist, elbow in valid_wrists:
                    dist = math.hypot(wrist[0] - w_center[0], wrist[1] - w_center[1])
                    if dist < max_dist and dist < min_dist:
                        min_dist = dist
                        best_weapon = w
                        active_wrist = wrist
                        active_elbow = elbow
            
            if best_weapon:
                p['has_weapon'] = True
                p['weapon_data'] = best_weapon
                
                # 4. Logic: Threat Detection (Holding Weapon)
                # Vector: Elbow -> Wrist
                if active_elbow is not None and active_elbow[0] > 0:
                    # Calculate vector
                    vec_x = active_wrist[0] - active_elbow[0]
                    vec_y = active_wrist[1] - active_elbow[1]
                    
                    # Normalize vector
                    mag = math.hypot(vec_x, vec_y)
                    if mag > 0:
                        vec_x /= mag
                        vec_y /= mag
                        
                        # New Logic: Raising arm/Holding gun aligns with a vector
                        # We treat ANY holding as a threat for now as requested.
                        # We preserve the vector for drawing purposes.
                        
                        p['is_aiming'] = True
                        # We don't have a specific target, so we can set it to None or a dummy box
                        # The UI might expect a box for red highlighting. 
                        # Let's set it to the person's own box or a projected point if strictly needed, 
                        # but for now None is safe if we handle it in drawing.
                        p['aiming_at'] = None 
                        p['aiming_vec'] = [float(vec_x), float(vec_y)]
        
        # Format final output
        # We return a flat list of "detections" for the frontend
        # Including Weapons and People info
        
        # 1. Add all weapons (even if not held? Yes, existing logic likely expects them)
        for w in weapons:
            detections.append(w)
            
        # 2. Add People Metadata
        for p in people:
            pose_entry = {
                "class_name": "person_pose",
                "box": p['box'],
                "score": 1.0, # Pose result score?
                "keypoints": p['keypoints'].tolist(),
                "has_weapon": p['has_weapon'],
                "is_aiming": p['is_aiming']
            }
            if p['is_aiming']:
                 pose_entry['aiming_at'] = p['aiming_at']
                 pose_entry['aiming_vec'] = p.get('aiming_vec')
                 
                 # Add specific threat entry for the UI to scream
                 detections.append({
                     "class_name": "THREAT_AIMING",
                     "score": 1.0,
                     "box": p['aiming_at'] # Highlight victim?
                 })
                 
            detections.append(pose_entry)

        self.last_detections = detections
        return detections
