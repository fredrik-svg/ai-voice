import subprocess, threading, collections, time, warnings, sys, os, grp

# Suppress the pkg_resources deprecation warning from webrtcvad
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources.*")
    import webrtcvad

# Constants
PROCESS_START_CHECK_DELAY = 0.1  # seconds to wait before checking if arecord started successfully

def _is_user_in_audio_group_file():
    """Check if the current user is listed in the audio group in /etc/group.
    
    This checks the group file on disk, not the current session's active groups.
    Useful for detecting when a user has been added to audio group but hasn't
    logged out yet to activate the membership.
    
    Returns:
        bool: True if user is in audio group in /etc/group, False otherwise
    """
    try:
        username = os.getenv('USER') or os.getenv('USERNAME')
        if not username:
            return False
        
        # Read /etc/group to check if user is listed in audio group
        with open('/etc/group', 'r') as f:
            for line in f:
                if line.startswith('audio:'):
                    # Format: audio:x:29:user1,user2,user3
                    parts = line.strip().split(':')
                    if len(parts) >= 4:
                        members = parts[3].split(',')
                        if username in members:
                            return True
        return False
    except Exception:
        return False

def _is_user_in_audio_group_session():
    """Check if the audio group is active in the current session.
    
    Returns:
        bool: True if audio group is in current session's groups, False otherwise
    """
    try:
        # Get all groups for the current process
        groups = os.getgroups()
        # Get the audio group ID
        audio_gid = grp.getgrnam('audio').gr_gid
        return audio_gid in groups
    except Exception:
        return False

