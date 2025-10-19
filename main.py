import webview
from action_detection.action_detection import app as action_app
from weapon_detection.weapon_detection import app as weapon_app
from face_detection.face_detection import app as face_app
from app.app import app as main_app
import threading
import uvicorn

def run_main_app():
    uvicorn.run(main_app, host="localhost", port=8000)

def run_action_detection():
    uvicorn.run(action_app, host="localhost", port=8001)

def run_weapon_detection():
    uvicorn.run(weapon_app, host="localhost", port=8002)

def run_face_detection():
    uvicorn.run(face_app, host="localhost", port=8003)

threading.Thread(target=run_main_app, daemon=True).start()
threading.Thread(target=run_action_detection, daemon=True).start()
threading.Thread(target=run_weapon_detection, daemon=True).start()
threading.Thread(target=run_face_detection, daemon=True).start()

window = webview.create_window(
    'CVSentry',
    'http://localhost:5173',
    width=800,
    height=600,
)
webview.start(gui="gtk",debug=True)

