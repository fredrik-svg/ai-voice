#!/usr/bin/env python3
import sys, os, json, time, base64, threading, signal, yaml, uuid, logging
from src.mqtt_client import MqttClient
from src.audio_capture import AudioStreamer
from src.playback import play_wav_bytes
from src.gpio_button import Button
from src.utils import now_ms, new_session_id

# Setup logging
logger = logging.getLogger(__name__)

def check_venv():
    """Check if running in a virtual environment and warn if not."""
    # Check if we're in a virtual environment
    in_venv = (hasattr(sys, 'real_prefix') or 
               (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))
    
    if not in_venv:
        print("=" * 70, file=sys.stderr)
        print("VARNING: Körs inte i en virtuell Python-miljö!", file=sys.stderr)
        print("WARNING: Not running in a Python virtual environment!", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print("", file=sys.stderr)
        print("Detta kan orsaka problem på moderna Raspberry Pi OS (Bookworm)", file=sys.stderr)
        print("där systemets Python-miljö är 'externally-managed'.", file=sys.stderr)
        print("", file=sys.stderr)
        print("Rekommenderad lösning:", file=sys.stderr)
        print("  1. Kör: ./scripts/install_deps.sh (skapar venv)", file=sys.stderr)
        print("  2. Starta sedan med: ./scripts/run.sh", file=sys.stderr)
        print("", file=sys.stderr)
        print("Eller aktivera manuellt:", file=sys.stderr)
        print("  source venv/bin/activate", file=sys.stderr)
        print("  python3 -m src.agent config.yaml", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print("", file=sys.stderr)

def load_config(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

class VoiceAgent:
    def __init__(self, cfg):
        self.cfg = cfg
        self.mqtt = MqttClient(cfg)
        self.streamer = AudioStreamer(cfg)
        self.session_id = None
        self.seq = 0
        self.running = True
        self.mode = cfg['audio'].get('mode', 'ptt')
        self.topics = cfg['topics']
        self.button = None  # Store button reference for cleanup
        self.debug = cfg.get('debug', False)
        # Prepare topics
        for k in list(self.topics.keys()):
            t = self.topics[k].format(tenant=cfg['tenant'], user=cfg['user'], deviceId=cfg['deviceId'])
            self.topics[k] = t

    def connect(self):
        logger.info(f"Connecting to MQTT broker at {self.cfg['mqtt']['host']}:{self.cfg['mqtt']['port']}...")
        self.mqtt.connect()
        logger.info("✓ MQTT connected successfully")
        # subscribe to tts and response
        self.mqtt.subscribe(self.topics['tts'], qos=1, on_message=self.on_tts)
        self.mqtt.subscribe(self.topics['response'], qos=1, on_message=self.on_response)
        logger.info(f"✓ Subscribed to TTS and response topics")
        # online status
        self.publish_control({'status':'online'})
        logger.info(f"✓ Device '{self.cfg['deviceId']}' is now online")

    def publish_control(self, obj):
        payload = {
            'ts': now_ms(),
            'deviceId': self.cfg['deviceId'],
            **obj
        }
        if self.debug:
            logger.debug(f"[Control] {obj}")
        self.mqtt.publish_json(self.topics['control'], payload, qos=1, retain=False)

    def on_response(self, msg):
        try:
            data = json.loads(msg.payload.decode('utf-8'))
        except Exception:
            data = {'raw': msg.payload[:80].hex()}
        logger.info(f"[Response] {data}")

    def on_tts(self, msg):
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            if 'wav_b64' in data:
                wav = base64.b64decode(data['wav_b64'])
                logger.info(f"[TTS] Playing audio response ({len(wav)} bytes)")
                play_wav_bytes(wav, device=self.cfg['playback']['device'], volume_pct=self.cfg['playback'].get('volume_pct'))
                logger.info("[TTS] Playback complete")
        except Exception as e:
            logger.error(f"[TTS] Error: {e}")

    def _start_session(self):
        self.session_id = new_session_id()
        self.seq = 0
        logger.info(f"🎤 Session started: {self.session_id[:8]}...")
        self.publish_control({'event':'audio_start', 'session_id': self.session_id})

    def _end_session(self):
        if self.session_id:
            logger.info(f"✓ Session ended: {self.session_id[:8]}... ({self.seq} frames, {self.seq * self.cfg['audio']['chunk_ms']}ms)")
            self.publish_control({'event':'audio_end', 'session_id': self.session_id, 'frames': self.seq})
        self.session_id = None

    def _publish_frame(self, pcm: bytes):
        self.seq += 1
        if self.debug:
            logger.debug(f"[Audio] Frame {self.seq} ({len(pcm)} bytes)")
        self.mqtt.publish_json(self.topics['audio'], {
            'ts': now_ms(),
            'session_id': self.session_id,
            'seq': self.seq,
            'format': 's16le',
            'rate': self.cfg['audio']['rate'],
            'channels': self.cfg['audio']['channels'],
            'pcm_b64': base64.b64encode(pcm).decode('ascii')
        }, qos=0, retain=False)

    def run_ptt(self):
        # Button press toggles a single capture window (press=record for N seconds, auto-stop with VAD silence)
        self.button = Button(self.cfg['gpio']['button_pin'], self.cfg['gpio'].get('pull_up', True))
        self.button.on_pressed(lambda: threading.Thread(target=self._capture_once, daemon=True).start())
        self.button.start()
        logger.info(f"[Agent] PTT mode: press GPIO{self.cfg['gpio']['button_pin']} button to talk")
        logger.info(f"[Agent] VAD silence threshold: {self.cfg['audio']['vad_silence_ms']}ms")
        while self.running:
            time.sleep(0.2)

    def _capture_once(self):
        """Capture audio once (PTT mode) with graceful error handling."""
        try:
            self._start_session()
            self.streamer.start()
            silence_ms = 0
            try:
                for is_speech, frame in self.streamer.vad_stream():
                    if is_speech:
                        silence_ms = 0
                        self._publish_frame(frame)
                    else:
                        silence_ms += self.cfg['audio']['chunk_ms']
                        if silence_ms >= int(self.cfg['audio']['vad_silence_ms']):
                            logger.debug(f"Silence threshold reached ({silence_ms}ms), ending capture")
                            break
            finally:
                self.streamer.stop()
        except Exception as e:
            logger.error(f"[ERROR] Audio capture failed: {e}")
        finally:
            self._end_session()

    def run_vad(self):
        """Run in VAD mode with graceful error handling."""
        logger.info("[Agent] VAD mode: auto start on voice, stop after silence")
        logger.info(f"[Agent] VAD aggressiveness: {self.cfg['audio']['vad_mode']}, silence threshold: {self.cfg['audio']['vad_silence_ms']}ms")
        try:
            self.streamer.start()
            in_session = False
            silence_ms = 0
            try:
                for is_speech, frame in self.streamer.vad_stream():
                    if is_speech and not in_session:
                        in_session = True
                        self._start_session()
                        silence_ms = 0
                    if in_session:
                        if is_speech:
                            self._publish_frame(frame)
                            silence_ms = 0
                        else:
                            silence_ms += self.cfg['audio']['chunk_ms']
                        if silence_ms >= int(self.cfg['audio']['vad_silence_ms']):
                            logger.debug(f"Silence threshold reached ({silence_ms}ms), ending session")
                            self._end_session()
                            in_session = False
                            silence_ms = 0
            finally:
                self.streamer.stop()
                if in_session:
                    self._end_session()
        except Exception as e:
            logger.error(f"[ERROR] Audio capture failed: {e}")
            logger.error(f"[ERROR] VAD mode cannot continue without audio device. Exiting.")
            self.stop()
            sys.exit(1)

    def stop(self):
        logger.info("Shutting down voice agent...")
        self.running = False
        try: self.streamer.stop()
        except Exception: pass
        if self.button:
            try: self.button.stop()
            except Exception: pass
        self.publish_control({'status':'offline'})
        logger.info("✓ Voice agent stopped")

def main():
    # Check if running in virtual environment
    check_venv()
    
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    with open(cfg_path, 'r') as f:
        cfg = yaml.safe_load(f)
    
    # Setup logging based on debug flag
    debug = cfg.get('debug', False)
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    if debug:
        logger.info("Debug mode enabled - verbose logging active")
    
    agent = VoiceAgent(cfg)
    agent.connect()

    import signal
    def handle_sig(sig, frm):
        agent.stop()
        sys.exit(0)
    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    mode = cfg['audio'].get('mode', 'ptt').lower()
    if mode == 'vad':
        agent.run_vad()
    else:
        agent.run_ptt()

if __name__ == "__main__":
    main()
