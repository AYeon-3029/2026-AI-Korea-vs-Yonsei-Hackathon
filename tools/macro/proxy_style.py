"""대리 상대 후보의 스타일(전진 비율 fwd = 20~120턴 W 중 상대 본진 쪽 칸 비율, 40턴 W)과 기준 봇 상대 승점률을 잰다.

실제 9/29 20시 패배 상대: 신촌을못가 fwd 0.26 · 참새튀김기 0.40 · AIKU 0.49 (우리 v14 0.06~0.08). 이런 공세형 대리를 만든다.
사용 (WSL): python3 tools/macro/proxy_style.py --cands p_press,p_raid --base v15 --seeds 73000-73019
"""
from __future__ import annotations

import argparse
import os
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, value  # noqa: E402
from branch import OPPS, parse_range  # noqa: E402


def run(args):
    seed, cand, side, base = args
    c = Agent(*OPPS[cand])
    b = Agent(*OPPS[base]) if base in OPPS else Agent(base)
    g = Game(seed, *((c, b) if side == "Y" else (b, c)))
    op = "K" if side == "Y" else "Y"
    bm, bo = g.state.bases[side], g.state.bases[op]
    man = lambda a, q: abs(a[0] - q[0]) + abs(a[1] - q[1])
    fr, w40 = [], None
    while g.result is None:
        g.step()
        t = g.state.turn
        if 20 <= t <= 120:
            tot = fwd = 0
            for (x, y, tm, k), n in g.state.units.items():
                if tm == side and k == "W":
                    tot += n
                    fwd += n if man((x, y), bo) < man((x, y), bm) else 0
            if tot:
                fr.append(fwd / tot)
        if t == 40:
            w40 = sum(n for (x, y, tm, k), n in g.state.units.items() if tm == side and k == "W")
    return cand, value(g.result, side), float(np.mean(fr)) if fr else 0.0, w40 or 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cands", required=True)
    ap.add_argument("--base", default="v15")
    ap.add_argument("--seeds", default="73000-73019")
    a = ap.parse_args()
    jobs = [(s, c, side, a.base) for s in parse_range(a.seeds) for c in a.cands.split(",") for side in "YK"]
    res = {}
    with Pool(24) as p:
        for c, v, f, w in p.imap_unordered(run, jobs):
            res.setdefault(c, []).append((v, f, w))
    for c, rows in res.items():
        r = np.array(rows)
        print(f"{c:<14} 대 {a.base} 승점률 {r[:, 0].mean():.3f}  fwd {r[:, 1].mean():.2f}  W40 {r[:, 2].mean():.0f}  ({len(r)}경기)")


if __name__ == "__main__":
    main()
