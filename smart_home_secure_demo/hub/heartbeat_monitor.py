from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import threading
import time

sys.path.append(str(Path(__file__).resolve().parents[1]))

from cryptography.exceptions import InvalidTag

from shared.crypto_utils import b64_decode, project_root
from shared.messaging import decrypt_message, load_hub_session
from shared.mqtt_helpers import make_client, run_subscriber
from shared.topics import MQTT_HOST, MQTT_PORT, TOPIC_HEARTBEAT

OFFLINE_AFTER_SECONDS = 15
WRITE_INTERVAL_SECONDS = 2

_last_seen = {}
_lock = threading.Lock()

'''
Heartbeat Monitor erkennt welche Geräte online sind (Zuhörer)
'''


def _onboarded_devices(root: Path):
    base = root / "hub" / "session_keys"
    return [f.stem for f in sorted(base.glob("*.json"))] if base.exists() else []


def _writer_loop(root: Path):
    """schreibt logs: logs/hearbeats.json"""
    while True:
        now = datetime.now(timezone.utc)
        devices = {}
        with _lock:
            seen = dict(_last_seen)
        for device_id in _onboarded_devices(root):
            last = seen.get(device_id)
            status = "offline"
            age = None
            if last:
                try:
                    age = (now - datetime.fromisoformat(last)).total_seconds()
                    status = "online" if age <= OFFLINE_AFTER_SECONDS else "offline"
                except Exception:
                    pass
            devices[device_id] = {"status": status, "lastSeen": last,
                                  "ageSeconds": round(age, 1) if age is not None else None}
        (root / "logs").mkdir(parents=True, exist_ok=True)
        (root / "logs" / "heartbeats.json").write_text(
            json.dumps({"generatedAt": now.isoformat(), "devices": devices}, indent=2),
            encoding="utf-8")
        time.sleep(WRITE_INTERVAL_SECONDS)


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Heartbeat-Monitor verbunden mit Broker {MQTT_HOST}:{MQTT_PORT}")
    client.subscribe(TOPIC_HEARTBEAT)
    print(f"Abonniert: {TOPIC_HEARTBEAT}  (Strg+C zum Beenden)\n")


def on_message(client, userdata, msg):
    try:
        hb = json.loads(msg.payload)
        device_id = hb["deviceId"]
        session = load_hub_session(device_id, required=False)
        if session is None:
            return
        # entschlüsselung authentifiziert gleichzeitig
        decrypt_message(b64_decode(session["sessionKey"]), hb)
        with _lock:
            _last_seen[device_id] = datetime.now(timezone.utc).isoformat()
        print(f"Heartbeat OK von {device_id}")
    except InvalidTag:
        print("Heartbeat VERWORFEN: InvalidTag (gefälscht oder falscher Key!!!)")
    except Exception as exc:
        print(f"Heartbeat-Fehler: {exc}")


def main() -> None:
    root = project_root()
    threading.Thread(target=_writer_loop, args=(root,), daemon=True).start()
    client = make_client("heartbeat-monitor", on_connect=on_connect, on_message=on_message)
    run_subscriber(client)


if __name__ == "__main__":
    main()