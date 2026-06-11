from datetime import datetime, timezone
from pathlib import Path
import json
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from cryptography.exceptions import InvalidTag

from shared.crypto_utils import b64_decode, project_root
from shared.messaging import decrypt_message, load_hub_session
from shared.mqtt_helpers import make_client, run_subscriber
from shared.topics import MQTT_HOST, MQTT_PORT, TOPIC_TELEMETRY_WILDCARD

'''
- Empfänger ist Zuhörer, entschlüsselt und empfägnt über MQTT
- nutzt Session Key wie Gerät zum verschlüsseln, aber von Hub Seite
'''


def on_connect(client, userdata, flags, reason_code, properties):
    """empfängt alle Daten"""
    print(f"Hub verbunden mit Broker {MQTT_HOST}:{MQTT_PORT} (rc={reason_code})")
    client.subscribe(TOPIC_TELEMETRY_WILDCARD)
    print(f"Abonniert: {TOPIC_TELEMETRY_WILDCARD}\nWarte auf Daten...\n")


def on_message(client, userdata, msg):
    """bei eingehender Sensornachricht: lesen, anhand der DeviceID passenden SessionKey holen"""
    root = project_root()
    try:
        broker_message = json.loads(msg.payload)
        device_id = broker_message["deviceId"]
        session = load_hub_session(device_id)
        telemetry = decrypt_message(b64_decode(session["sessionKey"]), broker_message)  # entschlüsselt und prüft

        metric = telemetry.get("metric", "value")
        hub_view = {
            "receivedAt": datetime.now(timezone.utc).isoformat(),
            "topic": broker_message["topic"],
            "sessionId": broker_message["sessionId"],
            "decryptedPayload": telemetry,
        }
        (root / "logs" / f"hub_view_{metric}.json").write_text(
            json.dumps(hub_view, indent=2), encoding="utf-8")
        room = telemetry.get("room", "unknown")
        (root / "logs" / f"hub_view_{metric}_{room}.json").write_text(
            json.dumps(hub_view, indent=2), encoding="utf-8")

        print(f"[{device_id}] entschlüsselt: {metric}={telemetry['value']} "
              f"{telemetry.get('unit', '')} (Raum {telemetry.get('room', '?')}) - Integrität OK")
    except InvalidTag:
        print("FEHLER: InvalidTag - Nachricht manipuliert oder falscher Schlüssel!!! Verworfen")
    except Exception as exc:
        print(f"FEHLER beim Verarbeiten: {exc}")


def main() -> None:
    client = make_client("hub-receiver", on_connect=on_connect, on_message=on_message)
    run_subscriber(client)


if __name__ == "__main__":
    main()
