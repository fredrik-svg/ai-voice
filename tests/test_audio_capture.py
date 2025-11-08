#!/usr/bin/env python3
"""
Tests for audio capture functionality.

These tests verify that the audio capture module correctly handles
the stereo-to-mono conversion pipeline for WM8960 codec.
"""

import unittest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.audio_capture import AudioStreamer


class TestAudioCapture(unittest.TestCase):
    """Test AudioStreamer configuration and command generation."""

    def setUp(self):
        """Set up test configuration."""
        self.test_config = {
            'audio': {
                'rate': 16000,
                'channels': 1,
                'format': 'S16_LE',
                'device': 'plughw:1,0',
                'chunk_ms': 20,
                'vad_mode': 2,
                'vad_silence_ms': 800,
                'mode': 'ptt'
            }
        }

    def test_init(self):
        """Test that AudioStreamer initializes correctly."""
        streamer = AudioStreamer(self.test_config)
        
        self.assertEqual(streamer.rate, 16000)
        self.assertEqual(streamer.chunk_ms, 20)
        self.assertEqual(streamer.device, 'plughw:1,0')
        self.assertEqual(streamer.format, 'S16_LE')
        self.assertFalse(streamer.running)
        self.assertIsNone(streamer.proc)
        self.assertIsNone(streamer.arecord_proc)

    def test_arecord_cmd_returns_two_parts(self):
        """Test that _arecord_cmd returns both arecord and sox commands."""
        streamer = AudioStreamer(self.test_config)
        arecord_cmd, sox_cmd = streamer._arecord_cmd()
        
        # Verify both commands are returned
        self.assertIsInstance(arecord_cmd, list)
        self.assertIsInstance(sox_cmd, list)
        self.assertGreater(len(arecord_cmd), 0)
        self.assertGreater(len(sox_cmd), 0)

    def test_arecord_cmd_stereo_capture(self):
        """Test that arecord captures in stereo (2 channels)."""
        streamer = AudioStreamer(self.test_config)
        arecord_cmd, sox_cmd = streamer._arecord_cmd()
        
        # Find the -c flag in arecord command
        self.assertIn('-c', arecord_cmd)
        c_index = arecord_cmd.index('-c')
        channels = arecord_cmd[c_index + 1]
        
        # Should be recording in stereo (2 channels) for WM8960 hardware
        self.assertEqual(channels, '2', 
                        "arecord should record in stereo (2 channels) for WM8960 codec")

    def test_arecord_cmd_device(self):
        """Test that arecord uses the configured device."""
        streamer = AudioStreamer(self.test_config)
        arecord_cmd, sox_cmd = streamer._arecord_cmd()
        
        # Check device is specified
        self.assertIn('-D', arecord_cmd)
        d_index = arecord_cmd.index('-D')
        device = arecord_cmd[d_index + 1]
        
        self.assertEqual(device, 'plughw:1,0')

    def test_arecord_cmd_format_and_rate(self):
        """Test that arecord uses the correct format and rate."""
        streamer = AudioStreamer(self.test_config)
        arecord_cmd, sox_cmd = streamer._arecord_cmd()
        
        # Check format
        self.assertIn('-f', arecord_cmd)
        f_index = arecord_cmd.index('-f')
        format_type = arecord_cmd[f_index + 1]
        self.assertEqual(format_type, 'S16_LE')
        
        # Check rate
        self.assertIn('-r', arecord_cmd)
        r_index = arecord_cmd.index('-r')
        rate = arecord_cmd[r_index + 1]
        self.assertEqual(rate, '16000')

    def test_sox_cmd_stereo_to_mono_conversion(self):
        """Test that sox converts from stereo to mono."""
        streamer = AudioStreamer(self.test_config)
        arecord_cmd, sox_cmd = streamer._arecord_cmd()
        
        # Sox should specify input as 2 channels and output as 1 channel
        # Find input channels specification
        input_c_index = None
        output_c_index = None
        for i, arg in enumerate(sox_cmd):
            if arg == '-c':
                if input_c_index is None:
                    input_c_index = i
                else:
                    output_c_index = i
        
        self.assertIsNotNone(input_c_index, "sox should specify input channels")
        self.assertIsNotNone(output_c_index, "sox should specify output channels")
        
        # Input should be stereo (2 channels)
        self.assertEqual(sox_cmd[input_c_index + 1], '2',
                        "sox input should be stereo (2 channels)")
        
        # Output should be mono (1 channel)
        self.assertEqual(sox_cmd[output_c_index + 1], '1',
                        "sox output should be mono (1 channel)")

    def test_sox_cmd_uses_stdin_stdout(self):
        """Test that sox reads from stdin and writes to stdout for piping."""
        streamer = AudioStreamer(self.test_config)
        arecord_cmd, sox_cmd = streamer._arecord_cmd()
        
        # Sox should use '-' for input and output to enable piping
        dash_count = sox_cmd.count('-')
        # Should have at least 2 dashes (input and output), 
        # plus more for other flags like -t, -e, -b, -c, -r
        self.assertGreaterEqual(dash_count, 2,
                               "sox should use stdin/stdout for piping")

    def test_chunk_bytes_calculation(self):
        """Test that chunk_bytes is calculated correctly for mono output."""
        streamer = AudioStreamer(self.test_config)
        
        # For 16000 Hz, 20ms, mono S16_LE:
        # 16000 samples/sec * 0.020 sec * 2 bytes/sample = 640 bytes
        expected_chunk_bytes = 16000 * 2 * 20 // 1000
        self.assertEqual(streamer.chunk_bytes, expected_chunk_bytes)


if __name__ == '__main__':
    print("=" * 70)
    print("Audio Capture Test Suite")
    print("Testing stereo-to-mono conversion pipeline for WM8960 codec")
    print("=" * 70)
    print()
    
    # Run tests with verbose output
    unittest.main(verbosity=2)
