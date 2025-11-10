# Snabbstart: Raspberry Pi 5 + ReSpeaker USB 4-Mic Array

Denna guide tar dig genom de viktigaste stegen för att komma igång med Raspberry Pi 5 och ReSpeaker USB 4-Mic Array.

## Hårdvara som behövs

- ✅ Raspberry Pi 5 (4GB eller 8GB rekommenderas)
- ✅ ReSpeaker USB 4-Mic Array
- ✅ MicroSD-kort (32GB+ rekommenderas)
- ✅ USB-C strömadapter (min 5V/3A för Pi 5)
- ✅ (Valfritt) Högtalare eller hörlurar för 3.5mm uttag
- ✅ (Valfritt) Extern knapp för PTT-läge

## Steg 1: Installera Raspberry Pi OS

1. Ladda ner och installera [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Välj **Raspberry Pi OS (64-bit)** - Bookworm rekommenderas
3. Skriv till SD-kortet
4. Sätt i SD-kortet i Pi 5 och starta upp

## Steg 2: Anslut hårdvara

1. Anslut ReSpeaker USB 4-Mic Array till en av Pi 5:s USB-portar
2. Kontrollera att den känns igen:
   ```bash
   lsusb | grep -i audio
   arecord -l
   ```
   Du bör se något som `ReSpeaker 4 Mic Array (UAC1.0)`

## Steg 3: Klona och installera

```bash
# Uppdatera systemet först
sudo apt update && sudo apt upgrade -y

# Klona repositoryt
git clone https://github.com/fredrik-svg/ai-voice.git voice-agent
cd voice-agent

# Kör Pi5-specifik installation
chmod +x scripts/install_deps_pi5.sh
./scripts/install_deps_pi5.sh
```

Installationen tar några minuter och installerar:
- Python 3 och virtuell miljö
- ALSA-verktyg för ljudhantering
- Sox för ljudkonvertering
- Python-beroenden (MQTT, VAD, etc.)

## Steg 4: Konfigurera

```bash
# Kopiera Pi5-specifik konfiguration
cp config.pi5-usb.example.yaml config.yaml

# Redigera konfigurationen
nano config.yaml
```

**Viktigaste inställningar att ändra:**

```yaml
# Din MQTT-broker (t.ex. HiveMQ Cloud)
mqtt:
  host: abc123.s1.eu.hivemq.cloud  # Din broker-URL
  port: 8883
  username: ditt-användarnamn       # Dina credentials
  password: ditt-lösenord
  tls: true

# Verifiera ljudenhetens namn
audio:
  device: "plughw:CARD=ArrayUAC10,DEV=0"  # Kontrollera med 'arecord -l'
  mode: "vad"  # Automatisk aktivering vid röst (rekommenderat)
```

**Tips:** För att hitta rätt device-namn, kör `arecord -l` och titta på card-namnet.

## Steg 5: Testa ljudinspelning

Innan du startar agenten, testa att USB-arrayen fungerar:

```bash
# Spela in 5 sekunder testljud (alla 6 kanaler)
arecord -D plughw:CARD=ArrayUAC10,DEV=0 -c 6 -f S16_LE -r 16000 -d 5 test.wav

# Spela upp via USB-arrayens 3.5mm utgång
aplay -D plughw:CARD=ArrayUAC10,DEV=0 test.wav
```

Om detta fungerar är din hårdvara korrekt konfigurerad! 🎉

## Steg 6: Starta Voice Agent

```bash
# Kör i utvecklingsläge
chmod +x scripts/run.sh
./scripts/run.sh
```

Du bör se:
```
[agent] VAD mode: auto start on voice, stop after silence.
```

**Testa:** Prata nära mikrofonerna. Agenten bör:
1. Detektera din röst (VAD aktiverar)
2. Börja streama ljud till MQTT
3. Stoppa efter tystnad

## Steg 7: Produktionsdrift (valfritt)

För att köra som systemd-tjänst:

```bash
# Kopiera och aktivera systemd-tjänst
sudo cp systemd/voice-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable voice-agent
sudo systemctl start voice-agent

# Följ loggarna
sudo journalctl -u voice-agent -f
```

**OBS:** Redigera `/etc/systemd/system/voice-agent.service` om du:
- Installerade i en annan katalog än `/home/pi/voice-agent`
- Använder ett annat användarnamn än `pi`

## Lägen: VAD vs PTT

### VAD-läge (rekommenderat för ReSpeaker USB)
```yaml
audio:
  mode: "vad"
```
- Aktiveras automatiskt när röst detekteras
- Stoppar efter tystnad (800ms standard)
- Hands-free operation
- Perfekt för hands-free användning

### PTT-läge (kräver extern knapp)
```yaml
audio:
  mode: "ptt"

gpio:
  button_pin: 17  # GPIO-pin för knapp
  pull_up: true
```
- Kräver manuell aktivering via knapp
- Mer batterivänligt för portabel användning
- Behöver extern knapp ansluten till GPIO

## Kanalkonfiguration

ReSpeaker USB 4-Mic Array har 6 kanaler:
- **Kanal 0**: Processat ljud (AEC, beamforming, brusreducering) ⭐ Rekommenderat
- **Kanaler 1-4**: Råa mikrofoner
- **Kanal 5**: Playback ljud

### Processat läge (standard)
```yaml
audio:
  channel_mode: "processed"  # Använd kanal 0 (DSP-bearbetat)
```
Bäst för: Röstassistenter, ASR, speech-to-text

### Beamformed läge
```yaml
audio:
  channel_mode: "beamformed"  # Medelvärde av råa mikrofoner
```
Bäst för: Egen signal-processing, forskning

## Felsökning

### "No module named 'paho'"
```bash
# Aktivera virtuell miljö manuellt
source venv/bin/activate
pip install -r requirements.txt
```

### "Audio device not found"
```bash
# Kontrollera USB-anslutning
lsusb | grep -i audio

# Lista alla ljudenheter
arecord -l

# Uppdatera device i config.yaml baserat på output
```

### "Input/output error" vid inspelning
USB behöver mindre buffertar än I²S:
```yaml
audio:
  buffer_size: 4096  # Testa även 2048
  period_size: 512   # Testa även 256
```

### VAD aktiveras inte
```yaml
audio:
  vad_mode: 1  # Mindre aggressiv (0-3)
  vad_silence_ms: 1000  # Längre timeout
```

### MQTT-anslutning misslyckas
```bash
# Testa MQTT-anslutning
mosquitto_pub -h abc123.s1.eu.hivemq.cloud -p 8883 \
  -u ditt-användarnamn -P ditt-lösenord \
  --capath /etc/ssl/certs \
  -t test/topic -m "hello"
```

## Nästa steg

1. **Konfigurera backend**: Se [docs/N8N_INTEGRATION.md](N8N_INTEGRATION.md) för n8n-workflow
2. **Läs fullständig dokumentation**: [README.pi5-usb.md](README.pi5-usb.md)
3. **Anpassa efter behov**: Justera VAD-parametrar, buffer-storlekar, etc.
4. **LED-kontroll**: Utforska [respeaker/usb_4_mic_array](https://github.com/respeaker/usb_4_mic_array) för LED-programmering

## Support och resurser

- **GitHub Issues**: [fredrik-svg/ai-voice/issues](https://github.com/fredrik-svg/ai-voice/issues)
- **ReSpeaker Wiki**: [https://wiki.seeedstudio.com/ReSpeaker-USB-Mic-Array/](https://wiki.seeedstudio.com/ReSpeaker-USB-Mic-Array/)
- **Pi 5 Docs**: [https://www.raspberrypi.com/documentation/computers/raspberry-pi.html](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html)

Lycka till med ditt röstprojekt! 🎤🤖
