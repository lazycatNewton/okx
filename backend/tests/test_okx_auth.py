"""OKX REST/WS 私有请求签名单元测试（对照官方文档定义的签名算法，非网络调用）。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re

from okx_backend.okx_client.auth import (
    build_rest_auth_headers,
    build_ws_login_args,
    rest_timestamp,
    sign_rest_request,
)


def test_rest_timestamp_matches_iso8601_millisecond_format() -> None:
    ts = rest_timestamp()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", ts)


def test_sign_rest_request_matches_documented_algorithm() -> None:
    """sign 算法见 introduction.md：Base64(HMAC-SHA256(SecretKey, ts+method+path+body))。"""

    secret = "22582BD0CFF14C41EDBF1AB98506286D"
    timestamp = "2020-12-08T09:08:57.715Z"
    method = "GET"
    path = "/api/v5/account/balance?ccy=BTC"

    expected = base64.b64encode(
        hmac.new(secret.encode(), f"{timestamp}{method}{path}".encode(), hashlib.sha256).digest()
    ).decode()

    assert sign_rest_request(secret, timestamp, method, path) == expected


def test_sign_rest_request_includes_body_when_present() -> None:
    secret = "secret"
    timestamp = "2020-12-08T09:08:57.715Z"
    body = '{"instId":"BTC-USDT"}'

    with_body = sign_rest_request(secret, timestamp, "POST", "/api/v5/trade/order", body)
    without_body = sign_rest_request(secret, timestamp, "POST", "/api/v5/trade/order", "")
    assert with_body != without_body


def test_build_rest_auth_headers_has_all_required_fields() -> None:
    headers = build_rest_auth_headers(
        "key", "secret", "pass", "GET", "/api/v5/public/economic-calendar"
    )
    assert set(headers) == {
        "OK-ACCESS-KEY", "OK-ACCESS-SIGN", "OK-ACCESS-TIMESTAMP", "OK-ACCESS-PASSPHRASE",
    }
    assert headers["OK-ACCESS-KEY"] == "key"
    assert headers["OK-ACCESS-PASSPHRASE"] == "pass"


def test_build_ws_login_args_signs_fixed_verify_path() -> None:
    """依据需求文档：签名对象固定为 GET /users/self/verify，秒级时间戳，SecretKey 本身不发送。"""

    args = build_ws_login_args("key", "secret", "pass")
    assert len(args) == 1
    entry = args[0]
    assert entry["apiKey"] == "key"
    assert entry["passphrase"] == "pass"
    assert "secret" not in entry.values()
    assert re.fullmatch(r"\d+", entry["timestamp"])

    expected_sign = base64.b64encode(
        hmac.new(
            b"secret", f"{entry['timestamp']}GET/users/self/verify".encode(), hashlib.sha256
        ).digest()
    ).decode()
    assert entry["sign"] == expected_sign
