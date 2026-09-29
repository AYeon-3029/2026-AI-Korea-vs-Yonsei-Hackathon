"""실제 리플레이의 학생회관·공학관 소유 흐름과 그 주변 병력(체비쇼프 R 칸 안 W·F)을 턴별로 찍는다.

칸: 소유(K 우리/y 상대/. 중립) + 주변 '우리W:상대W' + 우리F/상대F 가 건물 위에 있으면 F/f.
사용 (WSL): python3 tools/replay_eco.py <replay.json> [시작턴-끝턴] [--R 2] [--types HALL,ENG]
"""
from __future__ import annotations

import json
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    R = 2
    types = ("HALL", "ENG")
    for i, a in enumerate(sys.argv):
        if a == "--R":
            R = int(sys.argv[i + 1])
        if a == "--types":
            types = tuple(sys.argv[i + 1].split(","))
    args = [a for a in args if not a.isdigit() or "-" in a]
    r = json.load(open(args[0], encoding="utf-8"))
    lo, hi = 1, 160
    if len(args) > 1:
        lo, hi = map(int, args[1].split("-"))
    me = r["side"]
    T = [t for t in r["turns"] if t.get("observation")]
    b0 = [b for b in T[0]["observation"]["buildings"] if b["type"] in types]
    print("turn  W(우리:상대)  " + "  ".join(f"{b['type'][:2]}({b['x']},{b['y']})" for b in b0))
    for t in T:
        o = t["observation"]
        if not lo <= o["turn"] <= hi:
            continue
        own = {b["id"]: b["owner"] for b in o["buildings"]}
        tw = {True: 0, False: 0}
        for team, kind, x, y, n in o["units"]:
            if kind == "W":
                tw[team == me] += n
        cols = []
        for b in b0:
            mw = ew = 0
            f = ""
            for team, kind, x, y, n in o["units"]:
                d = max(abs(x - b["x"]), abs(y - b["y"]))
                if kind == "W" and d <= R:
                    if team == me:
                        mw += n
                    else:
                        ew += n
                if kind == "F" and d == 0:
                    f += "F" if team == me else "f"
            ow = own[b["id"]]
            oc = "K" if ow == me else "." if ow in ("N", None) else "y"
            cols.append(f"{oc}{mw:>3}:{ew:<3}{f:<2}")
        print(f"{o['turn']:>4}  {tw[True]:>3}:{tw[False]:<3}     " + "  ".join(f"{c:<10}" for c in cols))


if __name__ == "__main__":
    main()
