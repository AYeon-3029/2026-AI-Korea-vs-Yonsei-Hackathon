"""실전 리플레이에서 상대(와 우리)의 행동 지표를 뽑아 상위 팀과 하위 팀을 비교한다(상위 팀 아이디어 추출용).

지표(20~120턴 평균, 상대 진영 기준)
  fwd    W 중 상대(=우리) 본진 쪽 칸 비율           stack  W 가 있는 칸당 평균 W(뭉침)          top3  가장 큰 W 무리 3개의 비율
  gar    W 중 자기 건물 칸 위 비율(주둔)             gb     W 1명 이상 주둔한 자기 건물 수      F      평균 F
  Fesc   F 중 같은 칸·1칸 옆에 자기 W 가 있는 비율(엄호 동행)    Fdie  F 사망(추정: 줄어든 F) 합
  hosp   병원 보유 턴 비율      tele   역 2개 이상 보유 턴 비율     cap20  20턴까지 점령 건물 수
  eco_t  우리 학생회관·공학관을 처음 빼앗은 턴     retake  우리가 빼앗은 그들 건물을 되찾는 데 걸린 평균 턴
  wgain  W 증가량/턴(생산 속도 대리)   engage 우리 W 와 1칸 안에서 맞선 자기 W 비율
사용 (WSL): python3 tools/opp_behavior.py
"""
from __future__ import annotations

import glob
import json
import os
from collections import defaultdict

import numpy as np

N = 15
RANK = {"tAIger": 1, "붉은 산호초": 2, "치명ㄷ": 3, "ACE": 4, "AIKU": 5, "참새튀김기": 5, "페이커": 7, "신촌을못가": 8,
        "오산기지정예병": 10, "야구사랑했단": 12, "황자구그는감히전설이라할수있다": 17, "양진장": 19, "뉴비들": 33, "후라.AI": 37,
        "너구리": 55, "200OK": 73}
