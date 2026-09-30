"""Optuna 12차: 새 스위치 전용 좁은 탐색(10·11차의 넓은 탐색은 새 시드에서 모두 기준 미만 — 과적합).

탐색 공간은 JSON 파일로 받는다: {"fixed": {...}, "float": {"k": [lo, hi]}, "int": {"k": [lo, hi]}}
목적 = 세 풀(현실 12 · 공세 6 · 흉내 mc16 12) 동일 비중 평균 승점. 시작점 = fixed 만 켠 설정.
사용 (WSL):
  TUNE_VER=dev31 python3 tools/macro/tune12.py --study s12 --space out/tune/s12/space.json --trials 40 --seeds 177000-177019
  TUNE_VER=dev31 python3 tools/macro/tune12.py --study s12 --space out/tune/s12/space.json --verify 5 --vseeds 178000-178099
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

import optuna

sys.path.insert(0, os.path.dirname(__file__))
from tune11 import ROOT, TUNE_OPPS, evaluate  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--study", required=True)
    p.add_argument("--space", required=True)
    p.add_argument("--trials", type=int, default=40)
    p.add_argument("--seeds", default="177000-177019")
    p.add_argument("--workers", type=int, default=24)
    p.add_argument("--verify", type=int, default=0)
    p.add_argument("--vseeds", default="178000-178099")
    a = p.parse_args()
    from branch import parse_range
    sp = json.load(open(a.space, encoding="utf-8"))
    fixed = sp.get("fixed", {})
    work = os.path.join(ROOT, "out/tune", a.study)
    os.makedirs(work, exist_ok=True)
    study = optuna.create_study(study_name=a.study, storage=f"sqlite:///{work}/study.db", load_if_exists=True,
                                direction="maximize", sampler=optuna.samplers.TPESampler(seed=12, multivariate=True))
    done = [t for t in study.trials if t.value is not None]

    def full(params):
        # "ph.<키>" 는 시기별 덮어쓰기 묶음 ph_P 로 모은다
        out = {k: v for k, v in {**fixed, **params}.items() if not k.startswith("ph.")}
        ph = {k[3:]: v for k, v in params.items() if k.startswith("ph.")}
        if ph:
            out["ph_P"] = {**fixed.get("ph_P", {}), **ph}
        return out
    if a.verify:
        top = sorted(done, key=lambda t: -t.value)[:a.verify]
        seeds = parse_range(a.vseeds)
        with Pool(a.workers) as pool:
            base, bp, _ = evaluate(pool, {}, seeds, TUNE_OPPS)
            print(f"기준(스위치 끔) {base:.4f}  " + " ".join(f"{g} {v:.3f}" for g, v in bp.items()), flush=True)
            for t in top:
                v, parts, err = evaluate(pool, full(t.params), seeds, TUNE_OPPS)
                print(f"#{t.number} 탐색 {t.value:.4f} → 검증 {v:.4f} ({v - base:+.4f})  "
                      + " ".join(f"{g} {parts[g] - bp[g]:+.3f}" for g in parts) + f"  예외 {err}  {json.dumps(full(t.params))}", flush=True)
                json.dump(full(t.params), open(os.path.join(work, f"t{t.number}.json"), "w"))
        return
    seeds = parse_range(a.seeds)
    with Pool(a.workers) as pool:
        if not done:
            base, bp, _ = evaluate(pool, {}, seeds, TUNE_OPPS)
            print(f"기준(스위치 끔) {base:.4f}  " + " ".join(f"{g} {v:.3f}" for g, v in bp.items()), flush=True)
            if sp.get("start"):
                study.enqueue_trial(sp["start"])

        def objective(trial):
            params = {k: trial.suggest_float(k, *r) for k, r in sp.get("float", {}).items()}
            params.update({k: trial.suggest_int(k, *r) for k, r in sp.get("int", {}).items()})
            t0 = time.time()
            v, parts, err = evaluate(pool, full(params), seeds, TUNE_OPPS)
            trial.set_user_attr("parts", parts)
            print(f"#{trial.number} {v:.4f} " + " ".join(f"{g} {x:.3f}" for g, x in parts.items())
                  + f" ({time.time() - t0:.0f}s) 예외 {err}  {json.dumps(params)}", flush=True)
            return v if err == 0 else v - 0.5
        study.optimize(objective, n_trials=a.trials - len(done))


if __name__ == "__main__":
    main()
