"""실제 리플레이 한 턴을 격자로 찍는다(우리 = 대문자 쪽, 상대 = 소문자 쪽).

칸 표기: 건물 2글자(종류 + 소유 k/y/.) + 아군 'W수[F수]' / 상대 'w수[f수]'.
건물 종류: P 광장 H 학생회관 L 도서관 E 공학관 O 병원 T 역 V 방송국 D 보급소, 본진 '##'.

사용 (WSL): python3 tools/replay_view.py <replay.json> <턴> [<턴> ...] [--cmd]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

TY = {"PLAZA": "P", "HALL": "H", "LIBRARY": "L", "ENG": "E", "HOSPITAL": "O", "STATION": "T", "WATCH": "V", "DEPOT": "D"}


def load(path):
    r = json.load(open(path, encoding="utf-8"))
    T = {t["observation"]["turn"]: t for t in r["turns"] if t.get("observation")}
    return r, T


def render(r, t, show_cmd=False):
    me = r["side"]
    o = t["observation"]
    terr = o["map"]
    bl = {(b["x"], b["y"]): b for b in o["buildings"]}
    cells = defaultdict(lambda: defaultdict(int))
    tot = defaultdict(int)
    for team, kind, x, y, n in o["units"]:
        cells[(x, y)][(team == me, kind)] += n
        tot[(team == me, kind)] += n
    res = o.get("resources", {})
    print(f"== turn {o['turn']}  우리 W{tot[(True, 'W')]} F{tot[(True, 'F')]}  상대 W{tot[(False, 'W')]} F{tot[(False, 'F')]}"
          f"  자원 {res}  점수 {o.get('scores')}")
    W = 10
    print("   " + "".join(f"{x:^{W}}" for x in range(15)))
    for y in range(15):
        row = []
        for x in range(15):
            ch = terr[y][x]
            if ch == "#":
                s = "  ######  "
            else:
                b = bl.get((x, y))
                if ch == "H":
                    bs = "##"
                elif b:
                    ow = b["owner"]
                    bs = TY.get(b["type"], "?") + ("K" if ow == me else "y" if ow not in ("N", None) else ".")
                else:
                    bs = "  "
                c = cells.get((x, y), {})
                a = ""
                if c.get((True, "W")) or c.get((True, "F")):
                    a = (str(c.get((True, "W"), "")) or "") + ("F" + str(c[(True, "F")]) if c.get((True, "F")) else "")
                e = ""
                if c.get((False, "W")) or c.get((False, "F")):
                    e = (str(c.get((False, "W"), "")) or "") + ("f" + str(c[(False, "F")]) if c.get((False, "F")) else "")
                u = a + ("|" + e if e else "")
                s = f"{bs}{u:<8}"[:W]
            row.append(s)
        print(f"{y:>2} " + "".join(f"{s:<{W}}" for s in row))
    if show_cmd:
        print("  명령:", "; ".join((t.get("command") or {}).get("lines", [])))
    ev = o.get("events")
    if ev:
        print("  이벤트:", ev if len(str(ev)) < 600 else str(ev)[:600])


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    r, T = load(args[0])
    for a in args[1:]:
        if "-" in a:
            lo, hi = map(int, a.split("-"))
            ts = range(lo, hi + 1)
        else:
            ts = [int(a)]
        for k in ts:
            if k in T:
                render(r, T[k], "--cmd" in sys.argv)
