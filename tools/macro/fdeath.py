"""우리 F 가 어떤 상황에서 죽는지 분류한다(상위 팀 F 사망 3.8 vs 우리 9.4 격차 진단).

전투 단계를 가로채 전투 직전(이동 후) 칸 상태와 전투 후 우리 F 감소를 비교한다.
분류: 칸 종류(내 건물 / 적 건물 / 중립 건물 / 빈 칸) · 이번 턴 이동했는지 · 칸 위 아군 W · 적 W 수 ·
      이동 전 상태에서 그 칸 1칸 안 적 W(예고된 위협이었는지).
사용 (WSL): python3 tools/macro/fdeath.py --ver v18 --seeds 100000-100029 [--params '{}'] [--opps ...]
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
import sim  # noqa: E402
from sim import Agent, Game, value  # noqa: E402
from branch import OPPS, PUSH_POOL, REAL_POOL, parse_range  # noqa: E402
import engine.pipeline as pl  # noqa: E402

_orig_combat = pl.step_combat
LOG: list = []
CTX: dict = {}


def _combat(state, events=None):
    side = CTX["side"]
    op = "K" if side == "Y" else "Y"
    pre = {}
    for (x, y, t, k), c in state.units.items():
        if t == side and k == "F" and c > 0:
            b = state.building_at(x, y)
            pre[(x, y)] = (c, state.get_unit(x, y, side, "W"), state.get_unit(x, y, op, "W"),
                           None if b is None else (b.btype, b.owner))
    _orig_combat(state, events)
    prev = CTX["prev"]
    for (x, y), (c, myw, opw, b) in pre.items():
        lost = c - state.get_unit(x, y, side, "F")
        if lost <= 0:
            continue
        stayed = prev.get((x, y, side, "F"), 0)
        near = sum(n for (px, py, t, k), n in prev.items()
                   if t == op and k == "W" and abs(px - x) + abs(py - y) <= 1)
        if b is None:
            where = "empty"
        else:
            where = "own" if b[1] == side else "enemy" if b[1] == op else "neutral"
        why = [f"{r[3]}{'' if r[1] != r[2] else '@'}/{'S' if r[4] else 'U'}{'S' if r[5] else 'U'}"
               + ('+' if r[6] else '') for r in CTX["dbg"] if r[0] == state.turn and tuple(r[2]) == (x, y)] if CTX["dbg"] is not None else []
        LOG.append({"why": why, "turn": state.turn, "lost": lost, "where": where, "btype": b[0] if b else "",
                    "moved": stayed < c, "myw": myw, "opw": opw, "near": near})


pl.step_combat = _combat


def run(args):
    seed, opp, side, ver, params = args
    me = Agent(ver, params)
    o = Agent(*OPPS[opp])
    g = Game(seed, *((me, o) if side == "Y" else (o, me)))
    LOG.clear()
    CTX["side"] = side
    CTX["dbg"] = None
    if hasattr(me.mod, "FDBG"):
        me.mod.FDBG = CTX["dbg"] = []
    while g.result is None:
        CTX["prev"] = dict(g.state.units)
        g.step()
    return {"seed": seed, "opp": opp, "side": side, "v": value(g.result, side), "turns": g.state.turn,
            "deaths": list(LOG)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ver", default="v18")
    p.add_argument("--params", default="{}")
    p.add_argument("--seeds", required=True)
    p.add_argument("--opps", default=",".join(REAL_POOL + PUSH_POOL))
    p.add_argument("--workers", type=int, default=20)
    p.add_argument("--out", default="")
    a = p.parse_args()
    jobs = [(s, o, side, a.ver, json.loads(a.params)) for s in parse_range(a.seeds) for o in a.opps.split(",") for side in "YK"]
    t0 = time.time()
    with Pool(a.workers) as pool:
        rows = list(pool.imap_unordered(run, jobs, chunksize=2))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n = len(rows)
    tot = sum(d["lost"] for r in rows for d in r["deaths"])
    print(f"{a.ver} {n}경기 승점 {sum(r['v'] for r in rows) / n:.3f}  F 사망/경기 {tot / n:.2f}  {time.time() - t0:.0f}s")
    for lab, sel in (("승", lambda r: r["v"] == 1), ("무", lambda r: r["v"] == 0.5), ("패", lambda r: r["v"] == 0)):
        rs = [r for r in rows if sel(r)]
        if rs:
            print(f"  {lab} {len(rs):4d}경기  F 사망/경기 {sum(d['lost'] for r in rs for d in r['deaths']) / len(rs):.2f}")
    D = [d for r in rows for d in r["deaths"]]

    def show(title, key):
        c = Counter()
        for d in D:
            c[key(d)] += d["lost"]
        print(title, "  ".join(f"{k}:{v / n:.2f}" for k, v in c.most_common()))

    show("칸      ", lambda d: d["where"] + ("/" + d["btype"] if d["btype"] else ""))
    show("이동    ", lambda d: "이동" if d["moved"] else "정지")
    show("아군W   ", lambda d: "W0" if d["myw"] == 0 else "W1+")
    show("예고    ", lambda d: "적W인접" if d["near"] > 0 else "기습(인접 적W 없음)")
    show("적W-아군W", lambda d: str(min(d["opw"] - d["myw"], 5)))
    show("구간    ", lambda d: f"{(d['turn'] - 1) // 40 * 40 + 1}-{(d['turn'] - 1) // 40 * 40 + 40}")
    show("사유    ", lambda d: ",".join(sorted(set(d["why"]))) or "?")
    show("칸×이동×W", lambda d: f"{d['where']}/{'이동' if d['moved'] else '정지'}/{'W0' if d['myw'] == 0 else 'W1+'}")


if __name__ == "__main__":
    main()
