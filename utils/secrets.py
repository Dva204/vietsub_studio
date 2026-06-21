"""Luu secret bang Windows DPAPI, ciphertext duoc dat trong SQLite settings."""

from __future__ import annotations

import base64
import ctypes
import os
from ctypes import wintypes

from utils.db import Database


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class SecretStore:
    def __init__(self, database: Database):
        self.database = database

    def set(self, key: str, value: str):
        encrypted = _protect(value.encode("utf-8"))
        payload = "dpapi:" + base64.b64encode(encrypted).decode("ascii")
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, payload),
            )

    def get(self, key: str):
        connection = self.database.connect()
        try:
            row = connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        finally:
            connection.close()
        if not row:
            return None
        payload = row["value"] or ""
        if not payload.startswith("dpapi:"):
            raise ValueError("Secret khong dung dinh dang DPAPI")
        encrypted = base64.b64decode(payload[6:])
        return _unprotect(encrypted).decode("utf-8")

    def delete(self, key: str):
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM settings WHERE key = ?", (key,))


def _protect(data: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("DPAPI chi ho tro Windows")
    return _crypt_protect(data, decrypt=False)


def _unprotect(data: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("DPAPI chi ho tro Windows")
    return _crypt_protect(data, decrypt=True)


def _crypt_protect(data: bytes, *, decrypt: bool) -> bytes:
    buffer = ctypes.create_string_buffer(data, len(data))
    input_blob = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    output_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob), wintypes.LPCWSTR, ctypes.POINTER(_DataBlob),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.POINTER(_DataBlob),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    if decrypt:
        success = crypt32.CryptUnprotectData(
            ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)
        )
    else:
        success = crypt32.CryptProtectData(
            ctypes.byref(input_blob), "VietDub Studio", None, None, None, 0,
            ctypes.byref(output_blob),
        )
    if not success:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(output_blob.pbData, wintypes.HLOCAL))
