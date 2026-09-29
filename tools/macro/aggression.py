"""공격성 비교(팀원 관찰: 상대가 침투해 병력을 소모하는 동안 우리는 반격 침투가 없다): 버전별 W 전진 비율과 반격 여부.

- 전진 비율: 20~140턴, 아군 W 중 상대 본진 쪽 절반에 있는 비율
- 방어 이득 후 반격: 한 턴에 우리 진영에서 상대 W 가 우리보다 많이 줄어든(상쇄로 이긴) 뒤 10턴 안에 우리 전진 W 가 늘었는가
사용 (WSL): python3 tools/macro/aggression.py --vers v12,v14 --seeds 66000-66019
"""
from __future__ import annotations

import argparse
import os
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, value  # noqa: E402
from branch import OPPS, REAL_POOL, parse_range  # noqa: E402


def run(args):
    seed, opp, side, ver = args
    me = Agent(ver)
    o = Agent(*OPPS[opp])
    g = Game(seed, *((me, o) if side == "Y" else (o, me)))
    op = "K" if side == "Y" else "Y"
    bm, bo = g.state.bases[side], g.state.bases[op]
    man = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
    fr, fwd_hist, enW_home = [], [], []
    while g.result is None:
        g.step()
        s = g.state
        tot = fw = eh = 0
        for (x, y, t, k), c in s.units.items():
            if k != "W":
                continue
            if t == side:
                tot += c
                fw += c if man((x, y), bo) < man((x, y), bm) else 0
            elif man((x, y), bm) < man((x, y), bo):
                eh += c
        fwd_hist.append(fw)
        enW_home.append(eh)
        if 20 <= s.turn <= 140 and tot:
            fr.append(fw / tot)
    # 방어 이득 사건: 우리 진영 적 W 가 3턴 사이 5명 이상 줄어듦 → 이후 10턴 안 우리 전진 W 최대 증가
    counters = []
    for i in range(3, len(enW_home) - 10):
        if enW_home[i - 3] - enW_home[i] >= 5:
            counters.append(max(fwd_hist[i:i + 10]) - fwd_hist[i])
    return float(np.mean(fr)) if fr else 0.0, counters, value(g.result, side)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--vers", default="v12,v14")
    p.add_argument("--seeds", default="66000-66019")
    a = p.parse_args()
    for ver in a.vers.split(","):
        jobs = [(s, o, side, ver) for s in parse_range(a.seeds) for o in REAL_POOL for side in "YK"]
        with Pool(24) as pool:
            rows = pool.map(run, jobs, chunksize=2)
        c = [x for r in rows for x in r[1]]
        print(f"{ver}: 전진 비율 {np.mean([r[0] for r in rows]):.3f} · 방어 이득 사건 {len(c) / len(rows):.1f}/경기 → "
              f"10턴 안 전진 W 증가 평균 {np.mean(c):.1f}명 (증가 없음 {np.mean([x <= 0 for x in c]):.2f}) · 승점률 {np.mean([r[2] for r in rows]):.3f}")


if __name__ == "__main__":
    main()
