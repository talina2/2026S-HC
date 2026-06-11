from pathlib import Path
import sys
from shared.crypto_utils import (generate_ed25519_private_key, project_root, save_private_key, save_public_key, )

sys.path.append(str(Path(__file__).resolve().parents[1]))

'''
Certificate Authority: 
    - Hub vertraut nur Geräten, die offizielles Zertifikat vorweisen können 
    - stellt Zertifikate aus und Signiert sie 
    - public Key zusätzlich im Hub gespeichert -> trust anchor 
'''


def main() -> None:
    """Legt CA einmalig an"""
    root = project_root()

    ca_private_key_path = root / "ca" / "ca_private_key.pem"
    ca_public_key_path = root / "ca" / "ca_public_key.pem"
    trusted_ca_public_key_path = root / "hub" / "trusted_ca_public_key.pem"

    if ca_private_key_path.exists() or ca_public_key_path.exists():
        print("CA keys already exist. No new CA was created.")
        print(f"Private key: {ca_private_key_path}")
        print(f"Public key:  {ca_public_key_path}")
        return

    private_key = generate_ed25519_private_key()
    public_key = private_key.public_key()
    save_private_key(private_key, ca_private_key_path)
    save_public_key(public_key, ca_public_key_path)
    save_public_key(public_key, trusted_ca_public_key_path)

    print("CA created successfully.")
    print(f"Private key: {ca_private_key_path}")
    print(f"Public key:  {ca_public_key_path}")
    print(f"Trusted CA copy for hub: {trusted_ca_public_key_path}")


if __name__ == "__main__":
    main()
