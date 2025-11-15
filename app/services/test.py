import asyncio
import cv2
import os
import numpy as np # Import numpy for decoding

# Set OpenCV to use X11 instead of Wayland (if needed)
# os.environ["QT_QPA_PLATFORM"] = "xcb"

# Import from the file av_handler.py
from avhandler import AVHandler 

async def main():
    av_manager = AVHandler()
    camera_id = "cam_1"
    # IMPORTANT: Update this with your actual RTSP URL
    rtsp_url = "rtsp://192.168.100.86:8080/h264_ulaw.sdp" 
    pipeline_started = False
    
    try:
        print(f"Attempting to start pipeline for {camera_id} at {rtsp_url}...")
        await av_manager.start_pipeline(camera_id, rtsp_url)
        pipeline_started = True
        print("Pipeline started successfully.")
        
        print("Press 'q' in the window to quit the stream")
        cv2.namedWindow(camera_id, cv2.WINDOW_NORMAL)
        
        while True:
            # 1. Get JPEG bytes from the handler
            jpeg_bytes = av_manager.get_frame(camera_id)
            
            if jpeg_bytes is not None:
                # 2. Decode JPEG bytes into a NumPy array
                # Convert bytes to a 1D numpy array
                np_arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
                # Decode the numpy array as a color image
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                
                # 3. Show the decoded image
                if img is not None:
                    cv2.imshow(camera_id, img)
                else:
                    print("Failed to decode frame")
            
            # Check for quit key
            key = cv2.waitKey(1)
            if key & 0xFF == ord('q'):
                print("'q' pressed, stopping...")
                break
            
            await asyncio.sleep(0.001) 
            
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Cleaning up resources...")
        cv2.destroyAllWindows()
        if pipeline_started:
            await av_manager.stop_pipeline(camera_id)
            print("Pipeline stopped.")
        print("Cleanup complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user (Ctrl+C)")