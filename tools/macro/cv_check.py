"""Runnable cv checks: disabled switches preserve commands; active switches preserve symmetry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sim import Agent, Game, module
from runner.protocol import serialize_init, serialize_turn
from branch import OPPS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ver", default="cv-1")
    ap.add_argument("--official", default="", help="timing.py --out JSON: compare fast simulator with official runner")
    args = ap.parse_args()
    ver = args.ver
    if args.official:
        rows = json.loads(Path(args.official).read_text())
        for row in rows:
            me, other = Agent(ver), Agent(*OPPS.get(row["opp"], (row["opp"], {})))
            g = Game(row["seed"], *((me, other) if row["side"] == "Y" else (other, me)))
            g.run()
            keys = ("winner", "score", "turns", "reason")
            assert all(g.result[k] == row["result"][k] for k in keys), (row["seed"], row["opp"], row["side"])
            assert me.errors == other.errors == 0
        print(f"PASS: {len(rows)} official/fast-simulator results agree; zero exceptions")
        return
    flags = {k: True for k in module(ver).P if k.startswith("cv_")}
    turns = 0
    for seed in (219000, 219001):
        for opp in ("p_lodge", "srv14_eco"):
            for side in "YK":
                baseline, candidate, other = Agent("v19"), Agent(ver, {k: False for k in flags}), Agent(*OPPS[opp])
                g = Game(seed, *((baseline, other) if side == "Y" else (other, baseline)))
                candidate.start(serialize_init(g.state, side))
                while g.result is None:
                    # Clone the decision state so the live baseline advances exactly once.
                    text = serialize_turn(g.state, side, g.state.turn + 1)
                    expected = baseline.clone().decide(text)
                    actual = candidate.decide(text)
                    assert expected == actual, (seed, opp, side, g.state.turn)
                    g.step()
                    turns += 1
                assert baseline.errors == candidate.errors == other.errors == 0
    for seed in range(219010, 219014):
        ay, ak = Agent(ver, flags), Agent(ver, flags)
        g = Game(seed, ay, ak)
        g.run()
        assert g.result["winner"] == "DRAW", (seed, g.result)
        assert ay.errors == ak.errors == 0
    # Waste must be measured after spending, at the actual resource-cap operation.
    from types import SimpleNamespace
    import diagnose
    state = SimpleNamespace(resources={"Y": 20}, config={"resource": {"resource_cap": 40}})
    diagnose.WASTE.clear()
    diagnose.tracked_resource(state, "Y", 10)
    assert state.resources["Y"] == 30 and diagnose.WASTE["Y"] == 0
    state.resources["Y"] = 38
    diagnose.tracked_resource(state, "Y", 10)
    assert state.resources["Y"] == 40 and diagnose.WASTE["Y"] == 8
    print(f"PASS: {turns} command-equivalent turns; 4 active-switch mirrors; zero exceptions")
    print("PASS: resource-cap waste is measured after spending")


if __name__ == "__main__":
    main()
