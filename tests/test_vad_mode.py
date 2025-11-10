#!/usr/bin/env python3
"""
Tests for VAD mode behavior in the voice agent.

These tests verify that VAD mode correctly:
1. Only publishes audio frames when speech is detected
2. Does not publish silence frames
3. Starts session on first speech
4. Ends session after silence threshold
"""

import unittest
import sys
import os
from unittest.mock import Mock, MagicMock, patch, call
import yaml

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agent import VoiceAgent


class TestVADMode(unittest.TestCase):
    """Test VAD mode behavior."""

    def setUp(self):
        """Set up test configuration for VAD mode."""
        self.test_config = {
            'tenant': 'TEST',
            'user': 'testuser',
            'deviceId': 'test-device',
            'mqtt': {
                'host': 'localhost',
                'port': 1883,
                'username': 'test',
                'password': 'test',
                'tls': False,
                'clientIdPrefix': 'test-'
            },
            'topics': {
                'audio': 't/{tenant}/u/{user}/voice/{deviceId}/audio',
                'control': 't/{tenant}/u/{user}/voice/{deviceId}/control',
                'response': 't/{tenant}/u/{user}/voice/{deviceId}/response',
                'tts': 't/{tenant}/u/{user}/voice/{deviceId}/tts'
            },
            'audio': {
                'rate': 16000,
                'channels': 1,
                'format': 'S16_LE',
                'device': 'plughw:1,0',
                'chunk_ms': 20,
                'vad_mode': 2,
                'vad_silence_ms': 800,
                'mode': 'vad',
                'input_channels': 2
            },
            'gpio': {
                'button_pin': 17,
                'pull_up': True
            },
            'playback': {
                'device': 'plughw:1,0',
                'volume_pct': 90
            }
        }

    def test_vad_mode_only_publishes_speech_frames(self):
        """Test that VAD mode only publishes frames when speech is detected, not silence."""
        agent = VoiceAgent(self.test_config)
        
        # Mock MQTT client
        agent.mqtt = Mock()
        agent.mqtt.publish_json = Mock()
        
        # Mock streamer to simulate speech and silence patterns
        agent.streamer = Mock()
        
        # Simulate pattern: silence, speech, speech, silence, silence (end session), silence
        # Each tuple is (is_speech, frame_data)
        mock_vad_stream = [
            (False, b'silence_frame_1'),  # Silence before speech - should not publish
            (True, b'speech_frame_1'),    # Speech starts - should start session and publish
            (True, b'speech_frame_2'),    # Speech continues - should publish
            (False, b'silence_frame_2'),  # Silence 20ms - should not publish
            (False, b'silence_frame_3'),  # Silence 40ms - should not publish
            # ... continue silence pattern until threshold (800ms = 40 frames)
        ] + [(False, b'silence_frame_%d' % i) for i in range(4, 42)]  # 38 more silence frames to reach 800ms total
        
        agent.streamer.vad_stream = Mock(return_value=iter(mock_vad_stream))
        agent.streamer.start = Mock()
        agent.streamer.stop = Mock()
        
        # Track published frames
        published_frames = []
        
        def capture_publish(topic, data, **kwargs):
            if 'pcm_b64' in data:
                published_frames.append(data)
        
        agent.mqtt.publish_json.side_effect = capture_publish
        
        # Run VAD mode until it stops (simulating SIGINT after session ends)
        original_running = agent.running
        call_count = [0]
        
        def check_running():
            call_count[0] += 1
            # Stop after processing all frames plus a bit more for cleanup
            return call_count[0] < 50
        
        agent.running = property(lambda self: check_running())
        
        # Patch threading to avoid actual background threads in tests
        with patch('threading.Thread'):
            try:
                agent.run_vad()
            except (StopIteration, AttributeError):
                # Expected when mock iterator runs out
                pass
        
        # Verify behavior:
        # 1. Only speech frames should be published (2 frames: speech_frame_1 and speech_frame_2)
        self.assertEqual(len(published_frames), 2, 
                        f"Should only publish 2 speech frames, but published {len(published_frames)}")
        
        # 2. Silence frames should NOT be published
        for frame_data in published_frames:
            # Decode the base64 to check it's a speech frame
            import base64
            pcm_data = base64.b64decode(frame_data['pcm_b64'])
            self.assertIn(b'speech', pcm_data,
                         f"Published frame should be a speech frame, but got: {pcm_data}")
            self.assertNotIn(b'silence', pcm_data,
                           f"Published frame should NOT be a silence frame, but got: {pcm_data}")
        
        # 3. Session should be started once
        control_calls = [call for call in agent.mqtt.publish_json.call_args_list 
                        if 'audio_start' in str(call)]
        self.assertEqual(len(control_calls), 1, "Should start session exactly once")
        
        # 4. Session should be ended once after silence threshold
        control_calls = [call for call in agent.mqtt.publish_json.call_args_list 
                        if 'audio_end' in str(call)]
        self.assertEqual(len(control_calls), 1, "Should end session exactly once after silence")

    def test_ptt_mode_only_publishes_speech_frames(self):
        """Test that PTT mode only publishes frames when speech is detected (existing behavior)."""
        # Change mode to PTT for comparison
        self.test_config['audio']['mode'] = 'ptt'
        agent = VoiceAgent(self.test_config)
        
        # Mock MQTT client
        agent.mqtt = Mock()
        agent.mqtt.publish_json = Mock()
        
        # Mock streamer
        agent.streamer = Mock()
        
        # Simulate pattern: speech, speech, silence, silence (end capture)
        mock_vad_stream = [
            (True, b'speech_frame_1'),    # Speech - should publish
            (True, b'speech_frame_2'),    # Speech - should publish
            (False, b'silence_frame_1'),  # Silence 20ms - should not publish
            (False, b'silence_frame_2'),  # Silence 40ms - should not publish
        ] + [(False, b'silence_frame_%d' % i) for i in range(3, 42)]  # More silence to reach threshold
        
        agent.streamer.vad_stream = Mock(return_value=iter(mock_vad_stream))
        agent.streamer.start = Mock()
        agent.streamer.stop = Mock()
        
        # Track published frames
        published_frames = []
        
        def capture_publish(topic, data, **kwargs):
            if 'pcm_b64' in data:
                published_frames.append(data)
        
        agent.mqtt.publish_json.side_effect = capture_publish
        
        # Run PTT mode once (simulating a button press)
        agent._capture_once()
        
        # Verify behavior:
        # 1. Only speech frames should be published (2 frames)
        self.assertEqual(len(published_frames), 2,
                        f"PTT mode should only publish 2 speech frames, but published {len(published_frames)}")
        
        # 2. Silence frames should NOT be published
        for frame_data in published_frames:
            import base64
            pcm_data = base64.b64decode(frame_data['pcm_b64'])
            self.assertIn(b'speech', pcm_data,
                         f"PTT published frame should be a speech frame")


if __name__ == '__main__':
    print("=" * 70)
    print("VAD Mode Test Suite")
    print("Testing that VAD mode only publishes speech frames")
    print("=" * 70)
    print()
    
    # Run tests with verbose output
    unittest.main(verbosity=2)
