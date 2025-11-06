import subprocess, threading, collections, time
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

    def start(self):
        if self.running: return
        self.proc = subprocess.Popen(self._arecord_cmd(), stdout=subprocess.PIPE, bufsize=0)
        self.running = True

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
