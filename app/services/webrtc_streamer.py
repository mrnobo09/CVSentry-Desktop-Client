import asyncio
import json
import logging
import os
import time
import fractions
from typing import Optional, Dict

import av
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
    RTCDataChannel,
    MediaStreamTrack,
)
from aiortc.contrib.media import MediaRelay

from turbojpeg import TurboJPEG

logger = logging.getLogger("webrtc_streamer")

_jpeg = TurboJPEG()

CLOUD_SRS_WHIP_URL = os.getenv("CLOUD_SRS_WHIP_URL", "http://localhost:1985/rtc/v1/publish/")
CLOUD_DJANGO_URL = os.getenv("DJANGO_URL", "http://host.docker.internal:8000")
SRS_API_USER = os.getenv("SRS_API_USERNAME", "cvsentry_srs")
SRS_API_PASS = os.getenv("SRS_API_PASSWORD", "")


def detect_hw_encoder():
    for name in ["h264_nvenc", "h264_qsv", "h264_vaapi", "libx264"]:
        try:
            av.Codec(name, "w")
            logger.info(f"Detected hardware encoder: {name}")
            return name
        except Exception:
            continue
    logger.warning("No hardware encoder found, using libx264 (software)")
    return "libx264"


HW_ENCODER = detect_hw_encoder()


class PipelineVideoTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self, camera_id: str):
        super().__init__()
        self.camera_id = camera_id
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=5)
        self._frame_count = 0

    async def recv(self) -> av.VideoFrame:
        frame_data = await self._queue.get()
        jpeg_bytes = frame_data["jpeg_bytes"]

        try:
            img_array = _jpeg.decode(jpeg_bytes)
        except Exception:
            img_array = None

        if img_array is None:
            if self._frame_count > 0:
                try:
                    last = getattr(self, "_last_frame", None)
                    if last is not None:
                        return last
                except Exception:
                    pass
            raise asyncio.QueueEmpty()

        frame = av.VideoFrame.from_ndarray(img_array, format="bgr24")
        # Use 10 FPS as a reasonable default for PTS increments at 90kHz timebase
        frame.pts = self._frame_count * 9000
        frame.time_base = fractions.Fraction(1, 90000)

        self._frame_count += 1
        self._last_frame = frame
        return frame

    def feed(self, jpeg_bytes: bytes, frame_number: int, detections: dict):
        item = {
            "jpeg_bytes": jpeg_bytes,
            "frame_number": frame_number,
            "detections": detections,
        }
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self._queue.put_nowait(item)


class HardwareH264EncoderMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._codec_name = HW_ENCODER

    async def _create_encoder(self, codec_params):
        if codec_params.name.upper() in ("H264", "H.264"):
            opts = {}
            if self._codec_name == "h264_nvenc":
                codec = await asyncio.to_thread(
                    av.CodecContext.create, self._codec_name, "w"
                )
                codec.options = {
                    "preset": "p1",
                    "tune": "ull",
                    "zerolatency": 1,
                    "delay": 0,
                    "rc": "cbr",
                    "b": "500k",
                }
                return codec
            elif self._codec_name == "h264_qsv":
                codec = await asyncio.to_thread(
                    av.CodecContext.create, self._codec_name, "w"
                )
                return codec
            elif self._codec_name == "h264_vaapi":
                codec = await asyncio.to_thread(
                    av.CodecContext.create, self._codec_name, "w"
                )
                return codec
        return await super()._create_encoder(codec_params)


class HardwareRTCPeerConnection(RTCPeerConnection):
    async def _create_sender(self, *args, **kwargs):
        sender = await super()._create_sender(*args, **kwargs)
        orig_create_encoder = sender._create_encoder

        async def hw_create_encoder(codec_params):
            if codec_params.name.upper() in ("H264", "H.264"):
                codec = await asyncio.to_thread(
                    av.CodecContext.create, HW_ENCODER, "w"
                )
                codec.options = {
                    "preset": "p1",
                    "tune": "ull",
                    "zerolatency": 1,
                    "delay": 0,
                    "rc": "cbr",
                    "b": "500k",
                }
                return codec
            return await orig_create_encoder(codec_params)

        sender._create_encoder = hw_create_encoder
        return sender


