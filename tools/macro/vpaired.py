"""서로 다른 두 봇 버전(A, B)을 같은 시드·상대·진영에서 쌍 비교한다(paired.py 는 같은 버전의 파라미터 비교).

사용 (WSL): python3 tools/macro/vpaired.py --a v16 --b cv-3 --seeds 131000-131099 --opps m16_야구사랑했단,... [--pa '{}'] [--pb '{}']
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, value  # noqa: E402
from branch import OPPS, parse_range  # noqa: E402


def one(seed, opp, side, ver, params):
    me = Agent(ver, params)
    o = Agent(*OPPS[opp])
    g = Game(seed, *((me, o) if side == "Y" else (o, me)))
    g.run()
    return value(g.result, side), me.errors


def job(args):
    seed, opp, side, a, pa, b, pb = args
    return opp, one(seed, opp, side, a, pa), one(seed, opp, side, b, pb)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--pa", default="{}")
    p.add_argument("--pb", default="{}")
    p.add_argument("--seeds", required=True)
    p.add_argument("--opps", required=True)
    p.add_argument("--workers", type=int, default=24)
    a = p.parse_args()
    jobs = [(s, o, side, a.a, json.loads(a.pa), a.b, json.loads(a.pb))
            for s in parse_range(a.seeds) for o in a.opps.split(",") for side in "YK"]
    t0 = time.time()
    res, err = {}, 0
    with Pool(a.workers) as pool:
        for opp, ra, rb in pool.imap_unordered(job, jobs, chunksize=2):
            res.setdefault(opp, []).append((ra[0], rb[0]))
            err += ra[1] + rb[1]
    allv = np.array([x for v in res.values() for x in v])
    d = allv[:, 1] - allv[:, 0]
    print(f"{len(allv)}쌍  {a.a} {allv[:, 0].mean():.3f}  {a.b} {allv[:, 1].mean():.3f}  차 {d.mean():+.4f} ± {d.std() / np.sqrt(len(d)):.4f}"
          f"  예외 {err}  {time.time() - t0:.0f}s")
    for o, v in sorted(res.items()):
        v = np.array(v)
        print(f"  {o:<28} {a.a} {v[:, 0].mean():.3f}  {a.b} {v[:, 1].mean():.3f}  {v[:, 1].mean() - v[:, 0].mean():+.3f}")


if __name__ == "__main__":
    main()
