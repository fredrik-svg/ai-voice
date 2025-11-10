# Raspberry Pi 5 – Voice Agent (ReSpeaker USB 4-Mic Array)

Lättviktig röstagent optimerad för **Raspberry Pi 5** som:
- spelar in 16 kHz mono via **ReSpeaker USB 4-Mic Array** (USB audio),
- använder hårdvaru-DSP för AEC, beamforming och brusreducering,
- VAD (WebRTC) för automatisk aktivering eller manuell push-to-talk,
- streamar PCM som base64-chunks över **MQTT** till din backend/n8n,
- spelar upp TTS-svar (WAV base64) lokalt via USB-arrayens 3.5mm-utgång.

> **Obs!** Denna variant är anpassad för **Raspberry Pi 5** med **ReSpeaker USB 4-Mic Array**. För Raspberry Pi Zero 2 med I²S HAT, se [README.md](README.md).

## Funktioner specifika för ReSpeaker USB 4-Mic Array

### Inbyggd DSP-bearbetning
ReSpeaker USB 4-Mic Array har en XMOS XVF-3000 DSP som ger:
- **Acoustic Echo Cancellation (AEC)**: Eliminerar eko från högtalare
- **Beamforming**: Fokuserar på ljud från önskad riktning
- **Noise Suppression**: Reducerar bakgrundsljud
- **De-reverberation**: Minskar ekande ljud
- **Voice Activity Detection (VAD)**: Hårdvarubaserad röstdetektering

### 6-kanalers audiokonfiguration
Arrayen tillhandahåller 6 audiokanaler:
- **Kanal 0**: Processat ljud (AEC, beamforming, brusreducering) - **rekommenderat för ASR**
- **Kanal 1-4**: Rått ljud från varje mikrofon
- **Kanal 5**: Uppspelningsljud (playback)

Standard konfigurationen använder **kanal 0** (processat ljud) för bästa ASR-resultat.

### 12 RGB-lysdioder
Arrayen har 12 individuellt adresserbara RGB-LEDs som kan användas för visuell feedback (kräver separat implementation).

## Krav
- **Raspberry Pi 5**
- **ReSpeaker USB 4-Mic Array** (USB)
- Raspberry Pi OS (Bookworm rekommenderas)
- MQTT-broker (TLS), t.ex. Mosquitto/EMQX/HiveMQ

## Installation (på Pi 5)

```bash
git clone <ditt-repo> voice-agent
cd voice-agent
cp config.pi5-usb.example.yaml config.yaml

# Installera paket och Python-deps (skapar automatiskt en virtuell miljö)
chmod +x scripts/install_deps_pi5.sh
./scripts/install_deps_pi5.sh
```

**OBS:** Skriptet skapar automatiskt en virtuell Python-miljö (`venv/`) för att undvika problem med "externally-managed-environment" i moderna Raspberry Pi OS-versioner (Bookworm).

### Verifiera USB-ljudenheten

Efter installation, verifiera att ReSpeaker USB 4-Mic Array är igenkänd:

```bash
arecord -l
```

Du bör se något liknande:
```
card 1: ArrayUAC10 [ReSpeaker 4 Mic Array (UAC1.0)], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
```

### Testa ljudinspelning

Testa inspelning med alla 6 kanaler:
```bash
# Spela in 3 sekunder med 6 kanaler
arecord -D plughw:CARD=ArrayUAC10,DEV=0 -c 6 -f S16_LE -r 16000 -d 3 test.wav

# Spela upp (USB-arrayen har 3.5mm utgång)
aplay -D plughw:CARD=ArrayUAC10,DEV=0 test.wav
```

**Tips:** Om `ArrayUAC10` inte fungerar, använd `plughw:1,0` där `1` är kortnumret från `arecord -l`.

## Konfiguration

Redigera `config.yaml`:

```yaml
tenant: GENIO
user: fredrik
deviceId: voice-pi5-usb

mqtt:
  host: YOUR_HIVEMQ_CLOUD_HOST.hivemq.cloud
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
  device: "plughw:CARD=ArrayUAC10,DEV=0"  # ReSpeaker USB 4-Mic Array
  rate: 16000
  chunk_ms: 20
  vad_mode: 2
  vad_silence_ms: 800
  mode: "vad"           # "vad" rekommenderas (automatisk) eller "ptt" (knapp)
  buffer_size: 4096     # USB behöver mindre buffertar än I²S
  period_size: 512      # Optimerat för USB-ljud
  input_channels: 6     # ReSpeaker USB har 6 kanaler
  channel_mode: "processed"  # "processed" (kanal 0) eller "beamformed" (avg kanaler 1-4)

gpio:
  button_pin: 17        # Endast för PTT-läge med extern knapp
  pull_up: true

playback:
  device: "plughw:CARD=ArrayUAC10,DEV=0"  # USB-arrayens 3.5mm utgång
  volume_pct: 90
```

### Audio-konfiguration: Detaljerad förklaring

#### `device`
ALSA-enhetsnamn för ReSpeaker USB 4-Mic Array. Kan vara:
- `plughw:CARD=ArrayUAC10,DEV=0` (namnbaserat, rekommenderat)
- `plughw:1,0` (kortnummer från `arecord -l`)

#### `input_channels`
Antal kanaler att spela in från hårdvaran:
- `6`: Alla kanaler (standard för ReSpeaker USB)
- `1`: Endast processat ljud (kräver speciell firmware)

