"""실제 리플레이 자원 회계: 전투병은 C1 상쇄로만 죽으므로 양쪽 W 손실은 항상 같다.
→ 상대 W 생산량 = 상대 생존 W + 우리 W 손실(= 우리 생산 − 우리 생존). 수입·W 단가·F 생산·점령 지출·낭비를 비교한다.

사용 (WSL): python3 tools/real_econ.py 'Real Match Replay/V12_0929_8am'
"""
from __future__ import annotations

import glob
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from real_analyze import load  # noqa: E402


def econ(path):
    r, me, op, T, terr, blds0, score = load(path)
    btype = {b["id"]: b["type"] for b in blds0}
    res = r["result"]
    g = {"file": os.path.basename(path), "res": "승" if res["winner"] == me else "패" if res["winner"] == op else "무",
         "reason": res["reason"]}
    inc = {me: 0, op: 0}
    w_spawn = f_spawn = 0
    w_cost_paid = 0
    wasted = 0
    neut_by = {me: 0, op: 0}        # 상대 건물을 중립화한 횟수(= 그 팀의 공격 성공)
    prevown = None
    prev_res = None
    halls = {me: [], op: []}
    engs = {me: [], op: []}
    marks = {}
    for idx, t in enumerate(T):
        o = t["observation"]
        turn = o["turn"]
        own = {b["id"]: b["owner"] for b in o["buildings"]}
        nh = {s: sum(1 for i, w in own.items() if w == s and btype[i] == "HALL") for s in (me, op)}
        ne = {s: sum(1 for i, w in own.items() if w == s and btype[i] == "ENG") for s in (me, op)}
        for s in (me, op):
            halls[s].append(nh[s])
            engs[s].append(ne[s])
            inc[s] += 10 + 2 * nh[s]
        if prevown:
            for i, w in own.items():
                pw = prevown[i]
                if pw in (me, op) and w == "N":
                    neut_by[op if pw == me else me] += 1
        rs = o["resources"][me]
        if prev_res is not None and prev_res + 10 + 2 * nh[me] > 40:
            wasted += prev_res + 10 + 2 * nh[me] - 40
        prev_res = rs
        for ln in (t.get("command") or {}).get("lines", []):
            tok = ln.split()
            if tok and tok[0] == "SPAWN":
                n = int(tok[2])
                if tok[1] == "W":
                    w_spawn += n
                    w_cost_paid += n * max(2, 3 - ne[me])
                elif tok[1] == "F":
                    f_spawn += n
        units = defaultdict(int)
        for team, kind, x, y, n in o["units"]:
            units[(team, kind)] += n
        if turn in (40, 80, 120) or idx == len(T) - 1:
            lost_w = w_spawn - units[(me, "W")]
            marks[turn] = (w_spawn, units[(me, "W")] + 0, units[(op, "W")] + lost_w, units[(op, "W")],
                           f_spawn, units[(op, "F")])
        prevown = own
    n = len(T)
    g.update({"turns": n - 1, "inc_me": inc[me], "inc_op": inc[op], "hall_me": sum(halls[me]) / n, "hall_op": sum(halls[op]) / n,
              "eng_me": sum(engs[me]) / n, "eng_op": sum(engs[op]) / n, "w_spawn": w_spawn, "f_spawn": f_spawn,
              "w_cost": w_cost_paid, "wasted": wasted, "neut_me": neut_by[me], "neut_op": neut_by[op], "marks": marks})
    return g


def main():
    gs = [econ(f) for f in sorted(glob.glob(os.path.join(sys.argv[1], "*.json")))]
    print("경기 | 결과 | 수입 우:상 | 평균 학관 우:상 | 평균 공학 우:상 | W 생산 우:상(추정) | F 생산 우 | 낭비 | 중립화 성공 우:상")
    for g in gs:
        last = g["marks"][max(g["marks"])]
        print(f"{g['file']:<17} {g['res']}({g['reason'][:5]}) | {g['inc_me']}:{g['inc_op']} | {g['hall_me']:.2f}:{g['hall_op']:.2f} |"
              f" {g['eng_me']:.2f}:{g['eng_op']:.2f} | {last[0]}:{last[2]} | {g['f_spawn']} | {g['wasted']} | {g['neut_me']}:{g['neut_op']}")
    print("\n40·80·120턴 누적 W 생산 우:상(추정)")
    for g in gs:
        print(f"{g['file']:<17} {g['res']} " + "  ".join(f"{t}턴 {m[0]}:{m[2]}" for t, m in sorted(g["marks"].items())))


if __name__ == "__main__":
    main()
