"""봇 명령의 구조화 표현.

엔진 코어는 순수 상태 전이만 다루므로(CLAUDE.md 원칙 4), 텍스트 프로토콜 파싱은
러너 계층(M3)에서 담당하고 여기서는 이미 파싱된 명령 객체만 취급한다.

방향 코드: U(y-1) / D(y+1) / L(x-1) / R(x+1)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# 방향 → (dx, dy)
DIRECTIONS = {
    "U": (0, -1),
    "D": (0, 1),
    "L": (-1, 0),
    "R": (1, 0),
}

KINDS = ("F", "W", "S")


@dataclass(frozen=True)
class Spawn:
    """본진(또는 점령 중인 병원)에서 생산. x,y 미지정이면 본진에서 생산."""
    kind: str
    count: int
    x: Optional[int] = None
    y: Optional[int] = None


@dataclass(frozen=True)
class Move:
    """1칸 이동."""
    x: int
    y: int
    kind: str
    count: int
    direction: str


@dataclass(frozen=True)
class Move2:
    """정찰병(S) 2칸 이동. 경유 셀에서는 전투 없음, 도착 셀에서만 판정."""
    x: int
    y: int
    count: int
    dir1: str
    dir2: str
    kind: str = "S"


@dataclass(frozen=True)
class Tele:
    """점령 중인 역 → 점령 중인 역 순간이동(턴 1회, 합계 최대 max_units명)."""
    x: int
    y: int
    kind: str
    count: int
    tx: int
    ty: int


@dataclass(frozen=True)
class Priority:
    """점령 자원 배정 우선순위. coords = [(x,y), ...]."""
    coords: List[Tuple[int, int]] = field(default_factory=list)
