import ssl, json, threading
from typing import Callable
from paho.mqtt import client as mqtt

class MqttClient:
    def __init__(self, cfg):
        self.cfg = cfg
        cid_prefix = cfg['mqtt'].get('clientIdPrefix', 'voice-')
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{cid_prefix}{id(self)}", clean_session=True)
        self.client.username_pw_set(cfg['mqtt']['username'], cfg['mqtt']['password'])
        if cfg['mqtt'].get('tls', True):
            self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self._connected = threading.Event()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self._connected.set()
        else:
            self._connected.clear()

    def _on_disconnect(self, client, userdata, reason_code, properties):
        self._connected.clear()

    def connect(self):
        self.client.connect(self.cfg['mqtt']['host'], int(self.cfg['mqtt']['port']), keepalive=30)
        self.client.loop_start()
        self._connected.wait(timeout=10)

    def subscribe(self, topic, qos=1, on_message: Callable = None):
        if on_message:
            self.client.message_callback_add(topic, lambda c, u, m: on_message(m))
        self.client.subscribe(topic, qos=qos)

    def publish_json(self, topic, obj, qos=1, retain=False):
        import json
        payload = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.client.publish(topic, payload, qos=qos, retain=retain)
