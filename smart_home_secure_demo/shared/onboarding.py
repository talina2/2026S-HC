from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import uuid

from shared.crypto_utils import (b64_encode, derive_session_key, generate_x25519_private_key, load_private_key,
                                 load_x25519_private_key, project_root, save_x25519_private_key,
                                 session_key_fingerprint, sign_json, x25519_public_from_b64, x25519_public_to_b64, )

PROTOCOL_VERSION = "1.0"

sys.path.append(str(Path(__file__).resolve().parents[1]))


def device_paths(root: Path, device_id: str) -> dict:
    """Alle Datei-Pfade eines Geräts"""
    credential_dir = root / "devices" / "device_credentials" / device_id
    logs_dir = root / "logs"
    return {
        "certificate": credential_dir / "device_certificate.json",
        "device_private_key": credential_dir / "device_private_key.pem",
        "ephemeral_private_key": credential_dir / "onboarding_ephemeral_private_key.pem",
        "device_session_key": credential_dir / "session_key.json",
        "request": logs_dir / f"onboarding_request_{device_id}.json",
        "response": logs_dir / f"onboarding_response_{device_id}.json",
    }


def create_onboarding_request(device_id: str, requested_scope: str,
                              log_prefix: str | None = None) -> None:
    """Erzeugt eine signierte Onboarding-Anfrage und legt sie unter logs ab"""
    prefix = log_prefix or device_id
    root = project_root()
    paths = device_paths(root, device_id)

    if not paths["certificate"].exists():
        raise FileNotFoundError(
            f"Geräte-Zertifikat für '{device_id}' fehlt! "
            f"Bitte zuerst ein Zertifikat ausstellen (ca/issue_device_certificate.py)"
        )

    certificate = json.loads(paths["certificate"].read_text(encoding="utf-8"))
    device_private_key = load_private_key(paths["device_private_key"])

    # X25519 Schlüssel für DIESES Onboarding erzeugen und sichern
    ephemeral_private_key = generate_x25519_private_key()
    save_x25519_private_key(ephemeral_private_key, paths["ephemeral_private_key"])
    ephemeral_public_b64 = x25519_public_to_b64(ephemeral_private_key.public_key())

    # Anfrage zusammenbauen
    request_payload = {
        "certificate": certificate,
        "deviceId": device_id,
        "requestId": str(uuid.uuid4()),
        "requestedScope": requested_scope,
        "protocolVersion": PROTOCOL_VERSION,
        "ephemeralPublicKey": ephemeral_public_b64,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Proof-of-Possession: mit dem privaten Geräte Key signiert
    request_signature = sign_json(device_private_key, request_payload)
    onboarding_request = {"payload": request_payload, "signature": request_signature}

    paths["request"].parent.mkdir(parents=True, exist_ok=True)
    paths["request"].write_text(json.dumps(onboarding_request, indent=2), encoding="utf-8")

    print(f"[{prefix}] Onboarding-Anfrage erstellt und signiert")
    print(f"Request ID: {request_payload['requestId']}")
    print(f"Ephemeral Public Key: {ephemeral_public_b64}")
    print(f"Anfrage gespeichert: {paths['request']}")


def finalize_session(device_id: str, log_prefix: str | None = None) -> None:
    """Liest die Hub-Antwort und leitet den gemeinsamen Session Key ab"""
    prefix = log_prefix or device_id
    root = project_root()
    paths = device_paths(root, device_id)

    if not paths["response"].exists():
        raise FileNotFoundError(
            f"Onboarding-Antwort für '{device_id}' fehlt"
            "Bitte zuerst 'python hub/commissioner.py' ausführen."
        )

    response = json.loads(paths["response"].read_text(encoding="utf-8"))
    if response.get("status") != "accepted":
        print(f"[{prefix}] Onboarding wurde vom Hub nicht akzeptiert: {response.get('status')}")
        return

    # eigenen emphemeral Schlüssel laden und den public ephemeral vom hub
    ephemeral_private_key = load_x25519_private_key(paths["ephemeral_private_key"])
    hub_public_key = x25519_public_from_b64(response["hubEphemeralPublicKey"])

    # shared secret mit hub Schlüssel berechnen
    shared_secret = ephemeral_private_key.exchange(hub_public_key)
    session_key = derive_session_key(shared_secret)
    fingerprint = session_key_fingerprint(session_key)

    session_record = {
        "deviceId": device_id,
        "sessionId": response["sessionId"],
        "sessionKey": b64_encode(session_key),
        "fingerprint": fingerprint,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    paths["device_session_key"].write_text(json.dumps(session_record, indent=2), encoding="utf-8")

    print(f"[{prefix}] Session Key auf Geräteseite abgeleitet")
    print(f"Session ID: {response['sessionId']}")
    print(f"Session-Key gespeichert: {paths['device_session_key']}")
    print(f"Fingerprint Gerät: {fingerprint}")
