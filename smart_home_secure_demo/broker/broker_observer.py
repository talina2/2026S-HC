from datetime import datetime, timezone
from pathlib import Path
import json
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from shared.crypto_utils import project_root
from shared.mqtt_helpers import make_client, run_subscriber
from shared.topics import MQTT_HOST, MQTT_PORT, TOPIC_ALL

FEED_MAX = 15
_feed = []

'''Simuliert einen heimlichen zuhörer am broker '''

def _write_feed(root: Path) -> None:
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "logs" / "broker_feed.json").write_text(
        json.dumps(_feed, indent=2), encoding="utf-8")


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Observer verbunden mit Broker {MQTT_HOST}:{MQTT_PORT}")
    client.subscribe(TOPIC_ALL)
    print(f"Mithoeren auf: {TOPIC_ALL}\n(Strg+C zum Beenden)\n")


def on_message(client, userdata, msg):
    root = project_root()
    print(f"--- Nachricht auf Topic '{msg.topic}' ---")
    entry = {"observedAt": datetime.now(timezone.utc).isoformat(), "topic": msg.topic}
    try:
        data = json.loads(msg.payload)
        enc = data.get("encryptedPayload", {})
        entry.update({
            "deviceId": data.get("deviceId"),
            "algorithm": enc.get("algorithm"),
            "nonce": enc.get("nonce"),
            "ciphertext": enc.get("ciphertext"),
        })
        print(f"deviceId: {data.get('deviceId')}")
        print(f"algorithm: {enc.get('algorithm')}")
        print(f"nonce: {enc.get('nonce')}")
        print(f"ciphertext: {str(enc.get('ciphertext',''))[:48]}")
        print("-> Klartext-Messwert NICHT sichtbar (verschlüsselt)\n")
    except Exception:
        entry["raw"] = str(msg.payload)
        print(f"Rohdaten: {msg.payload!r}\n")

    _feed.insert(0, entry)
    del _feed[FEED_MAX:]
    _write_feed(root)


def main() -> None:
    client = make_client("broker-observer", on_connect=on_connect, on_message=on_message)
    run_subscriber(client)


if __name__ == "__main__":
    main()