import subprocess
import shlex
import time
import threading
from queue import Queue, Empty, Full

class RTMPStreamer:
    def __init__(self, rtmp_url: str, width: int = 1280, height: int = 720, fps: int = 15):
        self.rtmp_url = rtmp_url
        self.fps = fps
        self.frame_interval = 1.0 / fps
        self.process = None
        self.running = False
        
        # Buffer: Holds frames to smooth out bursts
        self.frame_queue = Queue(maxsize=3)  
        self.writer_thread = None
        
        # FFmpeg Command
        # -bufsize and -maxrate are critical for low-fps streaming stability
        command_str = (
            f"ffmpeg -y "
            # --- CRITICAL INPUT LATENCY FLAGS ---
            f"-fflags nobuffer -probesize 32 -analyzeduration 0 " 
            # ------------------------------------
            f"-f image2pipe -vcodec mjpeg -r {fps} -i - "
            f"-c:v libx264 -preset ultrafast -tune zerolatency "
            f"-pix_fmt yuv420p -g {fps*2} -b:v 1000k -maxrate 1000k -bufsize 1500k "
            f"-flush_packets 1 " # Forces immediate output
            f"-f flv {rtmp_url}"
        )
        self.command = shlex.split(command_str)
    
    def start(self):
        if self.process is not None:
            return
        
        print(f"📡 Starting RTMP Stream: {self.rtmp_url}")
        
        # 1. Start FFmpeg (bufsize=0 ensures unbuffered pipe for real-time)
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE, # Capture errors to debug "Black Screen"
            bufsize=0               # CRITICAL: Disable Python buffering
        )
        
        # 2. Start Background Pacer
        self.running = True
        self.writer_thread = threading.Thread(target=self._frame_pacer, daemon=True)
        self.writer_thread.start()
        
        # 3. Start Error Logger (Optional but recommended)
        threading.Thread(target=self._log_ffmpeg_errors, daemon=True).start()

    def _frame_pacer(self):
        """Writes frames ensuring a minimum time gap to smooth bursts."""
        last_write_time = 0
        
        while self.running:
            try:
                # Wait for a frame (blocking allows CPU to rest)
                frame_bytes = self.frame_queue.get(timeout=1.0)
            except Empty:
                continue # Keep waiting if no input

            # --- PACING LOGIC ---
            # Calculate how long since the last frame was sent
            elapsed = time.time() - last_write_time
            wait_needed = self.frame_interval - elapsed

            # If we are going too fast (Burst), slow down
            if wait_needed > 0:
                time.sleep(wait_needed)

            # Write to FFmpeg
            self._write_to_pipe(frame_bytes)
            last_write_time = time.time()

    def _write_to_pipe(self, frame_bytes):
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(frame_bytes)
                self.process.stdin.flush()
            except BrokenPipeError:
                print(f"⚠️ Pipe broken for {self.rtmp_url}. Restarting...")
                self._restart_process()
            except Exception as e:
                print(f"⚠️ Write Error: {e}")

    def write(self, frame_bytes: bytes):
        """Public API: Drops oldest frame if queue is full to prioritize live feed."""
        if not self.running: return

        try:
            self.frame_queue.put_nowait(frame_bytes)
        except Full:
            # Drop oldest to make room for new (Low Latency Strategy)
            try:
                self.frame_queue.get_nowait()
                self.frame_queue.put_nowait(frame_bytes)
            except:
                pass

    def _log_ffmpeg_errors(self):
        """Reads FFmpeg stderr to help debug black screens."""
        while self.running and self.process:
            line = self.process.stderr.readline()
            if line:
                # Filter out generic info, print only errors/warnings
                line_str = line.decode('utf-8', errors='ignore').strip()
                if "Error" in line_str or "warning" in line_str.lower():
                    print(f"ffmpeg [{self.rtmp_url}]: {line_str}")

    def _restart_process(self):
        self.stop()
        self.start()

    def stop(self):
        self.running = False
        if self.process:
            try:
                self.process.stdin.close()
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                pass
            self.process = None
        print(f"🛑 Stopped Stream: {self.rtmp_url}")