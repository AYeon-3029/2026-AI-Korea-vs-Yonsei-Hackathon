"""게임 상태 모델.

결정성 원칙(CLAUDE.md 원칙 1): 부동소수점/난수 금지, dict/set 순회 순서에
의존하는 로직 금지. 순회가 필요한 곳은 항상 명시적으로 정렬한다.

유닛 표현: 개별 ID/체력 없이 (x, y, team, kind) → 인원 수 로만 표현(SPEC 3절).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

TEAMS = ("Y", "K")

# 건물 종류 코드
BUILDING_TYPES = (
    "PLAZA",     # 중앙광장
    "HALL",      # 학생회관
    "STATION",   # 역
    "LIBRARY",   # 도서관
    "ENG",       # 공학관
    "HOSPITAL",  # 병원
    "WATCH",     # 감시 거점
    "DEPOT",     # 보급소
)


@dataclass
class Building:
    """건물 하나의 상태.

    owner: 'N'(중립) / 'Y' / 'K'
    stage: 0(중립) / 1(직전 턴 소유→중립화된 정보성 표시) / 2(완전 소유)
           ※ SPEC 8절 [확정]: stage=1 은 정보성 필드일 뿐 stage=0 과 동일 취급.
    score: 건물 고정 점수(전역 정보). PLAZA 는 항상 config.plaza_score.
    """
    id: int
    x: int
    y: int
    btype: str
    score: int
    owner: str = "N"
    stage: int = 0

    @property
    def pos(self) -> Tuple[int, int]:
        return (self.x, self.y)


@dataclass
class GameState:
    config: dict
    # terrain[y][x] ∈ {'.', '#', 'B', 'H'}
    terrain: List[List[str]]
    buildings: Dict[int, Building]
    bases: Dict[str, Tuple[int, int]]                       # team -> (x, y)
    resources: Dict[str, int] = field(default_factory=lambda: {"Y": 0, "K": 0})
    # (x, y, team, kind) -> count (양수만 저장)
    units: Dict[Tuple[int, int, str, str], int] = field(default_factory=dict)
    turn: int = 0
    # 보급소 최초 점령 보너스: building_id -> 이미 보너스 받은 팀 집합
    depot_claimed: Dict[int, Set[str]] = field(default_factory=dict)
    # 팀별 점수 공개된 건물 id 집합(영구)
    revealed: Dict[str, Set[int]] = field(default_factory=lambda: {"Y": set(), "K": set()})
    # 누적 점령-턴(타이브레이커 ③): 매 턴 소유 건물 점수 합을 누적
    occupation_score_turns: Dict[str, int] = field(default_factory=lambda: {"Y": 0, "K": 0})

    # ---- 파생 인덱스 ----
    def building_at(self, x: int, y: int) -> Optional[Building]:
        for b in self.sorted_buildings():
            if b.x == x and b.y == y:
                return b
        return None

    def sorted_buildings(self) -> List[Building]:
        """id 오름차순으로 정렬된 건물 목록(결정적 순회용)."""
        return [self.buildings[i] for i in sorted(self.buildings)]

    # ---- 유닛 조작 ----
    def get_unit(self, x: int, y: int, team: str, kind: str) -> int:
        return self.units.get((x, y, team, kind), 0)

    def set_unit(self, x: int, y: int, team: str, kind: str, count: int) -> None:
        key = (x, y, team, kind)
        if count <= 0:
            self.units.pop(key, None)
        else:
            self.units[key] = count

    def add_unit(self, x: int, y: int, team: str, kind: str, count: int) -> None:
        if count <= 0:
            return
        self.set_unit(x, y, team, kind, self.get_unit(x, y, team, kind) + count)

    def remove_unit(self, x: int, y: int, team: str, kind: str, count: int) -> int:
        """최대 count 명 제거, 실제 제거 인원 반환."""
        have = self.get_unit(x, y, team, kind)
        take = min(have, max(0, count))
        self.set_unit(x, y, team, kind, have - take)
        return take

    def team_has_units_at(self, x: int, y: int, team: str) -> bool:
        return any(self.get_unit(x, y, team, k) > 0 for k in ("F", "W", "S"))

    def clone(self) -> "GameState":
        return copy.deepcopy(self)

    # ---- 지형 질의 ----
    def in_bounds(self, x: int, y: int) -> bool:
        h = self.config["grid"]["height"]
        w = self.config["grid"]["width"]
        return 0 <= x < w and 0 <= y < h

    def is_passable(self, x: int, y: int) -> bool:
        """진입 가능 여부(장애물 '#' 만 진입 불가)."""
        if not self.in_bounds(x, y):
            return False
        return self.terrain[y][x] != "#"


def blank_terrain(config: dict) -> List[List[str]]:
    w = config["grid"]["width"]
    h = config["grid"]["height"]
    return [["." for _ in range(w)] for _ in range(h)]


def new_game(
    config: dict,
    *,
    terrain: Optional[List[List[str]]] = None,
    buildings: Optional[List[Building]] = None,
    bases: Optional[Dict[str, Tuple[int, int]]] = None,
    resources: Optional[Dict[str, int]] = None,
) -> GameState:
    """테스트/러너에서 쓰는 상태 생성 헬퍼.

    terrain 미지정 시 전면 평지. bases 미지정 시 양 끝 중앙.
    """
    if terrain is None:
        terrain = blank_terrain(config)
    if bases is None:
        h = config["grid"]["height"]
        w = config["grid"]["width"]
        bases = {"Y": (0, h // 2), "K": (w - 1, h // 2)}
    blist = buildings or []
    bmap = {b.id: b for b in blist}
    # 건물/본진 지형 표기
    for b in blist:
        terrain[b.y][b.x] = "B"
    for team, (bx, by) in bases.items():
        terrain[by][bx] = "H"
    start = config["resource"]["start_resource"]
    res = resources if resources is not None else {"Y": start, "K": start}
    return GameState(
        config=config,
        terrain=terrain,
        buildings=bmap,
        bases=dict(bases),
        resources=dict(res),
    )
