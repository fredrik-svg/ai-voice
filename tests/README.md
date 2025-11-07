# MQTT Tests

Dessa tester verifierar att MQTT-klienten fungerar korrekt för att skicka och ta emot meddelanden.

## Krav

- Python 3.x
- Mosquitto MQTT broker (för lokala tester)

## Installation

Installera beroenden:
```bash
pip install -r requirements.txt
```

För att köra testerna lokalt, installera Mosquitto:
```bash
# Ubuntu/Debian
sudo apt-get install mosquitto mosquitto-clients

# macOS
brew install mosquitto
```

## Köra testerna

### Med lokal Mosquitto broker

1. Starta Mosquitto:
```bash
sudo systemctl start mosquitto  # Linux
# eller
mosquitto -c /opt/homebrew/etc/mosquitto/mosquitto.conf  # macOS
```

2. Kör testerna:
```bash
cd /path/to/ai-voice
PYTHONPATH=. python3 tests/test_mqtt_client.py
```

Eller med pytest:
```bash
pip install pytest
PYTHONPATH=. pytest tests/test_mqtt_client.py -v
```

## Vad testerna verifierar

Testerna kontrollerar följande funktionalitet:

1. **test_mqtt_connect**: Verifierar att anslutning till MQTT-brokern fungerar
2. **test_mqtt_publish_and_subscribe**: Testar att publicera och ta emot enkla textmeddelanden
3. **test_mqtt_publish_json**: Testar att skicka och ta emot JSON-meddelanden
4. **test_mqtt_multiple_messages**: Verifierar att flera meddelanden i följd hanteras korrekt

## Konfiguration

Testerna använder som standard en lokal Mosquitto-broker på `localhost:1883` utan TLS. 
För att testa mot en annan broker, redigera `setUp()`-metoden i `test_mqtt_client.py`.

## Output

När alla tester körs framgångsrikt ser du:
```
======================================================================
MQTT Client Test Suite
Testar att skicka och ta emot meddelanden via MQTT
======================================================================

test_mqtt_connect ... ✓ Anslutning till MQTT-broker fungerar
ok
test_mqtt_multiple_messages ... ✓ Skickade 5 meddelanden
✓ Mottog 5 meddelanden
✓ Flera meddelanden i följd fungerar
ok
test_mqtt_publish_and_subscribe ... ✓ Skickade meddelande: 'Hej från MQTT test!'
✓ Mottog meddelande: 'Hej från MQTT test!'
✓ Skicka och ta emot meddelanden fungerar
ok
test_mqtt_publish_json ... ✓ Skickade JSON: {...}
✓ Mottog JSON: {...}
✓ JSON-meddelanden fungerar korrekt
ok

----------------------------------------------------------------------
Ran 4 tests in 5.413s

OK
```
