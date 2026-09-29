"""Optuna 6차: v14 중심, 넓은 공간(5차에서 빠진 초반·가치 파라미터 + 깃발 뽑힘 방지·정찰), v14 계열 상대 풀.

봇 = Model/history/dev4 (v14 + f_own_*(안정 정렬 수정본) · f_no_station_wait 코드). 시작점 = v14 기본값(enqueue).
시행 = 상대 12종 × 고정 시드 × 양 진영(시드 공유로 비교 잡음을 줄인다).

사용 (WSL):
  python3 tools/macro/tune6.py --study s6 --trials 400
  python3 tools/macro/tune6.py --study s6 --verify 6 --vseeds 46000-46099
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
from branch import OPPS, SRV12_ECO, SRV12_EGF, SRV12_PRESS, parse_range  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
# 6차는 dev4(삭제됨, dev7 에서 f_own_* 외 스위치를 끄면 같다)로 돌렸다. 기본값은 오늘 스위치를 모두 담은 dev7.
VER = os.environ.get("TUNE_VER", "dev7")
# v14 기반 스타일 변형(실제 서버 모방 스타일을 v14 위에)
OPPS["v14"] = ("v14", {})
OPPS["srv14_press"] = ("v14", SRV12_PRESS)
OPPS["srv14_eco"] = ("v14", SRV12_ECO)
OPPS["srv14_egf"] = ("v14", SRV12_EGF)
OPPS["x14_rush"] = ("v14", {"max_f": 3, "min_f": 2, "w_margin": 40, "guard_radius": 4, "siege_bld_bonus": 14.0,
                            "siege_ring_value": 8.0, "risk_local_w": 0.0})
OPPS["x14_fswarm"] = ("v14", {"max_f": 9, "min_f": 7, "min_w": 3, "w_margin": 10})
TUNE_OPPS = ["v14", "srv14_press", "srv14_eco", "srv14_egf", "x14_rush", "x14_fswarm",
             "v13", "b72", "srv12_press", "x_press", "x_eco", "x_center"]
# 7차 현실 풀: 실제 상대의 'F 가 1칸 옆 도착 → 3턴 안 탈취 허용률' 0.50(tools/real_react.py)에 맞춘 중간형 6 + 반응형 강자 6
# (중간형 0.48~0.55, 반응형 0.37~0.43, 평균 ≈ 0.46). 중간형은 진입 차단을 끈 v14 변형과 진입 차단 이전 버전(v10·v9).
SEMI = {"f_block": 0, "eco_block_extra": 0}
OPPS["semi14"] = ("dev5", SEMI)
OPPS["semi14_g6"] = ("dev5", dict(SEMI, guard_radius=6))
OPPS["semi14_press"] = ("dev5", dict(SEMI, guard_radius=8, siege_bld_bonus=12.0, siege_ring_value=6.0, w_margin=34))
OPPS["semi14_eco"] = ("dev5", dict(SEMI, eng_bonus=16.0, hall_bonus=16.0,
                                   deny={"ENG": 6.0, "LIBRARY": 1.5, "HALL": 6.0, "HOSPITAL": 1.0}))
OPPS.setdefault("v9", ("v9", {}))
REAL_OPPS = ["semi14", "semi14_g6", "semi14_press", "semi14_eco", "v10", "v9",
             "v14", "srv14_press", "srv14_eco", "b72", "x_press", "x_eco"]
if os.environ.get("TUNE_POOL") == "real":
    TUNE_OPPS = REAL_OPPS

V14 = {"max_f": 5, "min_f": 5, "min_w": 5, "w_margin": 27, "guard_radius": 15, "risk_local_w": 0.4215, "hall_bonus": 8.7462,
       "eng_bonus": 8.1937, "escort_extra": 5, "siege_bld_bonus": 9.7066, "enemy_owned_mult": 1.7663,
       "eco_block_extra": 3, "eco_block_worth": 2.8223, "f_block": 1, "block_worth": 2.868, "retake_w": 0.3904,
       "retake_risk": 0.0979, "rush_k": 0.1173,
       "center_expect": 2.2857, "side_expect": 1.2124, "dist_offset": 4.9975, "depot_bonus": 2.2573, "lib_bonus": 2.9107,
       "hosp_bonus": 3.744, "chase_mult": 1.3194, "escort_dist": 3, "escort_bonus": 1.0011, "siege_ring_value": 3.1323,
       "siege_stage": 3, "endgame_turn": 148, "enemy_f_penalty": 0.9432, "tele_min_gain": 3,
       "early_turn": 0, "max_f_early": 5, "f_own_R": 0, "f_no_station_wait": False}


def space(trial: optuna.Trial) -> dict:
    f = trial.suggest_float
    i = trial.suggest_int
    extra = {}
    if VER not in ("dev3", "dev4"):   # dev5 부터: 미끼(사용자 제안). 실제 상대가 중간 정도로 반응하므로 현실 풀에서 판단한다
        extra = {"feint_n": i("feint_n", 0, 4), "feint_sep": i("feint_sep", 3, 8)}
    return extra | {
        "max_f": i("max_f", 4, 8), "min_f": i("min_f", 3, 6), "min_w": i("min_w", 3, 8), "w_margin": i("w_margin", 20, 34),
        "guard_radius": i("guard_radius", 10, 20), "risk_local_w": f("risk_local_w", 0.25, 0.65),
        "hall_bonus": f("hall_bonus", 5.0, 13.0), "eng_bonus": f("eng_bonus", 5.0, 13.0), "escort_extra": i("escort_extra", 3, 7),
        "siege_bld_bonus": f("siege_bld_bonus", 6.0, 13.0), "enemy_owned_mult": f("enemy_owned_mult", 1.3, 2.3),
        "eco_block_extra": i("eco_block_extra", 2, 5), "eco_block_worth": f("eco_block_worth", 0.5, 5.0),
        "f_block": i("f_block", 0, 2), "block_worth": f("block_worth", 1.5, 5.0),
        "retake_w": f("retake_w", 0.0, 1.0), "retake_risk": f("retake_risk", 0.0, 0.5), "rush_k": f("rush_k", 0.0, 0.4),
        # 5차에서 빠진 파라미터
        "center_expect": f("center_expect", 1.8, 3.2), "side_expect": f("side_expect", 0.9, 1.6),
        "dist_offset": f("dist_offset", 3.0, 7.0), "depot_bonus": f("depot_bonus", 1.0, 4.0), "lib_bonus": f("lib_bonus", 1.5, 4.5),
        "hosp_bonus": f("hosp_bonus", 2.0, 5.5), "chase_mult": f("chase_mult", 0.9, 1.8), "escort_dist": i("escort_dist", 2, 4),
        "escort_bonus": f("escort_bonus", 0.3, 2.5), "siege_ring_value": f("siege_ring_value", 1.5, 5.0),
        "siege_stage": i("siege_stage", 1, 4), "endgame_turn": i("endgame_turn", 140, 156),
        "enemy_f_penalty": f("enemy_f_penalty", 0.5, 1.0), "tele_min_gain": i("tele_min_gain", 2, 4),
        # 초반·새 스위치
        # 초반 F 늘리기는 재검에서 손해(6·7·8 → −0.02·−0.05·−0.08)라 줄이는 쪽만 본다. 정찰병은 −0.04~−0.05 로 제외.
        "early_turn": trial.suggest_categorical("early_turn", [0, 20, 30, 40]), "max_f_early": i("max_f_early", 3, 5),
        "f_own_R": i("f_own_R", 0, 4), "f_no_station_wait": trial.suggest_categorical("f_no_station_wait", [False, True]),
    }


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
    p.add_argument("--trials", type=int, default=400)
    p.add_argument("--seeds", default="45000-45039")
    p.add_argument("--workers", type=int, default=24)
    p.add_argument("--verify", type=int, default=0)
    p.add_argument("--vseeds", default="46000-46099")
    a = p.parse_args()
    work = os.path.join(ROOT, "out/tune", a.study)
    os.makedirs(work, exist_ok=True)
    study = optuna.create_study(study_name=a.study, storage=f"sqlite:///{work}/study.db", load_if_exists=True,
                                direction="maximize", sampler=optuna.samplers.TPESampler(seed=6, multivariate=True))
    done = [t for t in study.trials if t.value is not None]
    if a.verify:
        top = sorted(done, key=lambda t: -t.value)[:a.verify]
        seeds = parse_range(a.vseeds)
        with Pool(a.workers) as pool:
            base, bo, _ = evaluate(pool, {}, seeds, TUNE_OPPS)
            print(f"기준(v14) {base:.4f}  " + " ".join(f"{o}={v:.3f}" for o, v in sorted(bo.items())))
            for t in top:
                v, by, err = evaluate(pool, t.params, seeds, TUNE_OPPS)
                print(f"#{t.number} 탐색 {t.value:.4f} → 검증 {v:.4f} ({v - base:+.4f}) 예외 {err}  "
                      + " ".join(f"{o}={x:.3f}" for o, x in sorted(by.items())))
                json.dump(t.params, open(os.path.join(work, f"t{t.number}.json"), "w"))
        return
    if not done:
        study.enqueue_trial(V14 if VER in ("dev3", "dev4") else dict(V14, feint_n=0, feint_sep=5))
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
