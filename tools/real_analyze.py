"""실제 서버 리플레이 심층 분석: 경기 흐름·건물 상실 원인·경제·병력 활용·상대 행동.

서버 리플레이는 우리 관점이다(turns[i].observation = i 턴 입력, command = 우리 명령). 상대 점수는 비공개라
공개된 점수 + 180° 대칭 짝으로 채우고, 끝까지 모르는 건물은 지역 기댓값(중앙 3, 양 진영 1.5)으로 둔다.

사용 (WSL): python3 tools/real_analyze.py 'Real Match Replay/V12_0929_8am'
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter, defaultdict

N = 15


def load(path):
    r = json.load(open(path, encoding="utf-8"))
    me = r["side"]
    op = "Y" if me == "K" else "K"
    T = [t for t in r["turns"] if t.get("observation")]
    terr = T[0]["observation"]["map"]
    blds0 = T[0]["observation"]["buildings"]
    pos = {(b["x"], b["y"]): b["id"] for b in blds0}
    mirror = {b["id"]: pos.get((N - 1 - b["x"], N - 1 - b["y"]), b["id"]) for b in blds0}
    score = {}
    for t in T:
        for b in t["observation"]["buildings"]:
            if b.get("score") is not None and b["score"] >= 0:
                score[b["id"]] = b["score"]
        for k, v in (t.get("revealed") or {}).get("buildingScores", {}).items():
            score[int(k)] = v
    for i, j in list(mirror.items()):
        if i in score and j not in score:
            score[j] = score[i]
    for b in blds0:
        if b["id"] not in score:
            score[b["id"]] = 3 if 5 <= b["x"] <= 9 else 1.5
    return r, me, op, T, terr, blds0, score


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def analyze(path, verbose=True):
    r, me, op, T, terr, blds0, score = load(path)
    hs = [(x, y) for y, row in enumerate(terr) for x, ch in enumerate(row) if ch == "H"]
    first = [(u[2], u[3]) for t in T for u in t["observation"]["units"] if u[0] == me][:1]
    base_me = min(hs, key=lambda h: man(h, first[0])) if first else hs[0]
    base_op = [h for h in hs if h != base_me][0]
    btype = {b["id"]: b["type"] for b in blds0}
    bpos = {b["id"]: (b["x"], b["y"]) for b in blds0}
    res = r["result"]
    out = {"file": os.path.basename(path), "result": "승" if res["winner"] == me else "패" if res["winner"] == op else "무",
           "reason": res["reason"], "turns": len(T) - 1}
    tl = []
    lost, gained = [], []
    cap_turns = {me: 0, op: 0}
    prev = None
    fwd = {me: [], op: []}
    spread = []
    opp_hosp_spawn = 0
    opp_tele = 0
    my_spawn = Counter()
    lead_hist = []
    for idx, t in enumerate(T):
        o = t["observation"]
        turn = o["turn"]
        units = defaultdict(int)
        cells = defaultdict(dict)
        for team, kind, x, y, n in o["units"]:
            units[(team, kind)] += n
            cells[(x, y)][(team, kind)] = cells[(x, y)].get((team, kind), 0) + n
        own = {b["id"]: b["owner"] for b in o["buildings"]}
        pts = {s: sum(score[i] for i, w in own.items() if w == s) for s in (me, op)}
        nb = {s: sum(1 for w in own.values() if w == s) for s in (me, op)}
        eco = {s: {ty: sum(1 for i, w in own.items() if w == s and btype[i] == ty) for ty in ("ENG", "HALL", "HOSPITAL", "STATION", "LIBRARY")}
               for s in (me, op)}
        rs = o["resources"]
        for s in (me, op):
            if rs.get(s, 0) >= 36:
                cap_turns[s] += 1
        lead_hist.append(pts[me] - pts[op])
        # W 전진 비율(상대 본진 쪽 칸)
        for s, mb, ob in ((me, base_me, base_op), (op, base_op, base_me)):
            tot = f = 0
            for (x, y), d in cells.items():
                n = d.get((s, "W"), 0)
                tot += n
                if man((x, y), ob) < man((x, y), mb):
                    f += n
            if tot and 20 <= turn <= 140:
                fwd[s].append(f / tot)
        myw_cells = sum(1 for d in cells.values() if d.get((me, "W"), 0))
        opw_cells = sum(1 for d in cells.values() if d.get((op, "W"), 0))
        if 20 <= turn <= 140:
            spread.append((myw_cells, opw_cells, units[(me, "W")], units[(op, "W")]))
        if turn % 20 == 0 or idx == len(T) - 1:
            tl.append((turn, pts[me], pts[op], nb[me], nb[op], units[(me, "F")], units[(op, "F")], units[(me, "W")], units[(op, "W")],
                       rs.get(me), rs.get(op), eco[me]["ENG"], eco[op]["ENG"], eco[me]["HALL"], eco[op]["HALL"],
                       eco[me]["HOSPITAL"], eco[op]["HOSPITAL"]))
        if prev is not None:
            pown, pcells = prev
            for i, w in own.items():
                pw = pown[i]
                if pw == me and w != me:
                    p = bpos[i]
                    pd = pcells.get(p, {})
                    near_en = sum(d.get((op, "W"), 0) for c, d in pcells.items() if man(c, p) <= 1)
                    near_my = sum(d.get((me, "W"), 0) for c, d in pcells.items() if man(c, p) <= 1)
                    en_f_adj = sum(d.get((op, "F"), 0) for c, d in pcells.items() if man(c, p) <= 1)
                    lost.append({"turn": turn, "type": btype[i], "sc": score[i], "myW_on": pd.get((me, "W"), 0),
                                 "myF_on": pd.get((me, "F"), 0), "enW_adj": near_en, "myW_adj": near_my, "enF_adj": en_f_adj,
                                 "home": man(p, base_me) < man(p, base_op)})
                if pw != me and w == me:
                    gained.append({"turn": turn, "type": btype[i], "enemy": pw == op})
            # 상대 병원 생산·TELE 추정: 병원 칸에 새로 나타난 상대 유닛, 이전 턴 1칸 안에 없던 곳에 나타난 상대 무리
            for i, w in own.items():
                if w == op and btype[i] == "HOSPITAL":
                    p = bpos[i]
                    now = sum(v for (tm, k), v in cells.get(p, {}).items() if tm == op)
                    before = sum(v for c, d in pcells.items() if man(c, p) <= 1 for (tm, k), v in d.items() if tm == op)
                    if now > before:
                        opp_hosp_spawn += 1
            op_st = [bpos[i] for i, w in own.items() if w == op and btype[i] == "STATION"]
            if len(op_st) >= 2:
                for p in op_st:
                    now = sum(v for (tm, k), v in cells.get(p, {}).items() if tm == op)
                    before = sum(v for c, d in pcells.items() if man(c, p) <= 1 for (tm, k), v in d.items() if tm == op)
                    if now > before and man(p, base_op) > 1:
                        opp_tele += 1
        cmd = (t.get("command") or {}).get("lines", [])
        for ln in cmd:
            tok = ln.split()
            if tok and tok[0] == "SPAWN":
                my_spawn[tok[1]] += int(tok[2])
        prev = (own, cells)
    out.update({"timeline": tl, "lost": lost, "gained": gained, "cap": cap_turns, "my_spawn": dict(my_spawn),
                "fwd_me": sum(fwd[me]) / max(1, len(fwd[me])), "fwd_op": sum(fwd[op]) / max(1, len(fwd[op])),
                "spread": [sum(x[k] for x in spread) / max(1, len(spread)) for k in range(4)],
                "opp_hosp": opp_hosp_spawn, "opp_tele": opp_tele, "lead": lead_hist})
    return out


def report(g):
    print(f"\n### {g['file']}  {g['result']} ({g['reason']}, {g['turns']}턴)  전진 비율 우리 {g['fwd_me']:.2f} / 상대 {g['fwd_op']:.2f}"
          f"  상한 근처 턴 우리 {g['cap'][list(g['cap'])[0]]} / 상대 {g['cap'][list(g['cap'])[1]]}"
          f"  상대 병원 생산 추정 {g['opp_hosp']} · TELE 추정 {g['opp_tele']}")
    print(f"  W 칸 수(분산) 우리 {g['spread'][0]:.1f}칸/{g['spread'][2]:.0f}명  상대 {g['spread'][1]:.1f}칸/{g['spread'][3]:.0f}명   우리 생산 {g['my_spawn']}")
    print("  턴 | 점수 우:상 | 건물 | F 우:상 | W 우:상 | 자원 | 공학 | 학관 | 병원")
    for row in g["timeline"]:
        t, pm, po, bm, bo, fm, fo, wm, wo, rm, ro, em, eo, hm, ho, pm2, po2 = row
        print(f"  {t:>3} | {pm:>4.1f}:{po:<4.1f} | {bm:>2}:{bo:<2} | {fm:>2}:{fo:<2} | {wm:>3}:{wo:<3} | {rm}:{ro} | {em}:{eo} | {hm}:{ho} | {pm2}:{po2}")
    L = g["lost"]
    if L:
        c = Counter(x["type"] for x in L)
        undef = sum(1 for x in L if x["myW_on"] == 0)
        outnum = sum(1 for x in L if x["enW_adj"] > x["myW_adj"])
        print(f"  건물 상실 {len(L)}건 (획득 {len(g['gained'])}, 적 건물 탈취 {sum(x['enemy'] for x in g['gained'])}) · 종류 {dict(c)}"
              f" · 칸 위 아군 W 0 {undef} · 주변 적 W 우세 {outnum} · 우리 진영 쪽 {sum(x['home'] for x in L)}")


def main():
    files = sorted(glob.glob(os.path.join(sys.argv[1], "*.json")))
    games = [analyze(f) for f in files]
    for g in games:
        report(g)
    print("\n=== 승/패 그룹 평균 ===")
    for res in ("승", "패"):
        gs = [g for g in games if g["result"] == res]
        if not gs:
            continue
        def avg(f):
            return sum(f(g) for g in gs) / len(gs)
        print(f"{res} {len(gs)}경기: 전진 우리 {avg(lambda g: g['fwd_me']):.2f} 상대 {avg(lambda g: g['fwd_op']):.2f} · "
              f"W 칸수 우리 {avg(lambda g: g['spread'][0]):.1f} 상대 {avg(lambda g: g['spread'][1]):.1f} · "
              f"W 수 우리 {avg(lambda g: g['spread'][2]):.0f} 상대 {avg(lambda g: g['spread'][3]):.0f} · "
              f"상실 {avg(lambda g: len(g['lost'])):.1f} 획득 {avg(lambda g: len(g['gained'])):.1f} · "
              f"상대 병원 {avg(lambda g: g['opp_hosp']):.1f} TELE {avg(lambda g: g['opp_tele']):.1f}")


if __name__ == "__main__":
    main()
