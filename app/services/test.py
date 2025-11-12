import asyncio
import cv2
import os

# Set OpenCV to use X11 instead of Wayland
os.environ["QT_QPA_PLATFORM"] = "xcb"

from avhandler import AVHandler

async def main():
    av_manager = AVHandler()
    camera_id = "cam_1"
    rtsp_url = "rtsp://192.168.100.86:8080/h264_ulaw.sdp"
    pipeline_started = False
    
    try:
        await av_manager.start_pipeline(camera_id, rtsp_url)
        pipeline_started = True
        
        print("Press 'q' to quit the stream")
        cv2.namedWindow(camera_id, cv2.WINDOW_NORMAL)
        
        while True:
            frame = av_manager.get_frame(camera_id)
            
            if frame is not None:
                cv2.imshow(camera_id, frame)
            
            key = cv2.waitKey(1)
            if key & 0xFF == ord('q'):
                break
            
            await asyncio.sleep(0.001)
            
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cv2.destroyAllWindows()
        if pipeline_started:
            await av_manager.stop_pipeline(camera_id)
            print("Pipeline stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program terminated by user")