"""맵 ASCII 렌더 (사람 확인용).

건물은 종류 약자 + 점수로 표시. 본진은 YH/KH, 장애물은 ##, 평지는 ·.
"""
from __future__ import annotations

from .generator import GameMap

ABBR = {
    "PLAZA": "PLZ", "HALL": "HAL", "STATION": "STA", "LIBRARY": "LIB",
    "ENG": "ENG", "HOSPITAL": "HOS", "WATCH": "WAT", "DEPOT": "DEP",
}
LEGEND = ("PLZ 중앙광장 · HAL 학생회관 · STA 역 · LIB 도서관 · "
          "ENG 공학관 · HOS 병원 · WAT 감시거점 · DEP 보급소  (약자 뒤 숫자=점수)")


def _cell(gmap: GameMap, x: int, y: int) -> str:
    for b in gmap.buildings:
        if b.x == x and b.y == y:
            return f"{ABBR[b.btype]}{b.score}"
    for team, (bx, by) in gmap.bases.items():
        if (x, y) == (bx, by):
            return f"{team}H"
    if gmap.terrain[y][x] == "#":
        return "##"
    return "·"


def render_ascii(gmap: GameMap) -> str:
    lines = [
        f"seed={gmap.seed}   총점(홀수)={gmap.total_score()}   "
        f"본진 Y{gmap.bases['Y']} K{gmap.bases['K']}",
        LEGEND,
        "     신촌(0-4)          중앙(5-9)          안암(10-14)",
        "    " + "".join(f"{x:>5}" for x in range(gmap.config["grid"]["width"])),
    ]
    for y in range(gmap.config["grid"]["height"]):
        row = f"{y:>2}  " + "".join(
            f"{_cell(gmap, x, y):<5}" for x in range(gmap.config["grid"]["width"])
        )
        lines.append(row)
    return "\n".join(lines)
