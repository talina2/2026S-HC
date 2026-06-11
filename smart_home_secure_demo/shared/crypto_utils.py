import base64
import json
from pathlib import Path
from typing import Any, Dict
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (Ed25519PrivateKey, Ed25519PublicKey, )
import hashlib
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import (X25519PrivateKey, X25519PublicKey, )
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


# Base64 Text Umwandlung für JSON
def b64_encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def b64_decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def canonical_json(data: Dict[str, Any]) -> bytes:
    """eindeutige Byte Darstellung wegen Signaturprüfung"""
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


'''
ED25519 Schlüsselpaar für Identitätsnachweis & Signatur
    - Private Key: geheim, wer den private key hat kann signieren
    - Public Key: öffentlich, jeder kann prüfen ohne selbst signieren zu können 
'''


def generate_ed25519_private_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def save_private_key(private_key: Ed25519PrivateKey, path: Path) -> None:
    """schreibt privaten Schlüssel als pem Datei"""
    ensure_parent_dir(path)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path.write_bytes(pem)


def save_public_key(public_key: Ed25519PublicKey, path: Path) -> None:
    """schreibt öffentlichen Schlüssel als pem Datei"""
    ensure_parent_dir(path)
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    path.write_bytes(pem)


def load_private_key(path: Path) -> Ed25519PrivateKey:
    """liest privaten Schlüssel aus pem Datei"""
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("Expected Ed25519 private key")
    return key


def load_public_key(path: Path) -> Ed25519PublicKey:
    """liest öffentlichen Schlüssel aus pem Datei"""
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("Expected Ed25519 public key")
    return key


# public key Base64-Text, damit er im JSON abgelegt werden kann
def public_key_to_b64(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return b64_encode(raw)


def public_key_from_b64(value: str) -> Ed25519PublicKey:
    raw = b64_decode(value)
    return Ed25519PublicKey.from_public_bytes(raw)


def sign_json(private_key: Ed25519PrivateKey, payload: Dict[str, Any]) -> str:
    """aus privater Schlüssel + Nachricht -> Signatur"""
    signature = private_key.sign(canonical_json(payload))
    return b64_encode(signature)


def verify_json_signature(public_key: Ed25519PublicKey, payload: Dict[str, Any], signature_b64: str, ) -> bool:
    """prüft öffentlicher Schlüssel + Nachricht + Signatur"""
    try:
        public_key.verify(b64_decode(signature_b64), canonical_json(payload))
        # gibt nur True zurück, wenn Signatur exakt zu dem öffentlichen Schlüssel und dieser Nachricht gehört
        return True
    except InvalidSignature:
        return False


'''
X25519: für Onboarding & die sichere Kommunikation
    - Gerät und Hub brauchen denselben geheimen Schlüssel
    - kann nicht über Protokoll geschickt werden 
    - Berechnung des Schlüssels auf beiden Seiten  
    - generiertes Schlüsselpaar: für Schlüsselaustausch
'''


def generate_x25519_private_key() -> X25519PrivateKey:
    return X25519PrivateKey.generate()


def save_x25519_private_key(private_key: X25519PrivateKey, path: Path) -> None:
    """speichert privaten Schlüssel als pem Datei"""
    ensure_parent_dir(path)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path.write_bytes(pem)


def load_x25519_private_key(path: Path) -> X25519PrivateKey:
    """liest privaten Schlüssel aus pem Datei"""
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, X25519PrivateKey):
        raise TypeError("Expected X25519 private key")
    return key


# Base64-Text zum Schreiben in Nachricht
def x25519_public_to_b64(public_key: X25519PublicKey) -> str:
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return b64_encode(raw)


def x25519_public_from_b64(value: str) -> X25519PublicKey:
    raw = b64_decode(value)
    return X25519PublicKey.from_public_bytes(raw)


def derive_session_key(shared_secret: bytes, info: bytes = b"smart-home-secure-demo session key") -> bytes:
    """der shared Secret Schlüssel ist nicht zur Verschlüsselung geeignet
    -> leitet aus shared secrert Session Key ab"""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=info,
    )
    return hkdf.derive(shared_secret)


def session_key_fingerprint(session_key: bytes) -> str:
    """Kurzer, gut vergleichbarer Fingerprint (erste 16 Hex-Zeichen von SHA256(key))."""
    return hashlib.sha256(session_key).hexdigest()[:16]


'''
AES-GCM: 
    - Gerät und Hub haben denselben Session-Key 
    - Damit werden Nachrichten ver und entschlüsselt 
    - niemand kann Nachrichten lesen, niemand kann es unbemerkt verändern 
'''


def aes_gcm_encrypt(session_key: bytes, plaintext: bytes, associated_data: bytes = None):
    """verschlüsselt die Daten"""
    # jedes mal Anders verschlüsselt damit keine Muster erkennbar sind
    nonce = os.urandom(12)
    aesgcm = AESGCM(session_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
    return nonce, ciphertext


def aes_gcm_decrypt(session_key: bytes, nonce: bytes, ciphertext: bytes,
                    associated_data: bytes = None) -> bytes:
    """Entschlüsselt, prüft Authentifizierungs-Tag -> wenn etwas nicht zusammenpasst
    InvalidTag, Text wird nicht entschlüsselt """
    aesgcm = AESGCM(session_key)
    return aesgcm.decrypt(nonce, ciphertext, associated_data)
