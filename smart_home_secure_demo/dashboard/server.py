from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json

DASHBOARD_DIR = Path(__file__).resolve().parent
ROOT = DASHBOARD_DIR.parent          # smart_home_secure_demo/
LOGS = ROOT / "logs"
SESSION_KEYS = ROOT / "hub" / "session_keys"
PORT = 8080
ONLINE_WINDOW_SECONDS = 30


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _age_seconds(iso_ts: str):
    try:
        ts = datetime.fromisoformat(iso_ts)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except Exception:
        return None


def build_state() -> dict:
    temp = _read_json(LOGS / "hub_view_temperature.json")
    humidity = _read_json(LOGS / "hub_view_humidity.json")
    motion = _read_json(LOGS / "hub_view_motion_livingroom.json")
    entrance = _read_json(LOGS / "hub_view_motion_entrance.json")
    perimeter = _read_json(LOGS / "hub_view_motion_perimeter.json")
    light = _read_json(LOGS / "state_light_actuator.json")
    heating = _read_json(LOGS / "state_heating_actuator.json")
    shutter = _read_json(LOGS / "state_shutter_actuator.json")
    alarm = _read_json(LOGS / "state_alarm_actuator.json")
    ventilation = _read_json(LOGS / "state_ventilation_actuator.json")
    presence = _read_json(LOGS / "state_presence.json")

    def telemetry(view):
        if not view:
            return None
        p = view.get("decryptedPayload", {})
        return {"value": p.get("value"), "unit": p.get("unit"),
                "room": p.get("room"), "receivedAt": view.get("receivedAt")}

    # Aufgenommene Geräte
    heartbeats = (_read_json(LOGS / "heartbeats.json") or {}).get("devices", {})
    devices = []
    if SESSION_KEYS.exists():
        for f in sorted(SESSION_KEYS.glob("*.json")):
            rec = _read_json(f) or {}
            did = rec.get("deviceId", f.stem)
            hb = heartbeats.get(did, {})
            devices.append({
                "deviceId": did,
                "fingerprint": rec.get("fingerprint"),
                "onboardedAt": rec.get("createdAt"),
                "status": hb.get("status", "unknown"),
                "lastSeen": hb.get("lastSeen"),
            })

    # Security Events (letzte 20)
    events = []
    sec = LOGS / "security_events.log"
    if sec.exists():
        for line in sec.read_text(encoding="utf-8").splitlines()[-20:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split(" ", 1)
            events.append({"time": parts[0],
                           "message": parts[1] if len(parts) > 1 else ""})
    events.reverse()  # neueste zuerst

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "temperature": telemetry(temp),
        "humidity": telemetry(humidity),
        "motion": telemetry(motion),
        "entrance": telemetry(entrance),
        "perimeter": telemetry(perimeter),
        "light": ({"state": light.get("state"), "reason": light.get("reason"),
                   "updatedAt": light.get("updatedAt")} if light else None),
        "heating": ({"state": heating.get("state"), "reason": heating.get("reason"),
                     "updatedAt": heating.get("updatedAt")} if heating else None),
        "shutter": ({"state": shutter.get("state"), "reason": shutter.get("reason"),
                     "updatedAt": shutter.get("updatedAt")} if shutter else None),
        "alarm": ({"state": alarm.get("state"), "reason": alarm.get("reason"),
                   "updatedAt": alarm.get("updatedAt")} if alarm else None),
        "ventilation": ({"state": ventilation.get("state"), "reason": ventilation.get("reason"),
                         "updatedAt": ventilation.get("updatedAt")} if ventilation else None),
        "presence": ({"state": presence.get("state"),
                      "source": presence.get("source")} if presence else None),
        "devices": devices,
        "securityEvents": events,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # ruhig bleiben

    def do_GET(self):
        if self.path in ("/api/state", "/api/state/"):
            body = json.dumps(build_state()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path in ("/api/broker", "/api/broker/"):
            feed = _read_json(LOGS / "broker_feed.json") or []
            body = json.dumps({"generatedAt": datetime.now(timezone.utc).isoformat(),
                               "feed": feed}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # Statische Dateien aus dem dashboard-Ordner
        rel = "index.html" if self.path in ("/", "") else self.path.lstrip("/")
        target = (DASHBOARD_DIR / rel).resolve()
        if DASHBOARD_DIR not in target.parents and target != DASHBOARD_DIR or not target.is_file():
            self.send_error(404)
            return
        ctype = ("text/html" if target.suffix == ".html" else
                 "text/css" if target.suffix == ".css" else
                 "application/javascript" if target.suffix == ".js" else
                 "application/octet-stream")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    print(f"Dashboard laeuft auf http://localhost:{PORT}  (Strg+C zum Beenden)")
    ThreadingHTTPServer(("localhost", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()