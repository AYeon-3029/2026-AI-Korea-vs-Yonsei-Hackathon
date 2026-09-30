"""두 버전 대결 리플레이를 공식 형식(tools/viewer.html)으로 저장한다. 시드 범위에서 결과별로 골라 저장.
사용 (WSL): python3 tools/macro/h2h_replay.py --a v20 --b cv-3 --seeds 170000-170039 --win 4 --loss 3 --draw 1
저장: out/replays/h2h/<a>-vs-<b>/<A결과>-seed<시드>-<a>=<진영>.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
from sim import CFG, Agent, Game, value  # noqa: E402
from branch import parse_range  # noqa: E402
from engine.pipeline import run_turn  # noqa: E402
from mapgen import generate  # noqa: E402
from runner.protocol import parse_commands, serialize_turn  # noqa: E402
from runner.replay import new_replay, turn_entry  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def play(args):
    seed, side, a, b, rec = args
    from branch import OPPS
    A, B = Agent(a, {}), (Agent(*OPPS[b]) if b in OPPS else Agent(b, {}))
    g = Game(seed, *((A, B) if side == "Y" else (B, A)))
    rp = None
    if rec:
        names = {side: {"name": a, "command": f"Model/history/{a}/main.py"},
                 ("K" if side == "Y" else "Y"): {"name": b, "command": f"Model/history/{b}/main.py"}}
        rp = new_replay(seed, CFG, generate(seed, CFG), names)
    while g.result is None:
        turn = g.state.turn + 1
        raw = {tm: g.agents[tm].decide(serialize_turn(g.state, tm, turn)) for tm in ("Y", "K")}
        cy, ck = parse_commands(raw["Y"]), parse_commands(raw["K"])
        ev = []
        g.state, g.result = run_turn(g.state, cy, ck, ev)
        if rec:
            rp["turns"].append(turn_entry(turn, raw["Y"], raw["K"], cy, ck, g.state, ev))
    v = value(g.result, side)
    if rec:
        res = dict(g.result)
        res["seed"] = seed
        rp["result"] = res
        lab = "승" if v == 1 else "무" if v == 0.5 else "패"
        d = os.path.join(ROOT, "out/replays/h2h", f"{a}-vs-{b}")
        os.makedirs(d, exist_ok=True)
        out = os.path.join(d, f"{a}{lab}-{g.result['reason']}-seed{seed}-{a}={side}.json")
        open(out, "w", encoding="utf-8").write(json.dumps(rp, ensure_ascii=False))
        return out, g.result
    return seed, side, v, g.result["reason"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--seeds", required=True)
    p.add_argument("--win", type=int, default=4)
    p.add_argument("--loss", type=int, default=3)
    p.add_argument("--draw", type=int, default=1)
    x = p.parse_args()
    with Pool(20) as pool:
        rows = pool.map(play, [(s, side, x.a, x.b, False) for s in parse_range(x.seeds) for side in "YK"])
        want = {1: x.win, 0: x.loss, 0.5: x.draw}
        pick, seen = [], set()
        # 승은 즉시승·점수승을 섞는다
        for r in sorted(rows, key=lambda r: (r[2], r[3] != "instant", r[0])):
            if want.get(r[2], 0) > 0 and r[0] not in seen:
                pick.append(r)
                seen.add(r[0])
                want[r[2]] -= 1
        outs = pool.map(play, [(s, side, x.a, x.b, True) for s, side, _, _ in pick])
    for out, res in outs:
        print(os.path.relpath(out, ROOT), res["winner"], res["reason"], res.get("score"))


if __name__ == "__main__":
    main()
