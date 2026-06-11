from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import uuid

sys.path.append(str(Path(__file__).resolve().parents[1]))

from shared.topics import ALLOWED_DEVICE_TYPES

from shared.crypto_utils import (generate_ed25519_private_key, load_private_key, project_root,
                                 public_key_to_b64, save_private_key, sign_json, )


def issue_certificate(device_id: str, device_type: str, manufacturer: str = "DemoSmart") -> None:
    root = project_root()

    ca_private_key_path = root / "ca" / "ca_private_key.pem"
    if not ca_private_key_path.exists():
        raise FileNotFoundError("CA private key not found. Run python ca/create_ca.py first.")

    ca_private_key = load_private_key(ca_private_key_path)
    device_private_key = generate_ed25519_private_key()
    device_public_key = device_private_key.public_key()

    certificate_payload = {
        "certificateId": str(uuid.uuid4()),
        "deviceId": device_id,
        "deviceType": device_type,
        "manufacturer": manufacturer,
        "publicKey": public_key_to_b64(device_public_key),
        "issuedBy": "DemoSmart CA",
        "issuedAt": datetime.now(timezone.utc).isoformat(),
    }

    signature = sign_json(ca_private_key, certificate_payload)
    certificate = {"payload": certificate_payload, "signature": signature}

    credential_dir = root / "devices" / "device_credentials" / device_id
    credential_dir.mkdir(parents=True, exist_ok=True)

    save_private_key(device_private_key, credential_dir / "device_private_key.pem")

    certificate_path = credential_dir / "device_certificate.json"
    certificate_path.write_text(json.dumps(certificate, indent=2), encoding="utf-8")

    issued_copy_path = root / "ca" / "issued_certificates" / f"{device_id}.json"
    issued_copy_path.parent.mkdir(parents=True, exist_ok=True)
    issued_copy_path.write_text(json.dumps(certificate, indent=2), encoding="utf-8")

    print("Device certificate issued successfully.")
    print(f"  Device ID:    {device_id}")
    print(f"  Device type:  {device_type}")
    print(f"  Manufacturer: {manufacturer}")
    print(f"  Certificate:  {certificate_path}")
    print(f"  Private key:  {credential_dir / 'device_private_key.pem'}")


def main() -> None:
    args = sys.argv[1:]

    if not args:
        # ohne Argumente das Standardgerät ausstellen
        issue_certificate("temp_sensor_01", "temperature_sensor", "DemoSmart")
        return

    if len(args) < 2:
        print("Verwendung: python ca/issue_device_certificate.py <device_id> <device_type> [manufacturer]")
        print(f"Erlaubte device_type-Werte: {sorted(ALLOWED_DEVICE_TYPES)}")
        sys.exit(1)

    device_id = args[0]
    device_type = args[1]
    manufacturer = args[2] if len(args) > 2 else "DemoSmart"

    if device_type not in ALLOWED_DEVICE_TYPES:
        print(f"Unbekannter device_type '{device_type}'.")
        print(f"Erlaubt sind: {sorted(ALLOWED_DEVICE_TYPES)}")
        sys.exit(1)

    issue_certificate(device_id, device_type, manufacturer)


if __name__ == "__main__":
    main()