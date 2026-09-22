"""测试环境固定为 ENV=localhost：单元测试不应依赖真实 Nacos 服务或未设置的 ENV。

pytest 会在收集测试模块之前先加载 conftest.py，时机上早于 tests/*.py 的顶层 import，
因此这里的 `os.environ.setdefault` 足以在任何模块读取 `ENV` 之前生效。
"""

from __future__ import annotations

import os

os.environ.setdefault("ENV", "localhost")
