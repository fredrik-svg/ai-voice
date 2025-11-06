import os, time, uuid, base64, json

def now_ms():
    return int(time.time() * 1000)

def new_session_id():
    return uuid.uuid4().hex

def b64(data: bytes) -> str:
    return base64.b64encode(data).decode('ascii')

def jb(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode('utf-8')
