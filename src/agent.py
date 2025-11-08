#!/usr/bin/env python3
import sys, os, json, time, base64, threading, signal, yaml, uuid
from src.mqtt_client import MqttClient
from src.audio_capture import AudioStreamer
from src.playback import play_wav_bytes
from src.gpio_button import Button
from src.utils import now_ms, new_session_id

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
        # Prepare topics
        for k in list(self.topics.keys()):
            t = self.topics[k].format(tenant=cfg['tenant'], user=cfg['user'], deviceId=cfg['deviceId'])
            self.topics[k] = t

    def connect(self):
        self.mqtt.connect()
        # subscribe to tts and response
        self.mqtt.subscribe(self.topics['tts'], qos=1, on_message=self.on_tts)
        self.mqtt.subscribe(self.topics['response'], qos=1, on_message=self.on_response)
        # online status
        self.publish_control({'status':'online'})

    def publish_control(self, obj):
        self.mqtt.publish_json(self.topics['control'], {
            'ts': now_ms(),
            'deviceId': self.cfg['deviceId'],
            **obj
        }, qos=1, retain=False)

    def on_response(self, msg):
        try:
            data = json.loads(msg.payload.decode('utf-8'))
        except Exception:
            data = {'raw': msg.payload[:80].hex()}
        print("[response]", data)

    def on_tts(self, msg):
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            if 'wav_b64' in data:
                wav = base64.b64decode(data['wav_b64'])
                play_wav_bytes(wav, device=self.cfg['playback']['device'], volume_pct=self.cfg['playback'].get('volume_pct'))
        except Exception as e:
            print("[tts] error:", e)

    def _start_session(self):
        self.session_id = new_session_id()
        self.seq = 0
        self.publish_control({'event':'audio_start', 'session_id': self.session_id})

    def _end_session(self):
        if self.session_id:
            self.publish_control({'event':'audio_end', 'session_id': self.session_id, 'frames': self.seq})
        self.session_id = None

    def _publish_frame(self, pcm: bytes):
        self.seq += 1
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
        print("[agent] PTT mode: press the HAT button to talk (or press Enter in console).")
        while self.running:
            time.sleep(0.2)

    def _capture_once(self):
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
                            break
            finally:
                self.streamer.stop()
        except Exception as e:
            print(f"[ERROR] Audio capture failed: {e}", file=sys.stderr)
        finally:
            self._end_session()

    def run_vad(self):
        print("[agent] VAD mode: auto start on voice, stop after silence.")
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
                        self._publish_frame(frame)
                        silence_ms = 0 if is_speech else (silence_ms + self.cfg['audio']['chunk_ms'])
                        if silence_ms >= int(self.cfg['audio']['vad_silence_ms']):
                            self._end_session()
                            in_session = False
            finally:
                self.streamer.stop()
                if in_session:
                    self._end_session()
        except Exception as e:
            print(f"[ERROR] Audio capture failed: {e}", file=sys.stderr)
            print(f"[ERROR] VAD mode cannot continue without audio device. Exiting.", file=sys.stderr)
            self.stop()
            sys.exit(1)

    def stop(self):
        self.running = False
        try: self.streamer.stop()
        except Exception: pass
        if self.button:
            try: self.button.stop()
            except Exception: pass
        self.publish_control({'status':'offline'})

def main():
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    with open(cfg_path, 'r') as f:
        cfg = yaml.safe_load(f)
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
