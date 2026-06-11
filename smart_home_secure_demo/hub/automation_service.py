from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import threading
import time

sys.path.append(str(Path(__file__).resolve().parents[1]))

from shared.mqtt_helpers import make_client, run_subscriber
from cryptography.exceptions import InvalidTag

from shared.crypto_utils import b64_decode, project_root
from shared.messaging import build_encrypted_message, decrypt_message, load_hub_session
from shared.topics import (
    MQTT_HOST, MQTT_PORT, TOPIC_TELEMETRY_WILDCARD,
    TOPIC_LIGHT_COMMAND, TOPIC_HEATING_COMMAND, TOPIC_SHUTTER_COMMAND, TOPIC_ALARM_COMMAND,
    TOPIC_VENTILATION_COMMAND,
)

# Aktoren, die Automation steuert
LIGHT_ACTUATOR_ID = "light_actuator_01"
HEATING_ACTUATOR_ID = "heating_actuator_01"
SHUTTER_ACTUATOR_ID = "shutter_actuator_01"
ALARM_ACTUATOR_ID = "alarm_actuator_01"
VENTILATION_ACTUATOR_ID = "ventilation_actuator_01"

# Heizung zwischen 20 und 22 Grad
TEMP_LOW = 20.0
TEMP_HIGH = 22.0

# Zeitfenster
SHUTTER_CLOSE_FROM_HOUR = 20   # 20:00 Rollladen zu
SHUTTER_OPEN_FROM_HOUR = 7     # 07:00 Rollladen auf
ALARM_NIGHT_FROM_HOUR = 22     # Nachtfenster für den Alarm 22-6 uhr
ALARM_NIGHT_TO_HOUR = 6

# Licht
LIGHT_DARK_FROM_HOUR = 12
LIGHT_DARK_TO_HOUR = 7

# Räume mit Spezialrolle
ENTRANCE_ROOM = "entrance"     # Tür -> nur Anwesenheit (door_event arrive/leave)
PERIMETER_ROOM = "perimeter"  # Außen -> nur Alarm

# Luftfeuchte für die Lüftung
HUMID_HIGH = 60.0
HUMID_LOW = 50.0

_last_command = {}  # was wurde zuletzt an Aktor gesendet
_lock = threading.Lock()


def _is_shutter_night(hour: int) -> bool:
    return hour >= SHUTTER_CLOSE_FROM_HOUR or hour < SHUTTER_OPEN_FROM_HOUR


def _is_alarm_night(hour: int) -> bool:
    return hour >= ALARM_NIGHT_FROM_HOUR or hour < ALARM_NIGHT_TO_HOUR


def _is_dark(hour: int) -> bool:
    return hour >= LIGHT_DARK_FROM_HOUR or hour < LIGHT_DARK_TO_HOUR


_presence = {"state": "abwesend"}
_presence_lock = threading.Lock()


def _set_presence(state: str, source: str) -> None:
    root = project_root()
    with _presence_lock:
        _presence["state"] = state
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "logs" / "state_presence.json").write_text(
        json.dumps({"state": state, "source": source,
                    "updatedAt": datetime.now(timezone.utc).isoformat()}, indent=2),
        encoding="utf-8")


