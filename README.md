# Raspberry Pi Voice Agent

Lättviktig röstagent som:
- spelar in 16 kHz mono via ljudenhet (I²S HAT eller USB),
- VAD (WebRTC) + push-to-talk via GPIO-knapp,
- streamar PCM som base64‑chunks över **MQTT** till din backend/n8n,
- spelar upp TTS‑svar (WAV base64) lokalt via `aplay`.

## Hårdvaruvarianter

Projektet stödjer flera Raspberry Pi-konfigurationer:

### Raspberry Pi Zero 2 WH + KEYESTUDIO ReSpeaker 2-Mic Pi HAT V1.0 (I²S)
- **Ljudkort:** WM8960 (I²S)
- **Mikrofoner:** 2 kanaler (stereo)
- **Knapp:** GPIO17 (inbyggd på HAT)
- **Dokumentation:** [README.md](README.md) (denna fil)
- **Config:** `config.example.yaml`

### Raspberry Pi 5 + ReSpeaker USB 4-Mic Array 📘
- **Ljudkort:** USB Audio (UAC 1.0)
- **Mikrofoner:** 6 kanaler (4 mics + processat ljud + playback)
- **DSP:** Inbyggd AEC, beamforming, brusreducering
- **Snabbstart:** [docs/QUICKSTART_PI5.md](docs/QUICKSTART_PI5.md) ⭐
- **Dokumentation:** [README.pi5-usb.md](README.pi5-usb.md)
- **Config:** `config.pi5-usb.example.yaml`
- **Installation:** `scripts/install_deps_pi5.sh`

> **Välj rätt variant:** Detta dokument beskriver konfigurationen för **Raspberry Pi Zero 2 WH med I²S HAT**. För **Raspberry Pi 5 med USB-array**, se [README.pi5-usb.md](README.pi5-usb.md).

---

## Raspberry Pi Zero 2 WH med KEYESTUDIO ReSpeaker 2-Mic Pi HAT V1.0

> **Obs!** Detta avsnitt förutsätter **V1.0**-hatten (codec **WM8960**). Har du annan modell (t.ex. Seeed V2 med TLV320) behöver du rätt overlay/drivrutin för den.

## Topics (default)
- Up: `t/<tenant>/u/<user>/voice/<deviceId>/audio` (QoS 0) – JSON med `pcm_b64` i 20 ms-ramar
- Ctl: `t/<tenant>/u/<user>/voice/<deviceId>/control` (QoS 1) – `status|audio_start|audio_end`
- Down: `t/<tenant>/u/<user>/voice/<deviceId>/response` (QoS 1) – valfria meddelanden
- TTS: `t/<tenant>/u/<user>/voice/<deviceId>/tts` (QoS 1) – JSON `{ wav_b64: "<...>" }`

> **För n8n-integration:** Se [docs/N8N_INTEGRATION.md](docs/N8N_INTEGRATION.md) för detaljer om hur man bygger ett workflow som vet vilket topic den ska svara på.

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

# Installera paket och Python-deps (skapar automatiskt en virtuell miljö)
chmod +x scripts/install_deps.sh
./scripts/install_deps.sh
```

**OBS:** Skriptet skapar automatiskt en virtuell Python-miljö (`venv/`) för att undvika problem med "externally-managed-environment" i moderna Raspberry Pi OS-versioner (Bookworm).

### Aktivera WM8960 (ljudkort)
Följ HAT‑leverantörens guide för WM8960/seeed‑voicecard på Bookworm.
Testa sedan att spela in/upp:
```bash
arecord -l                # se kort-id
# WM8960 kräver stereo (2 kanaler) inspelning
# Buffer och period size förhindrar I/O-fel
arecord -D plughw:1,0 -c 2 -f S16_LE -r 16000 --buffer-size 8192 --period-size 1024 -d 3 test.wav
aplay   -D plughw:1,0 test.wav
```
Ställ in ditt `device` i `config.yaml` (t.ex. `plughw:1,0`).

**OBS:** WM8960-kodeken kräver stereoinspelning (2 kanaler). Programmet hanterar automatiskt konvertering från stereo till mono via sox.

**Tips:** Om du får "Input/output error" vid inspelning, kontrollera att buffer- och periodstorlekarna är korrekt inställda i `config.yaml`. Standardvärdena (buffer_size: 8192, period_size: 1024) är optimerade för WM8960.

## Konfiguration
Redigera `config.yaml`:
```yaml
tenant: GENIO
user: fredrik
deviceId: voice-zero-2

