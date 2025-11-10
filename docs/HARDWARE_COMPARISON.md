# Hårdvarujämförelse: Pi Zero 2 vs Pi 5

Detta dokument hjälper dig välja rätt hårdvarukonfiguration för ditt röstagent-projekt.

## Snabb jämförelse

| Funktion | Pi Zero 2 + I²S HAT | Pi 5 + USB Array |
|----------|---------------------|------------------|
| **Pris** | ~500 kr | ~1500 kr |
| **Mikrofoner** | 2 | 4 |
| **DSP** | Nej | Ja (AEC, beamforming) |
| **Latens** | Lägre (~5-10ms) | Högre (~20-40ms) |
| **Strömförbrukning** | Lägre (~1W) | Högre (~5-8W) |
| **Setup komplexitet** | Medel (kernel driver) | Låg (plug-and-play) |
| **Portabilitet** | Hög | Medel |
| **Ljudkvalitet** | Bra | Utmärkt |
| **GPIO knapp** | Inbyggd | Extern behövs |
| **Plattform** | Endast Raspberry Pi | Alla Linux/Mac/Win |

## Detaljerad jämförelse

### Raspberry Pi Zero 2 WH + KEYESTUDIO ReSpeaker 2-Mic Pi HAT V1.0

#### Fördelar ✅
- **Kompakt och portabel**: Perfekt för batteridrivna projekt
- **Låg strömförbrukning**: 1-2W, kan köras på powerbank
- **Låg latens**: I²S ger minimal fördröjning (5-10ms)
- **Inbyggd knapp**: GPIO17-knapp för PTT direkt på HAT
- **Billigare**: Totalkostnad ~500 kr
- **Hårdvaruintegrerad**: Allt på ett enda kort

#### Nackdelar ❌
- **Kräver I²S setup**: Kernel driver och device tree overlay
- **Färre mikrofoner**: Endast 2 mikrofoner (stereo)
- **Ingen hårdvaru-DSP**: Ingen AEC eller beamforming i hårdvara
- **Mindre kraftfull CPU**: Pi Zero 2 (4x Cortex-A53 1GHz)
- **Buffer issues**: Kräver noggrann buffer/period tuning

#### Bäst för:
- 🔋 Batteridrivna projekt
- 📦 Kompakta installationer
- 💰 Budgetmedvetna projekt
- ⚡ Låglatens-applikationer
- 🎒 Portabla enheter (wearables, robotar)

### Raspberry Pi 5 + ReSpeaker USB 4-Mic Array

#### Fördelar ✅
- **4 mikrofoner**: Bättre riktningskänslighet och beamforming
- **Hårdvaru-DSP**: XMOS XVF-3000 med AEC, beamforming, noise suppression
- **Plug-and-play**: Ingen kernel driver, bara anslut USB
- **Kraftfull CPU**: Pi 5 (4x Cortex-A76 2.4GHz)
- **Plattformsoberoende**: Fungerar på alla datorer (inte bara RPi)
- **12 RGB LEDs**: Visuell feedback möjlig
- **3.5mm utgång**: Inbyggd ljudutgång för högtalare

#### Nackdelar ❌
- **Högre strömförbrukning**: 5-8W (kräver 5V/3A adapter)
- **Dyrare**: Totalkostnad ~1500 kr
- **Högre latens**: USB audio ger ~20-40ms latens
- **Ingen inbyggd knapp**: Kräver extern knapp för PTT
- **Tar USB-port**: En port mindre tillgänglig
- **Större footprint**: Inte lika kompakt som HAT-lösning

#### Bäst för:
- 🎤 Professionell ljudkvalitet behövs
- 🏠 Stationära installationer (smarta hem)
- 🔊 Multi-room audio system
- 🤖 Avancerad röstassistent med AEC
- 🧪 Utveckling och prototyping
- 💪 CPU-krävande applikationer

## Tekniska specifikationer

### Audio Processing Pipeline

#### I²S HAT (Pi Zero 2)
```
Mikrofoner (2) → WM8960 Codec (I²S) → Pi Zero 2 → sox (stereo→mono) → VAD → MQTT
```
- Sample rate: 16kHz
- Kanaler: 2 (stereo)
- Format: S16_LE
- Buffer: 8192 frames
- Period: 1024 frames

#### USB Array (Pi 5)
```
Mikrofoner (4) → XMOS DSP (AEC/Beamforming) → USB → Pi 5 → sox (6ch→mono) → VAD → MQTT
```
- Sample rate: 16kHz
- Kanaler: 6 (4 mics + processat + playback)
- Format: S16_LE
- Buffer: 4096 frames
- Period: 512 frames

### DSP Features (endast USB Array)

| Feature | I²S HAT | USB Array |
|---------|---------|-----------|
| Acoustic Echo Cancellation | ❌ | ✅ |
| Beamforming | ❌ | ✅ |
| Noise Suppression | ❌ | ✅ |
| De-reverberation | ❌ | ✅ |
| Hardware VAD | ❌ | ✅ |

