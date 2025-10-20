import gi
import asyncio
import cv2
import numpy as np
import os

# Set OpenCV to use X11 instead of Wayland
os.environ["QT_QPA_PLATFORM"] = "xcb"

gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')  # Add this line
from gi.repository import Gst, GLib, GstApp  # Add GstApp

Gst.init(None)

from gsthandler import GstHandler

async def main():
    gst_manager = GstHandler()
    camera_id = "cam1"
    rtsp_url = "rtsp://192.168.100.78:8080/h264_ulaw.sdp"

    try:
        await gst_manager.start_pipeline(camera_id, rtsp_url)
        appsink = gst_manager.get_appsink(camera_id)

        # Ensure we're using GstAppSink
        if not isinstance(appsink, GstApp.AppSink):
            raise TypeError("Sink is not a GstAppSink")

        print("Press 'q' to quit the stream")
        cv2.namedWindow(camera_id, cv2.WINDOW_NORMAL)

        while True:
            sample = appsink.try_pull_sample(Gst.SECOND)  # Use try_pull_sample with timeout
            if not sample:
                await asyncio.sleep(0.001)
                continue

            buf = sample.get_buffer()
            caps = sample.get_caps()
            width = caps.get_structure(0).get_value('width')
            height = caps.get_structure(0).get_value('height')

            success, map_info = buf.map(Gst.MapFlags.READ)
            if not success:
                continue

            # Create a copy of the frame data
            frame = np.ndarray(
                (height, width, 3),
                buffer=map_info.data,
                dtype=np.uint8
            ).copy()  # Make sure to copy the data
            buf.unmap(map_info)

            # Display the frame
            cv2.imshow(camera_id, frame)

            # Handle key press with shorter wait time
            key = cv2.waitKey(1)
            if key & 0xFF == ord('q'):
                break

    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        cv2.destroyAllWindows()
        await gst_manager.stop_pipeline(camera_id)
        print("Pipeline stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program terminated by user")