def send_command(client, root: Path, actuator_id: str, command_topic: str, state: str, reason: str) -> None:
    with _lock:
        # letzter Zustand der an Aktor gesendet wurde
        if _last_command.get(actuator_id) == state:
            return  # Zustand unverändert -> nichts senden
        _last_command[actuator_id] = state
    try:
        session = load_hub_session(actuator_id)
    except FileNotFoundError as exc:
        print(f"(übersprungen: {exc})")
        return
    command_payload = {
        "deviceId": actuator_id, "command": "set_state", "state": state,
        "reason": reason, "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    message = build_encrypted_message(session, command_topic, command_payload)
    client.publish(command_topic, json.dumps(message))
    print(f"-> Befehl (verschlüsselt) an {actuator_id}: {state.upper()}  ({reason})")


def shutter_time_loop(client, root: Path) -> None:
    """Steuert den Rollladen rein nach Uhrzeit"""
    while True:
        hour = datetime.now().hour
        if _is_shutter_night(hour):
            send_command(client, root, SHUTTER_ACTUATOR_ID, TOPIC_SHUTTER_COMMAND,
                         "closed", f"Uhrzeit {hour}:00 - Nacht/Abend")
        else:
            send_command(client, root, SHUTTER_ACTUATOR_ID, TOPIC_SHUTTER_COMMAND,
                         "open", f"Uhrzeit {hour}:00 - Tag")
        time.sleep(30)


def make_on_message(root: Path):
    def on_message(client, userdata, msg):
        try:
            bm = json.loads(msg.payload)
            device_id = bm["deviceId"]
            session = load_hub_session(device_id)
            telemetry = decrypt_message(b64_decode(session["sessionKey"]), bm)
        except InvalidTag:
            print("FEHLER: InvalidTag - Daten verworfen")
            return
        except Exception as exc:
            print(f"FEHLER: {exc}")
            return

        metric = telemetry.get("metric")
        value = telemetry.get("value")
        print(f"[Automation] {device_id}: {metric}={value}")

        if metric == "temperature":
            if value < TEMP_LOW:
                send_command(client, root, HEATING_ACTUATOR_ID, TOPIC_HEATING_COMMAND,
                             "on", f"Temperatur unter {TEMP_LOW} °C")
            elif value > TEMP_HIGH:
                send_command(client, root, HEATING_ACTUATOR_ID, TOPIC_HEATING_COMMAND,
                             "off", f"Temperatur über {TEMP_HIGH} °C")
        elif metric == "motion":
            hour = datetime.now().hour
            room = telemetry.get("room")
            if room == ENTRANCE_ROOM:
                # Tür -> nur Anwesenheit
                if value is True:
                    direction = telemetry.get("direction")
                    if direction == "in":
                        _set_presence("anwesend", "Ankunft durch die Tür")
                    elif direction == "out":
                        _set_presence("abwesend", "Verlassen durch die Tür")
            elif room == PERIMETER_ROOM:
                # AUßEN/PERIMETER -> Alarm: abwesend ODER nachts
                if value is True:
                    with _presence_lock:
                        absent = _presence["state"] == "abwesend"
                    if absent or _is_alarm_night(hour):
                        grund = "niemand zuhause" if absent else f"nachts ({hour}:00 Uhr)"
                        send_command(client, root, ALARM_ACTUATOR_ID, TOPIC_ALARM_COMMAND,
                                     "on", f"Bewegung außen - {grund}!")
                else:
                    send_command(client, root, ALARM_ACTUATOR_ID, TOPIC_ALARM_COMMAND,
                                 "off", "Außenbereich ruhig")
            else:
                # INNEN -> nur Licht
                if value is True:
                    if _is_dark(hour):
                        send_command(client, root, LIGHT_ACTUATOR_ID, TOPIC_LIGHT_COMMAND,
                                     "on", "Bewegung bei Dunkelheit")
                else:
                    send_command(client, root, LIGHT_ACTUATOR_ID, TOPIC_LIGHT_COMMAND,
                                 "off", "keine Bewegung")
        elif metric == "humidity":
            if value > HUMID_HIGH:
                send_command(client, root, VENTILATION_ACTUATOR_ID, TOPIC_VENTILATION_COMMAND,
                             "on", f"Luftfeuchte über {HUMID_HIGH}%")
            elif value < HUMID_LOW:
                send_command(client, root, VENTILATION_ACTUATOR_ID, TOPIC_VENTILATION_COMMAND,
                             "off", f"Luftfeuchte unter {HUMID_LOW}%")

    return on_message


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Automation Service verbunden mit Broker {MQTT_HOST}:{MQTT_PORT}")
    client.subscribe(TOPIC_TELEMETRY_WILDCARD)
    print(f"Abonniert: {TOPIC_TELEMETRY_WILDCARD}")
    print("Regeln aktiv (inkl. zeitgesteuertem Rollladen + Nacht-Alarm).")
    print("Warte auf Sensordaten... (Strg+C zum Beenden)\n")


def main() -> None:
    root = project_root()
    client = make_client("automation-service", on_connect=on_connect, on_message=make_on_message(root))
    # Rollladen-Zeitsteuerung als Hintergrund-Thread
    threading.Thread(target=shutter_time_loop, args=(client, root), daemon=True).start()
    run_subscriber(client)


if __name__ == "__main__":
    main()