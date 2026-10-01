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
import glob
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
    # 극단 스타일 상대(상대 유형 적응의 상한 측정용)
    "x_rush": ("v13", {"max_f": 3, "min_f": 2, "w_margin": 40, "guard_radius": 4, "siege_bld_bonus": 14.0,
                       "siege_ring_value": 8.0, "risk_local_w": 0.0}),
    "x_turtle": ("v13", {"siege": False, "guard_radius": 30, "w_margin": 12}),
    "x_fswarm": ("v13", {"max_f": 10, "min_f": 8, "min_w": 2, "w_margin": 6}),
    "x_eco": ("v13", {"eng_bonus": 25.0, "hall_bonus": 25.0,
                      "deny": {"ENG": 8.0, "LIBRARY": 1.5, "HALL": 8.0, "HOSPITAL": 1.0}}),
    "x_center": ("v13", {"center_expect": 4.0, "side_expect": 0.8}),
    "x_greedy": ("v13", {"risk_local_w": 0.0, "enemy_owned_mult": 3.0, "dist_offset": 1.5}),
    "x_egf": ("v13", {"eg_f_turn": 130, "eg_max_f": 12, "eg_min_f": 10}),
    "x_press": ("v13", {"guard_radius": 6, "siege_bld_bonus": 12.0, "siege_ring_value": 7.0, "w_margin": 36,
                        "escort_extra": 6}),
}
OPPS["v14"] = ("v14", {})
# 현실 풀(실제 상대의 'F 1칸 옆 도착 → 3턴 안 탈취 허용' 0.50 에 맞춤): 중간형 6 + 반응형 강자 6 (tools/macro/tune6.py 와 같음)
_SEMI = {"f_block": 0, "eco_block_extra": 0}
OPPS["v9"] = ("v9", {})
OPPS["semi14"] = ("dev5", _SEMI)
OPPS["semi14_g6"] = ("dev5", dict(_SEMI, guard_radius=6))
OPPS["semi14_press"] = ("dev5", dict(_SEMI, guard_radius=8, siege_bld_bonus=12.0, siege_ring_value=6.0, w_margin=34))
OPPS["semi14_eco"] = ("dev5", dict(_SEMI, eng_bonus=16.0, hall_bonus=16.0,
                                   deny={"ENG": 6.0, "LIBRARY": 1.5, "HALL": 6.0, "HOSPITAL": 1.0}))
OPPS["srv14_press"] = ("v14", SRV12_PRESS)
OPPS["srv14_eco"] = ("v14", SRV12_ECO)
REAL_POOL = ["semi14", "semi14_g6", "semi14_press", "semi14_eco", "v10", "v9",
             "v14", "srv14_press", "srv14_eco", "b72", "x_press", "x_eco"]
# v14 맞춤 공격자(적대적 탐색 tools/macro/exploit.py --study x1): 수비적 경제형
for _n in (291, 239):
    _p = os.path.join(os.path.dirname(__file__), "../../out/tune/x1", f"t{_n}.json")
    if os.path.exists(_p):
        OPPS[f"x{_n}"] = ("dev11", json.load(open(_p)))
XOPPS = ["x_rush", "x_turtle", "x_fswarm", "x_eco", "x_center", "x_greedy", "x_egf", "x_press"]
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
# 9/29 20시 실전 패배 상대(신촌을못가 fwd 0.26 · 참새튀김기 0.40 · AIKU 0.49)를 닮은 공세형 대리(tools/macro/proxy_style.py)
_PUSH = {"guard_radius": 6, "siege_bld_bonus": 14.0, "siege_ring_value": 6.0, "w_margin": 36, "risk_local_w": 0.1}
OPPS["p_press"] = ("dev11", _PUSH)
OPPS["p_raid"] = ("dev11", dict(_PUSH, raid_w=2.0, raid_D=12))
OPPS["p_lodge"] = ("dev11", dict(_PUSH, raid_w=2.0, raid_D=12, hold_new=8, hold_R=3))
OPPS["p_rush"] = ("dev11", dict(_PUSH, guard_radius=4, siege_ring_value=9.0, w_margin=44, risk_local_w=0.0, max_f=4, min_f=3))
OPPS["p_center"] = ("dev11", dict(_PUSH, center_expect=3.5, plaza_bonus=3.0))
PUSH_POOL = ["p_press", "p_raid", "p_lodge", "p_rush", "p_center"]
# 실전 상대 흉내 봇(tools/macro/mimic.py fit): out/tune/mimic/<회차>/<상대>.json → OPPS["m16_<상대>"] (이름은 글자·숫자만)
MIMIC = {}
for _p in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "../../out/tune/mimic/*/*.json"))):
    _dir = os.path.basename(os.path.dirname(_p))
    _base = _dir.split("-", 1)[1] if "-" in _dir else "dev11"
    _tag = _dir.lstrip("V").split("_")[0]
    _pre = "m" if _base == "dev11" else "mc"
    _nm = "".join(ch for ch in os.path.basename(_p)[:-5].removeprefix("vs") if ch.isalnum())
    OPPS[f"{_pre}{_tag}_{_nm}"] = (_base, json.load(open(_p, encoding="utf-8")))
    MIMIC.setdefault(_pre + _tag, []).append(f"{_pre}{_tag}_{_nm}")

