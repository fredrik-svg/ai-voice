#!/usr/bin/env python3
"""
Tests for error handling in the agent module.

These tests verify that the agent correctly handles errors when
audio devices are unavailable or fail to start.
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agent import VoiceAgent


class TestErrorHandling(unittest.TestCase):
    """Test error handling in VoiceAgent."""

    def setUp(self):
        """Set up test configuration."""
        self.test_config = {
            'tenant': 'test',
            'user': 'test_user',
            'deviceId': 'test_device',
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
                'mode': 'ptt'
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

    @patch('src.agent.MqttClient')
    @patch('src.agent.AudioStreamer')
    def test_capture_once_handles_streamer_start_error(self, mock_streamer_class, mock_mqtt_class):
        """Test that _capture_once handles errors from streamer.start() gracefully."""
        # Create agent with mocked dependencies
        agent = VoiceAgent(self.test_config)
        
        # Mock the streamer to raise an error on start
        mock_streamer = Mock()
        mock_streamer.start.side_effect = RuntimeError("Failed to start audio capture: arecord: main:850: audio open error: No such file or directory")
        agent.streamer = mock_streamer
        
        # Mock the MQTT client
        agent.mqtt = Mock()
        agent.mqtt.publish_json = Mock()
        
        # Capture stderr
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            # Call _capture_once which should handle the error gracefully
            agent._capture_once()
            
            # Verify error was logged
            stderr_output = mock_stderr.getvalue()
            self.assertIn('[ERROR] Audio capture failed:', stderr_output)
            self.assertIn('Failed to start audio capture', stderr_output)
        
        # Verify streamer.start was called
        mock_streamer.start.assert_called_once()
        
        # Verify end_session was still called (in the finally block)
        # This is important to ensure cleanup happens even on error
        agent.mqtt.publish_json.assert_called()
        call_args = agent.mqtt.publish_json.call_args_list
        # Should have at least one call with 'audio_end' event
        has_end_event = any('audio_end' in str(call) for call in call_args)
        self.assertTrue(has_end_event, "Expected audio_end event to be published in finally block")

    @patch('src.agent.MqttClient')
    @patch('src.agent.AudioStreamer')
    def test_capture_once_handles_vad_stream_error(self, mock_streamer_class, mock_mqtt_class):
        """Test that _capture_once handles errors during VAD streaming gracefully."""
        # Create agent with mocked dependencies
        agent = VoiceAgent(self.test_config)
        
        # Mock the streamer to raise an error during vad_stream
        mock_streamer = Mock()
        mock_streamer.start = Mock()
        mock_streamer.vad_stream.side_effect = RuntimeError("Error reading audio stream")
        mock_streamer.stop = Mock()
        agent.streamer = mock_streamer
        
        # Mock the MQTT client
        agent.mqtt = Mock()
        agent.mqtt.publish_json = Mock()
        
        # Capture stderr
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            # Call _capture_once which should handle the error gracefully
            agent._capture_once()
            
            # Verify error was logged
            stderr_output = mock_stderr.getvalue()
            self.assertIn('[ERROR] Audio capture failed:', stderr_output)
        
        # Verify cleanup was called
        mock_streamer.stop.assert_called_once()

    @patch('src.agent.MqttClient')
    @patch('src.agent.AudioStreamer')
    @patch('sys.exit')
    def test_run_vad_exits_on_streamer_start_error(self, mock_exit, mock_streamer_class, mock_mqtt_class):
        """Test that run_vad exits gracefully when streamer.start() fails."""
        # Create agent with mocked dependencies
        agent = VoiceAgent(self.test_config)
        
        # Mock the streamer to raise an error on start
        mock_streamer = Mock()
        mock_streamer.start.side_effect = RuntimeError("Failed to start audio capture: arecord: main:850: audio open error: No such file or directory")
        agent.streamer = mock_streamer
        
        # Mock the MQTT client
        agent.mqtt = Mock()
        agent.mqtt.publish_json = Mock()
        
        # Capture stderr
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            # Call run_vad which should handle the error and exit
            agent.run_vad()
            
            # Verify error was logged
            stderr_output = mock_stderr.getvalue()
            self.assertIn('[ERROR] Audio capture failed:', stderr_output)
            self.assertIn('VAD mode cannot continue without audio device', stderr_output)
        
        # Verify sys.exit was called
        mock_exit.assert_called_once_with(1)


if __name__ == '__main__':
    print("=" * 70)
    print("Error Handling Test Suite")
    print("Testing graceful error handling for audio device failures")
    print("=" * 70)
    print()
    
    # Run tests with verbose output
    unittest.main(verbosity=2)
