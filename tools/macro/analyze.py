"""branch.py 결과 분석: 방침별 평균, 맵(상태)별 선택 신호의 일반화, 특징 → 방침 선택 모형(교차 검증).

사용: python3 tools/macro/analyze.py out/macro/map0.jsonl [--key map|state]
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, __import__("os").path.dirname(__file__))
from branch import NAMES  # noqa: E402


def load(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    return [r for r in rows if not r.get("done")]


def target(r, lam=0.01):
    """승점 + 작은 연속 지표(동률을 가르기 위한 보조)."""
    v = np.array(r["value"], float)
    m = np.clip(np.array(r["margin"], float), -30, 30)
    return v + lam * m / 30.0


def summary(rows):
    V = np.array([r["value"] for r in rows])
    K = V.shape[1]
    d = V - V[:, :1]
    print(f"행 {len(rows)} · 방침별 평균 승점률(같은 상태 쌍 비교, v13 대비 차 ± 표준오차)")
    for k in range(K):
        se = d[:, k].std() / np.sqrt(len(d))
        print(f"  {k:>2} {NAMES[rows[0]['macros'][k]]:<5} {V[:, k].mean():.3f}  {d[:, k].mean():+.3f} ± {se:.3f}"
              f"  (다름 {np.mean(d[:, k] != 0):.2f})")
    by = defaultdict(list)
    for r in rows:
        by[r["opp"]].append(r["value"])
    print("  상대별 v13 / 최선 방침(사후):")
    for o, vs in by.items():
        a = np.array(vs)
        print(f"    {o:<12} v13 {a[:, 0].mean():.3f}  최고 {NAMES[int(a.mean(0).argmax())]} {a.mean(0).max():.3f}")


def split_test(rows, key, reps=20, seed=0):
    """그룹(맵 또는 맵+진영) 안에서 상대 절반(A)으로 방침을 고르고 나머지(B)에서 평가 → v13 대비 이득."""
    rng = random.Random(seed)
    opps = sorted({r["opp"] for r in rows})
    groups = defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    gains = []
    for _ in range(reps):
        A = set(rng.sample(opps, len(opps) // 2))
        g_sum = n = 0
        for rs in groups.values():
            a = [target(r) for r in rs if r["opp"] in A]
            b = [np.array(r["value"], float) for r in rs if r["opp"] not in A]
            if not a or not b:
                continue
            k = int(np.mean(a, 0).argmax())
            bm = np.mean(b, 0)
            g_sum += (bm[k] - bm[0]) * len(b)
            n += len(b)
        gains.append(g_sum / n)
    return np.mean(gains), np.std(gains)


def fit_select(rows, feat_key, folds=5, alpha=3.0, thresh=0.0, seed=0, verbose=True):
    """리지 회귀로 방침별 (방침 − v13) 이득 예측, 맵 시드 단위 교차 검증. 예측 최대 이득 > thresh 일 때만 바꾼다."""
    names = sorted(rows[0][feat_key].keys())
    X = np.array([[r[feat_key][n] for n in names] for r in rows])
    Y = np.array([target(r) for r in rows])
    V = np.array([r["value"] for r in rows], float)
    D = Y - Y[:, :1]
    seeds = sorted({r["seed"] for r in rows})
    rng = random.Random(seed)
    rng.shuffle(seeds)
    fold_of = {s: i % folds for i, s in enumerate(seeds)}
    fid = np.array([fold_of[r["seed"]] for r in rows])
    gain, picks = 0.0, defaultdict(int)
    for f in range(folds):
        tr, te = fid != f, fid == f
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-6
        Xt = np.c_[(X[tr] - mu) / sd, np.ones(tr.sum())]
        Xe = np.c_[(X[te] - mu) / sd, np.ones(te.sum())]
        reg = alpha * np.eye(Xt.shape[1])
        reg[-1, -1] = 0
        Wt = np.linalg.solve(Xt.T @ Xt + reg, Xt.T @ D[tr])
        P = Xe @ Wt
        P[:, 0] = 0
        k = P.argmax(1)
        k[P.max(1) <= thresh] = 0
        gain += (V[te][np.arange(te.sum()), k] - V[te][:, 0]).sum()
        for kk in k:
            picks[int(kk)] += 1
    gain /= len(rows)
    if verbose:
        pk = ", ".join(f"{NAMES[rows[0]['macros'][k]]}:{c}" for k, c in sorted(picks.items()))
        print(f"  선택 모형(α={alpha}, 문턱 {thresh}) 교차 검증 이득 {gain:+.4f}  선택 분포 {pk}")
    return gain


def main():
    path = sys.argv[1]
    key = "map" if "--key" not in sys.argv else sys.argv[sys.argv.index("--key") + 1]
    rows = load(path)
    if key == "state":
        for t in sorted({r["t"] for r in rows}):
            rt = [r for r in rows if r["t"] == t]
            print(f"\n=== 분기 턴 {t} ===")
            summary(rt)
            m, s = split_test(rt, lambda r: (r["seed"], r["side"]))
            print(f"  상태별 사후 선택의 상대 간 일반화(맵·진영 그룹): {m:+.4f} ± {s:.4f}")
        print("\n=== 전체 턴 합쳐 선택 모형 ===")
        for a in (1.0, 10.0, 100.0):
            for th in (0.0, 0.05):
                fit_select(rows, "state", alpha=a, thresh=th)
        return
    summary(rows)
    for name, kf in (("맵", lambda r: r["seed"]), ("맵+진영", lambda r: (r["seed"], r["side"]))):
        m, s = split_test(rows, kf)
        print(f"  {name}별 사후 선택 → 다른 상대에게 이득: {m:+.4f} ± {s:.4f}")
    for a in (1.0, 10.0, 100.0):
        for th in (0.0, 0.05):
            fit_select(rows, "map", alpha=a, thresh=th)


if __name__ == "__main__":
    main()
