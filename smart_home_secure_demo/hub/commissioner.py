from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import uuid
from typing import Any, Dict, Optional, Tuple
from shared.crypto_utils import (b64_encode, derive_session_key, generate_x25519_private_key, load_public_key,
                                 project_root, public_key_from_b64, session_key_fingerprint, verify_json_signature,
                                 x25519_public_from_b64, x25519_public_to_b64, )

sys.path.append(str(Path(__file__).resolve().parents[1]))

from shared.topics import ALLOWED_DEVICE_TYPES

'''
Commissioner liest jede Onboarding Request und prüft
    - Zertifikat echt? CA prüfen 
    - Id Abgleich
    - Proof-of-Possession: Signatur der Anfrage prüfen
'''


def verify_device_certificate(certificate: Dict[str, Any]) -> bool:
    """Prüft CA-Signatur und Gültigkeit eines Zertifikats"""
    root = project_root()
    ca_public_key = load_public_key(root / "hub" / "trusted_ca_public_key.pem")

    payload = certificate.get("payload")
    signature = certificate.get("signature")

    if not isinstance(payload, dict):
        print("Rejected: certificate payload is missing")
        return False
    if not isinstance(signature, str):
        print("Rejected: certificate signature is missing")
        return False

    required_fields = {"certificateId", "deviceId", "deviceType", "manufacturer",
                       "publicKey", "issuedBy", "issuedAt", }
    missing_fields = required_fields.difference(payload.keys())
    if missing_fields:
        print(f"Rejected: missing certificate fields: {sorted(missing_fields)}")
        return False

    if payload["deviceType"] not in ALLOWED_DEVICE_TYPES:
        print(f"Rejected: unsupported device type: {payload['deviceType']}")
        return False

    if not verify_json_signature(ca_public_key, payload, signature):
        print("Rejected: CA signature is invalid")
        return False

    print("Accepted: Certificate is valid"
          f"(deviceId={payload['deviceId']}, type={payload['deviceType']})")
    return True


def _log_security_event(message: str) -> None:
    root = project_root()
    log_path = root / "logs" / "security_events.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")


def _write_rejected_response(response_path: Path, device_id: str, reason: str) -> None:
    response = {"status": "rejected", "deviceId": device_id, "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(), }
    response_path.parent.mkdir(parents=True, exist_ok=True)
    response_path.write_text(json.dumps(response, indent=2), encoding="utf-8")
    _log_security_event(f"ONBOARDING_REJECTED device={device_id} reason={reason}")


def process_onboarding_request(request_path: Path) -> Optional[Tuple[str, str]]:
    """Verarbeitet eine einzelne Onboarding-Anfrage -> Gibt (device_id, fingerprint) zurück"""
    root = project_root()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    payload = request.get("payload", {})
    request_signature = request.get("signature", "")
    claimed_device_id = payload.get("deviceId", "unknown")

    print(f"\nAnfrage: {request_path.name}")

    # CA-Signatur des Zertifikats prüfen
    certificate = payload.get("certificate")
    response_path = root / "logs" / f"onboarding_response_{claimed_device_id}.json"
    if not isinstance(certificate, dict) or not verify_device_certificate(certificate):
        print(" -> Onboarding abgelehnt: Zertifikatsprüfung fehlgeschlagen!")
        _write_rejected_response(response_path, claimed_device_id, "invalid_certificate")
        return None

    cert_payload = certificate["payload"]
    device_id = cert_payload["deviceId"]

    # deviceID in Zertifikat und Anfrage müssen gleich sein
    if device_id != claimed_device_id:
        print("-> Onboarding abgelehnt: deviceId in Zertifikat und Anfrage stimmen nicht überein!")
        _write_rejected_response(response_path, device_id, "device_id_mismatch")
        return None

    # Proof-of-Possession prüfen
    device_public_key = public_key_from_b64(cert_payload["publicKey"])
    if not verify_json_signature(device_public_key, payload, request_signature):
        print("-> Onboarding abgelehnt: Proof-of-Possession ungültig!")
        _write_rejected_response(response_path, device_id, "invalid_proof_of_possession")
        return None
    print("Proof-of-Possession bestätigt! Gerät besitzt den passenden privaten Schlüssel!")

    # X25519 Schlüsselberechnung -> Hub erzeut ephemeral key mit public key von Gerät
    device_ephemeral_public = x25519_public_from_b64(payload["ephemeralPublicKey"])
    hub_ephemeral_private = generate_x25519_private_key()
    shared_secret = hub_ephemeral_private.exchange(device_ephemeral_public)
    session_key = derive_session_key(shared_secret)
    fingerprint = session_key_fingerprint(session_key)
    session_id = str(uuid.uuid4())

    # Hub-Session-Key speichern
    session_record = {
        "deviceId": device_id,
        "sessionId": session_id,
        "sessionKey": b64_encode(session_key),
        "fingerprint": fingerprint,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    session_key_path = root / "hub" / "session_keys" / f"{device_id}.json"
    session_key_path.parent.mkdir(parents=True, exist_ok=True)
    session_key_path.write_text(json.dumps(session_record, indent=2), encoding="utf-8")

    # Onboarding-Antwort schreiben (inkl. Hub-Ephemeral-Public-Key)
    response = {
        "status": "accepted",
        "deviceId": device_id,
        "sessionId": session_id,
        "hubEphemeralPublicKey": x25519_public_to_b64(hub_ephemeral_private.public_key()),
        "grantedScope": payload.get("requestedScope"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    response_path.write_text(json.dumps(response, indent=2), encoding="utf-8")
    _log_security_event(f"ONBOARDING_ACCEPTED device={device_id} session={session_id} fp={fingerprint}")

    print(f"-> Akzeptiert. Session Key abgeleitet (sessionId={session_id}).")
    print(f"Fingerprint (Hub): {fingerprint}  | gespeichert: {session_key_path}")
    return device_id, fingerprint


def _archive_request(request_path: Path) -> None:
    """Verschiebt eine bearbeitete Anfrage nach logs/processed/ -> Anfragen werden nciht doppelt verarbeitet"""
    processed_dir = request_path.parent / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    request_path.replace(processed_dir / f"{stamp}_{request_path.name}")


def main() -> None:
    root = project_root()
    logs_dir = root / "logs"
    requests = sorted(logs_dir.glob("onboarding_request_*.json"))

    print("Commissioner: verarbeite offene Onboarding-Anfragen...")
    if not requests:
        print("Keine Onboarding-Anfragen gefunden. Bitte zuerst auf einem Geraet 'onboard' ausführen.")
        return

    accepted = 0
    for request_path in requests:
        if process_onboarding_request(request_path) is not None:
            accepted += 1
        _archive_request(request_path)  # bearbeitete Anfrage aufräumen

    print(f"\nFertig: {accepted} von {len(requests)} Anfragen akzeptiert.")


if __name__ == "__main__":
    main()
