"""v24(새로 짠 봇) Optuna: v2~v14 상대 승점 평균을 최대화한다(새 구조의 기본값이 감으로 정한 값이라 넓게 맞춘다).
사용 (WSL): python3 tools/macro/tune24.py --study t24a --trials 60 --seeds 60000-60029
검증:      python3 tools/macro/tune24.py --study t24a --verify 5 --vseeds 61000-61039
"""
import argparse, json, os, sys, time
from multiprocessing import Pool
import optuna
sys.path.insert(0, os.path.dirname(__file__))
from e24 import one  # noqa: E402
from branch import parse_range  # noqa: E402

OPPS = ["v2", "v4", "v5", "v7", "v9", "v10", "v14"]
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
VER = os.environ.get("TUNE_VER", "v24")


def evaluate(pool, params, seeds):
    jobs = [(s, o, side, VER, params) for s in seeds for o in OPPS for side in "YK"]
    vs = [r[1] for r in pool.imap_unordered(one, jobs, chunksize=2)]
    return sum(vs) / len(vs)


def suggest(t):
    return {
        "hall_bonus": t.suggest_float("hall_bonus", 0, 10), "eng_bonus": t.suggest_float("eng_bonus", 0, 8),
        "depot_bonus": t.suggest_float("depot_bonus", 0, 8), "plaza_bonus": t.suggest_float("plaza_bonus", 0, 5),
        "enemy_mult": t.suggest_float("enemy_mult", 1.0, 3.0),
        "max_f_early": t.suggest_int("max_f_early", 4, 10), "max_f": t.suggest_int("max_f", 3, 9),
        "early_turn": t.suggest_int("early_turn", 10, 60),
        "def_radius": t.suggest_int("def_radius", 1, 4), "def_mult": t.suggest_float("def_mult", 0.5, 4),
        "def_extra": t.suggest_int("def_extra", 0, 3), "def_fr": t.suggest_int("def_fr", 1, 5),
        "block_k": t.suggest_int("block_k", 0, 4), "block_mult": t.suggest_float("block_mult", 0.5, 5),
        "block_need_k": t.suggest_int("block_need_k", 1, 3),
        "hunt_range": t.suggest_int("hunt_range", 1, 6), "hunt_worth": t.suggest_float("hunt_worth", 0.5, 8),
        "main_c": t.suggest_float("main_c", 1, 10), "main_extra": t.suggest_int("main_extra", 0, 6),
        "main_stick": t.suggest_float("main_stick", 1.0, 3.0), "main_neutral": t.suggest_float("main_neutral", 0.2, 1.5),
        "main_depth": t.suggest_float("main_depth", 0, 1.0), "stage": t.suggest_int("stage", -1, 5),
        "f_c": t.suggest_float("f_c", 0.5, 6), "f_stick": t.suggest_float("f_stick", 1.0, 3.0),
        "f_risk": t.suggest_float("f_risk", 0, 2), "f_horizon": t.suggest_int("f_horizon", 1, 5),
        "f_depth": t.suggest_float("f_depth", 0, 1), "escort_extra": t.suggest_int("escort_extra", 0, 3),
        "eco_min": t.suggest_int("eco_min", 0, 4), "picket": t.suggest_categorical("picket", [False, True]),
        "w_safe": t.suggest_categorical("w_safe", [False, True]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", required=True)
    ap.add_argument("--trials", type=int, default=60)
    ap.add_argument("--seeds", default="60000-60029")
    ap.add_argument("--verify", type=int, default=0)
    ap.add_argument("--vseeds", default="61000-61039")
    ap.add_argument("--workers", type=int, default=28)
    a = ap.parse_args()
    d = os.path.join(ROOT, "out/tune", a.study)
    os.makedirs(d, exist_ok=True)
    st = optuna.create_study(study_name=a.study, storage=f"sqlite:///{d}/study.db", direction="maximize", load_if_exists=True,
                             sampler=optuna.samplers.TPESampler(seed=1, multivariate=True))
    seeds = parse_range(a.seeds)
    with Pool(a.workers) as pool:
        if a.verify:
            base = evaluate(pool, {}, parse_range(a.vseeds))
            print(f"기본 {base:.3f}", flush=True)
            top = sorted([t for t in st.trials if t.value is not None], key=lambda t: -t.value)[:a.verify]
            for t in top:
                v = evaluate(pool, t.params, parse_range(a.vseeds))
                print(f"#{t.number} 탐색 {t.value:.3f} 검증 {v:.3f} ({v - base:+.3f}) {json.dumps(t.params)}", flush=True)
            return
        if not st.trials:
            st.enqueue_trial({})
        for _ in range(a.trials):
            t = st.ask()
            p = suggest(t) if t.number > 0 or t.params else {}
            if t.number == 0 and not t.params:
                p = {}
            t0 = time.time()
            v = evaluate(pool, p, seeds)
            st.tell(t, v)
            print(f"#{t.number} {v:.3f} (최고 {st.best_value:.3f}) {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
