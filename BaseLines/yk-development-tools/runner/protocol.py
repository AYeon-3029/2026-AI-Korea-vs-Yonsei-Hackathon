"""봇 프로토콜 직렬화/파싱 (SPEC 12절).

러너 계층 전용(엔진과 I/O 분리, CLAUDE.md 원칙 4). 관점별 필터링 필수:
각 봇에게는 자기 팀이 공개한 건물 점수만 전달하고 미공개는 -1.
그 외 정보(지형/유닛/자원/소유권/단계/건물종류)는 전부 공개.
"""
from __future__ import annotations

from typing import List

from engine.commands import Move, Move2, Priority, Spawn, Tele
from engine.state import GameState

_TEAM_ORDER = {"Y": 0, "K": 1}
_KIND_ORDER = {"F": 0, "W": 1, "S": 2}


def _opp(team: str) -> str:
    return "K" if team == "Y" else "Y"


def serialize_init(state: GameState, team: str) -> str:
    """최초 1회 입력 블록 (INIT ... END)."""
    w = state.config["grid"]["width"]
    h = state.config["grid"]["height"]
    lines = [f"INIT {w} {h}", f"TEAM {team}"]
    for row in state.terrain:
        lines.append("MAP " + "".join(row))
    blds = state.sorted_buildings()
    lines.append(f"BUILDINGS {len(blds)}")
    for b in blds:
        lines.append(f"{b.id} {b.x} {b.y} {b.btype}")
    lines.append(f"BASE Y {state.bases['Y'][0]} {state.bases['Y'][1]}")
    lines.append(f"BASE K {state.bases['K'][0]} {state.bases['K'][1]}")
    lines.append("END")
    return "\n".join(lines) + "\n"


def _sorted_units(state: GameState):
    return sorted(
        state.units.items(),
        key=lambda kv: (_TEAM_ORDER[kv[0][2]], _KIND_ORDER[kv[0][3]], kv[0][1], kv[0][0]),
    )


def serialize_turn(state: GameState, team: str, turn: int) -> str:
    """매 턴 입력 블록. team 관점(점수 필터링)으로 생성."""
    opp = _opp(team)
    lines = [
        f"TURN {turn}",
        f"RESOURCE {state.resources[team]} {state.resources[opp]}",
    ]
    units = _sorted_units(state)
    lines.append(f"UNITS {len(units)}")
    for (x, y, t, k), c in units:
        lines.append(f"{t} {k} {x} {y} {c}")
    blds = state.sorted_buildings()
    lines.append(f"BUILDINGS {len(blds)}")
    for b in blds:
        score = b.score if b.id in state.revealed[team] else -1   # 관점별 필터링
        lines.append(f"{b.id} {b.x} {b.y} {b.btype} {b.owner} {b.stage} {score}")
    lines.append("END")
    return "\n".join(lines) + "\n"


KINDS = ("F", "W", "S")
DIRS = ("U", "D", "L", "R")


def parse_commands(lines: List[str]) -> List[object]:
    """봇 출력 라인을 엔진 명령 객체로 파싱. 잘못된 줄은 그 줄만 무시(SPEC 5절).

    **문법 검증은 여기서 전부 끝낸다**(토큰 수·병종·방향·인원). 유닛 존재 여부,
    좌표 통행 가능 여부, 자원 충분 여부 등 상태 의존 검증은 엔진이 담당한다.
    형식이 조금이라도 어긋나면 **그 줄 전체를 무시**한다 — 일부만 해석해 실행하면
    봇이 의도하지 않은 동작을 하게 된다(예: `MOVE2 x y W ...` 가 정찰병을 움직임).
    """
    cmds: List[object] = []
    for raw in lines:
        tok = raw.split()
        if not tok:
            continue
        try:
            cmd = _parse_line(tok)
        except (ValueError, IndexError):
            continue   # 형식 오류 → 무시
        if cmd is not None:
            cmds.append(cmd)
    return cmds


def _pos(s: str) -> int:
    """양의 정수만 허용(인원 수). 0·음수·비정수는 ValueError."""
    n = int(s)
    if n <= 0:
        raise ValueError(f"인원은 양의 정수여야 함: {s}")
    return n


def _kind(s: str) -> str:
    if s not in KINDS:
        raise ValueError(f"알 수 없는 병종: {s}")
    return s


def _dir(s: str) -> str:
    if s not in DIRS:
        raise ValueError(f"알 수 없는 방향: {s}")
    return s


def _parse_line(tok: List[str]):
    op = tok[0]
    n = len(tok)
    if op == "SPAWN":
        # SPAWN <kind> <count> [x y]  — 정확히 3 또는 5 토큰
        if n == 3:
            return Spawn(_kind(tok[1]), _pos(tok[2]))
        if n == 5:
            return Spawn(_kind(tok[1]), _pos(tok[2]), int(tok[3]), int(tok[4]))
        return None
    if op == "MOVE":
        # MOVE <x> <y> <kind> <count> <dir>  — 정확히 6 토큰
        if n != 6:
            return None
        return Move(int(tok[1]), int(tok[2]), _kind(tok[3]), _pos(tok[4]), _dir(tok[5]))
    if op == "MOVE2":
        # MOVE2 <x> <y> S <count> <dir1> <dir2>  — 정확히 7 토큰, 병종은 반드시 S
        if n != 7 or tok[3] != "S":
            return None
        return Move2(int(tok[1]), int(tok[2]), _pos(tok[4]), _dir(tok[5]), _dir(tok[6]))
    if op == "TELE":
        # TELE <x> <y> <kind> <count> <tx> <ty>  — 정확히 7 토큰
        if n != 7:
            return None
        return Tele(int(tok[1]), int(tok[2]), _kind(tok[3]), _pos(tok[4]),
                    int(tok[5]), int(tok[6]))
    if op == "PRIORITY":
        # PRIORITY x1 y1 x2 y2 ...  — 좌표는 반드시 짝수 개
        if (n - 1) % 2 != 0:
            return None
        nums = [int(t) for t in tok[1:]]
        return Priority([(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)])
    return None   # END·알 수 없는 명령 → 무시
