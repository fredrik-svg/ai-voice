import tempfile, subprocess, base64, json, os

def play_wav_bytes(wav_bytes: bytes, device: str = None, volume_pct: int = None):
    # Optionally set volume via 'amixer' for WM8960
    if volume_pct is not None:
        try:
            subprocess.call(['amixer', 'sset', 'Headphone', f'{int(volume_pct)}%'])
        except Exception:
            pass
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        f.write(wav_bytes)
        f.flush()
        path = f.name
    cmd = ['aplay', '-q']
    if device:
        cmd += ['-D', device]
    cmd += [path]
    try:
        subprocess.call(cmd)
    finally:
        try: os.unlink(path)
        except Exception: pass
