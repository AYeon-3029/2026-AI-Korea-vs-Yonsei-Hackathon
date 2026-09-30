"""LLM 지휘 경기 반사실 분석: 명령을 T턴까지만 적용하고 그 뒤는 명령 없이(= 기본 봇) 끝까지 둔다.

cut=0 은 명령 없는 거울전(무승부), cut=160 은 실제 경기. cut 사이의 승점 변화 = 그 구간 명령의 값.
턴 140/150/160 점수도 함께 출력한다.
사용 (WSL): python3 tools/macro/llm_cf.py --prefix v --cuts 0,50,100,150,160
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
import llm_match as L  # noqa: E402
from sim import Agent, Game, value  # noqa: E402
from engine.pipeline import team_score  # noqa: E402


def run(args):
    game, cut = args
    meta = json.load(open(os.path.join(L.gdir(game), "meta.json"), encoding="utf-8"))
    side = meta["side"]
    op = "K" if side == "Y" else "Y"
    lv, ov = L.vers(meta)
    me, opp = Agent(lv, {}), Agent(ov, {})
    g = Game(meta["seed"], *((me, opp) if side == "Y" else (opp, me)))
    m = L.module(lv)
    cmd = None
    marks = {}
    while g.result is None:
        t = g.state.turn
        if t in (140, 150):
            marks[t] = (team_score(g.state, side), team_score(g.state, op))
        if t == cut:
            cmd = None
            me.set_params({})
        p = os.path.join(L.gdir(game), f"cmd_{t:03d}.json")
        if t < cut and t % L.EVERY == 0 and os.path.exists(p):
            cmd = json.load(open(p, encoding="utf-8"))
            me.set_params({**L.posture_params(cmd.get("posture", "balanced"), lv),
                           **({"max_f": int(cmd["max_f"])} if cmd.get("max_f") else {})})
        m.CMD = {"focus": cmd.get("focus", []), "defend": cmd.get("defend", [])} if cmd else None
        g.step()
    m.CMD = None
    r = g.result
    sc = r.get("score") or {}
    return game, cut, side, value(r, side), r["reason"], g.state.turn, (sc.get(side), sc.get(op)), marks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="v")
    ap.add_argument("--cuts", default="0,50,100,150,160")
    a = ap.parse_args()
    games = sorted(os.path.basename(p) for p in glob.glob(os.path.join(L.ROOT, "out/llm", f"{a.prefix}[0-9]*")))
    cuts = [int(c) for c in a.cuts.split(",")]
    with Pool(min(24, os.cpu_count() or 4)) as pool:
        rows = pool.map(run, [(g, c) for g in games for c in cuts])
    tab = {}
    for game, cut, side, v, why, turn, sc, marks in rows:
        tab.setdefault(game, {})[cut] = (side, v, why, turn, sc, marks)
    print("경기       진영 " + " ".join(f"cut{c:<4d}" for c in cuts) + "   실제 140/150/160 점수(지휘관:상대)")
    tot = {c: 0.0 for c in cuts}
    for game in games:
        r = tab[game]
        side = r[cuts[0]][0]
        full = r[cuts[-1]]
        mk = full[5]
        pts = " ".join(f"{t}:{mk[t][0]}:{mk[t][1]}" for t in (140, 150) if t in mk)
        end = f"{full[3]}턴 {full[2]} {full[4][0]}:{full[4][1]}" if full[4][0] is not None else f"{full[3]}턴 {full[2]}"
        print(f"{game:10s} {side}    " + " ".join(f"{r[c][1]:<7.1f}" for c in cuts) + f"   {pts}  끝 {end}")
        for c in cuts:
            tot[c] += r[c][1]
    print("합계            " + " ".join(f"{tot[c]:<7.1f}" for c in cuts) + f"   / {len(games)}")
    for s in "YK":
        gs = [g for g in games if tab[g][cuts[0]][0] == s]
        print(f"  {s} 진영 {len(gs)}경기  " + " ".join(f"{sum(tab[g][c][1] for g in gs):<7.1f}" for c in cuts))


if __name__ == "__main__":
    main()
