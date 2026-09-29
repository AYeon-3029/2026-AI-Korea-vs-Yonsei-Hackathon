"""v15 관문: ① 기본값 동치(v15 {} == dev11 + s8 #153 반올림 값, 같은 경기) ② 거울전(v15 대 v15) 전부 무승부.

사용 (WSL): python3 tools/macro/gate_v15.py --seeds 70000-70039
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, margin, value  # noqa: E402
from branch import OPPS, REAL_POOL, parse_range  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
PR = json.load(open(os.path.join(ROOT, "out/tune/s8/t153_r.json")))


def eq(args):
    seed, opp, side = args
    out = []
    for me in (Agent("v15"), Agent("dev11", PR)):
        o = Agent(*OPPS[opp])
        g = Game(seed, *((me, o) if side == "Y" else (o, me)))
        g.run()
        out.append((g.result, round(margin(g, side), 6), me.errors))
    return out[0] == out[1], out[0][2] + out[1][2]


def mirror(seed):
    g = Game(seed, Agent("v15"), Agent("v15"))
    g.run()
    return value(g.result, "Y")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", default="70000-70039")
    a = p.parse_args()
    seeds = parse_range(a.seeds)
    with Pool(24) as pool:
        r = pool.map(eq, [(s, o, side) for s in seeds for o in REAL_POOL for side in "YK"], chunksize=2)
        print(f"동치 {sum(x[0] for x in r)}/{len(r)} · 예외 {sum(x[1] for x in r)}")
        m = pool.map(mirror, seeds)
        print(f"거울전 무승부 {sum(v == 0.5 for v in m)}/{len(m)}")


if __name__ == "__main__":
    main()
