from ultralytics import YOLO
import numpy as np

print("Loading weapon model...")
try:
    weapon_model = YOLO("../weapon_detection/weights/weapon/best.onnx", task="detect")
    print(f"Weapon model names: {weapon_model.names}")
    
    # Create fake 640x480 image
    fake_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    print("Testing prediction...")
    res = weapon_model.predict(source=fake_frame, conf=0.1, verbose=True)
    
    print(f"Results length: {len(res)}")
    if len(res) > 0:
        print(f"Boxes: {res[0].boxes}")
except Exception as e:
    print(f"Exception: {e}")
