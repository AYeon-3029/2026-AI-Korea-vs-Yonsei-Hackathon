"""실제 리플레이 한 턴을 봇에 다시 넣고 F 목표 점수(가치 · 위험 배율 · 최종 / 가장 가까운 F 거리)와 F 배정을 본다.

사용 (WSL): python3 tools/macro/ftarget.py <replay.json> --turns 70,80 [--ver dev20] [--params '{}'] [--top 8]
봇 모듈에 TDBG·FDBG 가 있어야 한다(Model/history/dev20).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent  # noqa: E402
from realstate import restore  # noqa: E402
from runner.protocol import serialize_init, serialize_turn  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replay")
    ap.add_argument("--ver", default="dev20")
    ap.add_argument("--params", default="{}")
    ap.add_argument("--turns", required=True)
    ap.add_argument("--top", type=int, default=8)
    a = ap.parse_args()
    want = {int(x) for x in a.turns.split(",")}
    ag = Agent(a.ver, json.loads(a.params))
    m = ag.mod
    for t in range(1, max(want) + 1):
        rs = restore(a.replay, max(1, t - 1))
        if rs is None:
            continue
        s, me, _ = rs
        s.turn = t - 1
        if t == 1:
            s.units.clear()
            s.resources = {"Y": 10, "K": 10}
            for b in s.buildings.values():
                b.owner, b.stage = "N", 0
        if ag.init is None:
            ag.start(serialize_init(s, me))
        m.TDBG = [] if t in want else None
        m.FDBG = [] if t in want else None
        out = ag.decide(serialize_turn(s, me, t))
        if t in want:
            F = sorted((x, y, n) for tm, x, y, k, n in [(k[2], k[0], k[1], k[3], c) for k, c in s.units.items()] if tm == me and k == "F")
            print(f"== {t}턴  우리 F {F}")
            for row in sorted(m.TDBG, key=lambda r: -r[6])[:a.top]:
                _, xy, ty, enemy, v, rm, fin, fd = row
                print(f"   {ty:<8}{xy} {'적' if enemy else '  '} 가치 {v:6.2f} × 위험 {rm:.3f} = {fin:6.2f}  F거리 {fd}")
            for row in m.FDBG:
                print("   F", row[1], "→", row[2], row[3])


if __name__ == "__main__":
    main()
