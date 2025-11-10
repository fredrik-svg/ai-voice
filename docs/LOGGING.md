# Logging Improvements

## Overview

The voice agent now has improved logging that provides clear feedback about what's happening without overwhelming you with noise.

## Logging Modes

### Normal Mode (`debug: false`)

In normal mode, you'll see:
- ✓ Connection status (MQTT connected, subscribed to topics)
- 🎤 Session lifecycle (when recording starts/stops with duration and frame count)
- Responses from the backend
- TTS playback events
- Errors and warnings

**What you WON'T see:**
- Individual MQTT publish messages
- Frame-by-frame audio data
- Low-level connection details

### Debug Mode (`debug: true`)

In debug mode, you'll see everything from normal mode PLUS:
- Individual MQTT publish messages with topic and size
- Frame-by-frame audio capture
- Control message contents
- Subscription details
- Low-level connection events

## Example Output

### Normal Mode
```
2025-11-10 17:59:07 [INFO] Connecting to MQTT broker at test.hivemq.cloud:8883...
2025-11-10 17:59:07 [INFO] ✓ MQTT connected successfully
2025-11-10 17:59:07 [INFO] ✓ Subscribed to TTS and response topics
2025-11-10 17:59:07 [INFO] ✓ Device 'voice-pi5-usb' is now online
2025-11-10 17:59:07 [INFO] [Agent] VAD mode: auto start on voice, stop after silence
2025-11-10 17:59:08 [INFO] 🎤 Session started: a1b2c3d4...
2025-11-10 17:59:09 [INFO] ✓ Session ended: a1b2c3d4... (15 frames, 300ms)
2025-11-10 17:59:09 [INFO] [Response] {'text': 'Hello, how can I help?'}
2025-11-10 17:59:09 [INFO] [TTS] Playing audio response (12345 bytes)
2025-11-10 17:59:09 [INFO] [TTS] Playback complete
```

### Debug Mode
```
2025-11-10 17:59:09 [INFO] Debug mode enabled - verbose logging active
2025-11-10 17:59:09 [INFO] Connecting to MQTT broker at test.hivemq.cloud:8883...
2025-11-10 17:59:09 [DEBUG] MQTT connection established
2025-11-10 17:59:09 [INFO] ✓ MQTT connected successfully
2025-11-10 17:59:09 [DEBUG] Subscribed to: t/GENIO/u/fredrik/voice/voice-pi5-usb/tts
2025-11-10 17:59:09 [INFO] ✓ Subscribed to TTS and response topics
2025-11-10 17:59:09 [DEBUG] [Control] {'status': 'online'}
2025-11-10 17:59:09 [DEBUG] Publishing to t/GENIO/u/fredrik/voice/voice-pi5-usb/control: 145 bytes
2025-11-10 17:59:09 [INFO] 🎤 Session started: a1b2c3d4...
2025-11-10 17:59:09 [DEBUG] [Audio] Frame 1 (640 bytes)
2025-11-10 17:59:09 [DEBUG] Publishing to t/GENIO/u/fredrik/voice/voice-pi5-usb/audio: 1024 bytes
...
```

## Configuration

To enable debug mode, set `debug: true` in your `config.yaml`:

```yaml
# Logging
debug: true  # Enable verbose logging
```

## Benefits

1. **Clear Feedback**: You can now see exactly what's happening (MQTT connected, session started, etc.)
2. **No Noise**: Repetitive MQTT publish messages are hidden in normal mode
3. **Easy Troubleshooting**: Enable debug mode when you need to diagnose issues
4. **Session Tracking**: See exactly when sessions start/stop and how many frames were captured

## Migration from Previous Version

Previously, the agent would print:
```
[MQTT] Publishing to topic: t/GENIO/u/fredrik/voice/voice-pi5-usb/audio
[MQTT] Publishing to topic: t/GENIO/u/fredrik/voice/voice-pi5-usb/audio
[MQTT] Publishing to topic: t/GENIO/u/fredrik/voice/voice-pi5-usb/control
```

Now in normal mode, you'll see meaningful events:
```
🎤 Session started: a1b2c3d4...
✓ Session ended: a1b2c3d4... (15 frames, 300ms)
```

And you can still see the detailed MQTT messages by setting `debug: true`.