class WebrtcStreamer:
    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.video_track = PipelineVideoTrack(camera_id)
        self.relay = MediaRelay()
        self.relayed_track = None
        self.local_peers: Dict[str, RTCPeerConnection] = {}
        self.local_data_channels: Dict[str, RTCDataChannel] = {}
        self.cloud_peer: Optional[RTCPeerConnection] = None
        self.cloud_data_channel: Optional[RTCDataChannel] = None
        self._cloud_connected = asyncio.Event()
        self._local_signaling_event = asyncio.Event()
        self._running = True

    def feed_frame(self, jpeg_bytes: bytes, frame_number: int, detections: dict):
        self.video_track.feed(jpeg_bytes, frame_number, detections)

    async def broadcast_metadata(self, frame_number: int, detections: dict, threat_meta: dict):
        msg = json.dumps({
            "type": "metadata",
            "frame_number": frame_number,
            "timestamp_us": int(time.time() * 1_000_000),
            "detections": detections,
            "threat": threat_meta,
        })
        for session_id, channel in list(self.local_data_channels.items()):
            try:
                if channel.readyState == "open":
                    channel.send(msg)
            except Exception:
                self.local_data_channels.pop(session_id, None)

    async def start_cloud_relay(self, srs_whip_url: str, srs_stream_url: str, jwt_token: str) -> bool:
        if self.cloud_peer:
            return True

        relayed = self.relay.subscribe(self.video_track)
        self.relayed_track = relayed

        pc = HardwareRTCPeerConnection()
        self.cloud_peer = pc

        pc.addTrack(relayed)

        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        try:
            import httpx
            auth = httpx.BasicAuth(SRS_API_USER, SRS_API_PASS) if SRS_API_PASS else None
            async with httpx.AsyncClient(timeout=15.0, auth=auth) as client:
                sdp_payload = {
                    "api": srs_whip_url,
                    "streamurl": srs_stream_url,
                    "clientip": None,
                    "sdp": pc.localDescription.sdp,
                }
                headers = {}
                if jwt_token:
                    headers["Authorization"] = f"Bearer {jwt_token}"

                resp = await client.post(
                    srs_whip_url,
                    json=sdp_payload,
                    headers=headers,
                )
                if resp.status_code not in (200, 201):
                    logger.error(f"[{self.camera_id}] Cloud WHIP error {resp.status_code}: {resp.text}")
                    return False

                data = resp.json()
                if data.get("code", 0) != 0:
                    logger.error(f"[{self.camera_id}] Cloud WHIP API error: {data}")
                    return False

                answer_sdp = data.get("sdp", "")
                await pc.setRemoteDescription(
                    RTCSessionDescription(sdp=answer_sdp, type="answer")
                )

            self._cloud_connected.set()
            logger.info(f"[{self.camera_id}] Cloud relay connected via WHIP")
            return True

        except Exception as e:
            logger.error(f"[{self.camera_id}] Cloud relay failed: {e}")
            return False

    async def handle_local_client_offer(self, offer_sdp: str) -> tuple[str, str]:
        relayed = self.relay.subscribe(self.video_track)

        pc = HardwareRTCPeerConnection()
        session_id = f"{self.camera_id}_{len(self.local_peers)}_{int(time.time()*1000)}"
        self.local_peers[session_id] = pc

        pc.addTrack(relayed)

        channel = pc.createDataChannel("detections")
        self.local_data_channels[session_id] = channel
        @channel.on("open")
        def on_open():
            logger.info(f"[{self.camera_id}] Local DataChannel open ({session_id})")

        offer = RTCSessionDescription(sdp=offer_sdp, type="offer")
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return session_id, pc.localDescription.sdp

    async def remove_local_client(self, session_id: str):
        pc = self.local_peers.pop(session_id, None)
        self.local_data_channels.pop(session_id, None)
        if pc:
            await pc.close()

    async def stop(self):
        self._running = False
        for session_id, pc in list(self.local_peers.items()):
            await pc.close()
        self.local_peers.clear()
        self.local_data_channels.clear()
        if self.cloud_peer:
            await self.cloud_peer.close()
            self.cloud_peer = None
        self.cloud_data_channel = None
        logger.info(f"[{self.camera_id}] WebRTC streamer stopped")
