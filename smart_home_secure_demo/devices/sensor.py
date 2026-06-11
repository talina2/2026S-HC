from datetime import datetime, timezone
from pathlib import Path
import json
import random
import sys
import time

sys.path.append(str(Path(__file__).resolve().parents[1]))

from shared.crypto_utils import project_root
from shared.messaging import build_encrypted_message, load_device_session
from shared.mqtt_helpers import background_client
from shared.onboarding import create_onboarding_request, finalize_session, device_paths


# Typ-spezifische Mess-Funktionen
_temp_state = {"value": 21.0}


def _actuator_state(actuator_type: str) -> str:
    try:
        data = json.loads((project_root() / "logs" / f"state_{actuator_type}.json").read_text(encoding="utf-8"))
        return data.get("state", "off")
    except Exception:
        return "off"


def build_temperature(device_id: str, room: str):
    """Realistischer Temperaturverlauf: Regelkreis mit der Heizung"""
    heating_on = _actuator_state("heating_actuator") == "on"
    target = 24.0 if heating_on else 18.0
    _temp_state["value"] += (target - _temp_state["value"]) * 0.15 + random.uniform(-0.15, 0.15)
    _temp_state["value"] = round(min(25.0, max(17.0, _temp_state["value"])), 1)
    payload = {
        "deviceId": device_id, "deviceType": "temperature_sensor", "room": "livingroom",
        "metric": "temperature", "value": _temp_state["value"], "unit": "celsius",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return payload, _temp_state["value"]


_motion_state = {"active": False, "remaining": 0}


def _is_present() -> bool:
    try:
        data = json.loads((project_root() / "logs" / "state_presence.json").read_text(encoding="utf-8"))
        return data.get("state") == "anwesend"
    except Exception:
        return False


def build_motion(device_id: str, room: str):
    """Bewegung in Schüben; innen nur bei Anwesenheit"""
    start_prob = None
    if room not in ("entrance", "perimeter") and not _is_present():
        _motion_state["active"] = False
        _motion_state["remaining"] = 0
        motion_detected = False
    else:
        start_prob, burst_min, burst_max = (0.05, 1, 2) if room == "entrance" else (0.15, 2, 5)
    if start_prob is not None and _motion_state["active"]:
        _motion_state["remaining"] -= 1
        if _motion_state["remaining"] <= 0:
            _motion_state["active"] = False
        motion_detected = True
    elif start_prob is not None and random.random() < start_prob:
        _motion_state["active"] = True
        _motion_state["remaining"] = random.randint(burst_min, burst_max)
        motion_detected = True
    elif start_prob is not None:
        motion_detected = False
    payload = {
        "deviceId": device_id, "deviceType": "motion_sensor", "room": room,
        "metric": "motion", "value": motion_detected, "unit": "boolean",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return payload, motion_detected


# Registry: Sensortyp -> Onboarding-Scope, Mess-Funktion
SENSORS = {
    "temperature_sensor": {"scope": "telemetry:temperature", "build": build_temperature},
    "motion_sensor":      {"scope": "telemetry:motion",      "build": build_motion},
}


def _sensor_config(device_id: str) -> dict:
    """Liest den Sensortyp aus dem Zertifikat und liefert die passende Registry-Zeile."""
    cert = json.loads(device_paths(project_root(), device_id)["certificate"].read_text(encoding="utf-8"))
    device_type = cert["payload"]["deviceType"]
    if device_type not in SENSORS:
        raise ValueError(f"Unbekannter Sensortyp '{device_type}'. Bekannt: {sorted(SENSORS)}")
    return SENSORS[device_type]


def send(device_id: str, room: str, count: int, interval: float) -> None:
    cfg = _sensor_config(device_id)
    session = load_device_session(device_id)
    print(f"[{device_id}] sende verschlüsselte Informationen (Raum {room}).\n")
    sent = 0
    with background_client(f"sensor-{device_id}") as client:
        try:
            while True:
                payload, value = cfg["build"](device_id, room)
                topic = f"home/{payload['room']}/{payload['metric']}/telemetry"
                client.publish(topic, json.dumps(build_encrypted_message(session, topic, payload)))
                sent += 1
                print(f"  -> #{sent} gesendet (verschlüsselt). Wert lokal: {value}")
                if count and sent >= count:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nBeendet.")


def main() -> None:
    if len(sys.argv) < 3:
        print("Verwendung: python devices/sensor.py <onboard|finalize|send> <device_id> [room] [anzahl] [intervall]")
        sys.exit(1)
    mode, device_id = sys.argv[1], sys.argv[2]
    if mode == "onboard":
        create_onboarding_request(device_id, _sensor_config(device_id)["scope"])
    elif mode == "finalize":
        finalize_session(device_id)
    elif mode == "send":
        room = sys.argv[3] if len(sys.argv) > 3 else "livingroom"
        count = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        interval = float(sys.argv[5]) if len(sys.argv) > 5 else 3.0
        send(device_id, room, count, interval)
    else:
        print("Unbekannter Modus. Verwende onboard | finalize | send.")


if __name__ == "__main__":
    main()