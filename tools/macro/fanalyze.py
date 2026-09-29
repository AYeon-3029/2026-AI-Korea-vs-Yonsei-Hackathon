"""fdev.py 결과 분석·학습: 깃발병 목표 배정의 보정 점수 r(φ) 를 학습한다.

모형: 후보 점수 = log(v13 점수) + w·φ(나머지 특징) 에서, 1순위 b 대신 대안 a 를 고르는 게 나은지(이득 > 0)를
로지스틱 순위 학습(pairwise)으로 맞춘다: P(a 가 낫다) = σ(w·(φa − φb) + (log sa − log sb)).
v13 의 선택은 w = 0(보정 없음)과 같다. 이득이 0 인(결과가 같은) 쌍은 쓰지 않고, 점수 차 이득 크기로 가중한다.

사용: python3 tools/macro/fanalyze.py out/macro/fdev0.jsonl [--save out/macro/fw.json]
"""
from __future__ import annotations

import json
import sys

import numpy as np

FEAT = ["logs", "d", "turn", "enemy_owned", "known", "score", "threat", "cover", "enW2", "enW4", "myW2", "myW4",
        "enF_d", "enSpawn_d", "mySpawn_d", "enF_on", "central",
        "HALL", "LIBRARY", "ENG", "HOSPITAL", "STATION", "WATCH", "DEPOT", "PLAZA"]


def load(path):
    R = [json.loads(l) for l in open(path, encoding="utf-8")]
    fb = np.array([r["fb"] for r in R])
    fa = np.array([r["fa"] for r in R])
    dv = np.array([r["dv"] for r in R])
    dm = np.array([r["dm"] for r in R])
    seeds = np.array([r["seed"] for r in R])
    return R, fb, fa, dv, dm, seeds


def design(fb, fa):
    """보정 특징: 차이 Δφ(log 점수 제외) + 차이 × 턴 진행(후반에 달라지는 효과)."""
    d = (fa - fb)[:, 1:]
    t = fb[:, 2:3]
    return np.c_[d, d * t]


def fit(X, off, y, wt, l2=1.0, iters=300, lr=0.5):
    """가중 로지스틱 회귀(오프셋 = log 점수 차, 계수 1 고정). 경사 하강."""
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        z = X @ w + off
        p = 1 / (1 + np.exp(-np.clip(z, -30, 30)))
        g = X.T @ ((p - y) * wt) / wt.sum() + l2 * w / len(y)
        w -= lr * g
    return w


def main():
    path = sys.argv[1]
    R, fb, fa, dv, dm, seeds = load(path)
    n = len(R)
    print(f"이탈 {n}건 · 승점 변화: 좋아짐 {np.mean(dv > 0):.3f} 나빠짐 {np.mean(dv < 0):.3f} (평균 {dv.mean():+.4f})")
    print(f"  연속 지표 변화: 좋아짐 {np.mean(dm > 0):.3f} 나빠짐 {np.mean(dm < 0):.3f} 같음 {np.mean(dm == 0):.3f} (평균 {dm.mean():+.3f})")
    for rk in (1, 2):
        m = np.array([r["rank"] == rk for r in R])
        print(f"  {rk}순위 다른 목표: 승점 {dv[m].mean():+.4f}  지표 {dm[m].mean():+.3f}")
    # 이득 신호: 승점 변화를 우선, 같으면 연속 지표
    gain = dv + 0.02 * np.clip(dm, -30, 30) / 30
    use = gain != 0
    X = design(fb, fa)
    off = fa[:, 0] - fb[:, 0]
    y = (gain > 0).astype(float)
    wt = np.abs(gain)
    mu, sd = X[use].mean(0), X[use].std(0) + 1e-6
    Xs = (X - mu) / sd
    # 시드 단위 5겹 교차 검증: 예측 '대안이 낫다' 인 이탈만 실제로 한다고 할 때 평균 이득
    us = np.unique(seeds)
    rng = np.random.default_rng(0)
    rng.shuffle(us)
    fold = {s: i % 5 for i, s in enumerate(us)}
    fid = np.array([fold[s] for s in seeds])
    for l2 in (1.0, 30.0, 300.0):
        for th in (0.5, 0.6, 0.7):
            tot_dv = tot_dm = cnt = 0
            for f in range(5):
                tr = (fid != f) & use
                te = fid == f
                w = fit(Xs[tr], off[tr], y[tr], wt[tr], l2=l2)
                p = 1 / (1 + np.exp(-(Xs[te] @ w + off[te])))
                pick = p > th
                tot_dv += dv[te][pick].sum()
                tot_dm += dm[te][pick].sum()
                cnt += pick.sum()
            print(f"  l2={l2:<6} 문턱 {th}: 이탈 선택 {cnt} ({cnt / n:.3f})  선택 이탈의 평균 승점 {tot_dv / max(1, cnt):+.4f}"
                  f"  지표 {tot_dm / max(1, cnt):+.3f}")
    if "--save" in sys.argv:
        w = fit(Xs[use], off[use], y[use], wt[use], l2=30.0)
        out = sys.argv[sys.argv.index("--save") + 1]
        json.dump({"w": w.tolist(), "mu": mu.tolist(), "sd": sd.tolist()}, open(out, "w"))
        names = [f"Δ{x}" for x in FEAT[1:]] + [f"Δ{x}×t" for x in FEAT[1:]]
        top = np.argsort(-np.abs(w))[:12]
        print("  큰 계수:", ", ".join(f"{names[i]} {w[i]:+.2f}" for i in top))
        print(f"  저장 {out}")


if __name__ == "__main__":
    main()
