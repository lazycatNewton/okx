"""ENV 启动参数驱动的配置装载单元测试。

依据 HANDOFF.md 用户确认（0.53 起，0.55 改为默认 localhost）：
- ENV 未设置时默认为 localhost；非法值（既不是 localhost 也不是 prod）直接抛异常终止。
- ENV=localhost（或未设置）：从 `.env.localhost` + OS 环境变量装载；Nacos 完全跳过。
- ENV=prod：不加载任何 dotenv 文件，全部配置必须来自真实 OS 环境变量；Nacos 强制启用。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from okx_backend.config import Settings, get_app_env


def test_get_app_env_defaults_to_localhost_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENV", raising=False)
    assert get_app_env() == "localhost"


def test_get_app_env_raises_on_invalid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "staging")
    with pytest.raises(RuntimeError, match="ENV"):
        get_app_env()


def test_get_app_env_accepts_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "localhost")
    assert get_app_env() == "localhost"


def test_get_app_env_accepts_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "prod")
    assert get_app_env() == "prod"


def test_prod_settings_ignore_dotenv_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """ENV=prod 时即使当前目录存在 .env.localhost，也不应读取其内容。"""

    dotenv = tmp_path / ".env.localhost"
    dotenv.write_text("OKX_APP_MYSQL_HOST=should-not-be-used\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.delenv("OKX_APP_MYSQL_HOST", raising=False)

    settings = Settings(_env_file=None)
    assert settings.mysql_host != "should-not-be-used"
    assert settings.mysql_host == "127.0.0.1"  # 字段默认值，因为 OS 环境变量里也没设置


def test_prod_settings_read_from_os_env_only(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    dotenv = tmp_path / ".env.localhost"
    dotenv.write_text("OKX_APP_MYSQL_HOST=from-dotenv\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("OKX_APP_MYSQL_HOST", "from-os-env")

    settings = Settings(_env_file=None)
    assert settings.mysql_host == "from-os-env"


def test_localhost_settings_read_from_dotenv_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    dotenv = tmp_path / ".env.localhost"
    dotenv.write_text("OKX_APP_MYSQL_HOST=from-dotenv-localhost\n")
    monkeypatch.setenv("ENV", "localhost")
    monkeypatch.delenv("OKX_APP_MYSQL_HOST", raising=False)

    # `.env.localhost` 路径已固定锚定到 backend/ 包根目录（见 config.py 顶部说明），
    # 不再随进程当前工作目录变化，因此这里显式传入 `_env_file` 而不是 chdir。
    settings = Settings(_env_file=str(dotenv))  # type: ignore[call-arg]
    assert settings.mysql_host == "from-dotenv-localhost"


def test_localhost_settings_os_env_overrides_dotenv_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    dotenv = tmp_path / ".env.localhost"
    dotenv.write_text("OKX_APP_MYSQL_HOST=from-dotenv-localhost\n")
    monkeypatch.setenv("ENV", "localhost")
    monkeypatch.setenv("OKX_APP_MYSQL_HOST", "from-os-env-wins")

    settings = Settings(_env_file=str(dotenv))  # type: ignore[call-arg]
    assert settings.mysql_host == "from-os-env-wins"


@pytest.mark.skipif(
    not (Path(__file__).resolve().parent.parent / ".env.localhost").is_file(),
    reason="需要本机 backend/.env.localhost（已被 gitignore，CI 中不存在）",
)
def test_settings_env_file_path_is_absolute_and_independent_of_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """回归测试：`.env.localhost` 必须锚定到 backend/ 包根目录的绝对路径，

    不能随进程当前工作目录变化——否则从仓库根目录或其他目录启动时会
    静默找不到该文件、所有字段退回默认值（例如 mysql_password 默认空
    字符串），只在真正连接 MySQL 时才会看到 "Access denied (using
    password: NO)"，而不是在配置装载阶段报错。
    """

    from okx_backend.config import Settings as SettingsClass

    env_file = SettingsClass.model_config.get("env_file")
    assert env_file is not None
    assert Path(str(env_file)).is_absolute()

    # 切换到一个不存在 .env.localhost 的空目录，默认（未传 _env_file）的
    # Settings() 仍应从 backend/.env.localhost 读取，而不是从当前目录读取。
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENV", "localhost")
    settings = Settings()
    assert settings.mysql_password != ""
