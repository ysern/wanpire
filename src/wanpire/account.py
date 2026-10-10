"""The box's one account: a user name and its password, for people and agents alike.

Kept in one JSON file (``/etc/wanpire/account``, mode 0600): the user name, a random salt and
the password's scrypt hash, never the password. No account means a new box: its web page's
first visit makes one. ``wanpire account set|reset``, over SSH on the box, changes or removes it
beside a running server, which reads the file again when it changes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from pathlib import Path

DEFAULT_PATH = "/etc/wanpire/account"
MIN_PASSWORD = 8
_USER = re.compile(r"[A-Za-z0-9._-]{1,32}")
_N, _R, _P = 2 ** 14, 8, 1


class InvalidAccount(ValueError):
    pass


def _hash(password: str, salt: bytes, n: int = _N, r: int = _R, p: int = _P) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32,
                          maxmem=64 * 1024 * 1024)


def check(user: str, password: str) -> None:
    """Raise :class:`InvalidAccount` with the reason, or return."""
    if not _USER.fullmatch(user or ""):
        raise InvalidAccount("a user name is 1 to 32 letters, digits, dots, dashes or underscores")
    if len(password or "") < MIN_PASSWORD:
        raise InvalidAccount(f"a password has at least {MIN_PASSWORD} characters")


class Account:
    """The account file, read again whenever it changes on disk."""

    def __init__(self, path: str | os.PathLike = DEFAULT_PATH):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._seen: tuple | None = None  # (mtime_ns, size) of the file last read
        self._doc: dict | None = None
        self._good: bytes | None = None  # a digest of the last pair that verified

    # -- reading --------------------------------------------------------------------------

    def _load(self) -> dict | None:
        try:
            st = self.path.stat()
        except FileNotFoundError:
            self._seen, self._doc, self._good = None, None, None
            return None
        key = (st.st_mtime_ns, st.st_size)
        if key != self._seen:
            self._doc = json.loads(self.path.read_text(encoding="utf-8"))
            self._seen, self._good = key, None
        return self._doc

    def exists(self) -> bool:
        with self._lock:
            return self._load() is not None

    @property
    def generation(self) -> tuple | None:
        """Changes whenever the account does: a session made under another is void."""
        with self._lock:
            self._load()
            return self._seen

    @property
    def user(self) -> str | None:
        with self._lock:
            doc = self._load()
            return doc["user"] if doc else None

    def verify(self, user: str, password: str) -> bool:
        with self._lock:
            doc = self._load()
            if doc is None:
                return False
            pair = hashlib.sha256(f"{user}\0{password}".encode("utf-8")).digest()
            if self._good is not None and hmac.compare_digest(pair, self._good):
                return True
            p = doc["params"]
            got = _hash(password, bytes.fromhex(doc["salt"]), p["n"], p["r"], p["p"])
            ok = hmac.compare_digest(user.encode("utf-8"), doc["user"].encode("utf-8"))
            ok = hmac.compare_digest(got, bytes.fromhex(doc["hash"])) and ok
            if ok:
                self._good = pair
            return ok

    # -- writing --------------------------------------------------------------------------

    def set(self, user: str, password: str) -> None:
        check(user, password)
        salt = secrets.token_bytes(16)
        doc = {"schema": "wanpire-account/1", "user": user, "scheme": "scrypt",
               "params": {"n": _N, "r": _R, "p": _P}, "salt": salt.hex(),
               "hash": _hash(password, salt).hex()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
            f.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)
        with self._lock:
            self._seen = None

    def create(self, user: str, password: str) -> bool:
        """Make the account only if there is none: the first visit. False when one exists."""
        with self._lock:
            if self._load() is not None:
                return False
        self.set(user, password)
        return True

    def reset(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        with self._lock:
            self._seen, self._doc, self._good = None, None, None
