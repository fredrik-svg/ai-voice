import ssl, json, threading, logging
from typing import Callable
from paho.mqtt import client as mqtt

logger = logging.getLogger(__name__)

class MqttClient:
    def __init__(self, cfg):
        self.cfg = cfg
        cid_prefix = cfg['mqtt'].get('clientIdPrefix', 'voice-')
        self.client = mqtt.Client(client_id=f"{cid_prefix}{id(self)}", clean_session=True)
        self.client.username_pw_set(cfg['mqtt']['username'], cfg['mqtt']['password'])
        if cfg['mqtt'].get('tls', True):
            self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self._connected = threading.Event()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected.set()
            logger.debug("MQTT connection established")
        else:
            self._connected.clear()
            logger.error(f"MQTT connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected.clear()
        if rc != 0:
            logger.warning(f"MQTT disconnected unexpectedly (rc={rc})")

    def connect(self):
        self.client.connect(self.cfg['mqtt']['host'], int(self.cfg['mqtt']['port']), keepalive=30)
        self.client.loop_start()
        self._connected.wait(timeout=10)

    def subscribe(self, topic, qos=1, on_message: Callable = None):
        if on_message:
            self.client.message_callback_add(topic, lambda c, u, m: on_message(m))
        self.client.subscribe(topic, qos=qos)
        logger.debug(f"Subscribed to: {topic}")

    def publish_json(self, topic, obj, qos=1, retain=False):
        import json
        payload = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        logger.debug(f"Publishing to {topic}: {len(payload)} bytes")
        self.client.publish(topic, payload, qos=qos, retain=retain)
