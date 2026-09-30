"""v19 의 F 위험 탈출(f_goal_flee) 부작용 점검: 같은 목표에서 몇 번이나 비키는지(맴돌기), F 가 점령 없이 보내는 턴.

사용 (WSL): python3 tools/macro/fdither.py --seeds 104000-104009 [--params '{"f_goal_flee":1,"f_trap_min":true}']
dev18(사유 기록 FDBG) 으로 돌린다. 기본 params = v19 값.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, value  # noqa: E402
from branch import OPPS, PUSH_POOL, REAL_POOL, XOPPS, parse_range  # noqa: E402


def run(args):
    seed, opp, side, params = args
    me = Agent("dev18", params)
    me.mod.FDBG = log = []
    o = Agent(*OPPS[opp])
    g = Game(seed, *((me, o) if side == "Y" else (o, me)))
    g.run()
    flee = [r for r in log if r[3] == "flee"]
    per_goal = Counter(tuple(r[1]) for r in flee)          # 같은 목표 칸에서 비킨 횟수
    return {"opp": opp, "v": value(g.result, side), "flee": len(flee), "max_same": max(per_goal.values(), default=0),
            "goals3": sum(1 for c in per_goal.values() if c >= 3), "fturns": len(log),
            "late": sum(1 for r in flee if r[0] > 140)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", required=True)
    p.add_argument("--params", default='{"f_goal_flee": 1, "f_trap_min": true}')
    p.add_argument("--opps", default=",".join(REAL_POOL + PUSH_POOL + XOPPS))
    p.add_argument("--workers", type=int, default=6)
    a = p.parse_args()
    jobs = [(s, o, side, json.loads(a.params)) for s in parse_range(a.seeds) for o in a.opps.split(",") for side in "YK"]
    with Pool(a.workers) as pool:
        rows = pool.map(run, jobs, chunksize=2)
    n = len(rows)
    print(f"{n}경기  비키기/경기 {np.mean([r['flee'] for r in rows]):.2f}  같은 목표 최대 {np.mean([r['max_same'] for r in rows]):.2f}"
          f" (최댓값 {max(r['max_same'] for r in rows)})  3회+ 비킨 목표/경기 {np.mean([r['goals3'] for r in rows]):.2f}"
          f"  141턴+ 비키기 {np.mean([r['late'] for r in rows]):.2f}")
    for lab, sel in (("승", 1), ("무", 0.5), ("패", 0)):
        rs = [r for r in rows if r["v"] == sel]
        if rs:
            print(f"  {lab} {len(rs)}경기 비키기 {np.mean([r['flee'] for r in rs]):.2f} 같은 목표 최대 {np.mean([r['max_same'] for r in rs]):.2f}")


if __name__ == "__main__":
    main()
