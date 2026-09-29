"""새 버전 관문: ① 기본값 동치(<ver> {} == <dev> + <ver> 의 P 중 params 키 값, 같은 경기) ② 거울전(<ver> 대 <ver>) 전부 무승부.

사용 (WSL): python3 tools/macro/gate_ver.py --ver v17 --dev dev15 --params out/tune/s9/t258.json --seeds 85900-85939
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, margin, module, value  # noqa: E402
from branch import OPPS, REAL_POOL, parse_range  # noqa: E402

A = {}


def eq(args):
    seed, opp, side = args
    out = []
    for me in (Agent(A["ver"]), Agent(A["dev"], A["pr"])):
        o = Agent(*OPPS[opp])
        g = Game(seed, *((me, o) if side == "Y" else (o, me)))
        g.run()
        out.append((g.result, round(margin(g, side), 6), me.errors))
    return out[0] == out[1], out[0][2] + out[1][2]


def mirror(seed):
    g = Game(seed, Agent(A["ver"]), Agent(A["ver"]))
    g.run()
    return value(g.result, "Y")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ver", required=True)
    p.add_argument("--dev", required=True)
    p.add_argument("--params", required=True)
    p.add_argument("--seeds", default="85900-85939")
    p.add_argument("--workers", type=int, default=8)
    a = p.parse_args()
    keys = json.load(open(a.params))
    P = module(a.ver).P
    A.update(ver=a.ver, dev=a.dev, pr={k: P[k] for k in keys})
    seeds = parse_range(a.seeds)
    with Pool(a.workers, initializer=A.update, initargs=(dict(A),)) as pool:
        r = pool.map(eq, [(s, o, side) for s in seeds for o in REAL_POOL for side in "YK"], chunksize=2)
        print(f"동치 {sum(x[0] for x in r)}/{len(r)} · 예외 {sum(x[1] for x in r)}", flush=True)
        m = pool.map(mirror, seeds)
        print(f"거울전 무승부 {sum(v == 0.5 for v in m)}/{len(m)}")


if __name__ == "__main__":
    main()
