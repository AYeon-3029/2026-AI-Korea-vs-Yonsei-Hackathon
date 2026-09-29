"""같은 상태에서 갈라 방침(파라미터 묶음)별 결과를 모은다 — 첫 턴 방향 선정·경기 중 방침 전환 학습 데이터.

작업 하나 = (시드, 상대, 내 진영, 분기 턴 t). v13 대 상대로 t 턴까지 진행한 뒤 방침마다 경기를 복제해
  - t == 0 : 경기 전체를 그 방침으로(첫 턴 방향 선정)
  - t > 0  : t+1 ~ t+window 턴만 그 방침, 이후 v13 기본으로(경기 중 전환)
끝까지 두고 결과(승 1/무 0.5/패 0)와 연속 지표(점수 차 + 점령-턴 차/160)를 기록한다. 방침 0 = v13 그대로.
양쪽 봇이 결정적이므로 같은 행의 방침 간 차이는 잡음 없는 쌍 비교다.

사용 (WSL): python3 tools/macro/branch.py --seeds 20000-20399 --turns 0 --out out/macro/map0.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, TOTAL, margin, value  # noqa: E402
from feats import map_features, state_features  # noqa: E402

# v13 기본 위에 덮어쓰는 방침. 스타일이 분명히 다르게(Optuna 상위 시행은 v13 과 거의 같은 점이다).
MACROS = [
    {},                                                                                   # 0 v13
    {"w_margin": 15, "guard_radius": 8, "siege_bld_bonus": 12.0, "siege_ring_value": 5.0,
     "risk_local_w": 0.1},                                                                # 1 공세
    {"w_margin": 32, "guard_radius": 25, "siege_bld_bonus": 4.0, "siege_ring_value": 1.5}, # 2 수세
    {"eng_bonus": 18.0, "hall_bonus": 15.0,
     "deny": {"ENG": 5.0, "LIBRARY": 1.5, "HALL": 5.0, "HOSPITAL": 1.0}},                 # 3 경제
    {"max_f": 8, "min_f": 6},                                                             # 4 F 물량
    {"max_f": 3, "min_f": 3, "min_w": 8},                                                 # 5 F 절약
    {"risk_local_w": 0.45},                                                               # 6 신중
    {"risk_local_w": 0.05, "enemy_owned_mult": 2.4},                                      # 7 무모(적 건물 탈취)
    {"center_expect": 3.2},                                                               # 8 중앙 우선
    {"center_expect": 1.7, "side_expect": 1.7},                                           # 9 변두리 우선
    {"dist_offset": 2.5},                                                                 # 10 가까운 목표 편중
    # 1차 결과(신중 +0.036) 검증용 변형
    {"risk_local_w": 0.35},                                                               # 11 신중 약
    {"risk_local_w": 0.6},                                                                # 12 신중 강
    {"risk_local_w": 0.45, "eng_bonus": 18.0, "hall_bonus": 15.0,
     "deny": {"ENG": 5.0, "LIBRARY": 1.5, "HALL": 5.0, "HOSPITAL": 1.0}},                 # 13 신중+경제
    {"risk_local_w": 0.45, "w_margin": 32, "guard_radius": 25, "siege_bld_bonus": 4.0,
     "siege_ring_value": 1.5},                                                            # 14 신중+수세
    {"risk_local_w": 0.45, "center_expect": 1.7, "side_expect": 1.7},                     # 15 신중+변두리
]
NAMES = ["v13", "공세", "수세", "경제", "F물량", "F절약", "신중", "무모", "중앙", "변두리", "근거리", "신중약", "신중강", "신중경제", "신중수세", "신중변두리"]

# pool_eval.py 의 VARIANTS 와 같은 상대(한 프로세스 안에서 돌린다)
SRV12_PRESS = {"guard_radius": 8, "siege_bld_bonus": 10.0, "siege_ring_value": 6.0, "w_margin": 34}
SRV12_ECO = {"eng_bonus": 16.0, "hall_bonus": 16.0, "deny": {"ENG": 6.0, "LIBRARY": 1.5, "HALL": 6.0, "HOSPITAL": 1.0}}
SRV12_EGF = {"eg_f_turn": 145, "eg_max_f": 10, "eg_min_f": 8}
B72 = {"max_f": 4, "min_f": 4, "min_w": 4, "w_margin": 23, "guard_radius": 14, "dist_offset": 4.2376,
       "hall_bonus": 7.5348, "eng_bonus": 8.3535, "lib_bonus": 2.3879, "depot_bonus": 2.4153,
       "hosp_bonus": 3.9643, "center_expect": 2.6741, "side_expect": 1.0388, "enemy_owned_mult": 1.837,
       "enemy_f_penalty": 0.4008, "siege_bld_bonus": 9.9713, "siege_ring_value": 5.4338,
       "chase_mult": 1.501, "endgame_turn": 158, "escort_bonus": 2.6751, "escort_extra": 4,
       "risk_local_w": 0.2865, "f_block": 2, "block_worth": 3.795}
OPPS = {
    "v13": ("v13", {}),
    "srv12_press": ("v12", SRV12_PRESS),
    "srv12_eco": ("v12", SRV12_ECO),
    "srv12_egf": ("v12", SRV12_EGF),
    "b72": ("v11", B72),
    "v11": ("v11", {}),
    "v12": ("v12", {}),
    # 방침 모형 검증용 추가 상대(학습 풀 밖)
    "srv13_press": ("v13", SRV12_PRESS),
    "srv13_eco": ("v13", SRV12_ECO),
    "v10": ("v10", {}),
}
POOL = ["v13", "srv12_press", "srv12_eco", "srv12_egf", "b72", "v11"]


def job(args):
    seed, opp, side, t, window, macros = args
    me = Agent("v13")
    ver, params = OPPS[opp]
    other = Agent(ver, params)
    ay, ak = (me, other) if side == "Y" else (other, me)
    g = Game(seed, ay, ak)
    g.run(until=t)
    row = {"seed": seed, "opp": opp, "side": side, "t": t, "window": window}
    if t == 0:
        row["map"] = map_features(g.state, side)
    else:
        row["state"] = state_features(g.state, side)
    if g.result is not None:            # 분기 전에 끝남
        row["done"] = True
        return row
    vals, mars = [], []
    for m in macros:
        h = g.fork()
        h.agents[side].set_params(MACROS[m])
        if t == 0 or window <= 0:
            h.run()
        else:
            h.run(until=min(TOTAL, t + window))
            h.agents[side].set_params({})
            h.run()
        vals.append(value(h.result, side))
        mars.append(round(margin(h, side), 4))
    row["macros"] = list(macros)
    row["value"] = vals
    row["margin"] = mars
    return row


def parse_range(text):
    out = []
    for part in text.split(","):
        if "-" in part:
            lo, hi = part.split("-")
            out.extend(range(int(lo), int(hi) + 1))
        elif part:
            out.append(int(part))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", required=True)
    p.add_argument("--turns", default="0", help="분기 턴(쉼표)")
    p.add_argument("--window", type=int, default=20)
    p.add_argument("--opps", default=",".join(POOL))
    p.add_argument("--macros", default=",".join(str(i) for i in range(len(MACROS))))
    p.add_argument("--workers", type=int, default=24)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    macros = [int(x) for x in a.macros.split(",")]
    jobs = [(s, o, side, t, a.window, macros)
            for s in parse_range(a.seeds) for o in a.opps.split(",") for side in "YK"
            for t in parse_range(a.turns)]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    t0 = time.time()
    with Pool(a.workers) as pool, open(a.out, "w", encoding="utf-8") as f:
        for i, row in enumerate(pool.imap_unordered(job, jobs, chunksize=2), 1):
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            if i % 200 == 0:
                print(f"{i}/{len(jobs)} {time.time() - t0:.0f}s", flush=True)
    print(f"완료 {len(jobs)}건 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
