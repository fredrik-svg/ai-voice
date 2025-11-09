# n8n Integration Guide – MQTT Topic Flow

Denna guide förklarar hur man konfigurerar ett n8n-flöde för att ta emot och svara på röstmeddelanden från AI Voice-agenten via MQTT.

## Snabbstart

**Fråga:** Hur vet n8n vilket topic den ska svara på?

**Svar:** n8n extraherar `tenant`, `user` och `deviceId` från det inkommande MQTT-topic och bygger sedan dynamiska svar-topics:

```javascript
// Från inkommande topic: t/GENIO/u/fredrik/voice/voice-zero-2/audio
const parts = topic.split('/');
const tenant = parts[1];    // GENIO
const user = parts[3];       // fredrik
const deviceId = parts[5];   // voice-zero-2

// Bygg svar-topics
const responseTopic = `t/${tenant}/u/${user}/voice/${deviceId}/response`;
const ttsTopic = `t/${tenant}/u/${user}/voice/${deviceId}/tts`;
```

Se [Steg 2: Extrahera Topic-information](#steg-2-extrahera-topic-information) för fullständigt exempel.

## Översikt

AI Voice-agenten kommunicerar via MQTT med fyra olika topic-typer:

| Topic | Riktning | QoS | Beskrivning |
|-------|----------|-----|-------------|
| `audio` | Device → n8n | 0 | Ljudramar (PCM base64) under inspelning |
| `control` | Device → n8n | 1 | Statusmeddelanden och händelser |
| `response` | n8n → Device | 1 | Textmeddelanden/svar till enheten |
| `tts` | n8n → Device | 1 | TTS-ljud (WAV base64) för uppspelning |

### Meddelandeflöde

```
Röst-Agent (Device)                MQTT Broker              n8n Backend
─────────────────────              ───────────              ────────────
       │                                │                         │
       │ 1. CONNECT                     │                         │
       ├───────────────────────────────>│                         │
       │                                │                         │
       │ 2. SUBSCRIBE (response, tts)   │                         │
       ├───────────────────────────────>│                         │
       │                                │                         │
       │ 3. PUBLISH (control: online)   │                         │
       ├───────────────────────────────>│                         │
       │                                │                         │
   [Användare trycker på knapp]        │                         │
       │                                │                         │
       │ 4. PUBLISH (control: audio_start)                        │
       ├───────────────────────────────>│                         │
       │                                ├────────────────────────>│
       │                                │  5. Extract topic info  │
       │                                │         (tenant, user,  │
       │                                │          deviceId)      │
       │                                │                         │
       │ 6. PUBLISH (audio frames...)   │                         │
       ├───────────────────────────────>│                         │
       │    20ms PCM chunks              ├────────────────────────>│
       │                                │  7. Accumulate frames   │
       │                                │                         │
       │ 8. PUBLISH (control: audio_end)│                         │
       ├───────────────────────────────>│                         │
       │                                ├────────────────────────>│
       │                                │  9. Process complete    │
       │                                │     audio session       │
       │                                │     - STT (Whisper)     │
       │                                │     - AI (OpenAI)       │
       │                                │     - TTS (ElevenLabs)  │
       │                                │                         │
       │                                │ 10. PUBLISH (tts)       │
       │<───────────────────────────────┤<────────────────────────┤
       │                                │   Using extracted topic │
       │                                │   for correct device    │
  11. Play audio                        │                         │
       │                                │                         │
```

## Topic-struktur

Topics använder ett hierarkiskt format med tenant, användare och enhets-ID:

```
t/{tenant}/u/{user}/voice/{deviceId}/{type}
```

### Exempel med standardkonfiguration:
```yaml
tenant: GENIO
user: fredrik
deviceId: voice-zero-2
```

Genererar följande topics:
- **Audio**: `t/GENIO/u/fredrik/voice/voice-zero-2/audio`
- **Control**: `t/GENIO/u/fredrik/voice/voice-zero-2/control`
- **Response**: `t/GENIO/u/fredrik/voice/voice-zero-2/response`
- **TTS**: `t/GENIO/u/fredrik/voice/voice-zero-2/tts`

## n8n Workflow-konfiguration

### Steg 1: MQTT Subscribe Node

Konfigurera en MQTT Subscribe-nod för att ta emot meddelanden från enheten.

**Node: MQTT Subscribe (Audio)**
```json
{
  "topic": "t/+/u/+/voice/+/audio",
  "qos": 0,
  "jsonParsePayload": true
}
```

**Node: MQTT Subscribe (Control)**
```json
{
  "topic": "t/+/u/+/voice/+/control",
  "qos": 1,
  "jsonParsePayload": true
}
```

Använd wildcards (`+`) för att matcha alla tenants, användare och enheter, eller specificera exakta värden för att filtrera:
- `t/GENIO/u/+/voice/+/audio` – endast GENIO tenant
- `t/GENIO/u/fredrik/voice/+/audio` – endast fredrik's enheter

### Steg 2: Extrahera Topic-information

n8n behöver veta **vilket topic den ska svara på**. Detta görs genom att extrahera tenant, user och deviceId från det inkommande topic.

**Node: Function (Parse Topic)**
```javascript
// Input topic exempel: t/GENIO/u/fredrik/voice/voice-zero-2/audio
const topic = $input.item.json.topic;
const parts = topic.split('/');

// Extrahera komponenter från topic-strukturen
const tenant = parts[1];      // GENIO
const user = parts[3];         // fredrik  
const deviceId = parts[5];     // voice-zero-2
const messageType = parts[6];  // audio, control, response, eller tts

// Bygg svar-topics
const responseTopic = `t/${tenant}/u/${user}/voice/${deviceId}/response`;
const ttsTopic = `t/${tenant}/u/${user}/voice/${deviceId}/tts`;

// Returnera data med topic-information
return {
  json: {
    ...($input.item.json),
    tenant: tenant,
    user: user,
    deviceId: deviceId,
    messageType: messageType,
    responseTopic: responseTopic,
    ttsTopic: ttsTopic,
    // Original payload finns i $input.item.json
  }
};
```

### Steg 3: Processera Audio-ramar

När du tar emot audio-meddelanden, bygg upp ljudströmmen från PCM-ramar.

**Audio Message Format:**
```json
{
  "ts": 1699531234567,
  "session_id": "uuid-here",
  "seq": 1,
  "format": "s16le",
  "rate": 16000,
  "channels": 1,
  "pcm_b64": "base64-encoded-pcm-data"
}
```

**Node: Function (Accumulate Audio)**
```javascript
// Gruppera ramar per session_id
const sessionId = $input.item.json.session_id;
const seq = $input.item.json.seq;
const pcmB64 = $input.item.json.pcm_b64;

// Använd workflow-statisk data för att lagra ramar
const context = $workflow.staticData;
if (!context.sessions) {
  context.sessions = {};
}

if (!context.sessions[sessionId]) {
  context.sessions[sessionId] = {
    frames: [],
    tenant: $input.item.json.tenant,
    user: $input.item.json.user,
    deviceId: $input.item.json.deviceId,
    responseTopic: $input.item.json.responseTopic,
    ttsTopic: $input.item.json.ttsTopic
  };
}

context.sessions[sessionId].frames.push({
  seq: seq,
  pcm_b64: pcmB64
});

return {
  json: {
    session_id: sessionId,
    frame_count: context.sessions[sessionId].frames.length,
    ...context.sessions[sessionId]
  }
};
```

### Steg 4: Detektera Session Slut

Lyssna på control-meddelanden för att veta när ljudinspelningen är klar.

**Control Message (audio_end):**
```json
{
  "ts": 1699531234567,
  "deviceId": "voice-zero-2",
  "event": "audio_end",
  "session_id": "uuid-here",
  "frames": 42
}
```

**Node: Switch (Filter Control Events)**
```javascript
// Routning baserat på event-typ
if ($input.item.json.event === 'audio_start') {
  return [0]; // Utgang 0: Session startad
} else if ($input.item.json.event === 'audio_end') {
  return [1]; // Utgang 1: Session avslutad, processera ljud
} else if ($input.item.json.event === 'status') {
  return [2]; // Utgang 2: Statusuppdatering
}
return [];
```

### Steg 5: Skicka Svar till Enheten

När du har processat ljudet (t.ex. via speech-to-text och AI), skicka tillbaka svar.

#### Alternativ A: Text Response

**Node: MQTT Publish (Response)**
```json
{
  "topic": "={{$json.responseTopic}}",
  "qos": 1,
  "message": {
    "text": "Hej! Jag hörde dig säga: Hello world",
    "timestamp": "={{Date.now()}}"
  }
}
```

#### Alternativ B: TTS Audio Response

**Node: MQTT Publish (TTS)**
```json
{
  "topic": "={{$json.ttsTopic}}",
  "qos": 1,
  "message": {
    "wav_b64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA..."
  }
}
```

TTS-meddelandet ska innehålla:
- `wav_b64`: WAV-fil (16 kHz, mono, 16-bit PCM) kodad som base64

## Komplett n8n Workflow Exempel

Här är ett komplett exempel på hur ett n8n-flöde kan se ut:

```
[MQTT Subscribe (Control)] → [Parse Topic] → [Switch (Event Type)]
                                                    ↓
                                              [audio_end]
                                                    ↓
                                         [Get Session Audio]
                                                    ↓
                                         [Combine PCM Frames]
                                                    ↓
                                         [Speech-to-Text (Whisper API)]
                                                    ↓
                                         [AI Processing (OpenAI)]
                                                    ↓
                                         [Text-to-Speech (ElevenLabs)]
                                                    ↓
                                         [Encode WAV to Base64]
                                                    ↓
                                         [MQTT Publish (TTS)]


[MQTT Subscribe (Audio)] → [Parse Topic] → [Accumulate Frames]
```

## Topic Routing Patterns

### Multi-tenant Setup

För att hantera flera kunder (tenants):

```javascript
// Filter baserat på tenant
const tenant = $input.item.json.tenant;

if (tenant === 'GENIO') {
  // Använd GENIO-specifik AI-modell
  return [0];
} else if (tenant === 'ACME') {
  // Använd ACME-specifik AI-modell
  return [1];
}
```

### Per-User Configuration

För att hantera olika användare:

```javascript
// Hämta användarspecifik konfiguration
const user = $input.item.json.user;
const userConfig = await getUserConfig(user);

// Använd användarens AI-preferenser
return {
  json: {
    ...($input.item.json),
    aiModel: userConfig.preferredModel,
    voice: userConfig.ttsVoice
  }
};
```

### Device-specific Handling

För att hantera olika enheter:

```javascript
// Olika hantering beroende på enhet
const deviceId = $input.item.json.deviceId;

if (deviceId.startsWith('voice-zero-')) {
  // Raspberry Pi Zero enheter
  return [0];
} else if (deviceId.startsWith('voice-pi4-')) {
  // Raspberry Pi 4 enheter  
  return [1];
}
```

## Säkerhetsaspekter

### MQTT ACL

Konfigurera MQTT-broker ACL för att säkerställa att:
- Enheter endast kan publicera till sina egna topics
- n8n kan läsa från alla device-topics men endast skriva till response/tts

**Exempel HiveMQ ACL:**
```xml
<!-- Device: voice-zero-2 -->
<topic-permission>
  <topic>t/GENIO/u/fredrik/voice/voice-zero-2/audio</topic>
  <publish-subscribe>PUBLISH</publish-subscribe>
</topic-permission>
<topic-permission>
  <topic>t/GENIO/u/fredrik/voice/voice-zero-2/control</topic>
  <publish-subscribe>PUBLISH</publish-subscribe>
</topic-permission>
<topic-permission>
  <topic>t/GENIO/u/fredrik/voice/voice-zero-2/response</topic>
  <publish-subscribe>SUBSCRIBE</publish-subscribe>
</topic-permission>
<topic-permission>
  <topic>t/GENIO/u/fredrik/voice/voice-zero-2/tts</topic>
  <publish-subscribe>SUBSCRIBE</publish-subscribe>
</topic-permission>

<!-- n8n Backend -->
<topic-permission>
  <topic>t/+/u/+/voice/+/audio</topic>
  <publish-subscribe>SUBSCRIBE</publish-subscribe>
</topic-permission>
<topic-permission>
  <topic>t/+/u/+/voice/+/control</topic>
  <publish-subscribe>SUBSCRIBE</publish-subscribe>
</topic-permission>
<topic-permission>
  <topic>t/+/u/+/voice/+/response</topic>
  <publish-subscribe>PUBLISH</publish-subscribe>
</topic-permission>
<topic-permission>
  <topic>t/+/u/+/voice/+/tts</topic>
  <publish-subscribe>PUBLISH</publish-subscribe>
</topic-permission>
```

## Debugging och Monitorering

### Lyssna på Topics med mosquitto_sub

```bash
# Lyssna på alla meddelanden från en specifik enhet
mosquitto_sub -h abc123.s1.eu.hivemq.cloud -p 8883 \
  --capath /etc/ssl/certs/ \
  -u voice-user -P s3cret \
  -t "t/GENIO/u/fredrik/voice/voice-zero-2/#" \
  -v

# Lyssna på alla control-meddelanden
mosquitto_sub -h abc123.s1.eu.hivemq.cloud -p 8883 \
  --capath /etc/ssl/certs/ \
  -u voice-user -P s3cret \
  -t "t/+/u/+/voice/+/control" \
  -v

# Lyssna på alla audio-meddelanden (kan vara mycket data!)
mosquitto_sub -h abc123.s1.eu.hivemq.cloud -p 8883 \
  --capath /etc/ssl/certs/ \
  -u voice-user -P s3cret \
  -t "t/+/u/+/voice/+/audio" \
  -v
```

### Logga Topics i n8n

Lägg till en Function-nod för att logga alla inkommande topics:

```javascript
console.log('Received message on topic:', $input.item.json.topic);
console.log('Payload:', JSON.stringify($input.item.json, null, 2));
return $input.all();
```

## n8n Workflow Export Exempel

Här är ett minimalt men komplett n8n workflow som du kan importera direkt:

```json
{
  "name": "AI Voice Agent - MQTT Handler",
  "nodes": [
    {
      "parameters": {
        "topic": "t/+/u/+/voice/+/control",
        "options": {
          "qos": 1,
          "jsonParsePayload": true
        }
      },
      "name": "MQTT Control Listener",
      "type": "n8n-nodes-base.mqtt",
      "typeVersion": 1,
      "position": [250, 300]
    },
    {
      "parameters": {
        "functionCode": "// Parse MQTT topic to extract routing information\nconst topic = $input.item.json.topic;\nconst parts = topic.split('/');\n\n// Extract components\nconst tenant = parts[1];\nconst user = parts[3];\nconst deviceId = parts[5];\nconst messageType = parts[6];\n\n// Build response topics\nconst responseTopic = `t/${tenant}/u/${user}/voice/${deviceId}/response`;\nconst ttsTopic = `t/${tenant}/u/${user}/voice/${deviceId}/tts`;\n\n// Return enriched data\nreturn {\n  json: {\n    ...($input.item.json),\n    tenant,\n    user,\n    deviceId,\n    messageType,\n    responseTopic,\n    ttsTopic\n  }\n};"
      },
      "name": "Parse Topic",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [450, 300]
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{$json.event}}",
              "value2": "audio_end"
            }
          ]
        }
      },
      "name": "Filter Audio End",
      "type": "n8n-nodes-base.if",
      "typeVersion": 1,
      "position": [650, 300]
    },
    {
      "parameters": {
        "topic": "={{$json.ttsTopic}}",
        "sendInputData": false,
        "message": "={\n  \"wav_b64\": \"{{$json.ttsAudioBase64}}\"\n}",
        "options": {
          "qos": 1
        }
      },
      "name": "MQTT Publish TTS",
      "type": "n8n-nodes-base.mqtt",
      "typeVersion": 1,
      "position": [1050, 300]
    }
  ],
  "connections": {
    "MQTT Control Listener": {
      "main": [[{"node": "Parse Topic", "type": "main", "index": 0}]]
    },
    "Parse Topic": {
      "main": [[{"node": "Filter Audio End", "type": "main", "index": 0}]]
    },
    "Filter Audio End": {
      "main": [
        [{"node": "Process Audio (Add your AI nodes here)", "type": "main", "index": 0}]
      ]
    }
  }
}
```

**Tips för att använda workflow-export:**
1. Kopiera JSON ovan
2. I n8n, klicka på **Import from File** eller **Import from Clipboard**
3. Klistra in JSON
4. Konfigurera MQTT-klientens anslutningsinställningar (broker, credentials)
5. Lägg till dina egna noder för STT/AI/TTS mellan "Filter Audio End" och "MQTT Publish TTS"

## Sammanfattning

För att ett n8n-flöde ska veta **vilket topic den ska svara på**:

1. **Ta emot meddelande** från MQTT med topic i payload
2. **Extrahera topic-komponenter** (tenant, user, deviceId) genom att splitta topic-strängen
3. **Bygg svar-topics** dynamiskt baserat på extraherade komponenter:
   - Response topic: `t/{tenant}/u/{user}/voice/{deviceId}/response`
   - TTS topic: `t/{tenant}/u/{user}/voice/{deviceId}/tts`
4. **Publicera svar** till de dynamiskt byggda topics

Detta tillåter n8n att hantera flera enheter, användare och tenants automatiskt genom topic-baserad routing.
