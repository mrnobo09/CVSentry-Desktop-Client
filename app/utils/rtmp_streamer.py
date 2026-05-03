import subprocess
import shlex
import threading

class RTMPStreamer:
    def __init__(self, rtmp_url: str, fps: int = 10):
        self.rtmp_url = rtmp_url
        self.fps = fps
        self.process = None
        self.running = False

        # FFmpeg command
        command_str = (
            f"ffmpeg -y "
            
            f"-use_wallclock_as_timestamps 1 "
            f"-fflags +nobuffer+discardcorrupt "
            f"-probesize 32 -analyzeduration 0 "
            f"-f image2pipe -vcodec mjpeg -i - "  
            
            f"-c:v libx264 "
            f"-preset ultrafast "
            f"-tune zerolatency "
            f"-x264-params 'bframes=0:force-cfr=1:no-mbtree=1:sync-lookahead=0:rc-lookahead=0:sliced-threads=1:threads=2' "
            f"-pix_fmt yuv420p "
            f"-bf 0 "
            f"-flags +low_delay "
            
            # ── RATE CONTROL: CBR with tighter buffer ──
            f"-b:v 300k -minrate 300k -maxrate 300k -bufsize 150k "
            
            # ── GOP: keyframe every second, no scene-cut insertions ──
            f"-r {fps} -g {fps} -keyint_min {fps} -sc_threshold 0 "
            
            # ── OUTPUT: zero client-side RTMP buffering ──
            f"-flush_packets 1 "
            f"-rtmp_buffer 0 "
            f"-rtmp_live live "
            f"-f flv {rtmp_url}"
        )
        self.command = shlex.split(command_str)

    def start(self):
        if self.process is not None:
            return
        
        print(f"📡 Starting RTMP Stream: {self.rtmp_url}")
        
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        
        self.running = True
        threading.Thread(target=self._log_ffmpeg_errors, daemon=True).start()

    def write(self, frame_bytes: bytes):
        """Direct, blocking write to FFmpeg. Zero queues, zero artificial pacing."""
        if not self.running or not self.process or not self.process.stdin:
            return

        try:
            self.process.stdin.write(frame_bytes)
            self.process.stdin.flush()
        except BrokenPipeError:
            print(f"⚠️ Pipe broken for {self.rtmp_url}. Restarting...")
            self._restart_process()
        except Exception as e:
            print(f"⚠️ Write Error: {e}")

    def _log_ffmpeg_errors(self):
        while self.running and self.process:
            line = self.process.stderr.readline()
            if line:
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