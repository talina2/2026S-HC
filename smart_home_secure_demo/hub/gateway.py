from pathlib import Path
import json
import sys
import time
from urllib.request import urlopen

sys.path.append(str(Path(__file__).resolve().parents[1]))

from shared.messaging import build_encrypted_message, load_device_session
from shared.mqtt_helpers import background_client
from shared.onboarding import create_onboarding_request, finalize_session

'''
Gateway -> wegen Heterogenität 
    - wegen http_weather_station: simpler http webserver, der kein MQTT und Verschlüsselung kennt 
    - gateway benötigt, um es in die sichere Infrastruktur einzubinden: 
      onboarded das Gerät stellvertretend, bestizt session key
    - quasi Adapter 
'''

DEFAULT_URL = "http://localhost:9001/reading"
REQUESTED_SCOPE = "telemetry:gateway"


def run(device_id: str, url: str, interval: float) -> None:
    session = load_device_session(device_id)
    print(f"[Gateway/{device_id}] Brücke HTTP -> MQTT aktiv; Quelle: {url}\n")

    with background_client(f"gateway-{device_id}") as client:
        try:
            while True:
                try:
                    with urlopen(url, timeout=3) as resp:
                        reading = json.loads(resp.read())
                except Exception as exc:
                    print(f"HTTP-Abruf fehlgeschlagen: {exc}")
                    time.sleep(interval)
                    continue

                topic = f"home/{reading.get('room', 'unknown')}/{reading.get('metric', 'value')}/telemetry"
                message = build_encrypted_message(session, topic, reading)
                client.publish(topic, json.dumps(message))
                print(f"HTTP {reading.get('value')}{reading.get('unit', '')} -> verschlüsselt nach MQTT '{topic}'")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nBeendet")


def main() -> None:
    if len(sys.argv) < 3:
        print("Verwendung: python hub/gateway.py <onboard|finalize|run> <device_id> [http_url] [intervall]")
        sys.exit(1)
    mode, device_id = sys.argv[1], sys.argv[2]
    prefix = f"Gateway/{device_id}"
    if mode == "onboard":
        create_onboarding_request(device_id, REQUESTED_SCOPE, log_prefix=prefix)
    elif mode == "finalize":
        finalize_session(device_id, log_prefix=prefix)
    elif mode == "run":
        url = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_URL
        interval = float(sys.argv[4]) if len(sys.argv) > 4 else 4.0
        run(device_id, url, interval)
    else:
        print("Unbekannter Modus. Verwende onboard | finalize | run.")


if __name__ == "__main__":
    main()
