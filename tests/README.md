# MQTT Tests

Dessa tester verifierar att MQTT-klienten fungerar korrekt för att skicka och ta emot meddelanden.

## Krav

- Python 3.x
- Mosquitto MQTT broker (för lokala tester)
- Virtuell Python-miljö (venv) - skapas automatiskt av `install_deps.sh`

## Installation

**OBS:** På moderna Raspberry Pi OS-versioner (Bookworm) är Python-miljön "externally-managed", vilket innebär att du inte kan installera paket systemövergripande med `pip install`. Använd alltid den virtuella miljön som skapas av `install_deps.sh`.

Installera beroenden med virtuell miljö:
```bash
cd /home/runner/work/ai-voice/ai-voice
chmod +x scripts/install_deps.sh
./scripts/install_deps.sh
```

Detta skapar en virtuell miljö i `venv/` och installerar alla beroenden där.

För att köra testerna lokalt, installera också Mosquitto:
```bash
# Ubuntu/Debian
sudo apt-get install mosquitto mosquitto-clients

# macOS
brew install mosquitto
```

## Köra testerna

**VIKTIGT:** Testerna måste köras med den virtuella miljön aktiverad. Använd någon av de medföljande skripten som automatiskt aktiverar venv:

### Med bash-skript (rekommenderat för Raspberry Pi):
```bash
cd /home/runner/work/ai-voice/ai-voice
./tests/run_tests.sh
# eller: bash tests/run_tests.sh
```

### Med Python wrapper:
```bash
cd /home/runner/work/ai-voice/ai-voice
python tests/run_tests.py
```

Båda skripten aktiverar automatiskt den virtuella miljön om den finns.

### Manuellt med aktiverad venv:
```bash
cd /home/runner/work/ai-voice/ai-voice
source venv/bin/activate
PYTHONPATH=. python3 tests/test_mqtt_client.py
deactivate
```

### Med pytest (avancerat):
```bash
cd /home/runner/work/ai-voice/ai-voice
source venv/bin/activate
pip install pytest
PYTHONPATH=. pytest tests/test_mqtt_client.py -v
deactivate
```

## Felsökning

### "ModuleNotFoundError: No module named 'paho'"

Detta betyder att du försöker köra testerna utanför den virtuella miljön. Lösningar:

1. **Använd testskripten** (rekommenderat):
   ```bash
   ./tests/run_tests.sh
   ```

2. **Aktivera venv manuellt**:
   ```bash
   source venv/bin/activate
   PYTHONPATH=. python3 tests/test_mqtt_client.py
   ```

3. **Om venv saknas, skapa den**:
   ```bash
   ./scripts/install_deps.sh
   ```

### "externally-managed-environment"

Om du ser detta fel när du försöker installera paket med `pip install`, betyder det att du försöker installera i system-Python. Använd istället:

```bash
# Skapa och använd virtuell miljö
./scripts/install_deps.sh

# Eller manuellt:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Vad testerna verifierar

Testerna kontrollerar följande funktionalitet:

1. **test_mqtt_connect**: Verifierar att anslutning till MQTT-brokern fungerar
2. **test_mqtt_publish_and_subscribe**: Testar att publicera och ta emot enkla textmeddelanden
3. **test_mqtt_publish_json**: Testar att skicka och ta emot JSON-meddelanden
4. **test_mqtt_multiple_messages**: Verifierar att flera meddelanden i följd hanteras korrekt

## MQTT Topic Visibility

**NYHET**: Testerna visar nu tydligt vilka MQTT-topics som används när meddelanden skickas och tas emot. Detta gör det enkelt att verifiera att meddelanden kommer fram till rätt destination.

När du kör testerna ser du nu:
- Vilken MQTT-broker som används (host:port)
- Exakt topic-path för varje meddelande som publiceras
- Bekräftelse på vilka topics meddelanden tas emot från

Exempel på output:
```
[Test] Ansluter till MQTT broker: localhost:1883
✓ Anslutning till MQTT-broker localhost:1883 fungerar

[Test] Prenumererar på topic: test/ai-voice/1762623680/multi
[Test] Publicerar 5 meddelanden till topic: test/ai-voice/1762623680/multi
✓ Skickade 5 meddelanden till 'test/ai-voice/1762623680/multi'
✓ Mottog 5 meddelanden från 'test/ai-voice/1762623680/multi'

[MQTT] Publishing to topic: test/ai-voice/1762623684/json
✓ Skickade JSON till 'test/ai-voice/1762623684/json': {...}
✓ Mottog JSON från 'test/ai-voice/1762623684/json': {...}
```

Detta gör det lätt att:
- Förstå var meddelanden skickas
- Verifiera att topics är korrekt konfigurerade
- Debugga MQTT-anslutningsproblem
- Konfigurera externa MQTT-klienter för att lyssna på rätt topics

## Konfiguration

Testerna använder `config.yaml` för MQTT-inställningar. Om filen saknas, kopiera `config.example.yaml`:

```bash
cp config.example.yaml config.yaml
# Redigera config.yaml med dina MQTT-inställningar
```

## Output

När alla tester körs framgångsrikt ser du tydlig information om MQTT-topics:
```
==================================================================
MQTT Client Test Suite
Testar att skicka och ta emot meddelanden via MQTT
==================================================================

test_mqtt_connect ... 
[Test] Ansluter till MQTT broker: localhost:1883
✓ Anslutning till MQTT-broker localhost:1883 fungerar
ok

test_mqtt_publish_and_subscribe ... 
[Test] Prenumererar på topic: test/ai-voice/1762623683
[Test] Publicerar till topic: test/ai-voice/1762623683
✓ Skickade meddelande till 'test/ai-voice/1762623683': 'Hej från MQTT test!'
✓ Mottog meddelande från 'test/ai-voice/1762623683': 'Hej från MQTT test!'
✓ Skicka och ta emot meddelanden fungerar
ok

test_mqtt_publish_json ... 
[Test] Prenumererar på topic: test/ai-voice/1762623684/json
[Test] Publicerar JSON till topic: test/ai-voice/1762623684/json
[MQTT] Publishing to topic: test/ai-voice/1762623684/json
✓ Skickade JSON till 'test/ai-voice/1762623684/json': {...}
✓ Mottog JSON från 'test/ai-voice/1762623684/json': {...}
✓ JSON-meddelanden fungerar korrekt
ok

----------------------------------------------------------------------
Ran 4 tests in 5.413s

OK
```

**Notera**: Med den nya topic visibility-funktionen kan du nu tydligt se:
- Vilka MQTT-topics som används för varje test
- Bekräftelse att meddelanden kommer fram till rätt topic
- Detta gör det enkelt att övervaka meddelanden med externa verktyg som `mosquitto_sub`
