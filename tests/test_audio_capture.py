#!/usr/bin/env python3
"""
Tests for audio capture functionality.

These tests verify that the audio capture module correctly handles
multi-channel to mono conversion pipeline for both:
- WM8960 codec (2-channel stereo)
- ReSpeaker USB 4-Mic Array (6-channel)
"""

import unittest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.audio_capture import AudioStreamer, _is_user_in_audio_group_file, _is_user_in_audio_group_session


class TestAudioCapture(unittest.TestCase):
    """Test AudioStreamer configuration and command generation."""

    def setUp(self):
        """Set up test configuration for WM8960 (2-channel)."""
        self.test_config = {
            'audio': {
                'rate': 16000,
                'channels': 1,
                'format': 'S16_LE',
                'device': 'plughw:1,0',
                'chunk_ms': 20,
                'vad_mode': 2,
                'vad_silence_ms': 800,
                'mode': 'ptt',
                'buffer_size': 8192,
                'period_size': 1024,
                'input_channels': 2
            }
        }
        
        self.usb_config = {
            'audio': {
                'rate': 16000,
                'channels': 1,
                'format': 'S16_LE',
                'device': 'plughw:CARD=ArrayUAC10,DEV=0',
                'chunk_ms': 20,
                'vad_mode': 2,
                'vad_silence_ms': 800,
                'mode': 'vad',
                'buffer_size': 4096,
                'period_size': 512,
                'input_channels': 6,
                'channel_mode': 'processed'
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
        """Test that arecord captures in stereo (2 channels) for WM8960."""
        streamer = AudioStreamer(self.test_config)
        arecord_cmd, sox_cmd = streamer._arecord_cmd()
        
        # Find the -c flag in arecord command
        self.assertIn('-c', arecord_cmd)
        c_index = arecord_cmd.index('-c')
        channels = arecord_cmd[c_index + 1]
        
        # Should be recording in stereo (2 channels) for WM8960 hardware
        self.assertEqual(channels, '2', 
                        "arecord should record in stereo (2 channels) for WM8960 codec")

    def test_arecord_cmd_6channel_capture(self):
        """Test that arecord captures in 6 channels for ReSpeaker USB."""
        streamer = AudioStreamer(self.usb_config)
        arecord_cmd, sox_cmd = streamer._arecord_cmd()
        
        # Find the -c flag in arecord command
        self.assertIn('-c', arecord_cmd)
        c_index = arecord_cmd.index('-c')
        channels = arecord_cmd[c_index + 1]
        
        # Should be recording in 6 channels for ReSpeaker USB
        self.assertEqual(channels, '6', 
                        "arecord should record in 6 channels for ReSpeaker USB 4-Mic Array")

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
        """Test that sox converts from stereo to mono for WM8960."""
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
    
    def test_sox_cmd_6channel_to_mono_conversion(self):
        """Test that sox converts from 6 channels to mono for ReSpeaker USB."""
        streamer = AudioStreamer(self.usb_config)
        arecord_cmd, sox_cmd = streamer._arecord_cmd()
        
        # Sox should specify input as 6 channels and output as 1 channel
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
        
        # Input should be 6 channels
        self.assertEqual(sox_cmd[input_c_index + 1], '6',
                        "sox input should be 6 channels for ReSpeaker USB")
        
        # Output should be mono (1 channel)
        self.assertEqual(sox_cmd[output_c_index + 1], '1',
                        "sox output should be mono (1 channel)")
    
    def test_sox_cmd_processed_mode_channel_selection(self):
        """Test that sox extracts channel 0 (processed) in processed mode."""
        streamer = AudioStreamer(self.usb_config)
        arecord_cmd, sox_cmd = streamer._arecord_cmd()
        
        # Should have 'remix' and '1' to select channel 1 (0-indexed becomes 1 in sox)
        self.assertIn('remix', sox_cmd)
        remix_index = sox_cmd.index('remix')
        self.assertEqual(sox_cmd[remix_index + 1], '1',
                        "sox should select channel 1 (processed audio) in processed mode")
    
    def test_sox_cmd_beamformed_mode(self):
        """Test that sox averages channels 1-4 in beamformed mode."""
        # Create config with beamformed mode
        beamformed_config = self.usb_config.copy()
        beamformed_config['audio'] = self.usb_config['audio'].copy()
        beamformed_config['audio']['channel_mode'] = 'beamformed'
        
        streamer = AudioStreamer(beamformed_config)
        arecord_cmd, sox_cmd = streamer._arecord_cmd()
        
        # Should have 'remix' with channels 2,3,4,5 (raw mics in 1-indexed)
        self.assertIn('remix', sox_cmd)
        remix_index = sox_cmd.index('remix')
        self.assertEqual(sox_cmd[remix_index + 1], '2,3,4,5',
                        "sox should average channels 2-5 (raw mics) in beamformed mode")

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

    def test_arecord_cmd_buffer_and_period_sizes(self):
        """Test that arecord includes buffer and period size parameters to prevent I/O errors."""
        streamer = AudioStreamer(self.test_config)
        arecord_cmd, sox_cmd = streamer._arecord_cmd()
        
        # Check buffer size parameter
        self.assertIn('--buffer-size', arecord_cmd)
        buffer_index = arecord_cmd.index('--buffer-size')
        buffer_size = arecord_cmd[buffer_index + 1]
        self.assertEqual(buffer_size, '8192',
                        "arecord should use buffer-size of 8192 to prevent I/O errors")
        
        # Check period size parameter
        self.assertIn('--period-size', arecord_cmd)
        period_index = arecord_cmd.index('--period-size')
        period_size = arecord_cmd[period_index + 1]
        self.assertEqual(period_size, '1024',
                        "arecord should use period-size of 1024 to balance latency and reliability")

    def test_buffer_and_period_sizes_when_not_specified(self):
        """Test that buffer and period sizes are NOT added when not specified in config."""
        # Create config without buffer/period settings
        config_without_buffer = {
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
        
        streamer = AudioStreamer(config_without_buffer)
        arecord_cmd, sox_cmd = streamer._arecord_cmd()
        
        # Should NOT have buffer and period sizes when not configured
        self.assertNotIn('--buffer-size', arecord_cmd, 
                        "Buffer size should not be added when not specified in config")
        self.assertNotIn('--period-size', arecord_cmd,
                        "Period size should not be added when not specified in config")
    
    def test_buffer_and_period_sizes_when_specified(self):
        """Test that buffer and period sizes ARE added when explicitly specified in config."""
        # Create config with explicit buffer/period settings
        config_with_buffer = {
            'audio': {
                'rate': 16000,
                'channels': 1,
                'format': 'S16_LE',
                'device': 'plughw:1,0',
                'chunk_ms': 20,
                'vad_mode': 2,
                'vad_silence_ms': 800,
                'mode': 'ptt',
                'buffer_size': 4096,
                'period_size': 512
            }
        }
        
        streamer = AudioStreamer(config_with_buffer)
        arecord_cmd, sox_cmd = streamer._arecord_cmd()
        
        # Should have buffer and period sizes when configured
        self.assertIn('--buffer-size', arecord_cmd, 
                     "Buffer size should be added when specified in config")
        self.assertIn('--period-size', arecord_cmd,
                     "Period size should be added when specified in config")
        
        buffer_index = arecord_cmd.index('--buffer-size')
        buffer_size = arecord_cmd[buffer_index + 1]
        self.assertEqual(buffer_size, '4096', "Buffer size should match config value")
        
        period_index = arecord_cmd.index('--period-size')
        period_size = arecord_cmd[period_index + 1]
        self.assertEqual(period_size, '512', "Period size should match config value")

    def test_validate_device_returns_false_when_arecord_unavailable(self):
        """Test that validate_device returns False when arecord command is not found."""
        streamer = AudioStreamer(self.test_config)
        
        # Mock subprocess.run to raise FileNotFoundError
        import subprocess
        from unittest.mock import patch
        
        with patch('subprocess.run', side_effect=FileNotFoundError("arecord not found")):
            result = streamer.validate_device()
            self.assertFalse(result, "validate_device should return False when arecord is not found")

    def test_validate_device_returns_false_on_nonzero_exit_code(self):
        """Test that validate_device returns False when arecord -l fails."""
        streamer = AudioStreamer(self.test_config)
        
        # Mock subprocess.run to return non-zero exit code
        import subprocess
        from unittest.mock import patch, Mock
        
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: No audio devices found"
        
        with patch('subprocess.run', return_value=mock_result):
            result = streamer.validate_device()
            self.assertFalse(result, "validate_device should return False when arecord -l fails")


class TestAudioGroupHelpers(unittest.TestCase):
    """Test audio group permission helper functions."""

    def test_is_user_in_audio_group_file_returns_bool(self):
        """Test that _is_user_in_audio_group_file returns a boolean."""
        result = _is_user_in_audio_group_file()
        self.assertIsInstance(result, bool)
    
    def test_is_user_in_audio_group_session_returns_bool(self):
        """Test that _is_user_in_audio_group_session returns a boolean."""
        result = _is_user_in_audio_group_session()
        self.assertIsInstance(result, bool)
    
    def test_is_user_in_audio_group_file_handles_missing_file(self):
        """Test that _is_user_in_audio_group_file handles missing /etc/group gracefully."""
        from unittest.mock import patch
        with patch('builtins.open', side_effect=FileNotFoundError):
            result = _is_user_in_audio_group_file()
            self.assertFalse(result)
    
    def test_is_user_in_audio_group_session_handles_missing_group(self):
        """Test that _is_user_in_audio_group_session handles missing audio group gracefully."""
        from unittest.mock import patch
        with patch('grp.getgrnam', side_effect=KeyError):
            result = _is_user_in_audio_group_session()
            self.assertFalse(result)


class TestAudioCaptureErrorHandling(unittest.TestCase):
    """Test error handling in AudioStreamer.start()."""

    def setUp(self):
        """Set up test configuration."""
        self.test_config = {
            'audio': {
                'rate': 16000,
                'channels': 1,
                'format': 'S16_LE',
                'device': 'plughw:CARD=ArrayUAC10,DEV=0',
                'chunk_ms': 20,
                'vad_mode': 2,
                'vad_silence_ms': 800,
                'mode': 'vad',
                'input_channels': 6,
                'channel_mode': 'processed'
            }
        }

    def test_start_detects_sox_failure_before_arecord(self):
        """Test that sox failure is detected before checking arecord (avoiding misleading SIGPIPE errors)."""
        from unittest.mock import patch, Mock
        from io import StringIO
        
        streamer = AudioStreamer(self.test_config)
        
        # Mock subprocess.Popen to simulate sox failing immediately
        mock_sox_proc = Mock()
        mock_sox_proc.poll.return_value = 1  # sox failed
        mock_sox_proc.stderr.read.return_value = b"sox FAIL formats: can't open input"
        
        mock_arecord_proc = Mock()
        mock_arecord_proc.poll.return_value = -13  # Would get SIGPIPE due to sox failure
        mock_arecord_proc.stdout = Mock()
        
        # Mock validate_device to return True (skip the subprocess.run call)
        with patch.object(streamer, 'validate_device', return_value=True):
            with patch('subprocess.Popen') as mock_popen:
                # First call creates arecord process, second call creates sox process
                mock_popen.side_effect = [mock_arecord_proc, mock_sox_proc]
                
                with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                    with self.assertRaises(RuntimeError) as context:
                        streamer.start()
                    
                    # Verify sox error is reported
                    stderr_output = mock_stderr.getvalue()
                    self.assertIn('[ERROR] sox failed to start', stderr_output)
                    self.assertIn("sox FAIL formats: can't open input", stderr_output)
                    
                    # Verify we DON'T see misleading permission error message
                    self.assertNotIn('Permission denied', stderr_output)
                    
                    # Verify the exception mentions sox, not arecord
                    self.assertIn('Failed to start audio conversion', str(context.exception))

    def test_start_detects_sigpipe_correctly(self):
        """Test that SIGPIPE (exit code -13) is correctly identified and reported."""
        from unittest.mock import patch, Mock
        from io import StringIO
        
        streamer = AudioStreamer(self.test_config)
        
        # Mock subprocess.Popen to simulate arecord getting SIGPIPE
        mock_sox_proc = Mock()
        mock_sox_proc.poll.return_value = None  # sox is still running
        
        mock_arecord_proc = Mock()
        mock_arecord_proc.poll.return_value = -13  # SIGPIPE
        mock_arecord_proc.stderr.read.return_value = b""  # No stderr output
        mock_arecord_proc.stdout = Mock()
        
        # Mock validate_device to return True
        with patch.object(streamer, 'validate_device', return_value=True):
            with patch('subprocess.Popen') as mock_popen:
                mock_popen.side_effect = [mock_arecord_proc, mock_sox_proc]
                
                with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                    with self.assertRaises(RuntimeError):
                        streamer.start()
                    
                    stderr_output = mock_stderr.getvalue()
                    # Should report SIGPIPE, not permission error
                    self.assertIn('arecord received SIGPIPE', stderr_output)
                    self.assertIn('broken pipe', stderr_output)
                    self.assertNotIn('Permission denied', stderr_output)
                    self.assertNotIn('audio group', stderr_output)

    def test_start_detects_permission_error_with_evidence(self):
        """Test that permission errors are only reported when there's actual evidence in stderr."""
        from unittest.mock import patch, Mock
        from io import StringIO
        
        streamer = AudioStreamer(self.test_config)
        
        # Mock subprocess.Popen to simulate actual permission error
        mock_sox_proc = Mock()
        mock_sox_proc.poll.return_value = None  # sox is still running
        
        mock_arecord_proc = Mock()
        mock_arecord_proc.poll.return_value = 1  # Non-zero exit
        mock_arecord_proc.stderr.read.return_value = b"arecord: main:850: audio open error: Permission denied"
        mock_arecord_proc.stdout = Mock()
        
        # Mock validate_device to return True
        with patch.object(streamer, 'validate_device', return_value=True):
            with patch('subprocess.Popen') as mock_popen:
                mock_popen.side_effect = [mock_arecord_proc, mock_sox_proc]
                
                with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                    with self.assertRaises(RuntimeError):
                        streamer.start()
                    
                    stderr_output = mock_stderr.getvalue()
                    # Should report permission error with helpful guidance
                    self.assertIn('Permission denied', stderr_output)
                    self.assertIn('Cannot access audio device', stderr_output)
                    # Should provide guidance about audio group
                    self.assertIn('audio', stderr_output.lower())

    def test_start_detects_device_not_found_error(self):
        """Test that device not found errors are properly reported."""
        from unittest.mock import patch, Mock
        from io import StringIO
        
        streamer = AudioStreamer(self.test_config)
        
        # Mock subprocess.Popen to simulate device not found
        mock_sox_proc = Mock()
        mock_sox_proc.poll.return_value = None  # sox is still running
        
        mock_arecord_proc = Mock()
        mock_arecord_proc.poll.return_value = 1  # Non-zero exit
        mock_arecord_proc.stderr.read.return_value = b"arecord: main:850: audio open error: No such file or directory"
        mock_arecord_proc.stdout = Mock()
        
        # Mock validate_device to return True
        with patch.object(streamer, 'validate_device', return_value=True):
            with patch('subprocess.Popen') as mock_popen:
                mock_popen.side_effect = [mock_arecord_proc, mock_sox_proc]
                
                with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                    with self.assertRaises(RuntimeError):
                        streamer.start()
                    
                    stderr_output = mock_stderr.getvalue()
                    # Should report device error
                    self.assertIn('Failed to open audio device', stderr_output)
                    self.assertIn('arecord -l', stderr_output)
                    # Should NOT report permission error
                    self.assertNotIn('Permission denied', stderr_output)


if __name__ == '__main__':
    print("=" * 70)
    print("Audio Capture Test Suite")
    print("Testing multi-channel to mono conversion pipeline for:")
    print("  - WM8960 codec (2-channel stereo)")
    print("  - ReSpeaker USB 4-Mic Array (6-channel)")
    print("=" * 70)
    print()
    
    # Run tests with verbose output
    unittest.main(verbosity=2)
