"""실제 리플레이: 우리 W 가 차지한(적 유닛 없음) 적·중립 건물에 우리 F 가 오지 않아 점령을 못 한 구간.

구간 = 같은 건물 칸에 우리 W ≥ 1, 적 유닛 0, 건물이 우리 소유가 아닌 턴이 이어진 것. 구간마다 길이, 가장 가까운 우리 F 까지의
거리(구간 첫 턴), 그동안 우리 F 수, 구간이 끝난 이유(우리 점령 / W 떠남 / 적 진입)를 센다.
사용 (WSL): python3 tools/real_wheld.py 'Real Match Replay/V16_0930_8am' [--min 3] [--show 파일조각]
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from real_analyze import load, man  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--min", type=int, default=3)
    ap.add_argument("--show", default="")
    a = ap.parse_args()
    tot = Counter()
    per_game = []
    for d in a.dirs:
        for path in sorted(glob.glob(os.path.join(d, "*.json"))):
            r, me, op, T, terr, blds0, score = load(path)
            w = r["result"]["winner"]
            res = "승" if w == me else "무" if w == "DRAW" else "패"
            btype = {b["id"]: b["type"] for b in blds0}
            bpos = {b["id"]: (b["x"], b["y"]) for b in blds0}
            open_seg = {}
            segs = []
            for t in T:
                o = t["observation"]
                turn = o["turn"]
                own = {b["id"]: b["owner"] for b in o["buildings"]}
                myW, enU, myF = Counter(), Counter(), []
                for tm, k, x, y, n in o["units"]:
                    if tm == me and k == "W":
                        myW[(x, y)] += n
                    elif tm == op:
                        enU[(x, y)] += n
                    if tm == me and k == "F":
                        myF.append(((x, y), n))
                for i, p in bpos.items():
                    held = own[i] != me and myW[p] > 0 and enU[p] == 0
                    if held and i not in open_seg:
                        fd = min((man(p, q) for q, _ in myF), default=99)
                        open_seg[i] = [turn, turn, fd, sum(n for _, n in myF), own[i]]
                    elif held:
                        open_seg[i][1] = turn
                    elif i in open_seg:
                        s = open_seg.pop(i)
                        why = "점령" if own[i] == me else "적진입" if enU[p] else "W떠남"
                        segs.append((i, *s, why))
            for i, s in open_seg.items():
                segs.append((i, *s, "끝"))
            long = [s for s in segs if s[2] - s[1] + 1 >= a.min]
            turns = sum(s[2] - s[1] + 1 for s in long)
            per_game.append((os.path.basename(d), os.path.basename(path), res, len(long), turns))
            for s in long:
                tot[(res, s[6])] += 1
                tot[(res, "턴")] += s[2] - s[1] + 1
            if a.show and a.show in path:
                for i, t0, t1, fd, nf, owner, why in sorted(long, key=lambda s: s[1]):
                    print(f"  {btype[i]:<8}{bpos[i]} {'적' if owner == op else '중립'} {t0}-{t1}턴({t1 - t0 + 1}) "
                          f"첫 턴 가장 가까운 F {fd}칸·F {nf}명 → {why}")
    for d, f, res, n, turns in per_game:
        print(f"{res} {d}/{f:<34} {a.min}턴+ 구간 {n:2d}개 · {turns:3d}턴")
    for res in ("승", "패"):
        n = sum(1 for g in per_game if g[2] == res)
        if n:
            print(f"[{res} {n}경기] 경기당 구간 {sum(g[3] for g in per_game if g[2] == res) / n:.1f} · 턴 {tot[(res, '턴')] / n:.1f}"
                  f" · 끝: 점령 {tot[(res, '점령')]} W떠남 {tot[(res, 'W떠남')]} 적진입 {tot[(res, '적진입')]}")


if __name__ == "__main__":
    main()
