"""밸런스 설정 로더.

모든 밸런스 수치는 config/balance.json에서 읽는다(CLAUDE.md 절대원칙 2).
코드에 수치를 하드코딩하지 않는다.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

# 저장소 루트 기준 기본 경로
_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "balance.json",
)


def load_config(path: str | None = None) -> Dict[str, Any]:
    """balance.json을 읽어 dict로 반환한다."""
    with open(path or _DEFAULT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
