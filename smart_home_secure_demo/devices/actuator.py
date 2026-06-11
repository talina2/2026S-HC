from datetime import datetime, timezone
from pathlib import Path
import json
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from shared.mqtt_helpers import make_client, run_subscriber
from cryptography.exceptions import InvalidTag

from shared.crypto_utils import b64_decode, project_root
from shared.messaging import decrypt_message, load_device_session
from shared.onboarding import create_onboarding_request, finalize_session, device_paths
from shared.topics import COMMAND_TOPIC_BY_TYPE

REQUESTED_SCOPE = "command:actuator"

'''
wird vom Broker aufgerufen wenn etwas kommt (Zuhörer)
'''


def listen(device_id: str) -> None:
    """liest aus dem eigenen Zertifikat Gerätetyp, sucht in topics.py nach passendem Kanal"""
    root = project_root()
    p = device_paths(root, device_id)
    certificate = json.loads(p["certificate"].read_text(encoding="utf-8"))
    device_type = certificate["payload"]["deviceType"]
    command_topic = COMMAND_TOPIC_BY_TYPE.get(device_type)
    if command_topic is None:
        raise ValueError(f"Kein Befehls-Topic für Gerätetyp '{device_type}'.")

    session = load_device_session(device_id)
    session_key = b64_decode(session["sessionKey"])
    state = {"value": "off"}  # Startzustand

    def write_state(reason):
        (root / "logs").mkdir(parents=True, exist_ok=True)
        (root / "logs" / f"state_{device_type}.json").write_text(
            json.dumps({"deviceId": device_id, "deviceType": device_type,
                        "state": state["value"], "reason": reason,
                        "updatedAt": datetime.now(timezone.utc).isoformat()}, indent=2),
            encoding="utf-8")

    write_state("Startzustand")

    def on_connect(client, userdata, flags, reason_code, properties):
        """Wird automatisch von MQTT aufgerufen"""
        print(f"[{device_id}] verbunden, abonniere {command_topic}")
        print(f"Startzustand: {state['value'].upper()}\n")
        client.subscribe(command_topic)

    def on_message(client, userdata, msg):
        try:
            cmd_msg = json.loads(msg.payload)
            if cmd_msg.get("deviceId") != device_id:
                return  # Befehl ist für einen anderen Aktor
            command = decrypt_message(session_key, cmd_msg)
            new_state = command.get("state", "off")
            if new_state != state["value"]:
                state["value"] = new_state
                print(f"[{device_id}] Zustand -> {new_state.upper()}  "
                      f"(Grund: {command.get('reason', '-')})")
                write_state(command.get("reason"))
        except InvalidTag:
            print(f"[{device_id}] FEHLER: InvalidTag - Befehl verworfen (manipuliert/falscher Key)")
        except Exception as exc:
            print(f"[{device_id}] FEHLER: {exc}")

    client = make_client(f"actuator-{device_id}", on_connect=on_connect, on_message=on_message)
    run_subscriber(client)


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(1)
    mode, device_id = sys.argv[1], sys.argv[2]
    if mode == "onboard":
        create_onboarding_request(device_id, REQUESTED_SCOPE)
    elif mode == "finalize":
        finalize_session(device_id)
    elif mode == "listen":
        listen(device_id)
    else:
        print("Unbekannter Modus. Verwende onboard | finalize | listen.")


if __name__ == "__main__":
    main()
