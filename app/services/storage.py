"""Object-storage adapter for image bytes.

The rest of the app only knows this interface, so switching from local disk to
S3/GCS is a config change, not a code change. Local backend signs URLs with an
HMAC so the download route can verify them the same way it would an S3 pre-signed
URL.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from pathlib import Path
from typing import Protocol

from app.config import get_settings


class Storage(Protocol):
    backend_name: str

    def save(self, key: str, data: bytes) -> None: ...
    def load(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def signed_url(self, key: str) -> tuple[str, int]: ...
    def verify_signature(self, key: str, expires: int, signature: str) -> bool: ...


class LocalStorage:
    backend_name = "local"

    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError("path traversal detected")
        return p

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def load(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def _sign(self, key: str, expires: int) -> str:
        secret = get_settings().jwt_secret.encode()
        msg = f"{key}:{expires}".encode()
        return hmac.new(secret, msg, hashlib.sha256).hexdigest()

    def signed_url(self, key: str) -> tuple[str, int]:
        ttl = get_settings().signed_url_ttl_seconds
        expires = int(time.time()) + ttl
        sig = self._sign(key, expires)
        return f"/v1/images/raw/{key}?expires={expires}&signature={sig}", ttl

    def verify_signature(self, key: str, expires: int, signature: str) -> bool:
        if expires < int(time.time()):
            return False
        return hmac.compare_digest(self._sign(key, expires), signature)


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        settings = get_settings()
        if settings.storage_backend == "local":
            _storage = LocalStorage(settings.storage_local_dir)
        else:  # pragma: no cover - S3 backend is a deployment concern
            raise NotImplementedError(
                f"storage backend {settings.storage_backend!r} not wired yet; "
                "implement an S3Storage class with the same Protocol"
            )
    return _storage
