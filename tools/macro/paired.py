"""같은 봇 버전의 두 파라미터 설정(A = 기준, B = 변경)을 같은 시드·상대·진영에서 쌍 비교한다(한 프로세스, 빠름).

사용 (WSL): python3 tools/macro/paired.py --ver dev --b '{"tele_queue": true}' --seeds 30000-30199
출력: 상대별·전체 승점률, 쌍 차이 ± 표준오차, 40턴 이후 역 위에 서 있는 아군 W 비율.
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
from branch import OPPS, POOL, XOPPS, parse_range  # noqa: E402


def one(seed, opp, side, ver, params):
    me = Agent(ver, params)
    o = Agent(*OPPS[opp])
    g = Game(seed, *((me, o) if side == "Y" else (o, me)))
    fr = []
    while g.result is None:
        g.step()
        if g.state.turn >= 40:
            st = {(b.x, b.y) for b in g.state.buildings.values() if b.btype == "STATION" and b.owner == side}
            tot = on = 0
            for (x, y, t, k), c in g.state.units.items():
                if t == side and k == "W":
                    tot += c
                    on += c if (x, y) in st else 0
            if tot:
                fr.append(on / tot)
    return value(g.result, side), (float(np.mean(fr)) if fr else 0.0), me.errors


def job(args):
    seed, opp, side, ver, pa, pb = args
    return opp, one(seed, opp, side, ver, pa), one(seed, opp, side, ver, pb)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ver", default="dev")
    p.add_argument("--a", default="{}")
    p.add_argument("--b", required=True)
    p.add_argument("--seeds", required=True)
    p.add_argument("--opps", default=",".join(POOL + ["v12", "srv13_press", "srv13_eco"] + XOPPS))
    p.add_argument("--workers", type=int, default=24)
    a = p.parse_args()
    pa, pb = json.loads(a.a), json.loads(a.b)
    jobs = [(s, o, side, a.ver, pa, pb) for s in parse_range(a.seeds) for o in a.opps.split(",") for side in "YK"]
    t0 = time.time()
    res = {}
    err = 0
    with Pool(a.workers) as pool:
        for opp, ra, rb in pool.imap_unordered(job, jobs, chunksize=2):
            res.setdefault(opp, []).append((ra[0], rb[0], ra[1], rb[1]))
            err += ra[2] + rb[2]
    allv = np.array([x for v in res.values() for x in v])
    d = allv[:, 1] - allv[:, 0]
    print(f"{len(allv)}쌍  A {allv[:, 0].mean():.3f}  B {allv[:, 1].mean():.3f}  차 {d.mean():+.4f} ± {d.std() / np.sqrt(len(d)):.4f}"
          f"  (다름 {np.mean(d != 0):.2f})  역 위 W A {allv[:, 2].mean():.3f} B {allv[:, 3].mean():.3f}  예외 {err}  {time.time() - t0:.0f}s")
    for o, v in sorted(res.items()):
        v = np.array(v)
        dd = v[:, 1] - v[:, 0]
        print(f"  {o:<12} A {v[:, 0].mean():.3f}  B {v[:, 1].mean():.3f}  {dd.mean():+.3f}  역 위 W {v[:, 2].mean():.2f}→{v[:, 3].mean():.2f}")


if __name__ == "__main__":
    main()
