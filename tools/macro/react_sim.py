"""로컬 상대의 위협 반응률을 실제 리플레이와 같은 지표(tools/real_react.py)로 잰다 — 상대 모방이 실제와 맞는지 확인용.

우리 = v14, 상대 = OPPS 이름. 위협 사건: 상대 건물 1칸 안에 우리 F(또는 W)가 새로 옴 + 건물 2칸 안 상대 W 0.
반응: 2턴 안 그 건물 1칸 안 상대 W ≥ 1(F) / ≥ 우리 수(W). 대조: 우리 유닛 3칸 밖·상대 W 없는 상대 건물에 2턴 안 상대 W 가 옴.

사용 (WSL): python3 tools/macro/react_sim.py --opps v14,nr14 --seeds 47000-47019
"""
from __future__ import annotations

import argparse
import os
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, value  # noqa: E402
from branch import OPPS, parse_range  # noqa: E402

NR = {"react": False}
OPPS["v14"] = ("v14", {})
OPPS["nr14"] = ("dev5", NR)
OPPS["nr14_press"] = ("dev5", dict(NR, guard_radius=8, siege_bld_bonus=12.0, siege_ring_value=6.0, w_margin=34))
OPPS["nr14_eco"] = ("dev5", dict(NR, eng_bonus=16.0, hall_bonus=16.0,
                                 deny={"ENG": 6.0, "LIBRARY": 1.5, "HALL": 6.0, "HOSPITAL": 1.0}))
OPPS["nr14_fswarm"] = ("dev5", dict(NR, max_f=8, min_f=6, min_w=4, w_margin=15))
# 중간형: 반응은 하되 진입 차단 없음(실제 상대의 탈취 허용률 0.50 에 맞추려는 후보)
OPPS.setdefault("v9", ("v9", {}))
SEMI = {"f_block": 0, "eco_block_extra": 0}
OPPS["semi14"] = ("dev5", SEMI)
OPPS["semi14_g6"] = ("dev5", dict(SEMI, guard_radius=6))
OPPS["semi14_press"] = ("dev5", dict(SEMI, guard_radius=8, siege_bld_bonus=12.0, siege_ring_value=6.0, w_margin=34))
OPPS["semi14_eco"] = ("dev5", dict(SEMI, eng_bonus=16.0, hall_bonus=16.0,
                                   deny={"ENG": 6.0, "LIBRARY": 1.5, "HALL": 6.0, "HOSPITAL": 1.0}))


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def run(args):
    seed, opp, side, kind = args
    me = Agent("v14")
    o = Agent(*OPPS[opp])
    g = Game(seed, *((me, o) if side == "Y" else (o, me)))
    op = "K" if side == "Y" else "Y"
    frames = []
    while g.result is None:
        g.step()
        s = g.state
        ew = {}
        th = {}
        for (x, y, t, k), c in s.units.items():
            if t == op and k == "W":
                ew[(x, y)] = ew.get((x, y), 0) + c
            if t == side and k == kind:
                th[(x, y)] = th.get((x, y), 0) + c
        own = {(b.x, b.y): b.owner for b in s.buildings.values()}
        frames.append((ew, own, th))
    cnt = lambda d, p, R: sum(n for c, n in d.items() if man(c, p) <= R)
    ev = rs = ctl = ctlr = 0
    arr = taken = 0      # 조건 없이: 우리 유닛이 상대 건물 1칸 안에 새로 옴 → 3턴 안 그 건물이 상대 소유가 아니게 됨
    for i in range(1, len(frames) - 3):
        ew, own, th = frames[i]
        pth = frames[i - 1][2]
        for p, w in own.items():
            if w != op:
                continue
            mine = cnt(th, p, 1)
            if mine and not cnt(pth, p, 1):
                arr += 1
                taken += any(frames[i + k][1][p] != op for k in (1, 2, 3))
            if mine and not cnt(pth, p, 1) and cnt(ew, p, 2) == 0:
                ev += 1
                need = 1 if kind == "F" else mine
                rs += cnt(frames[i + 1][0], p, 1) >= need or cnt(frames[i + 2][0], p, 1) >= need
            elif cnt(th, p, 3) == 0 and cnt(ew, p, 1) == 0:
                ctl += 1
                ctlr += cnt(frames[i + 1][0], p, 1) > 0 or cnt(frames[i + 2][0], p, 1) > 0
    return opp, ev, rs, ctl, ctlr, value(g.result, side), arr, taken


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--opps", default="v14,nr14,nr14_press,nr14_eco,nr14_fswarm,x_press")
    p.add_argument("--seeds", default="47000-47019")
    p.add_argument("--kind", default="F")
    a = p.parse_args()
    jobs = [(s, o, side, a.kind) for s in parse_range(a.seeds) for o in a.opps.split(",") for side in "YK"]
    with Pool(24) as pool:
        rows = pool.map(run, jobs)
    for o in a.opps.split(","):
        r = np.array([x[1:] for x in rows if x[0] == o], float)
        print(f"{o:<12} {a.kind} 위협 {int(r[:, 0].sum()):>4}건 반응 {r[:, 1].sum() / max(1, r[:, 0].sum()):.2f}"
              f" | 대조 {r[:, 3].sum() / max(1, r[:, 2].sum()):.2f} | v14 승점률 {r[:, 4].mean():.3f}"
              f" | 1칸 도착 {int(r[:, 5].sum())}건 → 3턴 안 탈취·중립화 {r[:, 6].sum() / max(1, r[:, 5].sum()):.2f}")


if __name__ == "__main__":
    main()
