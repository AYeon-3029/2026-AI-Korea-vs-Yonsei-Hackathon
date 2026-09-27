"""결정적 정수 PRNG (splitmix64).

CLAUDE.md 원칙 1: 부동소수점 금지, 모든 판정 정수 연산. 맵 생성의 시드 기반
PRNG 만 예외로 허용된다. 플랫폼/파이썬 버전과 무관하게 항상 같은 수열을
내도록 표준 라이브러리 random 대신 자체 정수 PRNG 를 쓴다.
"""
from __future__ import annotations

from typing import List, Sequence, TypeVar

_MASK = (1 << 64) - 1
T = TypeVar("T")


class Rng:
    def __init__(self, seed: int) -> None:
        self.state = seed & _MASK

    def _next(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & _MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
        return z ^ (z >> 31)

    def randint(self, a: int, b: int) -> int:
        """[a, b] 폐구간 정수. 결정적(약간의 모듈로 편향은 허용)."""
        return a + self._next() % (b - a + 1)

    def choice(self, seq: Sequence[T]) -> T:
        return seq[self.randint(0, len(seq) - 1)]

    def shuffle(self, lst: List[T]) -> None:
        """Fisher–Yates (제자리)."""
        for i in range(len(lst) - 1, 0, -1):
            j = self.randint(0, i)
            lst[i], lst[j] = lst[j], lst[i]
