"""cv experiments: cached baseline, raw paired rows, uncertainty clustered by map seed.

python3 tools/macro/cv_experiment.py --candidates out/cv/screen.json --seeds 211000-211029 --out out/cv/screen
Candidate JSON: {name: {ver: "cv-1", params: {...}}}. Default baseline is frozen v19.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from sim import Agent, Game, value
from branch import OPPS, REAL_POOL, PUSH_POOL, parse_range


def game(job):
    seed, opp, side, ver, params = job
    me, other = Agent(ver, params), Agent(*OPPS[opp])
    g = Game(seed, *((me, other) if side == "Y" else (other, me)))
    g.run()
    return dict(seed=seed, opp=opp, side=side, value=value(g.result, side),
                errors=me.errors + other.errors)


def summary(rows, baseline, opps):
    selected = [r for r in rows if r["opp"] in opps]
    clusters = defaultdict(list)
    av, bv = [], []
    for r in selected:
        a = baseline[(r["seed"], r["opp"], r["side"])]["value"]
        av.append(a)
        bv.append(r["value"])
        clusters[r["seed"]].append(r["value"] - a)
    d = np.array([np.mean(v) for v in clusters.values()])
    return dict(pairs=len(selected), seeds=len(d), a=float(np.mean(av)), b=float(np.mean(bv)),
                delta=float(np.mean(d)), se=float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else None,
                errors=sum(r["errors"] for r in selected))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidates", required=True)
    p.add_argument("--seeds", required=True)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--out", required=True)
    p.add_argument("--baseline", default="v19")
    a = p.parse_args()
    candidates = json.loads(Path(a.candidates).read_text())
    assert a.baseline not in candidates, "Baseline name is reserved"
    opps = list(dict.fromkeys(REAL_POOL + PUSH_POOL))
    seeds = parse_range(a.seeds)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    base = {}
    report_path = out / "summary.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    with Pool(a.workers) as pool:
        for name, spec in {a.baseline: dict(ver=a.baseline, params={}), **candidates}.items():
            t0 = time.monotonic()
            path = out / f"{name}.jsonl"
            # Only reuse a complete cache with the exact run definition.
            sources = sorted(Path(f"Model/history/{spec['ver']}").glob("*.py"))
            hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
            meta = dict(seeds=seeds, opps=opps, spec=spec, source_sha256=hashes)
            meta_path = out / f"{name}.meta.json"
            rows = []
            if path.exists() and meta_path.exists() and json.loads(meta_path.read_text()) == meta:
                rows = [json.loads(line) for line in path.read_text().splitlines()]
            if len(rows) != len(seeds) * len(opps) * 2:
                jobs = [(s, o, side, spec["ver"], spec["params"]) for s in seeds for o in opps for side in "YK"]
                rows = []
                with path.open("w") as f:
                    for r in pool.imap_unordered(game, jobs, chunksize=2):
                        rows.append(r)
                        f.write(json.dumps(r) + "\n")
                meta_path.write_text(json.dumps(meta, indent=2))
            assert not sum(r["errors"] for r in rows), f"{name}: agent exceptions"
            if name == a.baseline:
                base = {(r["seed"], r["opp"], r["side"]): r for r in rows}
            report[name] = {label: summary(rows, base, group) for label, group in
                            (("real", REAL_POOL), ("push", PUSH_POOL), ("all", opps))}
            report[name]["by_opp"] = {o: summary(rows, base, [o]) for o in opps}
            print(name, " ".join(f"{k}: {v['a']:.4f}->{v['b']:.4f} delta {v['delta']:+.4f} SE(seed) {v['se']:.4f} n={v['pairs']}"
                                  for k, v in report[name].items() if k in ("real", "push")),
                  f"{time.monotonic()-t0:.0f}s", flush=True)
            (out / "summary.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
