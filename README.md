# Raspberry Pi Zero 2 WH – Voice Agent (KEYESTUDIO ReSpeaker 2-Mic Pi HAT V1.0)

Lättviktig röstagent som:
- spelar in 16 kHz mono via **WM8960** (I²S) på KEYESTUDIO ReSpeaker 2‑Mic Pi HAT **V1.0**,
- VAD (WebRTC) + push-to-talk via **GPIO17**-knappen,
- streamar PCM som base64‑chunks över **MQTT** till din backend/n8n,
- spelar upp TTS‑svar (WAV base64) lokalt via `aplay`.

> **Obs!** Detta projekt förutsätter **V1.0**-hatten (codec **WM8960**). Har du annan modell (t.ex. Seeed V2 med TLV320) behöver du rätt overlay/drivrutin för den.

## Topics (default)
- Up: `t/<tenant>/u/<user>/voice/<deviceId>/audio` (QoS 0) – JSON med `pcm_b64` i 20 ms-ramar
- Ctl: `t/<tenant>/u/<user>/voice/<deviceId>/control` (QoS 1) – `status|audio_start|audio_end`
- Down: `t/<tenant>/u/<user>/voice/<deviceId>/response` (QoS 1) – valfria meddelanden
- TTS: `t/<tenant>/u/<user>/voice/<deviceId>/tts` (QoS 1) – JSON `{ wav_b64: "<...>" }`

## Krav
- Raspberry Pi **Zero 2 WH**
- KEYESTUDIO ReSpeaker 2‑Mic Pi HAT **V1.0** (WM8960)
- Raspberry Pi OS (Bookworm rekommenderas)
- MQTT‑broker (TLS), t.ex. Mosquitto/EMQX/HiveMQ

## Installation (på Pi)
```bash
git clone <ditt-repo> voice-agent
cd voice-agent
cp config.example.yaml config.yaml

# Installera paket och Python-deps
chmod +x scripts/install_deps.sh
./scripts/install_deps.sh
```

### Aktivera WM8960 (ljudkort)
Följ HAT‑leverantörens guide för WM8960/seeed‑voicecard på Bookworm.
Testa sedan att spela in/upp:
```bash
arecord -l                # se kort-id
arecord -D plughw:1,0 -f S16_LE -r 16000 -d 3 test.wav
aplay   -D plughw:1,0 test.wav
```
Ställ in ditt `device` i `config.yaml` (t.ex. `plughw:1,0`).

## Konfiguration
Redigera `config.yaml`:
```yaml
tenant: GENIO
user: fredrik
deviceId: voice-zero-2

mqtt:
  host: broker.example.com
  port: 8883
  username: voice-user
  password: s3cret
  tls: true

topics:
  audio: "t/{tenant}/u/{user}/voice/{deviceId}/audio"
  control: "t/{tenant}/u/{user}/voice/{deviceId}/control"
  response: "t/{tenant}/u/{user}/voice/{deviceId}/response"
  tts: "t/{tenant}/u/{user}/voice/{deviceId}/tts"

audio:
  device: "plughw:1,0"
  rate: 16000
  chunk_ms: 20
  vad_mode: 2
  vad_silence_ms: 800
  mode: "ptt"   # eller "vad"

gpio:
  button_pin: 17
  pull_up: true

playback:
  device: "plughw:1,0"
  volume_pct: 90
```

## Kör
```bash
# Dev
chmod +x scripts/run.sh
./scripts/run.sh

# Prod (systemd)
sudo cp systemd/voice-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable voice-agent
sudo systemctl start voice-agent
sudo journalctl -u voice-agent -f
```

## Backend: exempel på TTS-svar
Publicera en WAV (16 kHz, mono) som base64 till `tts`-topic:
```json
{
  "wav_b64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAA..."
}
```
Agenten spelar upp via `aplay` på ALSA‑enheten i `config.yaml`.

## Säkerhet
- Kör MQTT över **TLS**. Använd **mTLS** eller **kortlivad JWT** i produktion.
- Lås ACL så denna device endast kan publicera/lyssna på sina egna topics.

## Felsökning
- Ingen ljudenhet? Kontrollera att I²S är på (`dtparam=i2s=on`) och att rätt WM8960‑overlay/drivrutin är installerad.
- Hackigt ljud? Prova `plughw` istället för `hw`, sänk `vad_mode` till 1, eller öka `vad_silence_ms`.
- CPU-spikar? Kör i **ptt**‑läge och undvik konstant VAD om nätaggregatet är svagt.

## Licens
MIT
