"""OKX REST 私有请求签名与 business WS 登录签名。

依据 okx-v5-api Skill `introduction.md`：
- REST：`OK-ACCESS-SIGN` = Base64(HMAC-SHA256(SecretKey, timestamp + method + requestPath + body))；
  `timestamp` 为 ISO 8601 UTC 毫秒格式（如 `2020-12-08T09:08:57.715Z`）。
- WS 登录：`sign` = Base64(HMAC-SHA256(SecretKey, timestamp + "GET" + "/users/self/verify"))；
  `timestamp` 为秒级 Unix 时间戳字符串。两种时间戳格式不同，不能混用。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from datetime import UTC, datetime


def rest_timestamp() -> str:
    """ISO 8601 UTC 毫秒格式，如 `2020-12-08T09:08:57.715Z`。"""

    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def sign_rest_request(
    secret_key: str, timestamp: str, method: str, request_path: str, body: str = ""
) -> str:
    message = f"{timestamp}{method.upper()}{request_path}{body}"
    digest = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def build_rest_auth_headers(
    api_key: str, secret_key: str, passphrase: str, method: str, request_path: str, body: str = ""
) -> dict[str, str]:
    timestamp = rest_timestamp()
    sign = sign_rest_request(secret_key, timestamp, method, request_path, body)
    return {
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": passphrase,
    }


def build_ws_login_args(api_key: str, secret_key: str, passphrase: str) -> list[dict[str, str]]:
    """business WS `op=login` 的 `args`；秒级时间戳，签名对象固定为 `GET /users/self/verify`。"""

    timestamp = str(int(time.time()))
    message = f"{timestamp}GET/users/self/verify"
    digest = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    sign = base64.b64encode(digest).decode("utf-8")
    return [
        {
            "apiKey": api_key,
            "passphrase": passphrase,
            "timestamp": timestamp,
            "sign": sign,
        }
    ]