## Prestanda i olika scenarion

### Scenario 1: Smart högtalare i vardagsrum
**Rekommendation: Pi 5 + USB Array** 🏆

Varför:
- AEC behövs för att filtrera ut ljud från TV/musik
- 4 mikrofoner ger bättre pickup från olika vinklar
- Stationär = strömförbrukning spelar mindre roll
- Beamforming förbättrar röstidentifiering i bullriga miljöer

### Scenario 2: Bärbar röstassistent
**Rekommendation: Pi Zero 2 + I²S HAT** 🏆

Varför:
- Kompakt och lätt
- Låg strömförbrukning (batteridrivet)
- Lägre latens ger snabbare respons
- Mindre kostnad

### Scenario 3: Utveckling och prototyping
**Rekommendation: Pi 5 + USB Array** 🏆

Varför:
- Plug-and-play = snabbare setup
- Fungerar på alla datorer (utveckling på laptop)
- Kraftfullare CPU för experiment
- Enklare att debugga (USB = standard)

### Scenario 4: Industriell/kommersiell produkt
**Rekommendation: Pi Zero 2 + I²S HAT** 🏆

Varför:
- Lägre kostnad per enhet
- Mindre footprint
- Färre komponenter = högre reliabilitet
- Lägre strömförbrukning

## Migrera mellan varianter

### Från I²S HAT → USB Array

1. Kopiera din befintliga `config.yaml`
2. Använd `config.pi5-usb.example.yaml` som mall
3. Ändra följande:

```yaml
audio:
  device: "plughw:CARD=ArrayUAC10,DEV=0"  # Nytt USB-device
  buffer_size: 4096       # Mindre för USB
  period_size: 512        # Mindre för USB
  input_channels: 6       # 6 istället för 2
  channel_mode: "processed"  # Nytt fält
```

4. Kör `scripts/install_deps_pi5.sh` istället för `scripts/install_deps.sh`

### Från USB Array → I²S HAT

1. Installera I²S driver (följ README.md)
2. Använd `config.example.yaml` som mall
3. Ändra:

```yaml
audio:
  device: "plughw:1,0"    # I²S device
  buffer_size: 8192       # Större för I²S
  period_size: 1024       # Större för I²S
  input_channels: 2       # 2 istället för 6
  # channel_mode tas bort
```

## Kostnadsjämförelse (ca priser)

### Pi Zero 2 Setup
- Raspberry Pi Zero 2 WH: 200 kr
- KEYESTUDIO ReSpeaker 2-Mic HAT: 150 kr
- MicroSD kort 32GB: 100 kr
- USB-C kabel + adapter: 50 kr
- **Total: ~500 kr**

### Pi 5 Setup
- Raspberry Pi 5 (4GB): 800 kr
- ReSpeaker USB 4-Mic Array: 450 kr
- MicroSD kort 32GB: 100 kr
- USB-C 5V/3A adapter: 150 kr
- **Total: ~1500 kr**

## Sammanfattning och rekommendationer

### Välj Pi Zero 2 + I²S HAT om du:
- 💰 Har begränsad budget
- 🔋 Behöver batteridrift
- 📦 Vill ha kompakt design
- ⚡ Kräver låg latens
- 🎒 Bygger portabel enhet

### Välj Pi 5 + USB Array om du:
- 🎤 Kräver bästa ljudkvalitet
- 🏠 Bygger stationär installation
- 🔊 Behöver AEC (echo cancellation)
- 💪 Vill ha kraftfullare processor
- 🧪 Utvecklar och prototypar
- 🌐 Vill ha plattformsoberoende lösning

### Kan inte bestämma dig?
Börja med **Pi 5 + USB Array** för:
- Enklare setup (plug-and-play)
- Bättre ljudkvalitet out-of-the-box
- Mer förlåtande för nybörjare
- Enklare att migrera till annan plattform senare

## Frågor och svar

**Q: Kan jag använda ReSpeaker USB 4-Mic Array med Pi Zero 2?**
A: Ja, men Pi Zero 2:s begränsade CPU och USB 2.0 kan ge sämre prestanda. Rekommenderas inte.

**Q: Kan jag använda I²S HAT med Pi 5?**
A: Ja, men det kräver samma I²S-setup som för Pi Zero. USB-lösningen är enklare.

**Q: Vilken ger bäst ASR (speech recognition) resultat?**
A: USB Array på grund av DSP-bearbetning (AEC, beamforming, noise suppression).

**Q: Kan jag köra båda konfigurationerna med samma kod?**
A: Ja! Koden är identisk, endast `config.yaml` skiljer sig.

**Q: Vilken har bäst Wake Word Detection prestanda?**
A: USB Array tack vare hårdvaru-beamforming som fokuserar på röst.

## Ytterligare resurser

- [Pi Zero 2 fullständig guide](README.md)
- [Pi 5 fullständig guide](README.pi5-usb.md)
- [Pi 5 snabbstart](docs/QUICKSTART_PI5.md)
- [N8N Integration](docs/N8N_INTEGRATION.md)
