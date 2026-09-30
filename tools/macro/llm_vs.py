"""저장된 LLM 지휘 명령(out/llm/<경기>/cmd_*.json)을 그대로 재생하며 상대만 바꿔 본다(참고용: 명령은 원래 상대 전황에 맞춰 쓴 것).
사용 (WSL): python3 tools/macro/llm_vs.py --opp dev26 --params '{"recap_f":1}' g1,g2,b150003,...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
import llm_match as L  # noqa: E402
from sim import Agent, Game, value  # noqa: E402

A = {}


def run(game):
    meta = json.load(open(os.path.join(L.gdir(game), "meta.json"), encoding="utf-8"))
    lv, _ = L.vers(meta)
    llm, op = Agent(lv, {}), Agent(A["opp"], A["params"])
    g = Game(meta["seed"], *((llm, op) if meta["side"] == "Y" else (op, llm)))
    m = L.module(lv)
    cmd = None
    while g.result is None:
        t = g.state.turn
        p = os.path.join(L.gdir(game), f"cmd_{t:03d}.json")
        if t % L.EVERY == 0 and os.path.exists(p):
            cmd = json.load(open(p, encoding="utf-8"))
            llm.set_params({**L.posture_params(cmd.get("posture", "balanced"), lv),
                            **({"max_f": int(cmd["max_f"])} if cmd.get("max_f") else {})})
        m.CMD = {"focus": cmd.get("focus", []), "defend": cmd.get("defend", [])} if cmd else None
        g.step()
    m.CMD = None
    r = g.result
    return game, meta["side"], r["winner"], r["reason"], r.get("score"), value(r, meta["side"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("games")
    ap.add_argument("--opp", default="cv-3")
    ap.add_argument("--params", default="{}")
    a = ap.parse_args()
    A.update(opp=a.opp, params=json.loads(a.params))
    with Pool(12, initializer=A.update, initargs=({"opp": a.opp, "params": json.loads(a.params)},)) as pool:
        rows = pool.map(run, a.games.split(","))
    for game, side, w, why, sc, v in rows:
        print(f"{game:9s} LLM={side} 승자 {w} ({why}) {sc}  LLM 승점 {v}")
    print(f"LLM 승점 합 {sum(r[5] for r in rows)}/{len(rows)}  (상대 {a.opp} {a.params})")


if __name__ == "__main__":
    main()
