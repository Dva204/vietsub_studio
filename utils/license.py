"""Offline perpetual license verification bang Ed25519."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import tempfile
import uuid
from datetime import date
from pathlib import Path


class LicenseError(ValueError):
    pass


class LicenseManager:
    def __init__(self, public_key_pem: bytes, license_path: str | Path, product="vietdub-studio"):
        self.public_key_pem = public_key_pem
        self.license_path = Path(license_path)
        self.product = product

    def activate(self, token: str) -> dict:
        payload = self.validate_token(token)
        self.license_path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(
            prefix=".license_", suffix=".tmp", dir=self.license_path.parent
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                file.write(token.strip())
            os.replace(temp_name, self.license_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return payload

    def status(self) -> dict:
        if not self.license_path.is_file():
            return {"valid": False, "activated": False, "error": "Chua activate license"}
        try:
            payload = self.validate_token(
                self.license_path.read_text(encoding="utf-8").strip()
            )
            updates_until = date.fromisoformat(payload["updates_until"])
            return {
                "valid": True,
                "activated": True,
                "license_id": payload["license_id"],
                "customer": payload.get("customer", ""),
                "updates_until": payload["updates_until"],
                "updates_active": date.today() <= updates_until,
                "error": None,
            }
        except Exception as error:
            return {"valid": False, "activated": True, "error": str(error)}

    def validate_token(self, token: str) -> dict:
        try:
            payload_part, signature_part = token.strip().split(".", 1)
            payload_bytes = _decode_urlsafe(payload_part)
            signature = _decode_urlsafe(signature_part)
        except Exception as error:
            raise LicenseError("License token khong dung dinh dang") from error

        try:
            from cryptography.hazmat.primitives import serialization

            public_key = serialization.load_pem_public_key(self.public_key_pem)
            public_key.verify(signature, payload_bytes)
        except Exception as error:
            raise LicenseError("Chu ky license khong hop le") from error

        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except Exception as error:
            raise LicenseError("License payload khong hop le") from error
        required = {"license_id", "product", "machine_id", "updates_until"}
        if not required.issubset(payload):
            raise LicenseError("License thieu truong bat buoc")
        if payload["product"] != self.product:
            raise LicenseError("License khong danh cho san pham nay")
        if payload["machine_id"] != get_machine_id():
            raise LicenseError("License khong thuoc may nay")
        try:
            date.fromisoformat(payload["updates_until"])
        except ValueError as error:
            raise LicenseError("updates_until khong hop le") from error
        return payload


def get_machine_id() -> str:
    parts = [platform.system(), platform.machine()]
    if os.name == "nt":
        try:
            import winreg

            access = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                access,
            ) as key:
                parts.append(str(winreg.QueryValueEx(key, "MachineGuid")[0]))
        except OSError:
            parts.append(str(uuid.getnode()))
    else:
        parts.append(str(uuid.getnode()))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _decode_urlsafe(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
