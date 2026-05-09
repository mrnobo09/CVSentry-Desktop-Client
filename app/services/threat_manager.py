import time
import asyncio
import uuid
from typing import Dict, Any, Set
from routes.node_routes import send_threat_alert

class ThreatManager:
    def __init__(self, timeout_seconds=30.0):
        self.timeout_seconds = timeout_seconds
        
        # State per camera
        self.current_threat_id: Dict[str, str] = {}
        self.last_threat_time: Dict[str, float] = {}
        self.threat_data: Dict[str, Dict[str, Any]] = {}
        
    async def process_frame(self, camera_id: str, frame_id: int, is_aiming: bool, has_weapon: bool, number_of_guns: int, face_identities: list):
        now = time.time()
        
        # Determine current frame severity
        frame_severity = "severe" if is_aiming else "normal"
        has_threat = (number_of_guns > 0) or (len(face_identities) > 0)
        
        if not has_threat:
            return
            
        last_time = self.last_threat_time.get(camera_id, 0)
        is_new_threat = (now - last_time) > self.timeout_seconds
        
        if is_new_threat:
            # Start new threat window
            t_id = str(uuid.uuid4())
            self.current_threat_id[camera_id] = t_id
            self.threat_data[camera_id] = {
                "severity": frame_severity,
                "number_of_guns": number_of_guns,
                "identities": set(face_identities)
            }
            self.last_threat_time[camera_id] = now
            
            # Dispatch new threat
            asyncio.create_task(
                self._dispatch_alert(camera_id, frame_id, t_id, self.threat_data[camera_id])
            )
        else:
            # Existing threat window: update hysteresis and cumulative logic
            self.last_threat_time[camera_id] = now
            data = self.threat_data[camera_id]
            changed = False
            
            # 1. Severity Latching
            if frame_severity == "severe" and data["severity"] == "normal":
                data["severity"] = "severe"
                changed = True
                
            # 2. Max Guns
            if number_of_guns > data["number_of_guns"]:
                data["number_of_guns"] = number_of_guns
                changed = True
                
            # 3. Cumulative Faces
            new_faces = set(face_identities) - data["identities"]
            if new_faces:
                data["identities"].update(new_faces)
                changed = True
                
            if changed:
                asyncio.create_task(
                    self._dispatch_alert(camera_id, frame_id, self.current_threat_id[camera_id], data)
                )

    async def _dispatch_alert(self, camera_id: str, frame_id: int, threat_id: str, data: dict):
        # Convert identities set to list for JSON serialization
        identities_list = list(data["identities"])
        
        print(
            f"[app/threat_manager] 🚨 Dispatching threat_id={threat_id} "
            f"| severity={data['severity']} | guns={data['number_of_guns']} | faces={identities_list}"
        )
        await send_threat_alert(
            camera_id=camera_id,
            frame_id=frame_id,
            identities=identities_list,
            alert_type="THREAT", # Unified alert type
            threat_id=threat_id,
            severity=data["severity"],
            number_of_guns=data["number_of_guns"]
        )

threat_manager = ThreatManager()
