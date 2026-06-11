from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import time

sys.path.append(str(Path(__file__).resolve().parents[1]))

from shared.crypto_utils import project_root
from shared.messaging import build_encrypted_message, load_device_session
from shared.mqtt_helpers import background_client
from shared.topics import TOPIC_HEARTBEAT

'''
Heartbeat, damit Hub weiß welche Geräte am Leben sind (ausfallsicherheit) 
    - ist auch ein Sender, wie Sensor
    - Heartbeat wird verschlüsselt 
'''


def _onboarded_devices(root: Path):
    """alle Geräte die onboarded sind"""
    base = root / "devices" / "device_credentials"
    if not base.exists():
        return []
    return [d.name for d in sorted(base.iterdir()) if (d / "session_key.json").exists()]


def build_heartbeat(device_id: str, session: dict) -> dict:
    payload = {"deviceId": device_id, "deviceType": "heartbeat", "type": "heartbeat",
               "timestamp": datetime.now(timezone.utc).isoformat()}
    return build_encrypted_message(session, TOPIC_HEARTBEAT, payload)


def main() -> None:
    root = project_root()
    device_id = sys.argv[1] if len(sys.argv) > 1 else None
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0

    device_ids = [device_id] if device_id else _onboarded_devices(root)
    if not device_ids:
        print("Keine onboardeten Geräte gefunden -> Bitte zuerst setup_demo.sh / Onboarding.")
        return
    sessions = {d: load_device_session(d) for d in device_ids}

    client_id = "heartbeat-" + "_".join(device_ids)
    print(f"Heartbeat-Sender aktiv für: {', '.join(device_ids)}")
    print(f"Topic: {TOPIC_HEARTBEAT}, Intervall: {interval}s\n")

    with background_client(client_id) as client:
        try:
            while True:
                for d in device_ids:
                    client.publish(TOPIC_HEARTBEAT, json.dumps(build_heartbeat(d, sessions[d])))
                print(f"-> Heartbeat gesendet ({len(device_ids)} Geräte) "
                      f"{datetime.now().strftime('%H:%M:%S')}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nBeendet")


if __name__ == "__main__":
    main()