class AudioStreamer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.rate = int(cfg['audio']['rate'])
        self.chunk_ms = int(cfg['audio']['chunk_ms'])
        self.chunk_bytes = int(self.rate * 2 * self.chunk_ms / 1000)  # S16_LE mono => 2 bytes/sample
        self.device = cfg['audio']['device']
        self.format = cfg['audio']['format']
        self.proc = None
        self.arecord_proc = None
        self.vad = webrtcvad.Vad(int(cfg['audio']['vad_mode']))
        self.running = False


    def _arecord_cmd(self):
        # Multi-channel audio capture with conversion to mono
        # 
        # Hardware configurations:
        # - WM8960 (I2S HAT): 2-channel stereo capture
        # - ReSpeaker USB 4-Mic Array: 6-channel capture
        #   Channel 0: Processed audio (AEC, beamforming, noise suppression)
        #   Channels 1-4: Raw audio from each microphone
        #   Channel 5: Playback audio
        # 
        # Buffer and period sizes are optional and can be set to prevent I/O errors:
        # - I2S devices (like WM8960): Often need explicit buffer 8192, period 1024
        # - USB devices (like ReSpeaker USB): Usually work better without explicit sizes (let ALSA use defaults)
        # If not specified in config, ALSA will use appropriate defaults for the device
        buffer_size = self.cfg['audio'].get('buffer_size')
        period_size = self.cfg['audio'].get('period_size')
        
        # Get input channel count from config (default to 2 for backward compatibility)
        input_channels = self.cfg['audio'].get('input_channels', 2)
        
        arecord_part = [
            'arecord',
            '-q',
            '-D', self.device,
            '-c', str(input_channels),  # Record in specified channel count
            '-f', self.format,
            '-r', str(self.rate),
            '-t', 'raw'
        ]
        
        # Only add buffer and period sizes if explicitly configured
        # Some devices (like USB audio) work better without these parameters
        if buffer_size is not None:
            arecord_part.extend(['--buffer-size', str(buffer_size)])
        if period_size is not None:
            arecord_part.extend(['--period-size', str(period_size)])
        
        # Convert multi-channel to mono using sox
        # For ReSpeaker USB 4-Mic: channel_mode can be:
        # - "processed": use channel 0 (already processed by DSP)
        # - "beamformed": average channels 1-4 (raw mics)
        # For stereo (2-channel): always averages both channels
        channel_mode = self.cfg['audio'].get('channel_mode', 'processed')
        
        sox_part = [
            'sox',
            '-t', 'raw',
            '-e', 'signed-integer',
            '-b', '16',
            '-c', str(input_channels),
            '-r', str(self.rate),
            '-',  # read from stdin
            '-t', 'raw',
            '-e', 'signed-integer', 
            '-b', '16',
            '-c', '1',  # output mono
            '-r', str(self.rate),
            '-'  # write to stdout
        ]
        
        # Add channel remixing for specific modes
        if input_channels == 6 and channel_mode == 'processed':
            # Extract only channel 0 (processed audio) for ReSpeaker USB
            sox_part.append('remix')
            sox_part.append('1')  # Select channel 1 (0-indexed becomes 1 in sox)
        elif input_channels == 6 and channel_mode == 'beamformed':
            # Average channels 1-4 (raw microphones) for custom beamforming
            sox_part.append('remix')
            sox_part.append('2,3,4,5')  # Average channels 2-5 (mics 1-4 in 1-indexed)
        # For 2-channel or other configs, sox will average all channels by default
        
        return arecord_part, sox_part

    def validate_device(self):
        """Check if audio capture devices are available.
        
        This is a best-effort check to provide early feedback. The definitive
        validation happens when arecord actually attempts to open the device.
        
        Returns:
            bool: True if audio devices appear to be available, False otherwise.
        """
        try:
            # Try to list ALSA devices
            result = subprocess.run(['arecord', '-l'], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                print(f"[WARNING] Unable to list audio devices. Device '{self.device}' may not exist.", file=sys.stderr)
                print(f"[WARNING] Error output: {result.stderr.strip()}", file=sys.stderr)
                return False
            
            # Check if any capture devices are available (basic check)
            if 'card' not in result.stdout.lower():
                print(f"[WARNING] No audio capture devices found.", file=sys.stderr)
                return False
            
            return True
        except FileNotFoundError:
            print(f"[ERROR] arecord command not found. Please install alsa-utils.", file=sys.stderr)
            return False
        except subprocess.TimeoutExpired:
            print(f"[WARNING] Timeout while checking audio devices.", file=sys.stderr)
            return False
        except Exception as e:
            print(f"[WARNING] Error checking audio device: {e}", file=sys.stderr)
            return False

    def start(self):
        if self.running: return
        
        # Validate device availability (best-effort check)
        # Note: This provides early feedback but doesn't guarantee the specific
        # device in config will work. The actual validation happens when arecord starts.
        if not self.validate_device():
            print(f"[WARNING] Audio device pre-check failed. Will attempt to start anyway...", file=sys.stderr)
        
        try:
            # Create a pipeline: arecord (stereo) | sox (stereo->mono conversion)
            arecord_cmd, sox_cmd = self._arecord_cmd()
            
            # Start arecord process
            arecord_proc = subprocess.Popen(
                arecord_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Start sox process, reading from arecord's stdout
            self.proc = subprocess.Popen(
                sox_cmd,
                stdin=arecord_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Allow arecord to receive SIGPIPE if sox exits
            arecord_proc.stdout.close()
            
            # Store arecord process for cleanup
            self.arecord_proc = arecord_proc
            
            # Give the processes a moment to start, then check if they failed immediately
            time.sleep(PROCESS_START_CHECK_DELAY)
            
            # Check if sox failed first (since it's downstream and can cause arecord to get SIGPIPE)
            sox_poll = self.proc.poll()
            sox_stderr = ""
            if sox_poll is not None:
                sox_stderr = self.proc.stderr.read().decode('utf-8', errors='replace').strip()
                print(f"[ERROR] sox failed to start (exit code {sox_poll})", file=sys.stderr)
                if sox_stderr:
                    print(f"[ERROR] sox output: {sox_stderr}", file=sys.stderr)
                raise RuntimeError(f"Failed to start audio conversion: {sox_stderr}")
            
            # Check if arecord failed
            arecord_poll = arecord_proc.poll()
            if arecord_poll is not None:
                arecord_stderr = arecord_proc.stderr.read().decode('utf-8', errors='replace').strip()
                
                # Determine the actual error type based on stderr content and exit code
                is_permission_error = False
                stderr_lower = arecord_stderr.lower()
                
                # Only treat as permission error if there's actual evidence:
                # - Explicit "permission denied" in stderr
                # Note: Exit code -13 is SIGPIPE (broken pipe), NOT a permission error.
                # SIGPIPE happens when arecord writes to a closed pipe (e.g., if sox exited).
                # "audio open error" alone is not sufficient - need explicit permission message.
                if arecord_stderr and "permission denied" in stderr_lower:
                    is_permission_error = True
                
                # Report the error with appropriate context
                if is_permission_error:
                    print(f"[ERROR] arecord failed to start: Permission denied", file=sys.stderr)
                    if arecord_stderr:
                        print(f"[ERROR] arecord output: {arecord_stderr}", file=sys.stderr)
                    print(f"[ERROR] Cannot access audio device '{self.device}'.", file=sys.stderr)
                    
                    # Check if user is in audio group in /etc/group but not in current session
                    in_group_file = _is_user_in_audio_group_file()
                    in_session = _is_user_in_audio_group_session()
                    
                    if in_group_file and not in_session:
                        # User has been added to audio group but hasn't logged out yet
                        print(f"[INFO] You are listed in the 'audio' group, but it's not active in this session.", file=sys.stderr)
                        print(f"[INFO] This means you were recently added to the group but haven't logged out yet.", file=sys.stderr)
                        print(f"[INFO] ", file=sys.stderr)
                        print(f"[INFO] To activate the group membership:", file=sys.stderr)
                        print(f"[INFO]   1. Save your work and exit all programs", file=sys.stderr)
                        print(f"[INFO]   2. Log out completely (exit SSH session or log out of GUI)", file=sys.stderr)
                        print(f"[INFO]   3. Log back in", file=sys.stderr)
                        print(f"[INFO]   4. Verify with: groups (you should see 'audio' in the list)", file=sys.stderr)
                        print(f"[INFO] ", file=sys.stderr)
                        print(f"[INFO] Alternative for testing (temporary, resets on reboot):", file=sys.stderr)
                        print(f"[INFO]   sudo chmod a+rw /dev/snd/*", file=sys.stderr)
                    elif not in_group_file:
                        # User is not in audio group at all
                        print(f"[INFO] Your user doesn't have permission to access audio devices.", file=sys.stderr)
                        print(f"[INFO] To fix this, add your user to the 'audio' group:", file=sys.stderr)
                        print(f"[INFO]   sudo usermod -a -G audio $USER", file=sys.stderr)
                        print(f"[INFO]   Then log out and log back in for the changes to take effect.", file=sys.stderr)
                        print(f"[INFO] You can verify group membership with: groups", file=sys.stderr)
                    else:
                        # User is in audio group in session, but still getting permission error
                        # This could be due to other issues (e.g., device permissions, SELinux, etc.)
                        print(f"[INFO] You appear to be in the 'audio' group, but still getting permission errors.", file=sys.stderr)
                        print(f"[INFO] This could be due to:", file=sys.stderr)
                        print(f"[INFO]   - Device file permissions: Check 'ls -l /dev/snd/*'", file=sys.stderr)
                        print(f"[INFO]   - SELinux/AppArmor restrictions", file=sys.stderr)
                        print(f"[INFO]   - Device locked by another process", file=sys.stderr)
                        print(f"[INFO] Try temporarily: sudo chmod a+rw /dev/snd/*", file=sys.stderr)
                elif arecord_stderr and "audio open error" in stderr_lower:
                    # Device open error (not permission-related)
                    print(f"[ERROR] arecord failed to start (exit code {arecord_poll})", file=sys.stderr)
                    print(f"[ERROR] arecord output: {arecord_stderr}", file=sys.stderr)
                    print(f"[ERROR] Failed to open audio device '{self.device}'.", file=sys.stderr)
                    print(f"[INFO] Please verify the device exists and is configured correctly in config.yaml.", file=sys.stderr)
                    print(f"[INFO] Run 'arecord -l' to list available capture devices.", file=sys.stderr)
                    if "busy" in stderr_lower:
                        print(f"[INFO] The device may be in use by another application.", file=sys.stderr)
                        print(f"[INFO] Try closing other audio applications or use 'fuser -v /dev/snd/*' to find processes using audio.", file=sys.stderr)
                elif arecord_poll == -13 or (arecord_poll < 0 and abs(arecord_poll) == 13):
                    # SIGPIPE - likely sox failed first or pipe was closed
                    print(f"[ERROR] arecord received SIGPIPE (broken pipe)", file=sys.stderr)
                    if arecord_stderr:
                        print(f"[ERROR] arecord output: {arecord_stderr}", file=sys.stderr)
                    print(f"[INFO] This usually means the downstream process (sox) closed the pipe.", file=sys.stderr)
                    print(f"[INFO] Check that sox is installed and the audio pipeline configuration is correct.", file=sys.stderr)
                else:
                    # Generic error
                    print(f"[ERROR] arecord failed to start (exit code {arecord_poll})", file=sys.stderr)
                    if arecord_stderr:
                        print(f"[ERROR] arecord output: {arecord_stderr}", file=sys.stderr)
                
                raise RuntimeError(f"Failed to start audio capture: {arecord_stderr}")
            
            self.running = True
        except FileNotFoundError as e:
            if 'arecord' in str(e):
                print(f"[ERROR] arecord command not found. Please install alsa-utils.", file=sys.stderr)
            elif 'sox' in str(e):
                print(f"[ERROR] sox command not found. Please install sox.", file=sys.stderr)
            else:
                print(f"[ERROR] Command not found: {e}", file=sys.stderr)
            raise
        except Exception as e:
            print(f"[ERROR] Failed to start audio capture: {e}", file=sys.stderr)
            raise

    def stop(self):
        if not self.running: return
        
        # Terminate both sox and arecord processes
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except Exception:
                self.proc.kill()
        
        if hasattr(self, 'arecord_proc') and self.arecord_proc:
            self.arecord_proc.terminate()
            try:
                self.arecord_proc.wait(timeout=2)
            except Exception:
                self.arecord_proc.kill()
        
        self.running = False

    def frames(self):
        """Yield 20ms frames; each frame is bytes of length chunk_bytes."""
        buf = b''
        while self.running:
            data = self.proc.stdout.read(self.chunk_bytes - len(buf))
            if not data:
                break
            buf += data
            if len(buf) >= self.chunk_bytes:
                frame, buf = buf[:self.chunk_bytes], buf[self.chunk_bytes:]
                yield frame

    def vad_stream(self):
        """Detect speech segments using VAD; yield (is_speech, frame_bytes)."""
        for frame in self.frames():
            is_speech = self.vad.is_speech(frame, self.rate)
            yield is_speech, frame
