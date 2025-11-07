#!/usr/bin/env python3
"""
Test för MQTT-klient - verifierar att skicka och ta emot meddelanden fungerar
Test for MQTT client - verifies that sending and receiving messages works
"""
import unittest
import json
import time
import threading
import os
import yaml
from src.mqtt_client import MqttClient


def load_test_config():
    """Load test configuration from config.yaml if available, otherwise use localhost"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
    
    # Try to load from config.yaml
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                cfg = yaml.safe_load(f)
            
            # Check if config has valid MQTT settings (not placeholders)
            mqtt_host = cfg.get('mqtt', {}).get('host', '')
            if mqtt_host and not mqtt_host.startswith('YOUR_'):
                # Use config.yaml settings for testing against real broker
                print(f"\n[INFO] Using MQTT broker from config.yaml: {mqtt_host}")
                return cfg
        except Exception as e:
            print(f"\n[WARNING] Failed to load config.yaml: {e}")
    
    # Fall back to localhost for local testing
    print("\n[INFO] Using localhost MQTT broker for testing")
    return {
        'tenant': 'test',
        'user': 'testuser',
        'deviceId': 'test-device',
        'mqtt': {
            'host': 'localhost',  # Local Mosquitto broker
            'port': 1883,  # Non-TLS port for testing
            'username': '',  # Local broker doesn't require auth
            'password': '',
            'tls': False,  # Disable TLS for local test broker
            'clientIdPrefix': 'test-voice-'
        }
    }


class TestMqttClient(unittest.TestCase):
    """Test MQTT client send and receive functionality"""

    def setUp(self):
        """Set up test configuration from config.yaml or localhost"""
        self.cfg = load_test_config()
        self.test_topic = f"test/ai-voice/{int(time.time())}"
        self.received_messages = []
        self.message_received_event = threading.Event()

    def tearDown(self):
        """Clean up after test"""
        if hasattr(self, 'client') and self.client:
            try:
                self.client.client.loop_stop()
                self.client.client.disconnect()
            except Exception:
                pass

    def test_mqtt_connect(self):
        """Test: Anslutning till MQTT-broker ska fungera"""
        self.client = MqttClient(self.cfg)
        self.client.connect()
        
        # Verify connection
        self.assertTrue(self.client._connected.is_set(), 
                       "Kunde inte ansluta till MQTT-broker")
        print("✓ Anslutning till MQTT-broker fungerar")

    def test_mqtt_publish_and_subscribe(self):
        """Test: Skicka och ta emot meddelanden via MQTT"""
        self.client = MqttClient(self.cfg)
        self.client.connect()
        
        # Wait for connection
        self.assertTrue(self.client._connected.wait(timeout=5),
                       "Timeout när anslutning till MQTT-broker")

        # Define message handler
        def on_message(msg):
            payload = msg.payload.decode('utf-8')
            self.received_messages.append(payload)
            self.message_received_event.set()
        
        # Subscribe to test topic
        self.client.subscribe(self.test_topic, qos=1, on_message=on_message)
        time.sleep(1)  # Allow subscription to complete
        
        # Publish a test message
        test_payload = "Hej från MQTT test!"
        self.client.client.publish(self.test_topic, test_payload, qos=1)
        
        # Wait for message to be received
        received = self.message_received_event.wait(timeout=5)
        self.assertTrue(received, "Meddelande mottogs inte inom timeout")
        
        # Verify the message content
        self.assertEqual(len(self.received_messages), 1,
                        "Fel antal mottagna meddelanden")
        self.assertEqual(self.received_messages[0], test_payload,
                        "Mottaget meddelande matchar inte skickat meddelande")
        
        print(f"✓ Skickade meddelande: '{test_payload}'")
        print(f"✓ Mottog meddelande: '{self.received_messages[0]}'")
        print("✓ Skicka och ta emot meddelanden fungerar")

    def test_mqtt_publish_json(self):
        """Test: Skicka och ta emot JSON-meddelanden"""
        self.client = MqttClient(self.cfg)
        self.client.connect()
        
        # Wait for connection
        self.assertTrue(self.client._connected.wait(timeout=5),
                       "Timeout när anslutning till MQTT-broker")

        # Define message handler for JSON
        def on_json_message(msg):
            payload = json.loads(msg.payload.decode('utf-8'))
            self.received_messages.append(payload)
            self.message_received_event.set()
        
        # Subscribe to test topic
        self.client.subscribe(self.test_topic + "/json", qos=1, 
                            on_message=on_json_message)
        time.sleep(1)  # Allow subscription to complete
        
        # Publish a JSON message
        test_json = {
            'message': 'Test från MQTT',
            'timestamp': int(time.time()),
            'data': {
                'value': 42,
                'status': 'ok'
            }
        }
        self.client.publish_json(self.test_topic + "/json", test_json, qos=1)
        
        # Wait for message to be received
        received = self.message_received_event.wait(timeout=5)
        self.assertTrue(received, "JSON-meddelande mottogs inte inom timeout")
        
        # Verify the JSON message content
        self.assertEqual(len(self.received_messages), 1,
                        "Fel antal mottagna JSON-meddelanden")
        received_json = self.received_messages[0]
        self.assertEqual(received_json['message'], test_json['message'],
                        "JSON-meddelande matchar inte")
        self.assertEqual(received_json['data']['value'], 42,
                        "JSON-data matchar inte")
        
        print(f"✓ Skickade JSON: {test_json}")
        print(f"✓ Mottog JSON: {received_json}")
        print("✓ JSON-meddelanden fungerar korrekt")

    def test_mqtt_multiple_messages(self):
        """Test: Skicka och ta emot flera meddelanden i följd"""
        self.client = MqttClient(self.cfg)
        self.client.connect()
        
        # Wait for connection
        self.assertTrue(self.client._connected.wait(timeout=5),
                       "Timeout när anslutning till MQTT-broker")

        message_count = 5
        received_count = threading.Semaphore(0)
        
        def on_message(msg):
            payload = msg.payload.decode('utf-8')
            self.received_messages.append(payload)
            received_count.release()
        
        # Subscribe to test topic
        self.client.subscribe(self.test_topic + "/multi", qos=1, 
                            on_message=on_message)
        time.sleep(1)  # Allow subscription to complete
        
        # Publish multiple messages
        for i in range(message_count):
            message = f"Meddelande {i+1}"
            self.client.client.publish(self.test_topic + "/multi", 
                                     message, qos=1)
            time.sleep(0.1)  # Small delay between messages
        
        # Wait for all messages to be received
        for i in range(message_count):
            acquired = received_count.acquire(timeout=10)
            self.assertTrue(acquired, 
                          f"Timeout väntar på meddelande {i+1}/{message_count}")
        
        # Verify all messages were received
        self.assertEqual(len(self.received_messages), message_count,
                        f"Förväntade {message_count} meddelanden, fick {len(self.received_messages)}")
        
        print(f"✓ Skickade {message_count} meddelanden")
        print(f"✓ Mottog {len(self.received_messages)} meddelanden")
        print("✓ Flera meddelanden i följd fungerar")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("MQTT Client Test Suite")
    print("Testar att skicka och ta emot meddelanden via MQTT")
    print("="*70 + "\n")
    
    unittest.main(verbosity=2)
