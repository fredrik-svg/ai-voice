import subprocess, threading, collections, time, warnings, sys

# Suppress the pkg_resources deprecation warning from webrtcvad
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources.*")
    import webrtcvad

class AudioStreamer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.rate = int(cfg['audio']['rate'])
        self.chunk_ms = int(cfg['audio']['chunk_ms'])
        self.chunk_bytes = int(self.rate * 2 * self.chunk_ms / 1000)  # S16_LE mono => 2 bytes/sample
        self.device = cfg['audio']['device']
        self.format = cfg['audio']['format']
        self.proc = None
        self.vad = webrtcvad.Vad(int(cfg['audio']['vad_mode']))
        self.running = False

    def _arecord_cmd(self):
        return [
            'arecord',
            '-q',
            '-D', self.device,
            '-c', str(self.cfg['audio']['channels']),
            '-f', self.format,
            '-r', str(self.rate),
            '-t', 'raw'
        ]

    def validate_device(self):
        """Check if the audio device exists and is accessible."""
        try:
            # Try to list ALSA devices
            result = subprocess.run(['arecord', '-l'], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                print(f"[WARNING] Unable to list audio devices. Device '{self.device}' may not exist.", file=sys.stderr)
                print(f"[WARNING] Error output: {result.stderr.strip()}", file=sys.stderr)
                return False
            
            # Check if the device appears in the list (basic check)
            if 'card' not in result.stdout.lower():
                print(f"[WARNING] No audio capture devices found. Device '{self.device}' does not exist.", file=sys.stderr)
                print(f"[INFO] Available devices:\n{result.stdout}", file=sys.stderr)
                return False
            
            return True
        except FileNotFoundError:
            print(f"[ERROR] arecord command not found. Please install alsa-utils.", file=sys.stderr)
            return False
        except subprocess.TimeoutExpired:
            print(f"[WARNING] Timeout while checking audio devices.", file=sys.stderr)
            return False
        except Exception as e:
            print(f"[WARNING] Error checking audio device: {e}", file=sys.stderr)
            return False

    def start(self):
        if self.running: return
        
        # Validate device before attempting to start
        if not self.validate_device():
            print(f"[ERROR] Audio device '{self.device}' validation failed.", file=sys.stderr)
            print(f"[INFO] Please check your config.yaml and ensure the audio device is correctly configured.", file=sys.stderr)
            print(f"[INFO] Run 'arecord -l' to list available capture devices.", file=sys.stderr)
        
        try:
            self.proc = subprocess.Popen(
                self._arecord_cmd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Give the process a moment to start, then check if it failed immediately
            time.sleep(0.1)
            poll_result = self.proc.poll()
            if poll_result is not None:
                # Process has already exited - read the error
                stderr_output = self.proc.stderr.read().decode('utf-8', errors='replace').strip()
                print(f"[ERROR] arecord failed to start (exit code {poll_result})", file=sys.stderr)
                if stderr_output:
                    print(f"[ERROR] arecord output: {stderr_output}", file=sys.stderr)
                if "audio open error" in stderr_output.lower():
                    print(f"[ERROR] Failed to open audio device '{self.device}'. Please verify the device exists.", file=sys.stderr)
                    print(f"[INFO] Run 'arecord -l' to list available capture devices.", file=sys.stderr)
                raise RuntimeError(f"Failed to start audio capture: {stderr_output}")
            
            self.running = True
        except FileNotFoundError:
            print(f"[ERROR] arecord command not found. Please install alsa-utils.", file=sys.stderr)
            raise
        except Exception as e:
            print(f"[ERROR] Failed to start audio capture: {e}", file=sys.stderr)
            raise

    def stop(self):
        if not self.running: return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=2)
        except Exception:
            self.proc.kill()
        self.running = False

    def frames(self):
        """Yield 20ms frames; each frame is bytes of length chunk_bytes."""
        buf = b''
        while self.running:
            data = self.proc.stdout.read(self.chunk_bytes - len(buf))
            if not data:
                break
            buf += data
            if len(buf) >= self.chunk_bytes:
                frame, buf = buf[:self.chunk_bytes], buf[self.chunk_bytes:]
                yield frame

    def vad_stream(self):
        """Detect speech segments using VAD; yield (is_speech, frame_bytes)."""
        for frame in self.frames():
            is_speech = self.vad.is_speech(frame, self.rate)
            yield is_speech, frame