#### `channel_mode`
Hur multi-kanaler konverteras till mono:
- `"processed"`: Använd kanal 0 (DSP-processat ljud) - **rekommenderat för ASR**
- `"beamformed"`: Medelvärde av kanaler 1-4 (råa mikrofoner) - för egen beamforming

#### `buffer_size` och `period_size`
USB-ljudenheter behöver andra värden än I²S:
- `buffer_size: 4096` (vs 8192 för I²S)
- `period_size: 512` (vs 1024 för I²S)

#### `mode`
- `"vad"`: Automatisk aktivering vid röst (rekommenderat för ReSpeaker USB)
- `"ptt"`: Push-to-talk med extern knapp (kräver GPIO-anslutning)

### GPIO och Push-to-Talk

ReSpeaker USB 4-Mic Array har ingen inbyggd knapp. För PTT-läge:
1. Anslut en extern knapp till GPIO17 (eller annan pin)
2. Sätt `mode: "ptt"` i config.yaml
3. Konfigurera `gpio.button_pin` och `gpio.pull_up`

**Rekommendation:** Använd VAD-läge (`mode: "vad"`) för hands-free operation.

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

**Tips:** 
- Systemd-tjänsten använder automatiskt den virtuella miljön (`venv/bin/python3`) som skapades under installationen.
- Om du installerade agenten i en annan katalog än `/home/pi/voice-agent`, redigera tjänstefilen och uppdatera `WorkingDirectory` och `ExecStart` vägarna.
- På Raspberry Pi 5 kan du behöva uppdatera `User=pi` till ditt användarnamn om det är annorlunda.

## Backend: exempel på TTS-svar

Publicera en WAV (16 kHz, mono) som base64 till `tts`-topic:
```json
{
  "wav_b64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAA..."
}
```
Agenten spelar upp via USB-arrayens 3.5mm-utgång.

## Säkerhet
- Kör MQTT över **TLS**. Använd **mTLS** eller **kortlivad JWT** i produktion.
- Lås ACL så denna device endast kan publicera/lyssna på sina egna topics.

## Felsökning

### Ingen ljudenhet hittas
```bash
# Kontrollera att USB-arrayen är ansluten
lsusb | grep -i audio

# Lista ljudenheter
arecord -l
```

### Fel vid inspelning: "arecord failed to start (exit code -13)"

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

### Andra inspelningsfel
Om du får "Input/output error":
- Kontrollera buffer- och periodstorlekarna i config.yaml
- USB-ljud använder typiskt mindre buffertar: `buffer_size: 4096`, `period_size: 512`
- Prova olika värden: 2048/256 eller 8192/1024

### Hackigt ljud
- Prova `plughw` istället för `hw` i `device`-konfigurationen
- Sänk `vad_mode` till 1
- Öka `vad_silence_ms` till 1000 eller högre

### VAD aktiveras inte
ReSpeaker USB har hårdvaru-VAD (inbyggt i DSP), men vi använder också WebRTC VAD i mjukvara:
- Öka mikrofonnivån
- Sänk `vad_mode` till 1 eller 0 (mindre aggressiv)
- Testa med `channel_mode: "beamformed"` för att kombinera alla mikrofoner

### GPIO-fel på Raspberry Pi 5
Raspberry Pi 5 använder ny GPIO-hårdvara:
- RPi.GPIO fungerar men lgpio rekommenderas för nya projekt
- Kontrollera att `python3-rpi.gpio` är installerat
- För PTT-läge, verifiera att GPIO17 (eller din valda pin) är tillgänglig

## Fördelar med ReSpeaker USB 4-Mic Array

### Jämfört med I²S HAT (ReSpeaker 2-Mic)

**Fördelar:**
- ✅ Inbyggd DSP med AEC, beamforming och brusreducering
- ✅ 4 mikrofoner för bättre riktningskänslighet
- ✅ Plug-and-play (ingen kernel driver eller device tree)
- ✅ Fungerar på alla datorer (inte bara Raspberry Pi)
- ✅ 3.5mm ljudutgång för högtalare
- ✅ 12 RGB-LEDs för visuell feedback

**Nackdelar:**
- ❌ Något högre latens än I²S
- ❌ Tar en USB-port
- ❌ Något högre strömförbrukning (170-180mA)
- ❌ Ingen fysisk knapp (kräver extern för PTT)

## Avancerad användning

### Använd råa mikrofoner istället för processat ljud
För att använda råa mikrofoner med egen beamforming:
```yaml
audio:
  channel_mode: "beamformed"  # Medelvärde av mikrofoner 1-4
```

### Spara multi-kanalsljud för analys
För debugging eller analys:
```bash
# Spela in alla 6 kanaler
arecord -D plughw:CARD=ArrayUAC10,DEV=0 -c 6 -f S16_LE -r 16000 -d 10 debug_6ch.wav

# Analysera med Audacity eller Python
# Kanal 0: Processat
# Kanal 1-4: Råa mikrofoner
# Kanal 5: Playback
```

### LED-kontroll
ReSpeaker USB 4-Mic Array har 12 RGB-LEDs som kan kontrolleras via USB HID.
Se [respeaker/usb_4_mic_array](https://github.com/respeaker/usb_4_mic_array) för Python-bibliotek och exempel.

## Resurser

- [ReSpeaker USB 4-Mic Array Wiki](https://wiki.seeedstudio.com/ReSpeaker-USB-Mic-Array/)
- [GitHub: respeaker/usb_4_mic_array](https://github.com/respeaker/usb_4_mic_array)
- [Raspberry Pi 5 Documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html)

## Licens
MIT
