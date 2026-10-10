"""The box's one account: a user name and a salted scrypt hash of its password, in one file."""

import json
import os
import stat
import sys

import pytest

from wanpire.account import Account, InvalidAccount


def test_no_account_at_first(tmp_path):
    a = Account(tmp_path / "account")
    assert not a.exists()
    assert a.user is None
    assert not a.verify("admin", "whatever1")


def test_set_then_verify(tmp_path):
    a = Account(tmp_path / "account")
    a.set("admin", "correct horse")
    assert a.exists() and a.user == "admin"
    assert a.verify("admin", "correct horse")
    assert not a.verify("admin", "wrong horse")
    assert not a.verify("root", "correct horse")


def test_the_password_is_never_written(tmp_path):
    p = tmp_path / "account"
    Account(p).set("admin", "correct horse")
    text = p.read_text(encoding="utf-8")
    assert "correct horse" not in text
    doc = json.loads(text)
    assert doc["user"] == "admin" and doc["scheme"] == "scrypt"
    assert len(bytes.fromhex(doc["salt"])) == 16


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_the_file_is_private(tmp_path):
    p = tmp_path / "account"
    Account(p).set("admin", "correct horse")
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600


@pytest.mark.parametrize("user, password, says", [
    ("admin", "short", "8 characters"),
    ("", "long enough", "user name"),
    ("has space", "long enough", "user name"),
    ("x" * 33, "long enough", "user name"),
])
def test_invalid_accounts_are_refused(tmp_path, user, password, says):
    a = Account(tmp_path / "account")
    with pytest.raises(InvalidAccount, match=says):
        a.set(user, password)
    assert not a.exists()


def test_reset_removes_it(tmp_path):
    a = Account(tmp_path / "account")
    a.set("admin", "correct horse")
    a.reset()
    assert not a.exists()
    a.reset()  # twice is fine


def test_a_change_by_another_process_is_seen(tmp_path):
    p = tmp_path / "account"
    server = Account(p)
    server.set("admin", "correct horse")
    assert server.verify("admin", "correct horse")
    other = Account(p)  # `wanpire account set` beside the running server
    other.set("admin", "battery staple")
    os.utime(p, ns=(os.stat(p).st_atime_ns, os.stat(p).st_mtime_ns + 1_000_000))
    assert not server.verify("admin", "correct horse")
    assert server.verify("admin", "battery staple")
    other.reset()
    assert not server.exists()


def test_a_verified_pair_is_remembered(tmp_path, monkeypatch):
    a = Account(tmp_path / "account")
    a.set("admin", "correct horse")
    assert a.verify("admin", "correct horse")
    import wanpire.account as mod
    monkeypatch.setattr(mod, "_hash", lambda *_: pytest.fail("hashed again"))
    assert a.verify("admin", "correct horse")
