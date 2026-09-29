"""깃발 뽑힘(우리 건물 위 우리 F 가 전투로 죽어 즉시 중립) 진단 + 초반(15~40턴) 경쟁 진단.

깃발 뽑힘 분류: 직전 상태에 그 칸에 우리 F 가 있었으면 '머묾', 없었으면 '이번 턴 진입'.
'진입'은 다시 그 건물이 이동 경유(다른 목표로 가는 길)였는지 보려고, 진입 전 칸과의 관계는 따지지 않고 횟수·턴·그 턴 위협만 센다.
F 가 우리 건물 칸에 들어간 전체 횟수(경유 포함)도 센다 — 거르기 규칙이 얼마나 자주 개입할지 가늠한다.

사용 (WSL): python3 tools/macro/fpull.py --ver v14 --seeds 43000-43029
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
from engine.pipeline import run_turn  # noqa: E402
from runner.protocol import parse_commands, serialize_turn  # noqa: E402

OPPS["v14"] = ("v14", {})


def step_events(g):
    t = g.state.turn + 1
    cy = parse_commands(g.agents["Y"].decide(serialize_turn(g.state, "Y", t)))
    ck = parse_commands(g.agents["K"].decide(serialize_turn(g.state, "K", t)))
    ev = []
    g.state, g.result = run_turn(g.state, cy, ck, ev)
    return ev


def run(args):
    seed, opp, side, ver, params = args
    me = Agent(ver, params)
    o = Agent(*OPPS[opp])
    g = Game(seed, *((me, o) if side == "Y" else (o, me)))
    op = "K" if side == "Y" else "Y"
    pulls = []            # (턴, 분류, 건물 종류, 점수)
    enter_own = 0         # 우리 F 가 우리 건물 칸에 새로 들어간 횟수
    early = {}
    while g.result is None:
        pre = g.state
        own_pre = {(b.x, b.y): b for b in pre.buildings.values() if b.owner == side}
        f_pre = {(x, y): c for (x, y, t, k), c in pre.units.items() if t == side and k == "F"}
        ev = step_events(g)
        s = g.state
        f_now = {(x, y): c for (x, y, t, k), c in s.units.items() if t == side and k == "F"}
        for p in own_pre:
            if f_now.get(p, 0) and not f_pre.get(p, 0):
                enter_own += 1
        for e in ev:
            if e.get("type") == "neutralize" and "team" not in e and (e["x"], e["y"]) in own_pre:
                b = own_pre[(e["x"], e["y"])]
                kind = "머묾" if f_pre.get((e["x"], e["y"]), 0) else "진입"
                pulls.append((s.turn, kind, b.btype, b.score))
        if s.turn in (15, 25, 40):
            nb = lambda t: sum(1 for b in s.buildings.values() if b.owner == t)
            fl = lambda t: sum(c for (x, y, tt, k), c in s.units.items() if tt == t and k == "F")
            early[s.turn] = (nb(side) - nb(op), fl(side) - fl(op))
    return {"opp": opp, "v": value(g.result, side), "pulls": pulls, "enter_own": enter_own, "early": early}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ver", default="v14")
    p.add_argument("--params", default="{}")
    p.add_argument("--seeds", default="43000-43029")
    p.add_argument("--opps", default="v14,v13,srv12_press,srv12_eco,b72,x_press,x_eco,x_center")
    p.add_argument("--workers", type=int, default=24)
    a = p.parse_args()
    jobs = [(s, o, side, a.ver, json.loads(a.params)) for s in parse_range(a.seeds) for o in a.opps.split(",") for side in "YK"]
    with Pool(a.workers) as pool:
        rows = pool.map(run, jobs, chunksize=2)
    n = len(rows)
    allp = [x for r in rows for x in r["pulls"]]
    kinds = Counter(k for _, k, _, _ in allp)
    print(f"{n}경기 · 우리 깃발 뽑힘 경기당 {len(allp) / n:.2f}회 (머묾 {kinds['머묾'] / n:.2f}, 이번 턴 진입 {kinds['진입'] / n:.2f})"
          f" · F 가 우리 건물에 새로 들어간 횟수 경기당 {np.mean([r['enter_own'] for r in rows]):.1f}")
    for kind in ("머묾", "진입"):
        ps = [x for x in allp if x[1] == kind]
        if ps:
            print(f"  {kind}: 건물 {dict(Counter(b for _, _, b, _ in ps).most_common())} · 평균 점수 {np.mean([s for *_, s in ps]):.2f}"
                  f" · 턴 분포 1~40 {np.mean([t <= 40 for t, *_ in ps]):.2f} / 41~120 {np.mean([40 < t <= 120 for t, *_ in ps]):.2f} / 121~ {np.mean([t > 120 for t, *_ in ps]):.2f}")
    for name, cond in (("승", 1.0), ("패", 0.0)):
        rs = [r for r in rows if r["v"] == cond]
        if rs:
            print(f"  {name} {len(rs)}경기: 뽑힘 {np.mean([len(r['pulls']) for r in rs]):.2f}/경기 · "
                  + " · ".join(f"{t}턴 건물 차 {np.mean([r['early'][t][0] for r in rs if t in r['early']]):+.2f} F 차 {np.mean([r['early'][t][1] for r in rs if t in r['early']]):+.2f}"
                               for t in (15, 25, 40)))


if __name__ == "__main__":
    main()
