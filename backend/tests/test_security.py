"""安全与校验工具的单元测试。"""

from __future__ import annotations

from okx_backend.security import (
    generate_initial_password,
    hash_password,
    validate_username,
    verify_password,
)


def test_hash_and_verify_roundtrip() -> None:
    hashed = hash_password("Sup3r$ecret!")
    assert hashed != "Sup3r$ecret!"
    assert verify_password("Sup3r$ecret!", hashed)
    assert not verify_password("wrong-password", hashed)


def test_validate_username_accepts_only_lowercase_up_to_10_chars() -> None:
    assert validate_username("abc")
    assert validate_username("abcdefghij")  # 10 chars, boundary
    assert not validate_username("abcdefghijk")  # 11 chars
    assert not validate_username("")
    assert not validate_username("ABC")
    assert not validate_username("abc123")
    assert not validate_username("ab-c")


def test_generate_initial_password_meets_complexity_and_length() -> None:
    for _ in range(50):
        pwd = generate_initial_password()
        assert len(pwd) <= 18
        assert any(c.isupper() for c in pwd)
        assert any(c.islower() for c in pwd)
        assert any(c.isdigit() for c in pwd)
        assert any(not c.isalnum() for c in pwd)
