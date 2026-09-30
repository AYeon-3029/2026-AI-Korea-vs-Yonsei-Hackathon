"""Narrow Optuna search after cv ablation. Training/selection/final seeds stay disjoint."""
from __future__ import annotations

import argparse
import hashlib
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import optuna

from branch import REAL_POOL, PUSH_POOL, parse_range
from cv_experiment import game
from sim import module


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ver", default="cv-1")
    ap.add_argument("--center", required=True)
    ap.add_argument("--seeds", default="212000-212011")
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="out/cv/tune")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    center = json.loads(Path(a.center).read_text())
    base = {**module(a.ver).P, **center}
    seeds = parse_range(a.seeds)
    # Retain every opponent; weight the real and aggressive pools equally.
    opps = REAL_POOL + PUSH_POOL
    config = dict(ver=a.ver, center=center, seeds=seeds, opps=opps,
                  source_sha256=hashlib.sha256(Path(f"Model/history/{a.ver}/main.py").read_bytes()).hexdigest())
    config_path = out / "config.json"
    if config_path.exists():
        assert json.loads(config_path.read_text()) == config, "Study definition changed"
    config_path.write_text(json.dumps(config, indent=2))
    study = optuna.create_study(study_name="cv", storage=f"sqlite:///{out.resolve()}/study.db",
                               direction="maximize", load_if_exists=True,
                               sampler=optuna.samplers.TPESampler(seed=219, n_startup_trials=12))
    ints = {"max_f": (4, 5), "escort_extra": (3, 5), "eco_strike": (4, 6), "siege_stage": (3, 5)}
    floats = {"hall_bonus": (13.0, 17.0), "eng_bonus": (12.0, 16.0), "risk_local_w": (0.35, 0.55)}
    if not study.trials:
        study.enqueue_trial({k: base[k] for k in ints | floats})
        study.enqueue_trial({**{k: base[k] for k in ints | floats}, "escort_extra": 4})
    with Pool(a.workers) as pool:
        def objective(trial):
            params = dict(center)
            params.update({k: trial.suggest_int(k, *r) for k, r in ints.items()})
            params.update({k: trial.suggest_float(k, *r) for k, r in floats.items()})
            jobs = [(s, o, side, a.ver, params) for s in seeds for o in opps for side in "YK"]
            rows = list(pool.imap_unordered(game, jobs, chunksize=2))
            errors = sum(r["errors"] for r in rows)
            if errors:
                raise RuntimeError(f"{errors} agent errors")
            real = float(np.mean([r["value"] for r in rows if r["opp"] in REAL_POOL]))
            push = float(np.mean([r["value"] for r in rows if r["opp"] in PUSH_POOL]))
            trial.set_user_attr("real", real)
            trial.set_user_attr("push", push)
            (out / f"t{trial.number}.json").write_text(json.dumps(params, indent=2))
            (out / f"t{trial.number}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            print(f"trial {trial.number} real {real:.4f} push {push:.4f}", flush=True)
            return (real + push) / 2
        study.optimize(objective, n_trials=max(0, a.trials - sum(t.state.is_finished() for t in study.trials)))
    # Export distinct candidates; selection and confirmation run separately.
    top, seen = {}, set()
    for t in sorted((t for t in study.trials if t.value is not None), key=lambda t: -t.value):
        params = json.loads((out / f"t{t.number}.json").read_text())
        key = json.dumps(params, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        top[f"t{t.number}"] = dict(ver=a.ver, params=params)
        if len(top) == 3:
            break
    (out / "top.json").write_text(json.dumps(top, indent=2))


if __name__ == "__main__":
    main()
