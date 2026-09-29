"""깃발병 맴돌기 측정(팀원 관찰: 상대 건물을 W 1명이 지키면 우리 F 가 주변만 맴돈다).

맴돌기 턴: 우리 F 가 상대 건물 b 2칸 안(건물 칸 제외)에 있고, b 칸 위 상대 W ≥ 1, 3턴 안에 b 가 상대 소유에서 벗어나지 않음.
수비 규모별(칸 위 상대 W 1 / 2~3 / 4+)로 나눠 센다. 실제 리플레이(v12·v10)와 로컬(v14 대 현실 풀)을 같은 기준으로 비교한다.

사용 (WSL): python3 tools/macro/loiter.py            # 실제
            python3 tools/macro/loiter.py --sim --ver v14 --seeds 58000-58019
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from collections import Counter
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def count(frames, me, op):
    """frames: [(units{(team,kind):{cell:n}}, owner{cell:team})]. → (맴돌기 Counter, F 존재 턴 수)"""
    c = Counter()
    fturns = 0
    for i in range(len(frames) - 3):
        u, own = frames[i]
        myF = u.get((me, "F"), {})
        enW = u.get((op, "W"), {})
        if myF:
            fturns += 1
        for p, w in own.items():
            if w != op:
                continue
            g = enW.get(p, 0)
            if not g:
                continue
            if not any(1 <= man(q, p) <= 2 for q in myF):
                continue
            if any(frames[i + k][1][p] != op for k in (1, 2, 3)):
                continue
            c["1" if g == 1 else "2~3" if g <= 3 else "4+"] += 1
    return c, fturns


def real():
    from real_analyze import load
    tot, ft, n = Counter(), 0, 0
    for d in ("Real Match Replay/V12_0929_8am", "Real Match Replay/V10_0928_8pm"):
        for path in sorted(glob.glob(os.path.join(d, "*.json"))):
            r, me, op, T, *_ = load(path)
            frames = []
            for t in T:
                o = t["observation"]
                u = {}
                for tm, k, x, y, cnt in o["units"]:
                    u.setdefault((tm, k), {})[(x, y)] = u.setdefault((tm, k), {}).get((x, y), 0) + cnt
                frames.append((u, {(b["x"], b["y"]): b["owner"] for b in o["buildings"]}))
            c, f = count(frames, me, op)
            tot += c
            ft += f
            n += 1
    print(f"실제 {n}경기: 맴돌기 경기당 {sum(tot.values()) / n:.1f}턴 (칸 위 상대 W 1명 {tot['1'] / n:.1f} · 2~3명 {tot['2~3'] / n:.1f} · 4명+ {tot['4+'] / n:.1f})")


def sim_one(args):
    from sim import Agent, Game
    from branch import OPPS
    seed, opp, side, ver, params = args
    me = Agent(ver, params)
    o = Agent(*OPPS[opp])
    g = Game(seed, *((me, o) if side == "Y" else (o, me)))
    op = "K" if side == "Y" else "Y"
    frames = []
    while g.result is None:
        g.step()
        u = {}
        for (x, y, t, k), cnt in g.state.units.items():
            u.setdefault((t, k), {})[(x, y)] = u.setdefault((t, k), {}).get((x, y), 0) + cnt
        frames.append((u, {(b.x, b.y): b.owner for b in g.state.buildings.values()}))
    return count(frames, side, op)[0]


def sim(ver, seeds, params):
    from branch import REAL_POOL, parse_range
    import json
    jobs = [(s, o, side, ver, json.loads(params)) for s in parse_range(seeds) for o in REAL_POOL for side in "YK"]
    with Pool(24) as pool:
        rows = pool.map(sim_one, jobs)
    tot = sum(rows, Counter())
    n = len(rows)
    print(f"로컬 {ver} {params} {n}경기: 맴돌기 경기당 {sum(tot.values()) / n:.1f}턴 (1명 {tot['1'] / n:.1f} · 2~3명 {tot['2~3'] / n:.1f} · 4명+ {tot['4+'] / n:.1f})")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--sim", action="store_true")
    p.add_argument("--ver", default="v14")
    p.add_argument("--params", default="{}")
    p.add_argument("--seeds", default="58000-58019")
    a = p.parse_args()
    if a.sim:
        sim(a.ver, a.seeds, a.params)
    else:
        real()
