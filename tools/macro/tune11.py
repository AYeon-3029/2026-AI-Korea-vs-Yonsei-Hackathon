"""Optuna 11차: cv-3 중심(좁은 범위 0.8~1.25배, 정수 ±1~2) · 상대 = 현실 풀 12 + 공세형 6 + 실전 흉내 봇 mc16 12(9/30 08시 회차, cv-3 바탕).

10차의 탐색 시드 과적합을 줄이려고 범위를 좁히고 흉내 봇(실전 강도 재현)을 목적에 넣는다. 시작점 = cv-3 기본값(enqueue {}).
사용 (WSL):
  python3 tools/macro/tune11.py --study s11 --trials 200 --seeds 140000-140019
  python3 tools/macro/tune11.py --study s11 --verify 8 --vseeds 141000-141099
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
from branch import MIMIC, OPPS, PUSH_POOL, REAL_POOL, parse_range  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
VER = os.environ.get("TUNE_VER", "cv-3")
TUNE_OPPS = REAL_POOL + PUSH_POOL + ["semi14_press"] + MIMIC["mc16"]
BASE = copy.deepcopy(module(VER).P)

FLOATS = ["center_expect", "side_expect", "hall_bonus", "depot_bonus", "hosp_bonus", "eng_bonus", "lib_bonus",
          "enemy_owned_mult", "enemy_f_penalty", "dist_offset", "chase_mult", "siege_bld_bonus", "siege_ring_value",
          "block_worth", "escort_bonus", "risk_local_w", "retake_w", "retake_risk", "eco_block_worth", "rush_k",
          "eco_def_w", "eco_def_risk"]
INTS = ["max_f", "min_f", "min_w", "w_margin", "guard_radius", "escort_extra", "escort_dist", "eco_block_extra", "f_block",
        "siege_stage", "tele_min_gain", "endgame_turn", "max_f_early", "f_own_R", "eco_strike", "eco_strike_R"]
LOW = {"max_f": 3, "min_f": 2, "min_w": 2, "escort_dist": 1, "eco_block_extra": 0, "f_block": 0, "siege_stage": 1,
       "tele_min_gain": 1, "max_f_early": 3, "f_own_R": 0, "eco_strike": 1, "eco_strike_R": 2}


def space(trial: optuna.Trial) -> dict:
    out = {}
    for k in FLOATS:
        c = BASE[k]
        out[k] = trial.suggest_float(k, 0.8 * c, 1.25 * c) if c else trial.suggest_float(k, 0.0, 0.5)
    for k in INTS:
        c = BASE[k]
        step = 3 if k in ("w_margin", "endgame_turn") else 1
        out[k] = trial.suggest_int(k, max(LOW.get(k, 1), c - step), c + step)
    return out


def game(args):
    seed, opp, side, params = args
    me = Agent(VER, params)
    o = Agent(*OPPS[opp])
    r = play(seed, *((me, o) if side == "Y" else (o, me)))
    return opp, value(r, side), me.errors


def evaluate(pool, params, seeds, opps):
    jobs = [(s, o, side, params) for s in seeds for o in opps for side in "YK"]
    by, err = {}, 0
    for opp, v, e in pool.imap_unordered(game, jobs, chunksize=4):
        by.setdefault(opp, []).append(v)
        err += e
    grp = {"real": REAL_POOL, "push": PUSH_POOL + ["semi14_press"], "mimic": MIMIC["mc16"]}
    parts = {g: float(np.mean([v for o in os_ for v in by.get(o, [])])) for g, os_ in grp.items()}
    return float(np.mean(list(parts.values()))), parts, err       # 세 풀 동일 비중


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--study", required=True)
    p.add_argument("--trials", type=int, default=200)
    p.add_argument("--seeds", default="140000-140019")
    p.add_argument("--workers", type=int, default=24)
    p.add_argument("--verify", type=int, default=0)
    p.add_argument("--vseeds", default="141000-141099")
    a = p.parse_args()
    work = os.path.join(ROOT, "out/tune", a.study)
    os.makedirs(work, exist_ok=True)
    study = optuna.create_study(study_name=a.study, storage=f"sqlite:///{work}/study.db", load_if_exists=True,
                                direction="maximize", sampler=optuna.samplers.TPESampler(seed=11, multivariate=True))
    done = [t for t in study.trials if t.value is not None]
    if a.verify:
        top = sorted(done, key=lambda t: -t.value)[:a.verify]
        seeds = parse_range(a.vseeds)
        with Pool(a.workers) as pool:
            base, bp, _ = evaluate(pool, {}, seeds, TUNE_OPPS)
            print(f"기준 cv-3 {base:.4f}  " + " ".join(f"{g} {v:.3f}" for g, v in bp.items()), flush=True)
            for t in top:
                v, parts, err = evaluate(pool, t.params, seeds, TUNE_OPPS)
                print(f"#{t.number} 탐색 {t.value:.4f} → 검증 {v:.4f} ({v - base:+.4f})  "
                      + " ".join(f"{g} {parts[g] - bp[g]:+.3f}" for g in parts) + f"  예외 {err}", flush=True)
                json.dump(t.params, open(os.path.join(work, f"t{t.number}.json"), "w"))
        return
    if not done:
        study.enqueue_trial({k: BASE[k] for k in FLOATS + INTS})
    seeds = parse_range(a.seeds)
    with Pool(a.workers) as pool:
        def objective(trial):
            params = space(trial)
            t0 = time.time()
            v, parts, err = evaluate(pool, params, seeds, TUNE_OPPS)
            trial.set_user_attr("parts", parts)
            print(f"#{trial.number} {v:.4f} " + " ".join(f"{g} {x:.3f}" for g, x in parts.items())
                  + f" ({time.time() - t0:.0f}s) 예외 {err}", flush=True)
            return v if err == 0 else v - 0.5
        study.optimize(objective, n_trials=a.trials - len(done))


if __name__ == "__main__":
    main()
