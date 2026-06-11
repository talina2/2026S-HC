from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import time

sys.path.append(str(Path(__file__).resolve().parents[1]))

from shared.messaging import build_encrypted_message, load_device_session
from shared.mqtt_helpers import background_client

DEVICE_ID = "motion_sensor_outdoor_01"
ROOM = "entrance"
TOPIC = f"home/{ROOM}/motion/telemetry"


def _publish(client, session, value: bool, direction):
    payload = {
        "deviceId": DEVICE_ID, "deviceType": "motion_sensor", "room": ROOM,
        "metric": "motion", "value": value, "unit": "boolean",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if direction:
        payload["direction"] = direction
    client.publish(TOPIC, json.dumps(build_encrypted_message(session, TOPIC, payload)))


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "arrive"
    if action not in ("arrive", "leave"):
        print("Verwendung: python devices/door_event.py <arrive|leave>")
        sys.exit(1)
    direction = "in" if action == "arrive" else "out"

    session = load_device_session(DEVICE_ID)
    with background_client(f"door-{action}") as client:
        _publish(client, session, True, direction)   # Durchgang beginnt
        print(f"Tür-Ereignis '{action}' gesendet (Richtung {direction}) -> "
              f"Belegung wird '{'anwesend' if direction == 'in' else 'abwesend'}'")
        time.sleep(1.5)
        _publish(client, session, False, None)  # Durchgang vorbei


if __name__ == "__main__":
    main()