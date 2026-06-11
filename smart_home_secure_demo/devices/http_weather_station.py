from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import random
import sys
from pathlib import Path

DEVICE_ID = "weather_station_01"
ROOM = "livingroom"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9001

# Startwert
_state = {"humidity": 52.0}
_ROOT = Path(__file__).resolve().parents[1]

'''
HTTP-Wetterstation
    - Messwerte über einfache HTTP Schnittstelle 
    - benötigt Gateway um in das sichere Smart Home hub reinzukommen 
'''


def _ventilation_on() -> bool:
    try:
        data = json.loads((_ROOT / "logs" / "state_ventilation_actuator.json").read_text(encoding="utf-8"))
        return data.get("state") == "on"
    except Exception:
        return False


def make_reading() -> dict:
    """Kreislauf: Lüftung an -> Luftfeuchte sinkt, Lüftung aus -> Leuftfeuchte steigt"""
    target = 40.0 if _ventilation_on() else 70.0
    _state["humidity"] += (target - _state["humidity"]) * 0.15 + random.uniform(-1.0, 1.0)
    _state["humidity"] = round(min(75.0, max(35.0, _state["humidity"])), 1)
    return {
        "deviceId": DEVICE_ID,
        "deviceType": "weather_station",
        "room": ROOM,
        "metric": "humidity",
        "value": _state["humidity"],
        "unit": "percent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.rstrip("/") == "/reading":
            body = json.dumps(make_reading()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            print(f"[{DEVICE_ID}] HTTP GET /reading -> {json.loads(body)['value']} % Luftfeuchte")
        else:
            self.send_error(404)


def main() -> None:
    print(f"HTTP-Wetterstation läuft auf http://localhost:{PORT}/reading")
    ThreadingHTTPServer(("localhost", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()