import base64
import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from utils.license import LicenseManager, get_machine_id


class LicenseTests(unittest.TestCase):
    def setUp(self):
        self.private_key = Ed25519PrivateKey.generate()
        self.public_pem = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def _token(self, **overrides):
        payload = {
            "license_id": "LIC-001",
            "product": "vietdub-studio",
            "machine_id": get_machine_id(),
            "customer": "Test Customer",
            "updates_until": (date.today() + timedelta(days=365)).isoformat(),
        }
        payload.update(overrides)
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = self.private_key.sign(data)
        encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
        return f"{encode(data)}.{encode(signature)}"

    def test_activates_and_validates_machine_bound_license(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LicenseManager(self.public_pem, Path(temp_dir) / "license.key")
            manager.activate(self._token())
            status = manager.status()
        self.assertTrue(status["valid"])
        self.assertTrue(status["updates_active"])

    def test_rejects_wrong_machine_and_tampered_signature(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LicenseManager(self.public_pem, Path(temp_dir) / "license.key")
            with self.assertRaises(ValueError):
                manager.activate(self._token(machine_id="another-machine"))
            token = self._token()
            with self.assertRaises(ValueError):
                manager.activate("A" + token[1:])

    def test_expired_updates_do_not_disable_perpetual_license(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LicenseManager(self.public_pem, Path(temp_dir) / "license.key")
            manager.activate(
                self._token(updates_until=(date.today() - timedelta(days=1)).isoformat())
            )
            status = manager.status()
        self.assertTrue(status["valid"])
        self.assertFalse(status["updates_active"])


if __name__ == "__main__":
    unittest.main()
