"""Optuna 5차: 한 프로세스 시뮬레이터(tools/macro/sim.py)로 빠르게 파라미터를 탐색한다.

시행 = Model/history/dev 봇 + 파라미터 → 상대 풀 × 고정 시드 × 양 진영 승점률(같은 시드를 모든 시행이 공유해 비교 잡음을 줄인다).
시작점은 v13 + eco_block_extra 1 (enqueue). 결과는 out/tune/<study>/study.db.

사용 (WSL):
  python3 tools/macro/tune.py --study s5 --trials 300
  python3 tools/macro/tune.py --study s5 --report
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import optuna

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, play, value  # noqa: E402
from branch import OPPS, parse_range  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
OPPS["cand1"] = ("dev", {"eco_block_extra": 1})
TUNE_OPPS = ["cand1", "v13", "v12", "srv12_press", "srv12_eco", "srv12_egf", "b72", "x_press", "x_eco", "x_center"]
BASE = {"eco_block_extra": 1}


def space(trial: optuna.Trial) -> dict:
    return {
        # 새 가중치
        "eco_block_extra": trial.suggest_int("eco_block_extra", 0, 3),
        "eco_block_worth": trial.suggest_float("eco_block_worth", 0.0, 6.0),
        "f_block": trial.suggest_int("f_block", 1, 3),
        "block_worth": trial.suggest_float("block_worth", 1.5, 7.0),
        "retake_w": trial.suggest_float("retake_w", 0.0, 2.0),
        "retake_risk": trial.suggest_float("retake_risk", 0.0, 1.0),
        "rush_k": trial.suggest_float("rush_k", 0.0, 0.6),
        "tele_queue": trial.suggest_categorical("tele_queue", [False, True]),
        # v13 핵심 파라미터 둘레
        "max_f": trial.suggest_int("max_f", 4, 7),
        "min_f": trial.suggest_int("min_f", 3, 6),
        "min_w": trial.suggest_int("min_w", 4, 8),
        "w_margin": trial.suggest_int("w_margin", 16, 32),
        "guard_radius": trial.suggest_int("guard_radius", 12, 24),
        "risk_local_w": trial.suggest_float("risk_local_w", 0.05, 0.45),
        "hall_bonus": trial.suggest_float("hall_bonus", 6.0, 16.0),
        "eng_bonus": trial.suggest_float("eng_bonus", 8.0, 18.0),
        "escort_extra": trial.suggest_int("escort_extra", 2, 6),
        "siege_bld_bonus": trial.suggest_float("siege_bld_bonus", 4.0, 11.0),
        "enemy_owned_mult": trial.suggest_float("enemy_owned_mult", 1.2, 2.2),
    }


V13_START = {"eco_block_extra": 1, "eco_block_worth": 0.0, "f_block": 2, "block_worth": 3.5189, "retake_w": 0.0,
             "retake_risk": 0.0, "rush_k": 0.0, "tele_queue": False, "max_f": 5, "min_f": 5, "min_w": 6, "w_margin": 23,
             "guard_radius": 19, "risk_local_w": 0.2271, "hall_bonus": 9.6127, "eng_bonus": 12.6092, "escort_extra": 4,
             "siege_bld_bonus": 7.6216, "enemy_owned_mult": 1.7748}


def game(args):
    seed, opp, side, params = args
    me = Agent("dev", params)
    o = Agent(*OPPS[opp])
    r = play(seed, *((me, o) if side == "Y" else (o, me)))
    return opp, value(r, side), me.errors


def evaluate(pool, params, seeds, opps):
    jobs = [(s, o, side, params) for s in seeds for o in opps for side in "YK"]
    by = {}
    err = 0
    for opp, v, e in pool.imap_unordered(game, jobs, chunksize=4):
        by.setdefault(opp, []).append(v)
        err += e
    allv = [v for vs in by.values() for v in vs]
    return float(np.mean(allv)), {o: float(np.mean(v)) for o, v in by.items()}, err


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--study", required=True)
    p.add_argument("--trials", type=int, default=300)
    p.add_argument("--seeds", default="36000-36039")
    p.add_argument("--workers", type=int, default=24)
    p.add_argument("--report", action="store_true")
    p.add_argument("--verify", type=int, default=0, help="상위 N 개를 새 시드로 재평가")
    p.add_argument("--vseeds", default="37000-37099")
    a = p.parse_args()
    work = os.path.join(ROOT, "out/tune", a.study)
    os.makedirs(work, exist_ok=True)
    study = optuna.create_study(study_name=a.study, storage=f"sqlite:///{work}/study.db", load_if_exists=True,
                                direction="maximize", sampler=optuna.samplers.TPESampler(seed=5, multivariate=True))
    done = [t for t in study.trials if t.value is not None]
    if a.report or a.verify:
        top = sorted(done, key=lambda t: -t.value)[:max(10, a.verify)]
        for t in top[:10]:
            print(t.number, round(t.value, 4), json.dumps(t.params))
        if a.verify:
            seeds = parse_range(a.vseeds)
            with Pool(a.workers) as pool:
                base, bo, _ = evaluate(pool, BASE, seeds, TUNE_OPPS)
                print(f"기준(v13+eco1) {base:.4f}  " + " ".join(f"{o}={v:.3f}" for o, v in sorted(bo.items())))
                for t in top[:a.verify]:
                    v, by, err = evaluate(pool, t.params, seeds, TUNE_OPPS)
                    print(f"#{t.number} 탐색 {t.value:.4f} → 검증 {v:.4f} (기준 대비 {v - base:+.4f}) 예외 {err}  "
                          + " ".join(f"{o}={x:.3f}" for o, x in sorted(by.items())))
        return
    if not done:
        study.enqueue_trial(V13_START)
    seeds = parse_range(a.seeds)
    with Pool(a.workers) as pool:
        def objective(trial):
            params = space(trial)
            t0 = time.time()
            v, by, err = evaluate(pool, params, seeds, TUNE_OPPS)
            trial.set_user_attr("by_opp", by)
            trial.set_user_attr("errors", err)
            print(f"#{trial.number} {v:.4f} ({time.time() - t0:.0f}s) 예외 {err}", flush=True)
            return v if err == 0 else v - 0.5
        study.optimize(objective, n_trials=a.trials - len(done))


if __name__ == "__main__":
    main()
