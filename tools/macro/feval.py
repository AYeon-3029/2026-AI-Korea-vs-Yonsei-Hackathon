"""학습한 깃발병 배정 보정(fanalyze.py --save)을 매 배정에 적용한 v13h 를 v13 과 같은 조건에서 쌍 비교한다.

사용 (WSL): python3 tools/macro/feval.py out/macro/fw.json --seeds 25000-25199 [--scale 1.0]
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
from sim import Agent, play, value  # noqa: E402
from branch import OPPS, POOL, parse_range  # noqa: E402


class Scorer:
    """후보 점수 = log(v13 점수) + scale·(w·φ/σ + w'·φ·t/σ'). v13 선호 상위 top 개 후보 안에서만 고른다."""

    def __init__(self, W, scale=1.0, top=8):
        w, sd = np.array(W["w"]), np.array(W["sd"])
        k = len(w) // 2
        self.a, self.b = w[:k] / sd[:k], w[k:] / sd[k:]
        self.scale, self.top = scale, top

    def __call__(self, view, cands, feat):
        best, bi = None, None
        for i, c in enumerate(cands[:self.top]):
            f = np.array(feat(*c[1:5]))
            t = f[2]
            s = f[0] + self.scale * (f[1:] @ self.a + t * (f[1:] @ self.b))
            if best is None or s > best + 1e-12:
                best, bi = s, i
        return None if bi == 0 else bi


def job(args):
    seed, opp, side, W, scale = args
    ver, params = OPPS[opp]
    out = []
    for hooked in (False, True):
        me = Agent("v13h")
        if hooked:
            me.hook = Scorer(W, scale)
        other = Agent(ver, params)
        r = play(seed, *((me, other) if side == "Y" else (other, me)))
        out.append(value(r, side))
    return opp, out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("weights")
    p.add_argument("--seeds", required=True)
    p.add_argument("--opps", default=",".join(POOL + ["v12", "srv13_press", "srv13_eco"]))
    p.add_argument("--scale", type=float, default=1.0)
    p.add_argument("--workers", type=int, default=24)
    a = p.parse_args()
    W = json.load(open(a.weights))
    jobs = [(s, o, side, W, a.scale) for s in parse_range(a.seeds) for o in a.opps.split(",") for side in "YK"]
    t0 = time.time()
    res = {}
    with Pool(a.workers) as pool:
        for opp, (b, h) in pool.imap_unordered(job, jobs, chunksize=2):
            res.setdefault(opp, []).append((b, h))
    allv = np.array([x for v in res.values() for x in v])
    d = allv[:, 1] - allv[:, 0]
    print(f"{len(allv)}경기 쌍  v13 {allv[:, 0].mean():.3f}  보정 {allv[:, 1].mean():.3f}  차 {d.mean():+.4f} ± {d.std() / np.sqrt(len(d)):.4f}"
          f"  (다름 {np.mean(d != 0):.2f})  {time.time() - t0:.0f}s")
    for o, v in sorted(res.items()):
        v = np.array(v)
        print(f"  {o:<12} v13 {v[:, 0].mean():.3f}  보정 {v[:, 1].mean():.3f}")


if __name__ == "__main__":
    main()
