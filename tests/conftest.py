"""pytest 公共配置：让测试可以直接 import 仓库 ``scripts/`` 下的模块。

测试只依赖仓库内 ``tests/fixtures/`` 的样本文件，**不**依赖
``D:\\Projects\\GitHub\\`` 下任何模板仓的绝对路径 —— 避免核验器单测随外部
仓库漂移而失效。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

for candidate in (str(SCRIPTS_DIR),):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)