# tAIger(리더보드 1위) 소문 흉내: "별다른 방어 없이 전투병 돌진". cv-14 에서 반응형 방어(요격·경계·차단·엄호)를 끄고 공성·W 여유를 올린다.
_TIGER = {"react": False, "f_block": 0, "guard_radius": 0, "eco_block_extra": 0, "risk_local_w": 0.0}
OPPS["t_rush"] = ("cv-14", dict(_TIGER))
OPPS["t_rush_siege"] = ("cv-14", dict(_TIGER, siege_bld_bonus=30.0, siege_ring_value=6.0, w_margin=34))
OPPS["t_rush_all"] = ("cv-14", dict(_TIGER, siege_bld_bonus=40.0, siege_ring_value=9.0, w_margin=44, max_f=3, min_f=2))
TIGER_POOL = ["t_rush", "t_rush_siege", "t_rush_all"]

# 리더보드 V22 회차 B형 패배(160턴 스냅샷 직전 중앙 총공세) 재현: 이번 회차 흉내 봇(mc22)에 막판 공세를 얹는다.
# 145턴부터 후반 모드·F 증원(상한 8·최소 6)·목표 위험 무시. 우리 막판 대응(eg_def 등) 실험용.
_EG_PUSH = {"endgame_turn": 145, "eg_f_turn": 145, "eg_max_f": 8, "eg_min_f": 6, "eg_risk_scale": 0.0}
EG22 = []
for _n in MIMIC.get("mc22", []):
    _b, _p = OPPS[_n]
    OPPS["eg" + _n[2:]] = (_b, dict(_p, **_EG_PUSH))
    EG22.append("eg" + _n[2:])

# 상위 팀 모방 봇(리더보드 전략 지문 tools/lb_profile.py: F 고정·상시 호위·저주둔·경제 반복 기습). 바탕 dev40.
_TP = {"fesc_always": True, "fesc_min": 2, "eco_raid_t0": 15, "eco_raid_t1": 160, "eco_raid_always": True,
       "eco_raid_minw": 10, "eco_raid_fw": 1.0}
OPPS["tp_tiger"] = ("dev40", dict(_TP, max_f_early=3, early_turn=30, max_f=6, min_f=3, guard_radius=4, f_block=1,
                                  eco_block_extra=0, eco_raid_n=10))
OPPS["tp_yagu"] = ("dev40", dict(_TP, max_f_early=4, max_f=4, min_f=4, eco_raid_n=6))
OPPS["tp_aiku"] = ("dev40", dict(_TP, max_f_early=6, max_f=6, min_f=6, eco_raid_types="depot", eco_raid_n=12))
OPPS["tp_red"] = ("dev40", dict(_TP, max_f_early=3, max_f=3, min_f=3, guard_radius=4, f_block=0, eco_block_extra=0,
                                eco_raid_n=8, siege_spread=3))
TOP_POOL = ["tp_tiger", "tp_yagu", "tp_aiku", "tp_red"]
# tAIger형 2차: 수비는 v25 그대로(tAIger 도 W 60~70% 를 자기 건물 3칸 안에 둔다), 공격 습관만(상시 기습·F 3→6·호위)
_TG = dict(_TP, max_f_early=3, early_turn=30, max_f=6, min_f=3)
OPPS["tg_a"] = ("dev40", dict(_TG, eco_raid_n=10))
OPPS["tg_b"] = ("dev40", dict(_TG, eco_raid_n=6))
OPPS["tg_c"] = ("dev40", dict(_TG, eco_raid_n=10, eco_raid_types="eco+depot"))
OPPS["tg_d"] = ("dev40", dict(_TG, eco_raid_n=10, max_f_early=4, max_f=4, min_f=4))
OPPS["tg_e"] = ("dev40", dict(_TG, eco_raid_n=10, eco_raid_fw=0.0))
OPPS["tg_f"] = ("dev40", dict(_TP, eco_raid_n=10))       # F 는 v25 그대로, 기습·호위만
