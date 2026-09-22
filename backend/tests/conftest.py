"""测试环境固定为 ENV=localhost：单元测试不应依赖真实 Nacos 服务或未设置的 ENV。

必须在任何 `okx_backend.config` 被导入之前设置，因为 `deps.py`/`auth_router.py` 等模块
在导入期就顶层调用了 `get_settings()`（见各自的 `_settings = get_settings()`）。
pytest 会在收集测试模块之前先加载 conftest.py，时机上早于 tests/*.py 的顶层 import，
因此这里的 `os.environ.setdefault` 足以保证生效。
"""

from __future__ import annotations

import os

os.environ.setdefault("ENV", "localhost")
