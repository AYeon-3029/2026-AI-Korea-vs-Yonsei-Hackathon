"""LLM 경기 막판(마지막 결정 이후) 턴별 점수·건물 득실을 출력한다.
사용 (WSL): python3 tools/macro/llm_tail.py v170004 [--from 150]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import llm_match as L  # noqa: E402
from sim import Agent, Game  # noqa: E402
from engine.pipeline import team_score  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("game")
    ap.add_argument("--from", dest="t0", type=int, default=150)
    a = ap.parse_args()
    meta = json.load(open(os.path.join(L.gdir(a.game), "meta.json"), encoding="utf-8"))
    side, lv, (lv, ov) = meta["side"], None, L.vers(meta)
    op = "K" if side == "Y" else "Y"
    me, opp = Agent(lv, {}), Agent(ov, {})
    g = Game(meta["seed"], *((me, opp) if side == "Y" else (opp, me)))
    m = L.module(lv)
    cmd = None
    prev = None
    while g.result is None:
        t = g.state.turn
        p = os.path.join(L.gdir(a.game), f"cmd_{t:03d}.json")
        if t % L.EVERY == 0 and os.path.exists(p):
            cmd = json.load(open(p, encoding="utf-8"))
            me.set_params({**L.posture_params(cmd.get("posture", "balanced"), lv),
                           **({"max_f": int(cmd["max_f"])} if cmd.get("max_f") else {})})
        m.CMD = {"focus": cmd.get("focus", []), "defend": cmd.get("defend", [])} if cmd else None
        g.step()
        s = g.state
        own = {(b.x, b.y): b.owner for b in s.buildings.values()}
        if s.turn >= a.t0:
            ch = [f"{b.btype[:3]}{b.score}({b.x},{b.y}) {prev[(b.x, b.y)]}→{b.owner}"
                  for b in s.buildings.values() if prev and prev[(b.x, b.y)] != b.owner]
            print(f"{s.turn:3d} 지휘관 {team_score(s, side)} : {team_score(s, op)}  {'  '.join(ch)}")
        prev = own
    m.CMD = None
    print(g.result)


if __name__ == "__main__":
    main()
