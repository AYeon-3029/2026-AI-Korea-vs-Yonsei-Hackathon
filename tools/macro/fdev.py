"""깃발병 목표 배정 한 번을 v13 1순위 대신 다른 후보로 바꿔 끝까지 둔 결과 — 결정 단위 이득 데이터.

작업 = (시드, 상대, 내 진영). v13h(훅 달린 v13) 대 상대 경기를 진행하면서 무작위 턴 τ 들에서 경기를 복제하고,
그 턴 첫 배정(가장 점수 높은 깃발병·목표 쌍)을 1순위와 다른 목표의 k번째 후보로 바꾼 뒤 나머지는 v13 그대로 둔다.
기록: 1순위·대안 특징, 이득(대안 결과 − 원래 결과; 승점, 연속 지표). 결정적이므로 이득은 잡음 없는 쌍 비교다.

사용 (WSL): python3 tools/macro/fdev.py --seeds 24000-24299 --out out/macro/fdev0.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, TOTAL, margin, value  # noqa: E402
from branch import OPPS, POOL, parse_range  # noqa: E402


class Force:
    """turn 턴의 첫 배정에서 1순위와 다른 목표 중 rank 번째 후보를 고른다. 고른 두 후보의 특징을 남긴다."""

    def __init__(self, turn, rank):
        self.turn, self.rank = turn, rank
        self.done = False
        self.rec = None

    def __call__(self, view, cands, feat):
        if self.done or view.turn != self.turn:
            return None
        self.done = True
        best_t = cands[0][2]
        seen, alts = {best_t}, []
        for i, c in enumerate(cands):
            if c[2] not in seen:
                seen.add(c[2])
                alts.append(i)
        if len(alts) < self.rank:
            return None
        i = alts[self.rank - 1]
        self.rec = {"fb": feat(*cands[0][1:5]), "fa": feat(*cands[i][1:5]),
                    "nc": len(cands), "nt": len(seen)}
        return i


def job(args):
    seed, opp, side, n_tau, ranks = args
    rng = random.Random(seed * 1009 + (side == "K") * 7 + sum(map(ord, opp)))
    taus = sorted(rng.sample(range(3, TOTAL - 5), n_tau))
    me = Agent("v13h")
    ver, params = OPPS[opp]
    other = Agent(ver, params)
    g = Game(seed, *((me, other) if side == "Y" else (other, me)))
    forks = []
    for tau in taus:
        g.run(until=tau - 1)
        if g.result is not None:
            break
        for r in ranks:
            h = g.fork()
            hook = Force(tau, r)
            h.agents[side].hook = hook
            forks.append((tau, r, hook, h))
    g.run()
    base_v, base_m = value(g.result, side), margin(g, side)
    out = []
    for tau, r, hook, h in forks:
        h.run()
        if hook.rec is None:
            continue
        rec = dict(hook.rec)
        rec.update({"seed": seed, "opp": opp, "side": side, "tau": tau, "rank": r,
                    "dv": value(h.result, side) - base_v, "dm": round(margin(h, side) - base_m, 4)})
        out.append(rec)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", required=True)
    p.add_argument("--opps", default=",".join(POOL))
    p.add_argument("--taus", type=int, default=8)
    p.add_argument("--ranks", default="1,2")
    p.add_argument("--workers", type=int, default=24)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    ranks = [int(x) for x in a.ranks.split(",")]
    jobs = [(s, o, side, a.taus, ranks) for s in parse_range(a.seeds) for o in a.opps.split(",") for side in "YK"]
    t0 = time.time()
    n = 0
    with Pool(a.workers) as pool, open(a.out, "w", encoding="utf-8") as f:
        for i, rows in enumerate(pool.imap_unordered(job, jobs, chunksize=1), 1):
            for r in rows:
                f.write(json.dumps(r) + "\n")
            n += len(rows)
            if i % 200 == 0:
                print(f"{i}/{len(jobs)} 이탈 {n} {time.time() - t0:.0f}s", flush=True)
    print(f"완료 {len(jobs)}건 이탈 {n} {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
