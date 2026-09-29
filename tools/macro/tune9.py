"""Optuna 9차: v16 중심(좁은 범위) + 경제 열세 공격대·탈환·타격 스위치, 현실 풀 12 + 공세형 대리 6(9/29 20시 패배 상대 스타일).

봇 = Model/history/dev13 (기본값 = v16). 시작점 = v16 기본값({}, enqueue). 범위는 v16 값의 0.6~1.5배(정수는 ±2) — 8차의 winner's curse 를 줄이려고 좁힌다.
시행 = 상대 18종 × 고정 시드 × 양 진영(시드 공유).

사용 (WSL):
  python3 tools/macro/tune9.py --study s9 --trials 300
  python3 tools/macro/tune9.py --study s9 --verify 8 --vseeds 81000-81099
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import optuna

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, module, play, value  # noqa: E402
from branch import OPPS, PUSH_POOL, REAL_POOL, parse_range  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
VER = os.environ.get("TUNE_VER", "dev13")
TUNE_OPPS = REAL_POOL + PUSH_POOL + ["semi14_press"]   # semi14_press 는 두 풀에 모두 있어 비중 2
BASE = copy.deepcopy(module(VER).P)

FLOATS = ["center_expect", "side_expect", "hall_bonus", "depot_bonus", "hosp_bonus", "eng_bonus", "lib_bonus",
          "enemy_owned_mult", "enemy_f_penalty", "dist_offset", "chase_mult", "siege_bld_bonus", "siege_ring_value",
          "block_worth", "escort_bonus", "risk_local_w", "retake_w", "retake_risk", "eco_block_worth", "rush_k"]
INTS = ["max_f", "min_f", "min_w", "w_margin", "guard_radius", "escort_extra", "escort_dist", "eco_block_extra", "f_block",
        "siege_stage", "tele_min_gain", "endgame_turn", "max_f_early", "f_own_R"]
LOW = {"max_f": 3, "min_f": 2, "min_w": 2, "escort_dist": 1, "eco_block_extra": 0, "f_block": 0, "siege_stage": 1,
       "tele_min_gain": 1, "max_f_early": 3, "f_own_R": 0}


def space(trial: optuna.Trial) -> dict:
    out = {}
    for k in FLOATS:
        c = BASE[k]
        out[k] = trial.suggest_float(k, 0.6 * c, 1.5 * c)
    for k in INTS:
        c = BASE[k]
        step = 4 if k in ("w_margin", "endgame_turn") else 2
        out[k] = trial.suggest_int(k, max(LOW.get(k, 1), c - step), c + step)
    # 경제 열세 대응(dev12·dev13)
    out["eco_strike"] = trial.suggest_int("eco_strike", 1, 6)
    out["eco_strike_R"] = trial.suggest_int("eco_strike_R", 1, 3)
    out["eco_def_w"] = trial.suggest_float("eco_def_w", 0.0, 1.5)
    out["eco_def_risk"] = trial.suggest_float("eco_def_risk", 0.0, 0.7)
    out["strike_w"] = trial.suggest_int("strike_w", 0, 3)
    out["f_spread"] = trial.suggest_categorical("f_spread", [False, True])
    return out


START = {**{k: BASE[k] for k in FLOATS + INTS}, "eco_strike": 3, "eco_strike_R": 2, "eco_def_w": 0.0, "eco_def_risk": 0.0,
         "strike_w": 0, "f_spread": False}


def game(args):
    seed, opp, side, params = args
    me = Agent(VER, params)
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
    p.add_argument("--seeds", default="80000-80019")
    p.add_argument("--workers", type=int, default=20)
    p.add_argument("--verify", type=int, default=0)
    p.add_argument("--vseeds", default="81000-81099")
    a = p.parse_args()
    work = os.path.join(ROOT, "out/tune", a.study)
    os.makedirs(work, exist_ok=True)
    study = optuna.create_study(study_name=a.study, storage=f"sqlite:///{work}/study.db", load_if_exists=True,
                                direction="maximize", sampler=optuna.samplers.TPESampler(seed=9, multivariate=True))
    done = [t for t in study.trials if t.value is not None]
    if a.verify:
        top = sorted(done, key=lambda t: -t.value)[:a.verify]
        seeds = parse_range(a.vseeds)
        with Pool(a.workers) as pool:
            base, bo, _ = evaluate(pool, {}, seeds, TUNE_OPPS)
            print(f"기준(v16) {base:.4f}", flush=True)
            for t in top:
                v, by, err = evaluate(pool, t.params, seeds, TUNE_OPPS)
                print(f"#{t.number} 탐색 {t.value:.4f} → 검증 {v:.4f} ({v - base:+.4f}) 예외 {err}", flush=True)
                json.dump(t.params, open(os.path.join(work, f"t{t.number}.json"), "w"))
        return
    if not done:
        study.enqueue_trial(START)
    seeds = parse_range(a.seeds)
    with Pool(a.workers) as pool:
        def objective(trial):
            params = space(trial)
            t0 = time.time()
            v, by, err = evaluate(pool, params, seeds, TUNE_OPPS)
            trial.set_user_attr("by_opp", by)
            print(f"#{trial.number} {v:.4f} ({time.time() - t0:.0f}s) 예외 {err}", flush=True)
            return v if err == 0 else v - 0.5
        study.optimize(objective, n_trials=a.trials - len(done))


if __name__ == "__main__":
    main()
