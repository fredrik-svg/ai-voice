import subprocess, threading, collections, time, warnings, sys

# Suppress the pkg_resources deprecation warning from webrtcvad
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources.*")
    import webrtcvad

# Constants
PROCESS_START_CHECK_DELAY = 0.1  # seconds to wait before checking if arecord started successfully

class AudioStreamer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.rate = int(cfg['audio']['rate'])
        self.chunk_ms = int(cfg['audio']['chunk_ms'])
        self.chunk_bytes = int(self.rate * 2 * self.chunk_ms / 1000)  # S16_LE mono => 2 bytes/sample
        self.device = cfg['audio']['device']
        self.format = cfg['audio']['format']
        self.proc = None
        self.arecord_proc = None
        self.vad = webrtcvad.Vad(int(cfg['audio']['vad_mode']))
        self.running = False


    def _arecord_cmd(self):
        # WM8960 codec requires 2-channel (stereo) capture
        # We record in stereo and convert to mono using sox
        # to maintain compatibility with downstream mono processing
        # 
        # Buffer and period sizes are set to prevent I/O errors:
        # - Buffer size: 8192 frames (prevents buffer underruns)
        # - Period size: 1024 frames (balances latency and reliability)
        # These values are optimized for WM8960 at 16kHz stereo
        buffer_size = self.cfg['audio'].get('buffer_size', 8192)
        period_size = self.cfg['audio'].get('period_size', 1024)
        
        arecord_part = [
            'arecord',
            '-q',
            '-D', self.device,
            '-c', '2',  # Record in stereo (hardware requirement)
            '-f', self.format,
            '-r', str(self.rate),
            '-t', 'raw',
            '--buffer-size', str(buffer_size),
            '--period-size', str(period_size)
        ]
        
        # Convert stereo to mono using sox
        # -t raw: raw PCM format
        # -e signed-integer: signed integer samples
        # -b 16: 16-bit samples
        # -c 2: input is stereo
        # -r rate: sample rate
        # channels 1: output mono (averages the two channels)
        sox_part = [
            'sox',
            '-t', 'raw',
            '-e', 'signed-integer',
            '-b', '16',
            '-c', '2',
            '-r', str(self.rate),
            '-',  # read from stdin
            '-t', 'raw',
            '-e', 'signed-integer', 
            '-b', '16',
            '-c', '1',  # output mono
            '-r', str(self.rate),
            '-'  # write to stdout
        ]
        
        return arecord_part, sox_part

    def validate_device(self):
        """Check if audio capture devices are available.
        
        This is a best-effort check to provide early feedback. The definitive
        validation happens when arecord actually attempts to open the device.
        
        Returns:
            bool: True if audio devices appear to be available, False otherwise.
        """
        try:
            # Try to list ALSA devices
            result = subprocess.run(['arecord', '-l'], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                print(f"[WARNING] Unable to list audio devices. Device '{self.device}' may not exist.", file=sys.stderr)
                print(f"[WARNING] Error output: {result.stderr.strip()}", file=sys.stderr)
                return False
            
            # Check if any capture devices are available (basic check)
            if 'card' not in result.stdout.lower():
                print(f"[WARNING] No audio capture devices found.", file=sys.stderr)
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
        
        # Validate device availability (best-effort check)
        # Note: This provides early feedback but doesn't guarantee the specific
        # device in config will work. The actual validation happens when arecord starts.
        if not self.validate_device():
            print(f"[WARNING] Audio device pre-check failed. Will attempt to start anyway...", file=sys.stderr)
        
        try:
            # Create a pipeline: arecord (stereo) | sox (stereo->mono conversion)
            arecord_cmd, sox_cmd = self._arecord_cmd()
            
            # Start arecord process
            arecord_proc = subprocess.Popen(
                arecord_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Start sox process, reading from arecord's stdout
            self.proc = subprocess.Popen(
                sox_cmd,
                stdin=arecord_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Allow arecord to receive SIGPIPE if sox exits
            arecord_proc.stdout.close()
            
            # Store arecord process for cleanup
            self.arecord_proc = arecord_proc
            
            # Give the processes a moment to start, then check if they failed immediately
            time.sleep(PROCESS_START_CHECK_DELAY)
            
            # Check if arecord failed
            arecord_poll = arecord_proc.poll()
            if arecord_poll is not None:
                stderr_output = arecord_proc.stderr.read().decode('utf-8', errors='replace').strip()
                print(f"[ERROR] arecord failed to start (exit code {arecord_poll})", file=sys.stderr)
                if stderr_output:
                    print(f"[ERROR] arecord output: {stderr_output}", file=sys.stderr)
                if "audio open error" in stderr_output.lower():
                    print(f"[ERROR] Failed to open audio device '{self.device}'.", file=sys.stderr)
                    print(f"[INFO] Please verify the device exists and is configured correctly in config.yaml.", file=sys.stderr)
                    print(f"[INFO] Run 'arecord -l' to list available capture devices.", file=sys.stderr)
                raise RuntimeError(f"Failed to start audio capture: {stderr_output}")
            
            # Check if sox failed
            sox_poll = self.proc.poll()
            if sox_poll is not None:
                stderr_output = self.proc.stderr.read().decode('utf-8', errors='replace').strip()
                print(f"[ERROR] sox failed to start (exit code {sox_poll})", file=sys.stderr)
                if stderr_output:
                    print(f"[ERROR] sox output: {stderr_output}", file=sys.stderr)
                raise RuntimeError(f"Failed to start audio conversion: {stderr_output}")
            
            self.running = True
        except FileNotFoundError as e:
            if 'arecord' in str(e):
                print(f"[ERROR] arecord command not found. Please install alsa-utils.", file=sys.stderr)
            elif 'sox' in str(e):
                print(f"[ERROR] sox command not found. Please install sox.", file=sys.stderr)
            else:
                print(f"[ERROR] Command not found: {e}", file=sys.stderr)
            raise
        except Exception as e:
            print(f"[ERROR] Failed to start audio capture: {e}", file=sys.stderr)
            raise

    def stop(self):
        if not self.running: return
        
        # Terminate both sox and arecord processes
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except Exception:
                self.proc.kill()
        
        if hasattr(self, 'arecord_proc') and self.arecord_proc:
            self.arecord_proc.terminate()
            try:
                self.arecord_proc.wait(timeout=2)
            except Exception:
                self.arecord_proc.kill()
        
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
