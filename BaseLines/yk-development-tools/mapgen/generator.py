"""시드 기반 점대칭 맵 생성기 (SPEC 2절).

- 중심점 (7,7) 기준 180° 점대칭: (x,y) ↔ (14-x, 14-y)
- 건물 17개 = 중앙광장 1(정중앙, 3점) + 대칭쌍 8쌍(16개)
    · 신촌/안암 대칭쌍 5쌍: 학생회관/도서관/공학관/병원/역(신촌역·안암역)
    · 중앙 대칭쌍 3쌍: 서울역/감시거점/보급소
- 대칭쌍은 항상 같은 점수 → 맵 총점 항상 홀수(동점 방지)
- 모든 건물·본진 상호 도달 가능(연결성), 본부 간 최소 맨해튼 거리 확보
- 본진: 연세=신촌, 고려=점대칭 위치

같은 시드 → 항상 같은 맵.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from engine.state import Building
from .rng import Rng

# 신촌/안암 대칭쌍(신촌 쪽에 배치, 안암은 점대칭)과 중앙 대칭쌍의 건물 종류
SINCHON_PAIR_TYPES = ["HALL", "LIBRARY", "ENG", "HOSPITAL", "STATION"]  # 역=신촌역/안암역
CENTER_PAIR_TYPES = ["STATION", "WATCH", "DEPOT"]                       # STATION=서울역

Coord = Tuple[int, int]


@dataclass
class GameMap:
    seed: int
    config: dict
    terrain: List[List[str]]          # [y][x] ∈ {'.', '#', 'B', 'H'}
    buildings: List[Building]         # id 오름차순
    bases: Dict[str, Coord]           # {'Y': (x,y), 'K': (x,y)}

    def total_score(self) -> int:
        return sum(b.score for b in self.buildings)


def _sym(x: int, y: int) -> Coord:
    """중심 (7,7) 기준 180° 점대칭."""
    return (14 - x, 14 - y)


def _manhattan(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class _Builder:
    def __init__(self, seed: int, config: dict) -> None:
        self.seed = seed
        self.config = config
        self.w = config["grid"]["width"]
        self.h = config["grid"]["height"]
        self.rng = Rng(seed)
        self.terrain = [["." for _ in range(self.w)] for _ in range(self.h)]
        self.occupied: Set[Coord] = set()   # 건물/본진 셀(장애물 배치 금지)
        self.buildings: List[Building] = []
        self.bases: Dict[str, Coord] = {}
        self._mg = config["mapgen"]
        self.cx, self.cy = self._mg["center"]

    # ---- 영역 범위 ----
    def _region_x(self, name: str) -> Tuple[int, int]:
        lo, hi = self.config["regions"][name]
        return lo, hi

    def _free_cell(self, x: int, y: int) -> bool:
        return (x, y) not in self.occupied

    # ---- 1. 중앙광장 ----
    def place_plaza(self) -> None:
        score = self.config["buildings"]["plaza_score"]
        b = Building(id=0, x=self.cx, y=self.cy, btype="PLAZA", score=score)
        self.buildings.append(b)
        self.occupied.add((self.cx, self.cy))

    # ---- 2. 본진(연세=신촌, 고려=점대칭) ----
    def place_bases(self) -> None:
        lo, hi = self._region_x("sinchon")
        min_d = self.config["min_base_distance"]
        for _ in range(self._mg["max_place_attempts"]):
            bx = self.rng.randint(lo, hi)
            by = self.rng.randint(0, self.h - 1)
            ky, kx = _sym(bx, by)[1], _sym(bx, by)[0]
            if (bx, by) in self.occupied or (kx, ky) in self.occupied:
                continue
            if (bx, by) == (kx, ky):
                continue
            if _manhattan((bx, by), (kx, ky)) < min_d:
                continue
            self.bases["Y"] = (bx, by)
            self.bases["K"] = (kx, ky)
            self.occupied.add((bx, by))
            self.occupied.add((kx, ky))
            return
        raise RuntimeError(f"본진 배치 실패 (seed={self.seed})")

    # ---- 3. 건물 대칭쌍 ----
    def _place_pair(self, next_id: int, btype: str, region: str, score: int,
                    y_lo: int = 0, y_hi: Optional[int] = None) -> int:
        """region 안에 첫 건물을 두고 점대칭 파트너를 배치. 부여한 다음 id 반환.

        y_lo..y_hi 로 행 범위를 제한할 수 있다(중앙 건물의 y 여백 제약 등).
        """
        lo, hi = self._region_x(region)
        if y_hi is None:
            y_hi = self.h - 1
        for _ in range(self._mg["max_place_attempts"]):
            x = self.rng.randint(lo, hi)
            y = self.rng.randint(y_lo, y_hi)
            px, py = _sym(x, y)
            if (x, y) == (px, py):
                continue  # 자기대칭 셀(중앙) 제외
            if not self._free_cell(x, y) or not self._free_cell(px, py):
                continue
            self.buildings.append(Building(id=next_id, x=x, y=y, btype=btype, score=score))
            self.buildings.append(Building(id=next_id + 1, x=px, y=py, btype=btype, score=score))
            self.occupied.add((x, y))
            self.occupied.add((px, py))
            return next_id + 2
        raise RuntimeError(f"건물 배치 실패 (seed={self.seed}, type={btype})")

    def place_building_pairs(self) -> None:
        next_id = 1
        s_lo, s_hi = self._mg["sinchon_building_score"]
        c_lo, c_hi = self._mg["center_building_score"]
        margin = self._mg.get("central_y_margin", 0)   # 중앙 건물 y 여백 제약
        c_ylo, c_yhi = margin, self.h - 1 - margin
        for btype in SINCHON_PAIR_TYPES:              # 신촌↔안암 5쌍
            score = self.rng.randint(s_lo, s_hi)      # 1~2점
            next_id = self._place_pair(next_id, btype, "sinchon", score)
        for btype in CENTER_PAIR_TYPES:               # 중앙 3쌍 (y 는 margin..14-margin)
            score = self.rng.randint(c_lo, c_hi)      # 2~4점
            next_id = self._place_pair(next_id, btype, "center", score, c_ylo, c_yhi)

    # ---- 4. 장애물(점대칭, 연결성 보존) ----
    def _passable(self, terrain: List[List[str]], x: int, y: int) -> bool:
        return terrain[y][x] != "#"

    def _all_connected(self, terrain: List[List[str]]) -> bool:
        """모든 건물·본진 셀이 통행 가능 경로로 상호 도달 가능한지 BFS."""
        targets = {(b.x, b.y) for b in self.buildings}
        targets.update(self.bases.values())
        start = (self.cx, self.cy)   # 중앙광장에서 출발
        seen = {start}
        q = deque([start])
        while q:
            x, y = q.popleft()
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.w and 0 <= ny < self.h and (nx, ny) not in seen \
                        and self._passable(terrain, nx, ny):
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return targets.issubset(seen)

    def place_obstacles(self) -> None:
        target = self._mg["obstacle_pairs"]
        placed = 0
        for _ in range(self._mg["max_place_attempts"]):
            if placed >= target:
                break
            x = self.rng.randint(0, self.w - 1)
            y = self.rng.randint(0, self.h - 1)
            px, py = _sym(x, y)
            if (x, y) == (px, py):
                continue
            if (x, y) in self.occupied or (px, py) in self.occupied:
                continue
            if self.terrain[y][x] == "#" or self.terrain[py][px] == "#":
                continue
            # 잠정 배치 후 연결성 확인, 깨지면 되돌린다(결정적)
            self.terrain[y][x] = "#"
            self.terrain[py][px] = "#"
            if self._all_connected(self.terrain):
                placed += 1
            else:
                self.terrain[y][x] = "."
                self.terrain[py][px] = "."

    # ---- 마감: 지형에 건물/본진 표기 ----
    def finalize(self) -> GameMap:
        for b in self.buildings:
            self.terrain[b.y][b.x] = "B"
        for (bx, by) in self.bases.values():
            self.terrain[by][bx] = "H"
        self.buildings.sort(key=lambda b: b.id)
        return GameMap(self.seed, self.config, self.terrain, self.buildings, self.bases)


def generate(seed: int, config: dict) -> GameMap:
    """시드와 config 로부터 결정적 맵을 생성한다."""
    b = _Builder(seed, config)
    b.place_plaza()
    b.place_bases()
    b.place_building_pairs()
    b.place_obstacles()
    return b.finalize()


def to_state(gmap: GameMap):
    """생성된 맵으로 초기 GameState 를 만든다(엔진 연동)."""
    from engine.state import new_game
    return new_game(
        gmap.config,
        terrain=[row[:] for row in gmap.terrain],
        buildings=[Building(b.id, b.x, b.y, b.btype, b.score) for b in gmap.buildings],
        bases=dict(gmap.bases),
    )
