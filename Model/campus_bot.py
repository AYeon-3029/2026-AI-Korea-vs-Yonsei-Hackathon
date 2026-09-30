"""깃발 대항전 봇 스타터 킷 (Python).

프로토콜(규칙서 §12) 파싱/입출력 보일러플레이트. 표준 라이브러리만 사용하며
엔진에 의존하지 않는다(참가자 배포용). 봇은 `decide(view, init) -> list[str]`
함수를 정의하고 `campus_bot.run(decide)` 를 호출하면 된다.

방향 코드: U(y-1) / D(y+1) / L(x-1) / R(x+1)
"""
from __future__ import annotations

import sys
from typing import Callable, Dict, List, Optional, TextIO, Tuple

TEAMS = ("Y", "K")
KINDS = ("F", "W", "S")
DIRS: Dict[str, Tuple[int, int]] = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}


class Init:
    """게임 시작 시 1회 전달되는 고정 정보."""

    def __init__(self, width, height, team, terrain, buildings, bases):
        self.width = width
        self.height = height
        self.team = team                    # 내 팀 ('Y' 또는 'K')
        self.opp = "K" if team == "Y" else "Y"
        self.terrain = terrain              # list[list[str]]  '.','#','B','H'
        self.buildings = buildings          # list[dict] id,x,y,type
        self.bases = bases                  # {'Y':(x,y),'K':(x,y)}

    def in_bounds(self, x, y) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def passable(self, x, y) -> bool:
        return self.in_bounds(x, y) and self.terrain[y][x] != "#"


class View:
    """매 턴 전달되는 현재 상태(내 관점: 미공개 건물 점수는 -1)."""

    def __init__(self, turn, init, my_resource, opp_resource, units, buildings):
        self.turn = turn
        self.init = init
        self.team = init.team
        self.opp = init.opp
        self.my_resource = my_resource
        self.opp_resource = opp_resource
        self.units = units                  # list[dict] team,kind,x,y,count
        self.buildings = buildings          # list[dict] id,x,y,type,owner,stage,score

    def my_units(self, kind: Optional[str] = None):
        return [u for u in self.units
                if u["team"] == self.team and (kind is None or u["kind"] == kind)]

    def building_at(self, x, y):
        for b in self.buildings:
            if b["x"] == x and b["y"] == y:
                return b
        return None


# ------------------------------------------------------------------ 파싱

def parse_init(lines: List[str]) -> Init:
    _, w, h = lines[0].split()
    w, h = int(w), int(h)
    team = lines[1].split()[1]
    terrain = [list(lines[2 + i].split()[1]) for i in range(h)]
    idx = 2 + h
    nb = int(lines[idx].split()[1]); idx += 1
    buildings = []
    for _ in range(nb):
        bid, x, y, bt = lines[idx].split()
        buildings.append({"id": int(bid), "x": int(x), "y": int(y), "type": bt})
        idx += 1
    bases = {}
    for _ in range(2):
        _, t, x, y = lines[idx].split()
        bases[t] = (int(x), int(y))
        idx += 1
    return Init(w, h, team, terrain, buildings, bases)


def parse_turn(lines: List[str], init: Init) -> View:
    turn = int(lines[0].split()[1])
    _, own, opp = lines[1].split()
    k = int(lines[2].split()[1])
    idx = 3
    units = []
    for _ in range(k):
        t, kind, x, y, c = lines[idx].split()
        units.append({"team": t, "kind": kind, "x": int(x), "y": int(y), "count": int(c)})
        idx += 1
    nb = int(lines[idx].split()[1]); idx += 1
    buildings = []
    for _ in range(nb):
        bid, x, y, bt, owner, stage, score = lines[idx].split()
        buildings.append({"id": int(bid), "x": int(x), "y": int(y), "type": bt,
                          "owner": owner, "stage": int(stage), "score": int(score)})
        idx += 1
    return View(turn, init, int(own), int(opp), units, buildings)


# ------------------------------------------------------------------ 입출력 루프

def read_block(stream: TextIO) -> Optional[List[str]]:
    """END 로 끝나는 한 블록을 읽어 반환. EOF 면 None."""
    lines: List[str] = []
    for line in stream:
        line = line.rstrip("\n")
        if line == "END":
            return lines
        lines.append(line)
    return None


def run(decide: Callable[[View, Init], List[str]],
        stream_in: Optional[TextIO] = None, stream_out: Optional[TextIO] = None) -> None:
    si = stream_in or sys.stdin
    so = stream_out or sys.stdout
    init_lines = read_block(si)
    if init_lines is None:
        return
    init = parse_init(init_lines)
    while True:
        block = read_block(si)
        if block is None:
            break
        view = parse_turn(block, init)
        for cmd in decide(view, init):
            so.write(cmd + "\n")
        so.write("END\n")
        so.flush()
