"""두 버전 직접 대결: 시드마다 진영을 바꿔 두 번. A 기준 승/무/패·종료 사유·재탈환 발동 영향.
사용 (WSL): python3 tools/macro/h2h.py --a v20 --b cv-3 --seeds 170000-170499
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, value  # noqa: E402
from branch import parse_range  # noqa: E402


def one(args):
    seed, side, a, pa, b, pb = args
    A, B = Agent(a, pa), Agent(b, pb)
    g = Game(seed, *((A, B) if side == "Y" else (B, A)))
    g.run()
    r = g.result
    return seed, side, value(r, side), r["reason"], g.state.turn, A.errors + B.errors


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--pa", default="{}")
    p.add_argument("--pb", default="{}")
    p.add_argument("--seeds", required=True)
    p.add_argument("--workers", type=int, default=20)
    x = p.parse_args()
    jobs = [(s, side, x.a, json.loads(x.pa), x.b, json.loads(x.pb)) for s in parse_range(x.seeds) for side in "YK"]
    t0 = time.time()
    with Pool(x.workers) as pool:
        rows = pool.map(one, jobs, chunksize=4)
    n = len(rows)
    v = [r[2] for r in rows]
    mean = sum(v) / n
    se = (sum((t - mean) ** 2 for t in v) / (n - 1)) ** 0.5 / n ** 0.5
    c = Counter("승" if t == 1 else "무" if t == 0.5 else "패" for t in v)
    print(f"{x.a} 대 {x.b}  {n}경기  {x.a} 승점 {mean:.3f} ± {se:.3f}  승 {c['승']} 무 {c['무']} 패 {c['패']}  예외 {sum(r[5] for r in rows)}  {time.time() - t0:.0f}s")
    for side in "YK":
        vs = [r[2] for r in rows if r[1] == side]
        print(f"  {x.a}={side}: 승점 {sum(vs) / len(vs):.3f}")
    rs = Counter((("승" if r[2] == 1 else "무" if r[2] == 0.5 else "패"), r[3]) for r in rows)
    print("  종료:", "  ".join(f"{k[0]}/{k[1]}:{n_}" for k, n_ in rs.most_common()))
    # 시드별(두 진영 합) 결과
    by = {}
    for r in rows:
        by.setdefault(r[0], []).append(r[2])
    sc = Counter(sum(t) for t in by.values())
    print("  시드별 두 판 합(2=둘 다 승, 1=반반):", dict(sorted(sc.items())))


if __name__ == "__main__":
    main()
