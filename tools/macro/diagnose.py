"""한 봇의 승·패 경기를 지표로 비교해 어디서 지는지 본다(한 프로세스 시뮬레이터).

지표: 결과·종료 방식, 누적 수입 차, W 생산 차(= 살아 있는 W + 상쇄 손실, 양쪽 손실이 같다), 경제 건물 평균 보유,
      자원 상한 낭비, F 손실(생산 − 생존), 100턴 점수 차, 건물 종류별 상실 횟수.

사용 (WSL): python3 tools/macro/diagnose.py --ver v14 --seeds 42000-42039
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
from branch import OPPS, parse_range  # noqa: E402
from engine.pipeline import team_score  # noqa: E402

OPPS["v14"] = ("v14", {})


def run(args):
    seed, opp, side, ver, params = args
    me = Agent(ver, params)
    o = Agent(*OPPS[opp])
    g = Game(seed, *((me, o) if side == "Y" else (o, me)))
    op = "K" if side == "Y" else "Y"
    inc = {side: 0, op: 0}
    eco = {side: 0, op: 0}
    waste = {side: 0, op: 0}
    lost = Counter()
    prev_own = {}
    prev_units = None
    spawned = {side: Counter(), op: Counter()}
    d100 = None
    while g.result is None:
        before = {t: dict(g.state.resources) for t in (0,)}[0]
        units_before = Counter()
        for (x, y, t, k), c in g.state.units.items():
            units_before[(t, k)] += c
        g.step()
        s = g.state
        halls = {t: sum(1 for b in s.buildings.values() if b.owner == t and b.btype == "HALL") for t in (side, op)}
        for t in (side, op):
            inc[t] += 10 + 2 * halls[t]
            eco[t] += sum(1 for b in s.buildings.values() if b.owner == t and b.btype in ("HALL", "ENG"))
            if before[t] + 10 + 2 * halls[t] > 40:
                waste[t] += before[t] + 10 + 2 * halls[t] - 40
        for b in s.buildings.values():
            if prev_own.get(b.id) == side and b.owner != side:
                lost[b.btype] += 1
            prev_own[b.id] = b.owner
        if s.turn == 100:
            d100 = team_score(s, side) - team_score(s, op)
    n = g.state.turn
    units = Counter()
    for (x, y, t, k), c in g.state.units.items():
        units[(t, k)] += c
    return {"opp": opp, "v": value(g.result, side), "reason": g.result.get("reason"), "turns": n,
            "inc_diff": inc[side] - inc[op], "eco_me": eco[side] / n, "eco_op": eco[op] / n,
            "waste_me": waste[side], "waste_op": waste[op], "d100": d100, "lost": dict(lost),
            "w_end_diff": units[(side, "W")] - units[(op, "W")]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ver", default="v14")
    p.add_argument("--params", default="{}")
    p.add_argument("--seeds", default="42000-42039")
    p.add_argument("--opps", default="v14,v13,srv12_press,srv12_eco,srv12_egf,b72,x_press,x_eco,x_center,x_turtle")
    p.add_argument("--workers", type=int, default=24)
    a = p.parse_args()
    params = json.loads(a.params)
    jobs = [(s, o, side, a.ver, params) for s in parse_range(a.seeds) for o in a.opps.split(",") for side in "YK"]
    with Pool(a.workers) as pool:
        rows = pool.map(run, jobs, chunksize=2)
    print(f"{len(rows)}경기  승점률 {np.mean([r['v'] for r in rows]):.3f}")
    for o in a.opps.split(","):
        rs = [r for r in rows if r["opp"] == o]
        print(f"  {o:<12} {np.mean([r['v'] for r in rs]):.3f}")
    for name, cond in (("승", lambda r: r["v"] == 1), ("무", lambda r: r["v"] == 0.5), ("패", lambda r: r["v"] == 0)):
        rs = [r for r in rows if cond(r)]
        if not rs:
            continue
        m = lambda k: np.mean([r[k] for r in rs if r[k] is not None])
        reasons = Counter(r["reason"] for r in rs)
        lost = Counter()
        for r in rs:
            lost.update(r["lost"])
        print(f"\n[{name} {len(rs)}경기] 종료 {dict(reasons)}")
        print(f"  수입 차 {m('inc_diff'):+.0f} · 경제 건물 우리 {m('eco_me'):.2f} / 상대 {m('eco_op'):.2f} · 낭비 우리 {m('waste_me'):.0f} / 상대 {m('waste_op'):.0f}"
              f" · 100턴 점수 차 {m('d100'):+.1f} · 끝 W 차 {m('w_end_diff'):+.0f}")
        print("  경기당 상실: " + ", ".join(f"{k} {v / len(rs):.1f}" for k, v in lost.most_common()))
    # 패배 중 100턴에 앞서 있던 역전패 비율
    losses = [r for r in rows if r["v"] == 0 and r["d100"] is not None]
    if losses:
        print(f"\n패배 중 100턴에 앞서던 역전패 {np.mean([r['d100'] > 0 for r in losses]):.2f}, "
              f"수입이 앞섰는데 진 경기 {np.mean([r['inc_diff'] > 0 for r in losses]):.2f}")


if __name__ == "__main__":
    main()
