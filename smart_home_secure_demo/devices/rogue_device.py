from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import uuid

sys.path.append(str(Path(__file__).resolve().parents[1]))

from shared.crypto_utils import (generate_ed25519_private_key, generate_x25519_private_key, project_root,
                                 public_key_to_b64, sign_json, x25519_public_to_b64, )

'''
Rogue device 
    - zur Demo: was passiert wenn ein Angreifer versucht in den Hub zu kommen? 
    - Szenario 1 [forged]: Gerät stellt sich Zertifikat selber aus mit gefälschter CA 
    - Szenraio 2 [tampered]: Gerät nimmt echtes Zertifikat und verändert den Inhalt 
    - Szenario 3 [stolen]: Gerät kopiert ein echtes öffentliches Zertifikat 
    
'''


def _write_request(root: Path, request_filename: str, payload: dict, signature: str) -> Path:
    request = {"payload": payload, "signature": signature}
    path = root / "logs" / request_filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(request, indent=2), encoding="utf-8")
    return path


def _base_request_payload(certificate: dict, device_id: str, ephemeral_pub_b64: str) -> dict:
    return {
        "certificate": certificate,
        "deviceId": device_id,
        "requestId": str(uuid.uuid4()),
        "requestedScope": "telemetry:temperature",
        "protocolVersion": "1.0",
        "ephemeralPublicKey": ephemeral_pub_b64,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def scenario_forged(root: Path) -> Path:
    """Selbst ausgestelltes Zertifikat mit gefälschter CA"""
    fake_ca_key = generate_ed25519_private_key()
    device_key = generate_ed25519_private_key()
    ephemeral_key = generate_x25519_private_key()

    cert_payload = {
        "certificateId": str(uuid.uuid4()),
        "deviceId": "rogue_device_01",
        "deviceType": "temperature_sensor",
        "manufacturer": "EvilCorp",
        "publicKey": public_key_to_b64(device_key.public_key()),
        "issuedBy": "Fake CA",
        "issuedAt": datetime.now(timezone.utc).isoformat(),
    }
    certificate = {"payload": cert_payload, "signature": sign_json(fake_ca_key, cert_payload)}

    payload = _base_request_payload(certificate, "rogue_device_01",
                                    x25519_public_to_b64(ephemeral_key.public_key()))
    signature = sign_json(device_key, payload)  # PoP korrekt, aber Zertifikat ist gefälscht
    return _write_request(root, "onboarding_request_rogue_device_01.json", payload, signature)


def scenario_tampered(root: Path) -> Path:
    """Echtes Zertifikat genommen und nachträglich verändert"""
    real_cert_path = root / "devices" / "device_credentials" / "temp_sensor_01" / "device_certificate.json"
    if not real_cert_path.exists():
        raise FileNotFoundError("Für dieses Szenario muss temp_sensor_01 existieren")
    certificate = json.loads(real_cert_path.read_text(encoding="utf-8"))

    # Inhalt manipulieren
    certificate["payload"]["deviceId"] = "rogue_device_01"
    certificate["payload"]["manufacturer"] = "EvilCorp"

    device_key = generate_ed25519_private_key()
    ephemeral_key = generate_x25519_private_key()
    payload = _base_request_payload(certificate, "rogue_device_01",
                                    x25519_public_to_b64(ephemeral_key.public_key()))
    signature = sign_json(device_key, payload)
    return _write_request(root, "onboarding_request_rogue_device_01.json", payload, signature)


def scenario_stolen(root: Path) -> Path:
    """Echtes öffentliches Zertifikat kopiert"""
    real_cert_path = root / "devices" / "device_credentials" / "temp_sensor_01" / "device_certificate.json"
    if not real_cert_path.exists():
        raise FileNotFoundError("Für dieses Szenario muss temp_sensor_01 existieren")
    certificate = json.loads(real_cert_path.read_text(encoding="utf-8"))

    # Angreifer gibt sich als temp_sensor_01 aus und Zertifikat ist echt
    wrong_key = generate_ed25519_private_key() # besitzt nicht den echten device key
    ephemeral_key = generate_x25519_private_key()
    payload = _base_request_payload(certificate, "temp_sensor_01",
                                    x25519_public_to_b64(ephemeral_key.public_key()))
    signature = sign_json(wrong_key, payload)
    return _write_request(root, "onboarding_request_rogue_stolen.json", payload, signature)


SCENARIOS = {
    "forged": scenario_forged,
    "tampered": scenario_tampered,
    "stolen": scenario_stolen,
}


def main() -> None:
    scenario = sys.argv[1] if len(sys.argv) > 1 else "forged"
    if scenario not in SCENARIOS:
        print(f"Unbekanntes Szenario '{scenario}'. Erlaubt: {sorted(SCENARIOS)}")
        sys.exit(1)

    root = project_root()
    path = SCENARIOS[scenario](root)

    print(f"Rogue Device: Szenario '{scenario}' -> Angreifer Onboarding-Anfrage erzeugt")
    print(f"Anfrage gespeichert: {path}")
    print("'python hub/commissioner.py' ausführen, Hub sollte ablehnen")


if __name__ == "__main__":
    main()