mqtt:
  host: YOUR_HIVEMQ_CLOUD_HOST.hivemq.cloud  # t.ex. abc123.s1.eu.hivemq.cloud för HiveMQ Cloud
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
  device: "plughw:1,0"  # För seeed-2mic-voicecard (WM8960), använd card 1
  rate: 16000
  chunk_ms: 20
  vad_mode: 2
  vad_silence_ms: 800
  mode: "ptt"   # eller "vad"

gpio:
  button_pin: 17
  pull_up: true

playback:
  device: "plughw:1,0"  # Samma som audio device
  volume_pct: 90
```

### HiveMQ Cloud Konfiguration
Om du använder HiveMQ Cloud:
1. Skapa ett kluster på [HiveMQ Cloud](https://www.hivemq.com/mqtt-cloud-broker/)
2. Kopiera kluster-URL:en (t.ex. `abc123.s1.eu.hivemq.cloud`) till `mqtt.host`
3. Använd port `8883` för TLS-krypterad MQTT
4. Sätt `tls: true` för säker anslutning
5. Konfigurera användarnamn och lösenord från HiveMQ Cloud-kontrollpanelen

### Ljudkort Konfiguration
För att hitta rätt ljudkortsinställning, kör:
```bash
arecord -l
```

Exempel på output för seeed-2mic-voicecard (WM8960):
```
card 1: seeed2micvoicec [seeed-2mic-voicecard], device 0: bcm2835-i2s-wm8960-hifi wm8960-hifi-0 [...]
```

Använd sedan `plughw:1,0` i config.yaml (där `1` är card-numret och `0` är device-numret).

## Testning
Systemet inkluderar MQTT-tester för att verifiera anslutningen:

```bash
# Kör MQTT-tester
chmod +x tests/run_tests.sh
./tests/run_tests.sh
```

### Test mot HiveMQ Cloud
Testerna läser automatiskt från `config.yaml`:
- Om `config.yaml` har en giltig MQTT-broker (inte `YOUR_*` placeholder), används den för testning
- Om `config.yaml` inte finns eller har placeholders, används localhost (kräver Mosquitto)

För att testa mot HiveMQ Cloud:
1. Konfigurera `config.yaml` med dina HiveMQ Cloud-inställningar
2. Kör `./tests/run_tests.sh`
3. Testerna kommer ansluta till din HiveMQ Cloud-broker och verifiera funktionaliteten

## Kör
```bash
# Dev
chmod +x scripts/run.sh
./scripts/run.sh   # Aktiverar automatiskt venv om den finns

# Prod (systemd)
sudo cp systemd/voice-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable voice-agent
sudo systemctl start voice-agent
sudo journalctl -u voice-agent -f
```

**Tips:** Systemd-tjänsten använder automatiskt den virtuella miljön (`venv/bin/python3`) som skapades under installationen.

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

### "arecord failed to start (exit code -13)" eller behörighetsfel
Detta är vanligtvis ett behörighetsproblem. Din användare har inte tillåtelse att komma åt ljudenheten.

**Lösning:**
```bash
# Lägg till din användare i audio-gruppen
sudo usermod -a -G audio $USER

# Logga ut och logga in igen (eller starta om)
# Verifiera att du är med i gruppen:
groups
# Du ska se "audio" i listan
```

**Alternativ lösning (tillfällig, för testning):**
```bash
# Ändra behörigheter på ljudenheterna (återställs vid omstart)
sudo chmod a+rw /dev/snd/*
```

### Andra felsökningstips
- Ingen ljudenhet? Kontrollera att I²S är på (`dtparam=i2s=on`) och att rätt WM8960‑overlay/drivrutin är installerad.
- **Input/output error** vid inspelning? WM8960-kodeken kräver korrekt buffer- och periodstorlek. Kontrollera att `buffer_size: 8192` och `period_size: 1024` är satta i `config.yaml` (standardvärdena). Testa även med `arecord -D plughw:1,0 -c 2 -f S16_LE -r 16000 --buffer-size 8192 --period-size 1024 -d 3 test.wav`.
- Hackigt ljud? Prova `plughw` istället för `hw`, sänk `vad_mode` till 1, eller öka `vad_silence_ms`.
- CPU-spikar? Kör i **ptt**‑läge och undvik konstant VAD om nätaggregatet är svagt.

## Licens
MIT
