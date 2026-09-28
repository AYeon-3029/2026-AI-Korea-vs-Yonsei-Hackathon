"""신경망 익스플로이터(`Model/sparring/nnbot`) 가중치를 진화 전략(ES)으로 학습한다.

목표: 지정 상대들에게 이기는 것(승점률). 학습 데이터 없이 대전만으로 가중치를 옮긴다.
- 대칭 표본(antithetic): 잡음 ε 마다 θ+σε, θ−σε 두 후보를 같은 시드에서 평가해 분산을 줄인다.
- 세대마다 새 시드 묶음을 쓴다(한 시드 묶음에 과적합 방지). 순위 기반 적합도로 이상값 영향을 줄인다.
- 가중치는 0 에서 시작한다(= v10). 결과는 out/nn/<이름>/ 에 세대별로 저장하고, 최종 가중치를 weights.json 으로 쓴다.

사용 (WSL, 프로젝트 루트): python3 tools/train_nn.py --name nn1 --opps v10 --gens 30 --pop 6 --seeds-per 20
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from arena import play  # noqa: E402
from pool_eval import opp_cmd  # noqa: E402

HEADS = {"w": ("NN_W", 105, "weights.json"), "p": ("NN_P", 134, "policy.json")}
HEAD = "w"
BOT = f"{ROOT}/Model/sparring/nnbot/main.py"


def cmd(w):
    return f"{HEADS[HEAD][0]}='{json.dumps([round(x, 4) for x in w])}' python3 {BOT}"


def evaluate(pool, cands, opps, seeds):
    """후보별 승점률(같은 시드·같은 상대)과 후보×시드 승점률 표."""
    jobs, owner = [], []
    for ci, w in enumerate(cands):
        c = cmd(w)
        for opp in opps:
            oc = opp_cmd(opp)
            for seed in seeds:
                for side in "YK":
                    jobs.append((seed, c, oc, side, "") if side == "Y" else (seed, oc, c, side, ""))
                    owner.append(ci)
    per = [{s: [0.0, 0] for s in seeds} for _ in cands]
    for ci, (seed, side, r, _) in zip(owner, pool.map(play, jobs)):
        cell = per[ci][seed]
        cell[0] += 1.0 if r["winner"] == side else 0.5 if r["winner"] == "DRAW" else 0.0
        cell[1] += 1
    table = [{s: v / n for s, (v, n) in row.items()} for row in per]
    return [sum(row.values()) / len(row) for row in table], table


def curious_pick(rng, buf, k, alpha, beta):
    """Curious Replay 식 우선순위로 지난 맵 k 개를 뽑는다(비복원).

    우선순위 = (후보 간 성적 분산 + 0.01)^alpha × beta^재사용횟수. 분산이 큰 맵 = 후보마다 결과가 갈린 맵 = 정책 차이가
    드러나는 '놀라운' 맵. 재사용할수록 감쇠해 같은 맵에 과적합하지 않게 한다(원 논문의 방문 횟수 항).
    """
    items = [(s, (v + 0.01) ** alpha * beta ** n) for s, (v, n) in buf.items()]
    picked = []
    for _ in range(min(k, len(items))):
        tot = sum(w for _, w in items)
        x = rng.random() * tot
        for i, (s, w) in enumerate(items):
            x -= w
            if x <= 0:
                break
        picked.append(s)
        items.pop(i)
    return picked


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True)
    p.add_argument("--opps", default="v10")
    p.add_argument("--gens", type=int, default=30)
    p.add_argument("--pop", type=int, default=6, help="잡음 표본 수(후보 = 2 × pop)")
    p.add_argument("--sigma", type=float, default=0.3)
    p.add_argument("--lr", type=float, default=0.3)
    p.add_argument("--seeds-per", type=int, default=20)
    p.add_argument("--seed0", type=int, default=5000, help="세대별 시드 시작점(세대마다 새 묶음)")
    p.add_argument("--workers", type=int, default=24)
    p.add_argument("--rng", type=int, default=0)
    p.add_argument("--replay", type=float, default=0.0, help="세대 시드 중 지난 맵을 Curious Replay 우선순위로 다시 쓸 비율(0 = 끔)")
    p.add_argument("--replay-alpha", type=float, default=1.0)
    p.add_argument("--replay-beta", type=float, default=0.6)
    p.add_argument("--head", default="w", choices=sorted(HEADS), help="w = 목표 점수 보정(105), p = 판세별 파라미터 정책(134)")
    args = p.parse_args()
    global HEAD
    HEAD = args.head
    N = HEADS[HEAD][1]

    out = ROOT / "out/nn" / args.name
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.rng)
    theta = [0.0] * N
    opps = args.opps.split(",")
    pool = ProcessPoolExecutor(max_workers=args.workers)
    buf = {}                                             # 시드 → [후보 간 분산, 재사용 횟수]
    for gen in range(args.gens):
        n_rep = round(args.replay * args.seeds_per) if buf else 0
        seeds = curious_pick(rng, buf, n_rep, args.replay_alpha, args.replay_beta)
        fresh0 = args.seed0 + gen * args.seeds_per      # 새 맵은 세대마다 고유 범위에서
        seeds += list(range(fresh0, fresh0 + args.seeds_per - len(seeds)))
        eps = [[rng.gauss(0, 1) for _ in range(N)] for _ in range(args.pop)]
        cands = []
        for e in eps:
            cands.append([t + args.sigma * x for t, x in zip(theta, e)])
            cands.append([t - args.sigma * x for t, x in zip(theta, e)])
        cands.append(theta)                              # 현재 θ 의 성적(기록용)
        fit, table = evaluate(pool, cands, opps, seeds)
        for sd in seeds:
            xs = [row[sd] for row in table[:-1]]
            m = sum(xs) / len(xs)
            buf[sd] = [sum((x - m) ** 2 for x in xs) / len(xs), buf.get(sd, [0, -1])[1] + 1]
        cur = fit[-1]
        fit = fit[:-1]
        # 순위 기반 적합도(−0.5 ~ 0.5)
        order = sorted(range(len(fit)), key=lambda i: fit[i])
        rank = [0.0] * len(fit)
        for r_, i in enumerate(order):
            rank[i] = r_ / (len(fit) - 1) - 0.5
        grad = [0.0] * N
        for k, e in enumerate(eps):
            diff = rank[2 * k] - rank[2 * k + 1]
            for j in range(N):
                grad[j] += diff * e[j]
        theta = [t + args.lr / (args.pop * args.sigma) * g * args.sigma for t, g in zip(theta, grad)]
        best = max(fit)
        rec = {"gen": gen, "theta_rate": round(cur, 4), "best_cand": round(best, 4),
               "mean_cand": round(sum(fit) / len(fit), 4), "norm": round(sum(x * x for x in theta) ** 0.5, 3),
               "replayed": n_rep}
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        (out / f"gen{gen:03d}.json").write_text(json.dumps({"rec": rec, "theta": theta}))
    (out / HEADS[HEAD][2]).write_text(json.dumps([round(x, 5) for x in theta]))
    print(f"저장: {out / HEADS[HEAD][2]}")


if __name__ == "__main__":
    main()
