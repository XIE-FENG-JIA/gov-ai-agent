"""CLI 顯示工具：Rich console singleton。

fat-rotate-v3 Track A: utils.py 拆解後的顯示核心模組。
"""
from __future__ import annotations

from rich.console import Console

console = Console()

__all__ = ["console"]
