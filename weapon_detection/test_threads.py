import asyncio
from concurrent.futures import ThreadPoolExecutor
from ultralytics import YOLO
import numpy as np

model = YOLO('weights/weapon/recent_best.onnx', task='detect')
executor = ThreadPoolExecutor(max_workers=2)

def infer(idx):
    print(f"Thread {idx} starting")
    try:
        model.predict(np.zeros((640,640,3), dtype=np.uint8), device=0, verbose=False)
        print(f"Thread {idx} finished")
    except Exception as e:
        print(f"Thread {idx} Error: {e}")

async def main():
    loop = asyncio.get_running_loop()
    await asyncio.gather(
        loop.run_in_executor(executor, infer, 1),
        loop.run_in_executor(executor, infer, 2)
    )

asyncio.run(main())