NAMED = {"V12_0929_8am/replay (8).json": "붉은 산호초", "V12_0929_8am/replay (10).json": "야르렁파티"}
RANK["야르렁파티"] = 51


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def metrics(path, who):
    """who = 'op'(상대) | 'me'(우리)."""
    r = json.load(open(path, encoding="utf-8"))
    me = r["side"]
    op = "Y" if me == "K" else "K"
    side, other = (op, me) if who == "op" else (me, op)
    T = [t for t in r["turns"] if t.get("observation")]
    hs = [(x, y) for y, row in enumerate(T[0]["observation"]["map"]) for x, ch in enumerate(row) if ch == "H"]
    first = next(((u[2], u[3]) for t in T for u in t["observation"]["units"] if u[0] == side), hs[0])
    base = min(hs, key=lambda h: man(h, first))
    obase = [h for h in hs if h != base][0]
    bpos = {b["id"]: (b["x"], b["y"]) for b in T[0]["observation"]["buildings"]}
    btype = {b["id"]: b["type"] for b in T[0]["observation"]["buildings"]}
    acc = defaultdict(list)
    prevF = None
    fdie = 0
    eco_t = None
    lost_at = {}
    retakes = []
    prevW = None
    wgain = []
    cap20 = 0
    for t in T:
        o = t["observation"]
        turn = o["turn"]
        own = {b["id"]: b["owner"] for b in o["buildings"]}
        W = defaultdict(int)
        F = defaultdict(int)
        OW = defaultdict(int)
        for tm, k, x, y, n in o["units"]:
            if tm == side and k == "W":
                W[(x, y)] += n
            elif tm == side and k == "F":
                F[(x, y)] += n
            elif tm == other and k == "W":
                OW[(x, y)] += n
        nW, nF = sum(W.values()), sum(F.values())
        if prevF is not None and nF < prevF:
            fdie += prevF - nF
        prevF = nF
        if prevW is not None:
            wgain.append(max(0, nW - prevW))
        prevW = nW
        mine = [i for i, ow in own.items() if ow == side]
        if turn == 20:
            cap20 = len(mine)
        for i, ow in own.items():
            # 상대(other)의 진영 학생회관·공학관(other 본진에 가까운 것)을 처음 가져간 턴
            if ow == side and btype[i] in ("HALL", "ENG") and man(bpos[i], obase) < man(bpos[i], base) and eco_t is None:
                eco_t = turn
            if ow == other and i in lost_at is False:
                pass
        for i, ow in own.items():
            if ow != side and i in lost_at and lost_at[i] is not None and ow == other:
                pass
        # 되찾기: side 소유였다가 other 에게 넘어간 건물이 다시 side 로 돌아오는 시간
        for i, ow in own.items():
            if ow == other and i not in lost_at and acc["_owned_" + str(i)]:
                lost_at[i] = turn
            if ow == side:
                acc["_owned_" + str(i)] = [1]
                if i in lost_at:
                    retakes.append(turn - lost_at.pop(i))
        if 20 <= turn <= 120 and nW:
            acc["fwd"].append(sum(c for p, c in W.items() if man(p, obase) < man(p, base)) / nW)
            acc["stack"].append(nW / len(W))
            acc["top3"].append(sum(sorted(W.values())[-3:]) / nW)
            on_b = sum(W.get(bpos[i], 0) for i in mine)
            acc["gar"].append(on_b / nW)
            acc["gb"].append(sum(1 for i in mine if W.get(bpos[i], 0) > 0))
            acc["F"].append(nF)
            if nF:
                esc = sum(c for p, c in F.items() if any(W.get((p[0] + dx, p[1] + dy), 0) for dx, dy in
                                                           ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))))
                acc["Fesc"].append(esc / nF)
            acc["hosp"].append(any(btype[i] == "HOSPITAL" for i in mine))
            acc["tele"].append(sum(1 for i in mine if btype[i] == "STATION") >= 2)
            eng = sum(c for p, c in W.items() if any(man(p, q) <= 1 for q in OW))
            acc["engage"].append(eng / nW)
    out = {k: float(np.mean(v)) for k, v in acc.items() if not k.startswith("_")}
    out.update(Fdie=fdie, cap20=cap20, eco_t=eco_t if eco_t is not None else -1,
               retake=float(np.mean(retakes)) if retakes else -1, wgain=float(np.mean(wgain[20:120])) if len(wgain) > 20 else 0)
    res = r["result"]["winner"]
    out["res"] = "승" if res == me else "패" if res == op else "무"
    return out


KEYS = ["fwd", "stack", "top3", "gar", "gb", "F", "Fesc", "Fdie", "hosp", "tele", "cap20", "eco_t", "retake", "wgain", "engage"]


def main():
    root = os.path.join(os.path.dirname(__file__), "../Real Match Replay")
    rows = []
    for f in sorted(glob.glob(os.path.join(root, "V14_0929_8pm", "*.json"))):
        name = os.path.basename(f)[2:-5]
        rows.append((name, RANK.get(name, 99), f))
    for k, name in NAMED.items():
        rows.append((name, RANK[name], os.path.join(root, k)))
    print(f"{'상대':<16}{'순위':>4} 결과 " + " ".join(f"{k:>6}" for k in KEYS))
    groups = defaultdict(list)
    for name, rk, f in sorted(rows, key=lambda x: x[1]):
        m = metrics(f, "op")
        print(f"{name[:14]:<16}{rk:>4}  {m['res']}  " + " ".join(f"{m.get(k, 0):>6.2f}" for k in KEYS))
        groups["상위(≤10)" if rk <= 10 else "하위"].append(m)
    for g, ms in groups.items():
        print(f"{g:<20}      " + " ".join(f"{np.mean([m.get(k, 0) for m in ms]):>6.2f}" for k in KEYS))
    us = [metrics(f, "me") for _, _, f in rows]
    print(f"{'우리(v14·v12)':<20}      " + " ".join(f"{np.mean([m.get(k, 0) for m in us]):>6.2f}" for k in KEYS))


if __name__ == "__main__":
    main()
