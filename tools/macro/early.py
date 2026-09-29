"""초반(1~40턴) 정밀 진단: v14 의 이긴 경기와 진 경기에서 첫 40턴에 무엇이 달랐나.

지표(우리 / 상대):
- F 생산·손실(전투로 죽은 F = 직전 수 + 생산 − 현재, 생산은 본진·병원 칸 증가분으로 추정하지 않고 자원 흐름 대신 명령에서 센다 — 우리만 정확)
- 건물 종류별 첫 점령 턴(우리 쪽 학생회관·공학관, 광장, 보급소, 상대 쪽 경제 건물), 40턴까지 점령 수
- 보급소 보너스 수령 수, 20·40턴 자원·W·F, 첫 교전 턴
사용 (WSL): python3 tools/macro/early.py --seeds 55000-55059
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, value  # noqa: E402
from branch import OPPS, REAL_POOL, parse_range  # noqa: E402
from engine.pipeline import run_turn  # noqa: E402
from runner.protocol import parse_commands, serialize_turn  # noqa: E402


def run(args):
    seed, opp, side = args
    me = Agent("v14")
    o = Agent(*OPPS[opp])
    g = Game(seed, *((me, o) if side == "Y" else (o, me)))
    op = "K" if side == "Y" else "Y"
    s0 = g.state
    base = {t: s0.bases[t] for t in (side, op)}
    man = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
    home = {b.id: ("우" if man((b.x, b.y), base[side]) < man((b.x, b.y), base[op]) else "상") for b in s0.buildings.values()}
    first = {}                     # (팀, 키) → 첫 점령 턴
    f_spawn = 0
    f_lost_me = f_lost_op = 0
    w_lost = 0
    first_battle = None
    depot = {side: 0, op: 0}
    snap = {}
    spent_f = spent_w = 0
    while g.result is None and g.state.turn < 40:
        t = g.state.turn + 1
        pre = g.state
        lines = me.decide(serialize_turn(pre, side, t))
        oth = o.decide(serialize_turn(pre, op, t))
        for ln in lines:
            tok = ln.split()
            if tok and tok[0] == "SPAWN":
                if tok[1] == "F":
                    f_spawn += int(tok[2])
        cm, co = parse_commands(lines), parse_commands(oth)
        pre_units = defaultdict(int)
        for (x, y, tm, k), c in pre.units.items():
            pre_units[(tm, k)] += c
        pre_res = dict(pre.resources)
        ev = []
        g.state, g.result = run_turn(pre, *((cm, co) if side == "Y" else (co, cm)), ev)
        s = g.state
        if first_battle is None and any(e.get("type") == "combat" for e in ev):
            first_battle = t
        for b in s.buildings.values():
            if b.owner in (side, op):
                tm = b.owner
                key = f"{home[b.id]}{b.btype}"
                if (tm, key) not in first:
                    first[(tm, key)] = t
            if b.btype == "DEPOT":
                pass
        for tm in (side, op):
            depot[tm] = sum(1 for bid, ts in s.depot_claimed.items() if tm in ts)
        units = defaultdict(int)
        for (x, y, tm, k), c in s.units.items():
            units[(tm, k)] += c
        if t in (20, 40):
            snap[t] = {"W": (units[(side, "W")], units[(op, "W")]), "F": (units[(side, "F")], units[(op, "F")]),
                       "B": (sum(1 for b in s.buildings.values() if b.owner == side), sum(1 for b in s.buildings.values() if b.owner == op)),
                       "eco": (sum(1 for b in s.buildings.values() if b.owner == side and b.btype in ("HALL", "ENG")),
                               sum(1 for b in s.buildings.values() if b.owner == op and b.btype in ("HALL", "ENG")))}
    # F 손실(우리): 생산 − 현재 생존(40턴)
    units = defaultdict(int)
    for (x, y, tm, k), c in g.state.units.items():
        units[(tm, k)] += c
    f_lost_me = f_spawn - units[(side, "F")]
    g.run()
    return {"opp": opp, "v": value(g.result, side), "f_spawn": f_spawn, "f_lost": f_lost_me,
            "first_me": {k: t for (tm, k), t in first.items() if tm == side},
            "first_op": {k: t for (tm, k), t in first.items() if tm == op},
            "battle": first_battle, "depot": (depot[side], depot[op]), "snap": snap}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", default="55000-55059")
    p.add_argument("--opps", default=",".join(REAL_POOL))
    a = p.parse_args()
    jobs = [(s, o, side) for s in parse_range(a.seeds) for o in a.opps.split(",") for side in "YK"]
    with Pool(24) as pool:
        rows = pool.map(run, jobs, chunksize=2)
    W = [r for r in rows if r["v"] == 1]
    L = [r for r in rows if r["v"] == 0]
    print(f"{len(rows)}경기 승 {len(W)} 패 {len(L)}")
    m = lambda rs, f: np.mean([f(r) for r in rs])
    print(f"첫 교전 턴 승 {m(W, lambda r: r['battle'] or 99):.1f} / 패 {m(L, lambda r: r['battle'] or 99):.1f}")
    print(f"40턴까지 우리 F 생산 승 {m(W, lambda r: r['f_spawn']):.2f} / 패 {m(L, lambda r: r['f_spawn']):.2f} · "
          f"F 손실 승 {m(W, lambda r: r['f_lost']):.2f} / 패 {m(L, lambda r: r['f_lost']):.2f}")
    print(f"40턴까지 보급소 보너스(우리:상대) 승 {m(W, lambda r: r['depot'][0]):.2f}:{m(W, lambda r: r['depot'][1]):.2f}"
          f" / 패 {m(L, lambda r: r['depot'][0]):.2f}:{m(L, lambda r: r['depot'][1]):.2f}")
    for t in (20, 40):
        for k in ("B", "eco", "W", "F"):
            print(f"  {t}턴 {k:<3} 승 {m(W, lambda r: r['snap'][t][k][0] if t in r['snap'] else 0):.2f}:{m(W, lambda r: r['snap'][t][k][1] if t in r['snap'] else 0):.2f}"
                  f"  패 {m(L, lambda r: r['snap'][t][k][0] if t in r['snap'] else 0):.2f}:{m(L, lambda r: r['snap'][t][k][1] if t in r['snap'] else 0):.2f}")
    keys = sorted({k for r in rows for k in list(r["first_me"]) + list(r["first_op"])})
    print("\n첫 점령 턴(40턴 안, 못 하면 41) 우리 / 상대  — 승 | 패   (우=우리 진영 쪽, 상=상대 진영 쪽)")
    for k in keys:
        mw = np.mean([r["first_me"].get(k, 41) for r in W]); ow = np.mean([r["first_op"].get(k, 41) for r in W])
        ml = np.mean([r["first_me"].get(k, 41) for r in L]); ol = np.mean([r["first_op"].get(k, 41) for r in L])
        print(f"  {k:<12} 승 {mw:5.1f} / {ow:5.1f} | 패 {ml:5.1f} / {ol:5.1f}")


if __name__ == "__main__":
    main()
