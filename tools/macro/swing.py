"""20~40턴 W 격차 분해: 이긴 경기와 진 경기에서 생산량 차이가 어디서 오는가.

W 는 1:1 상쇄라 양쪽 손실이 같다 → W 격차 변화 = W 생산 격차. 생산 = (수입 + 보급소 보너스 − F 지출 − 점령 지출 − 잔액 변화) / W 단가.
요소(우리 − 상대, 20~40턴 합): 수입(학생회관), 보급소 보너스, F 생산 수, W 생산 수, W 평균 단가(공학관), 점령 횟수, 상한 낭비.
F·W 생산 수는 양쪽 모두 생산 칸(본진·병원) 증가 대신 자원 흐름으로 추정하지 않고, 우리 명령과 상대 명령(한 프로세스라 둘 다 보인다)에서 센다.

사용 (WSL): python3 tools/macro/swing.py --seeds 55000-55059
"""
from __future__ import annotations

import argparse
import os
import sys
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
    acc = {t: {"inc": 0, "depot": 0, "F": 0, "W": 0, "wcost": 0, "cap": 0, "waste": 0} for t in (side, op)}
    while g.result is None and g.state.turn < 40:
        t = g.state.turn + 1
        pre = g.state
        lines = {side: me.decide(serialize_turn(pre, side, t)), op: o.decide(serialize_turn(pre, op, t))}
        eng = {tm: sum(1 for b in pre.buildings.values() if b.owner == tm and b.btype == "ENG") for tm in (side, op)}
        cy, ck = parse_commands(lines["Y"]), parse_commands(lines["K"])
        dep_pre = {tm: sum(1 for ts in pre.depot_claimed.values() if tm in ts) for tm in (side, op)}
        res_pre = dict(pre.resources)
        ev = []
        g.state, g.result = run_turn(pre, cy, ck, ev)
        s = g.state
        if t <= 20:
            continue
        for tm in (side, op):
            a = acc[tm]
            halls = sum(1 for b in s.buildings.values() if b.owner == tm and b.btype == "HALL")
            a["inc"] += 10 + 2 * halls
            a["depot"] += 15 * (sum(1 for ts in s.depot_claimed.values() if tm in ts) - dep_pre[tm])
            price = max(2, 3 - eng[tm])
            nf = nw = 0
            budget = res_pre[tm]
            for ln in lines[tm]:
                tok = ln.split()
                if tok and tok[0] == "SPAWN":
                    n = int(tok[2])
                    if tok[1] == "F":
                        k = min(n, budget // 5)
                        nf += k
                        budget -= 5 * k
                    elif tok[1] == "W":
                        k = min(n, budget // price)
                        nw += k
                        budget -= price * k
            a["F"] += nf
            a["W"] += nw
            a["wcost"] += nw * price
            a["cap"] += sum(1 for e in ev if e.get("type") in ("capture", "neutralize") and e.get("team") == tm)
            a["waste"] += max(0, budget + 10 + 2 * halls - 40)
    g.run()
    d = {k: acc[side][k] - acc[op][k] for k in acc[side]}
    d["price_me"] = acc[side]["wcost"] / max(1, acc[side]["W"])
    d["price_op"] = acc[op]["wcost"] / max(1, acc[op]["W"])
    return value(g.result, side), d


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", default="55000-55059")
    a = p.parse_args()
    jobs = [(s, o, side) for s in parse_range(a.seeds) for o in REAL_POOL for side in "YK"]
    with Pool(24) as pool:
        rows = pool.map(run, jobs, chunksize=2)
    for name, v in (("승", 1.0), ("패", 0.0)):
        rs = [d for vv, d in rows if vv == v]
        m = lambda k: np.mean([d[k] for d in rs])
        print(f"[{name} {len(rs)}경기] 21~40턴 (우리 − 상대): W 생산 {m('W'):+.1f} · 수입 {m('inc'):+.1f} · 보급소 {m('depot'):+.1f} · "
              f"F 생산 {m('F'):+.2f} · 점령·중립화 {m('cap'):+.2f} · 낭비 {m('waste'):+.1f} · W 단가 우리 {m('price_me'):.2f} / 상대 {m('price_op'):.2f}")


if __name__ == "__main__":
    main()
