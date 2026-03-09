import threading
import uvicorn
from weapon_detection.weapon_detection import app as weapon_app
from face_detection.face_detection import app as face_app
from app.app import app as main_app


def run_main_app():
    uvicorn.run(main_app, host="localhost", port=8000)


def run_weapon_detection():
    uvicorn.run(weapon_app, host="localhost", port=8002)


def run_face_detection():
    uvicorn.run(face_app, host="localhost", port=8003)


threading.Thread(target=run_main_app, daemon=True).start()
threading.Thread(target=run_weapon_detection, daemon=True).start()
threading.Thread(target=run_face_detection, daemon=True).start()

# Keep main thread alive — the UI is served separately by Vite (npm run dev in app/ui/)
# or from the built dist/ mounted as StaticFiles in app/app.py
import time
while True:
    time.sleep(60)
