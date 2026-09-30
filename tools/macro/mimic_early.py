"""실제 맵 재대결의 초반 건물 점령 순서를 보여 준다(누가 어떤 건물을 몇 턴에 가져갔는지, F 위치).

사용 (WSL): python3 tools/macro/mimic_early.py 'Real Match Replay/V16_0930_8am/vs신촌을못가.json' --ours cv-3 --attacker cv-3 [--upto 40]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import mimic  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replay")
    ap.add_argument("--ours", default="cv-3")
    ap.add_argument("--params", default="{}")
    ap.add_argument("--attacker", default="cv-3")
    ap.add_argument("--upto", type=int, default=40)
    a = ap.parse_args()
    mimic.ATTACKER = a.attacker
    d = os.path.basename(os.path.dirname(a.replay)).split("_")
    tag = f"{d[0]}_{d[1]}" + ("" if a.attacker == "dev11" else f"-{a.attacker}")
    pj = os.path.join(mimic.ROOT, "out/tune/mimic", tag, os.path.basename(a.replay))
    params = json.load(open(pj, encoding="utf-8"))
    g, me, op = mimic.init_game(a.replay, a.ours, json.loads(a.params), params)
    s = g.state
    print(f"우리 {me} 본진 {s.bases[me]} · 상대 {op} 본진 {s.bases[op]}")
    print("건물:", " ".join(f"{b.btype[:4]}{(b.x, b.y)}" for b in sorted(s.buildings.values(), key=lambda b: (b.y, b.x))))
    prev = {i: "N" for i in s.buildings}
    while g.result is None and g.state.turn < a.upto:
        g.step()
        s = g.state
        ev = []
        for i, b in s.buildings.items():
            if b.owner != prev[i]:
                who = "우" if b.owner == me else "적" if b.owner == op else "N"
                ev.append(f"{b.btype[:4]}{(b.x, b.y)}→{who}")
            prev[i] = b.owner
        Wm = sum(n for (x, y, t, k), n in s.units.items() if t == me and k == "W")
        Wo = sum(n for (x, y, t, k), n in s.units.items() if t == op and k == "W")
        Fm = [(x, y) for (x, y, t, k), n in s.units.items() if t == me and k == "F" for _ in range(n)]
        nb = sum(1 for b in s.buildings.values() if b.owner == me), sum(1 for b in s.buildings.values() if b.owner == op)
        if ev or s.turn % 5 == 0:
            print(f"{s.turn:3d}턴 W {Wm:3d}:{Wo:3d} 건물 {nb[0]}:{nb[1]} 자원 {s.resources[me]}:{s.resources[op]} 우리F {sorted(Fm)}  {' '.join(ev)}")


if __name__ == "__main__":
    main()
