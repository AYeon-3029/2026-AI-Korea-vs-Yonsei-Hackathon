"""Model/main.py 의 P 파라미터를 Optuna 로 탐색한다 (HANDOFF §8-1).

설계
- 목적함수: 자기 대전 리그(pool_eval.LEAGUE) 상대 승점률. 포화된 v1~v4 풀을 더 긁으면 노이즈만
  학습하므로 신호가 남은 상대만 쓴다. 과적합 방어로 상대별 최악 승점률을 함께 넣는다.
    score = 전체 승점률 + WORST_W × 상대별 최소 승점률
  (Optuna 는 다목적 탐색에서 pruning 을 지원하지 않아 두 지표를 하나로 합쳤다.)
- 공통 시드(CRN): 모든 시행을 같은 시드·같은 상대에서 평가해 시행 간 차이의 분산을 줄인다.
- 경기 수 예산 pruning: STAGES 의 시드 묶음을 차례로 더해 가며 누적 점수를 보고하고,
  SuccessiveHalvingPruner 가 확실히 나쁜 시행을 초반에 끊는다. 이것이 속도의 핵심이다.
- 평가 대상 봇은 시작 시 out/tune/<study>/bot/ 로 복사해 고정한다(탐색 중 main.py 를 고쳐도 무관).
- 탐색 시드는 0-79·200-279. 검증 시드 100-179·400-479 는 --verify 에서만 쓴다(winner's curse 대비).

사용 (WSL, 프로젝트 루트에서):
  python3 tools/tune_optuna.py --study s1 --trials 300 --workers 24
  python3 tools/tune_optuna.py --study s1 --report            # 상위 시행 보기
  python3 tools/tune_optuna.py --study s1 --verify 5          # 상위 5개를 검증 시드에서 재평가
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import optuna  # noqa: E402

from arena import parse_seeds, play  # noqa: E402
from pool_eval import LEAGUE, opp_cmd  # noqa: E402

STAGES = ["0-19", "20-39", "40-79", "200-279"]      # 누적 20 → 40 → 80 → 160 시드
VERIFY = "100-179,400-479"
WORST_W = 0.5
BOT_FILES = ["main.py", "protocol.py", "campus_bot.py", "_generated.py", "tactical.py"]


def space(trial: optuna.Trial) -> dict:
    """탐색 범위. 현재 기본값을 가운데쯤 두고, 실측으로 기각한 스위치는 넣지 않는다."""
    return {
        "max_f": trial.suggest_int("max_f", 6, 16),
        "min_f": trial.suggest_int("min_f", 1, 5),
        "min_w": trial.suggest_int("min_w", 0, 5),
        "w_margin": trial.suggest_int("w_margin", 0, 20),
        "guard_radius": trial.suggest_int("guard_radius", 0, 14),
        "dist_offset": trial.suggest_float("dist_offset", 1.0, 10.0),
        "hall_bonus": trial.suggest_float("hall_bonus", 0.0, 10.0),
        "eng_bonus": trial.suggest_float("eng_bonus", 0.0, 10.0),
        "lib_bonus": trial.suggest_float("lib_bonus", 0.0, 5.0),
        "depot_bonus": trial.suggest_float("depot_bonus", 0.0, 6.0),
        "hosp_bonus": trial.suggest_float("hosp_bonus", 0.0, 4.0),
        "center_expect": trial.suggest_float("center_expect", 2.0, 4.0),
        "side_expect": trial.suggest_float("side_expect", 1.0, 2.0),
        "enemy_owned_mult": trial.suggest_float("enemy_owned_mult", 1.0, 2.0),
        "enemy_f_penalty": trial.suggest_float("enemy_f_penalty", 0.0, 1.0),
        "siege_bld_bonus": trial.suggest_float("siege_bld_bonus", 0.0, 10.0),
        "siege_ring_value": trial.suggest_float("siege_ring_value", 0.0, 5.0),
        "chase_mult": trial.suggest_float("chase_mult", 0.3, 1.5),
        "endgame_turn": trial.suggest_int("endgame_turn", 135, 161),
    }


def space_v2(trial: optuna.Trial) -> dict:
    """2차 탐색(v6 이후): v6 값 둘레로 좁히고, v6 이후 만든 스위치를 함께 탐색한다.
    조건부 파라미터를 쓰지 않아(꺼진 스위치의 하위 값도 늘 제안) 기본값을 그대로 첫 시행에 넣을 수 있다."""
    return {
        "max_f": trial.suggest_int("max_f", 4, 10),
        "min_f": trial.suggest_int("min_f", 2, 6),
        "min_w": trial.suggest_int("min_w", 2, 8),
        "w_margin": trial.suggest_int("w_margin", 10, 26),
        "guard_radius": trial.suggest_int("guard_radius", 8, 18),
        "dist_offset": trial.suggest_float("dist_offset", 2.0, 8.0),
        "hall_bonus": trial.suggest_float("hall_bonus", 4.0, 11.0),
        "eng_bonus": trial.suggest_float("eng_bonus", 5.0, 13.0),
        "lib_bonus": trial.suggest_float("lib_bonus", 0.5, 4.0),
        "depot_bonus": trial.suggest_float("depot_bonus", 0.0, 4.0),
        "hosp_bonus": trial.suggest_float("hosp_bonus", 1.0, 5.0),
        "center_expect": trial.suggest_float("center_expect", 2.0, 3.5),
        "side_expect": trial.suggest_float("side_expect", 1.0, 1.6),
        "enemy_owned_mult": trial.suggest_float("enemy_owned_mult", 1.3, 2.4),
        "enemy_f_penalty": trial.suggest_float("enemy_f_penalty", 0.2, 0.8),
        "siege_bld_bonus": trial.suggest_float("siege_bld_bonus", 5.0, 14.0),
        "siege_ring_value": trial.suggest_float("siege_ring_value", 2.0, 6.0),
        "chase_mult": trial.suggest_float("chase_mult", 0.8, 1.8),
        "endgame_turn": trial.suggest_int("endgame_turn", 140, 161),
        # v6 이후 스위치
        "escort_wait": trial.suggest_categorical("escort_wait", [False, True]),
        "escort_dist": trial.suggest_int("escort_dist", 1, 3),
        "escort_bonus": trial.suggest_float("escort_bonus", 0.0, 8.0),
        "f_idle_off": trial.suggest_categorical("f_idle_off", [False, True]),
        "lead_mode": trial.suggest_categorical("lead_mode", ["off", "consolidate"]),
        "lead_w": trial.suggest_categorical("lead_w", ["reserve", "pressure", "rapid"]),
        "lead_margin": trial.suggest_int("lead_margin", 3, 14),
        "lead_min_turn": trial.suggest_int("lead_min_turn", 60, 150),
        "rapid_garrison": trial.suggest_int("rapid_garrison", 1, 3),
    }


def space_v3(trial: optuna.Trial) -> dict:
    """3차 탐색(v11 이후): v11 값 둘레로 좁히고 v9 이후 추가된 엄호·위험 배율·진입 차단을 함께 탐색한다."""
    return {
        "max_f": trial.suggest_int("max_f", 4, 9),
        "min_f": trial.suggest_int("min_f", 3, 6),
        "min_w": trial.suggest_int("min_w", 3, 9),
        "w_margin": trial.suggest_int("w_margin", 18, 34),
        "guard_radius": trial.suggest_int("guard_radius", 10, 18),
        "dist_offset": trial.suggest_float("dist_offset", 3.0, 7.0),
        "hall_bonus": trial.suggest_float("hall_bonus", 6.0, 12.0),
        "eng_bonus": trial.suggest_float("eng_bonus", 6.0, 12.0),
        "lib_bonus": trial.suggest_float("lib_bonus", 1.0, 4.0),
        "depot_bonus": trial.suggest_float("depot_bonus", 0.5, 3.0),
        "hosp_bonus": trial.suggest_float("hosp_bonus", 2.0, 5.0),
        "center_expect": trial.suggest_float("center_expect", 2.0, 3.0),
        "side_expect": trial.suggest_float("side_expect", 1.0, 1.3),
        "enemy_owned_mult": trial.suggest_float("enemy_owned_mult", 1.3, 2.1),
        "enemy_f_penalty": trial.suggest_float("enemy_f_penalty", 0.3, 0.8),
        "siege_bld_bonus": trial.suggest_float("siege_bld_bonus", 5.0, 11.0),
        "siege_ring_value": trial.suggest_float("siege_ring_value", 3.0, 6.5),
        "chase_mult": trial.suggest_float("chase_mult", 1.0, 1.9),
        "endgame_turn": trial.suggest_int("endgame_turn", 145, 161),
        "escort_bonus": trial.suggest_float("escort_bonus", 0.5, 4.0),
        "escort_extra": trial.suggest_int("escort_extra", 1, 4),
        "risk_local_w": trial.suggest_float("risk_local_w", 0.05, 0.35),
        "f_block": trial.suggest_int("f_block", 1, 2),
        "block_worth": trial.suggest_float("block_worth", 1.0, 8.0),
    }


def _exploiter(overrides):
    """익스플로이터(v10 을 이기는 것만 목표로 하는 스파링 상대)용 공간: v2 에서 일부 범위만 특정 전략 쪽으로 좁힌다."""
    def f(trial):
        out = {}
        base = space_v2(_Rec(trial, overrides))
        out.update(base)
        return out
    return f


class _Rec:
    """space_v2 의 suggest 호출을 가로채 지정 파라미터의 범위를 바꾼다."""
    def __init__(self, trial, overrides):
        self.t, self.o = trial, overrides

    def suggest_int(self, name, lo, hi):
        lo, hi = self.o.get(name, (lo, hi))
        return self.t.suggest_int(name, lo, hi)

    def suggest_float(self, name, lo, hi):
        lo, hi = self.o.get(name, (lo, hi))
        return self.t.suggest_float(name, lo, hi)

    def suggest_categorical(self, name, choices):
        return self.t.suggest_categorical(name, self.o.get(name, choices))


SPACES = {"v1": space, "v2": space_v2, "v3": space_v3,
          # 익스플로이터: 돌격형 / 경제형 / 깃발병 물량형
          "x_atk": _exploiter({"guard_radius": (0, 5), "siege_bld_bonus": (8.0, 20.0),
                               "siege_ring_value": (4.0, 10.0), "w_margin": (5, 30)}),
          "x_eco": _exploiter({"eng_bonus": (10.0, 20.0), "hall_bonus": (9.0, 18.0),
                               "w_margin": (20, 40), "guard_radius": (10, 20)}),
          "x_fsw": _exploiter({"max_f": (10, 16), "min_f": (5, 10), "w_margin": (0, 20),
                               "dist_offset": (1.0, 5.0)})}


def defaults(bot_dir: Path) -> dict:
    """고정한 봇의 현재 기본값(첫 시행으로 넣어 기준선으로 삼는다)."""
    sys.path.insert(0, str(bot_dir))
    ns: dict = {}
    src = (bot_dir / "main.py").read_text(encoding="utf-8")
    start = src.index("P = {")
    end = src.index("\n}\n", start) + 2
    exec(src[start:end], {}, ns)
    sys.path.pop(0)
    return ns["P"]


class Evaluator:
    def __init__(self, bot_dir: Path, workers: int, opps: list[str]):
        self.bot = f"python3 {bot_dir}/main.py"
        self.opps = {o: opp_cmd(o) for o in opps}
        self.pool = ProcessPoolExecutor(max_workers=workers)

    def games(self, params: dict, seeds: str) -> dict[str, list[float]]:
        """상대별 경기 결과(1 / 0.5 / 0) 목록."""
        cmd = f"BOT_PARAMS='{json.dumps(params)}' {self.bot}"
        jobs, owner = [], []
        for opp, ocmd in self.opps.items():
            for seed in parse_seeds(seeds):
                for side in "YK":
                    cy, ck = (cmd, ocmd) if side == "Y" else (ocmd, cmd)
                    jobs.append((seed, cy, ck, side, ""))
                    owner.append(opp)
        out: dict[str, list[float]] = {o: [] for o in self.opps}
        for opp, (_, side, r, _) in zip(owner, self.pool.map(play, jobs)):
            if r.get("forfeit"):
                print(f"  경고: 몰수 {opp} {r['forfeit']}", file=sys.stderr, flush=True)
            out[opp].append(1.0 if r["winner"] == side else 0.5 if r["winner"] == "DRAW" else 0.0)
        return out


def summarize(res: dict[str, list[float]]) -> tuple[float, float, float, dict[str, float]]:
    per = {o: sum(v) / len(v) for o, v in res.items()}
    mean = sum(sum(v) for v in res.values()) / sum(len(v) for v in res.values())
    worst = min(per.values())
    return mean + WORST_W * worst, mean, worst, per


def merge(a: dict, b: dict) -> dict:
    return {k: a.get(k, []) + b.get(k, []) for k in set(a) | set(b)}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--study", required=True)
    p.add_argument("--trials", type=int, default=300)
    p.add_argument("--workers", type=int, default=24)
    p.add_argument("--opps", default=",".join(LEAGUE))
    p.add_argument("--space", default="v1", choices=sorted(SPACES), help="탐색 공간(v2 = v6 이후 스위치 포함)")
    p.add_argument("--enqueue", default="", help="첫 시행들로 넣을 추가 파라미터 JSON 목록(기본값에 덮어씀)")
    p.add_argument("--report", action="store_true")
    p.add_argument("--verify", type=int, default=0, help="상위 N개 시행을 검증 시드에서 재평가")
    p.add_argument("--verify-seeds", default=VERIFY, help="검증 시드(기본 100-179,400-479 는 많이 써서 새 시드 권장)")
    args = p.parse_args()

    work = ROOT / "out/tune" / args.study
    bot_dir = work / "bot"
    if not bot_dir.exists():
        bot_dir.mkdir(parents=True)
        for f in BOT_FILES:
            shutil.copy(ROOT / "Model" / f, bot_dir / f)
    storage = f"sqlite:///{work}/study.db"
    study = optuna.create_study(
        study_name=args.study, storage=storage, load_if_exists=True, direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=0, multivariate=True, n_startup_trials=30),
        pruner=optuna.pruners.SuccessiveHalvingPruner(min_resource=1, reduction_factor=3))
    done = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]

    if args.report or args.verify:
        done.sort(key=lambda t: -t.value)
        for t in done[:max(10, args.verify)]:
            a = t.user_attrs
            print(f"#{t.number:>4} score {t.value:.3f} mean {a['mean']:.3f} worst {a['worst']:.3f} "
                  f"{a['per']}")
        if not args.verify:
            print(f"완료 {len(done)} / 전체 {len(study.trials)}")
            return
        ev = Evaluator(bot_dir, args.workers, args.opps.split(","))
        base = {k: v for k, v in defaults(bot_dir).items() if k in done[0].params}
        rows = [("기준(기본값)", base)] + [(f"#{t.number}", t.params) for t in done[:args.verify]]
        for name, params in rows:
            s, mean, worst, per = summarize(ev.games(params, args.verify_seeds))
            per_s = " ".join(f"{o}={v:.3f}" for o, v in per.items())
            print(f"{name:<12} 검증 score {s:.3f} mean {mean:.3f} worst {worst:.3f} | {per_s}",
                  flush=True)
            if name != "기준(기본값)":
                print(f"             {json.dumps(params)}", flush=True)
        return

    ev = Evaluator(bot_dir, args.workers, args.opps.split(","))
    if not study.trials:
        base = defaults(bot_dir)
        keys = SPACES[args.space](optuna.trial.FixedTrial(base)).keys()
        study.enqueue_trial({k: base[k] for k in keys})
        for extra in json.loads(args.enqueue or "[]"):
            study.enqueue_trial({k: {**base, **extra}[k] for k in keys})

    def objective(trial: optuna.Trial) -> float:
        params = SPACES[args.space](trial)
        res: dict = {}
        for step, seeds in enumerate(STAGES):
            res = merge(res, ev.games(params, seeds))
            s, mean, worst, per = summarize(res)
            trial.report(s, step)
            if step < len(STAGES) - 1 and trial.should_prune():
                raise optuna.TrialPruned()
        trial.set_user_attr("mean", round(mean, 4))
        trial.set_user_attr("worst", round(worst, 4))
        trial.set_user_attr("per", {o: round(v, 3) for o, v in per.items()})
        return s

    def log(study: optuna.Study, t: optuna.trial.FrozenTrial) -> None:
        best = study.best_trial if any(
            x.state == optuna.trial.TrialState.COMPLETE for x in study.trials) else None
        tag = (f"{t.value:.3f}" if t.state == optuna.trial.TrialState.COMPLETE
               else f"pruned@{len(t.intermediate_values)}")
        print(f"trial {t.number:>4} {tag:<12} best {best.value:.3f} (#{best.number})"
              if best else f"trial {t.number:>4} {tag}", flush=True)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study.optimize(objective, n_trials=args.trials, n_jobs=1, callbacks=[log])


if __name__ == "__main__":
    main()
