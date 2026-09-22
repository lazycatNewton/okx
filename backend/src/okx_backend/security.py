"""密码哈希与会话辅助逻辑。

- 密码：Argon2（带盐的单向安全哈希），不保存明文。
- 会话：不透明 session id，状态存 Redis；Cookie 属性（HttpOnly/Secure/SameSite）由路由层设置。
"""

from __future__ import annotations

import re
import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def generate_session_id() -> str:
    return secrets.token_urlsafe(32)


_UPPER = string.ascii_uppercase
_LOWER = string.ascii_lowercase
_DIGITS = string.digits
_SPECIAL = "!@#$%^&*()-_=+"


def generate_initial_password(length: int = 18) -> str:
    """控制台创建唯一使用者账户时用的随机初始密码：<=18 位，含大小写字母/数字/特殊字符。

    本期不实现控制台，此函数仅供后续控制台或测试脚本复用。
    """

    if length < 4:
        raise ValueError("length must allow at least one char per required class")
    required = [
        secrets.choice(_UPPER),
        secrets.choice(_LOWER),
        secrets.choice(_DIGITS),
        secrets.choice(_SPECIAL),
    ]
    pool = _UPPER + _LOWER + _DIGITS + _SPECIAL
    remaining = [secrets.choice(pool) for _ in range(length - len(required))]
    chars = required + remaining
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


_USERNAME_RE = re.compile(r"^[a-z]{1,10}$")


def validate_username(username: str) -> bool:
    """用户名非空、仅小写英文字母（a-z）、长度不超过 10 字符。"""

    return bool(_USERNAME_RE.match(username))
