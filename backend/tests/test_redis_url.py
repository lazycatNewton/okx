from okx_backend.config import Settings


def _settings(**kw) -> Settings:
    return Settings(_env_file=None, redis_host="h", redis_port=6380, redis_db=2, **kw)  # type: ignore[call-arg]


def test_redis_url_without_credentials():
    assert _settings().redis_url == "redis://h:6380/2"


def test_redis_url_with_username_and_password():
    s = _settings(redis_username="u", redis_password="p")
    assert s.redis_url == "redis://u:p@h:6380/2"


def test_redis_url_encodes_special_characters():
    s = _settings(redis_username="a@b", redis_password="p:w/d@#")
    assert s.redis_url == "redis://a%40b:p%3Aw%2Fd%40%23@h:6380/2"


def test_redis_url_uses_tls_scheme_when_ssl_enabled():
    s = _settings(redis_username="u", redis_password="p", redis_ssl=True)
    assert s.redis_url == "rediss://u:p@h:6380/2"
