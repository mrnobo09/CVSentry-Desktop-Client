import gi
import asyncio

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GstApp  # Add GstApp

Gst.init(None)

class GstHandler:

    def __init__(self):
        self.pipelines = {}
        self.lock = asyncio.Lock()

    async def start_pipeline(self,camera_id:str,rtsp_url:str):
        async with self.lock:
            if camera_id in self.pipelines:
                raise ValueError(f"Pipeline for camera_id {camera_id} already exists.")
            pipeline = Gst.parse_launch(
            f"rtspsrc location={rtsp_url} latency=0 ! decodebin ! videoconvert ! video/x-raw,format=BGR ! appsink name=sink_{camera_id} emit-signals=true"
            )

            pipeline.set_state(Gst.State.PLAYING)
            self.pipelines[camera_id] = pipeline
        
    async def stop_pipeline(self,camera_id:str):
        async with self.lock:
            if camera_id not in self.pipelines:
                raise ValueError(f"No pipeline found for camera_id {camera_id}.")
            pipeline = self.pipelines[camera_id]
            pipeline.set_state(Gst.State.NULL)
            del self.pipelines[camera_id]

    def get_appsink(self,camera_id:str):
        if camera_id not in self.pipelines:
            raise ValueError(f"No pipeline found for camera_id {camera_id}.")
        pipeline = self.pipelines[camera_id]
        appsink = pipeline.get_by_name(f"sink_{camera_id}")
        return appsink
