from contextlib import contextmanager
import time
import paho.mqtt.client as mqtt
from shared.topics import MQTT_HOST, MQTT_PORT


def make_client(client_id, on_connect=None, on_message=None):
    """Erzeugt einen verbundenen MQTT-Client"""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    if on_connect is not None:
        client.on_connect = on_connect
    if on_message is not None:
        client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT)
    return client


def run_subscriber(client):
    """Zuhörer: verarbeitet eingehende Nachrichten"""
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
        client.disconnect()


@contextmanager
def background_client(client_id):
    """Sender"""
    client = make_client(client_id)
    client.loop_start()
    try:
        yield client
    finally:
        time.sleep(0.3)
        client.loop_stop()
        client.disconnect()