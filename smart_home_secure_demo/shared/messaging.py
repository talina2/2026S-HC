from pathlib import Path
import json

from shared.crypto_utils import (aes_gcm_encrypt, aes_gcm_decrypt, b64_encode, b64_decode,
                                 canonical_json, project_root, )


def _aad(topic: str, device_id: str) -> bytes:
    return f"{topic}|{device_id}".encode("utf-8")


def build_encrypted_message(session: dict, topic: str, payload: dict) -> dict:
    """Verschlüsselt payload und verpackt es als versandfertige MQTT-Nachricht"""
    session_key = b64_decode(session["sessionKey"])
    nonce, ciphertext = aes_gcm_encrypt(
        session_key, canonical_json(payload), _aad(topic, payload["deviceId"])
    )
    return {
        "topic": topic,
        "deviceId": payload["deviceId"],
        "sessionId": session["sessionId"],
        "encryptedPayload": {
            "algorithm": "AES_GCM",
            "nonce": b64_encode(nonce),
            "ciphertext": b64_encode(ciphertext),
        },
    }


def decrypt_message(session_key: bytes, broker_message: dict) -> dict:
    """Entschluesselt + authentifiziert eine MQTT-Nachricht; gibt Klartext zurück"""
    enc = broker_message["encryptedPayload"]
    plaintext = aes_gcm_decrypt(
        session_key,
        b64_decode(enc["nonce"]),
        b64_decode(enc["ciphertext"]),
        _aad(broker_message["topic"], broker_message["deviceId"]),
    )
    return json.loads(plaintext)


_device_session_cache: dict = {}
_hub_session_cache: dict = {}


def load_device_session(device_id: str, root: Path | None = None) -> dict:
    """Lädt den Session-Key eines Geräts"""
    root = root or project_root()
    if device_id not in _device_session_cache:
        path = root / "devices" / "device_credentials" / device_id / "session_key.json"
        if not path.exists():
            raise FileNotFoundError(
                f"Kein Session Key fuer '{device_id}'. Bitte zuerst das Onboarding abschliessen."
            )
        _device_session_cache[device_id] = json.loads(path.read_text(encoding="utf-8"))
    return _device_session_cache[device_id]


def load_hub_session(device_id: str, root: Path | None = None, required: bool = True):
    """Lädt den Hub-Session-Key für ein Gerät"""
    root = root or project_root()
    if device_id not in _hub_session_cache:
        path = root / "hub" / "session_keys" / f"{device_id}.json"
        if not path.exists():
            if required:
                raise FileNotFoundError(f"Kein Hub-Session-Key fuer '{device_id}'. Erst onboarden!")
            return None
        _hub_session_cache[device_id] = json.loads(path.read_text(encoding="utf-8"))
    return _hub_session_cache[device_id]
