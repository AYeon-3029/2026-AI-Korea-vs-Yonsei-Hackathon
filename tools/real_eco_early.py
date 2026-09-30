"""실제 리플레이: 우리 학생회관·공학관을 잃은 순간(우리 소유 → 중립/상대)마다 직전 턴들의 병력 상황으로 원인을 가른다.

분류(상실 직전 턴 기준)
  전체열세   전체 W 가 상대보다 적다(생산·교환 격차)
  배치실패   전체 W 는 상대 이상인데 그 건물 2칸 안에서 밀렸다(병력이 딴 데 있음)
  무방비     2칸 안에 우리 W 0 (전체 수와 무관)
각 상실마다 3턴 전~직전 2칸·4칸 안 양쪽 W, 우리 W 무게중심까지 거리, 적 F 도착 경로를 보여 준다.
사용 (WSL): python3 tools/real_eco_early.py 'Real Match Replay/V14_0929_8pm' [--upto 80] [--quiet]
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from real_analyze import load, man  # noqa: E402


def cnt(units, team, kind, p=None, R=None):
    return sum(n for tm, k, x, y, n in units if tm == team and k == kind and (p is None or man((x, y), p) <= R))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--upto", type=int, default=80)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    tally = Counter()
    rows = []
    for d in a.dirs:
        for path in sorted(glob.glob(os.path.join(d, "*.json"))):
            r, me, op, T, terr, blds0, score = load(path)
            res = "승" if r["result"]["winner"] == me else "무" if r["result"]["winner"] == "DRAW" else "패"
            hs = [(x, y) for y, row in enumerate(terr) for x, ch in enumerate(row) if ch == "H"]
            first = [(u[2], u[3]) for t in T for u in t["observation"]["units"] if u[0] == me][:1]
            base_me = min(hs, key=lambda h: man(h, first[0]))
            base_op = [h for h in hs if h != base_me][0]
            eco = {b["id"]: (b["type"], (b["x"], b["y"])) for b in blds0 if b["type"] in ("HALL", "ENG")}
            prev_own = {}
            head = False
            for k, t in enumerate(T):
                o = t["observation"]
                turn = o["turn"]
                own = {b["id"]: b["owner"] for b in o["buildings"]}
                for i, (bt, p) in eco.items():
                    if prev_own.get(i) == me and own[i] != me and turn <= a.upto:
                        side = "우리쪽" if man(p, base_me) < man(p, base_op) else "상대쪽"
                        pre = T[k - 1]["observation"]["units"]     # 상실 직전 턴 입력(= 그 턴 우리가 본 상태)
                        mw2, ew2 = cnt(pre, me, "W", p, 2), cnt(pre, op, "W", p, 2)
                        mwT, ewT = cnt(pre, me, "W"), cnt(pre, op, "W")
                        mws = [(x, y, n) for tm, kk, x, y, n in pre if tm == me and kk == "W"]
                        cx = sum(x * n for x, y, n in mws) / max(1, mwT)
                        cy = sum(y * n for x, y, n in mws) / max(1, mwT)
                        dcen = abs(cx - p[0]) + abs(cy - p[1])
                        if mw2 == 0:
                            cls = "무방비"
                        elif mwT < ewT:
                            cls = "전체열세"
                        else:
                            cls = "배치실패"
                        if mw2 == 0 and mwT < ewT:
                            cls = "무방비+전체열세"
                        tally[(cls, side)] += 1
                        hist = []
                        for j in range(max(0, k - 4), k + 1):
                            u = T[j]["observation"]["units"]
                            hist.append(f"{T[j]['observation']['turn']}:우{cnt(u, me, 'W', p, 2)}/{cnt(u, me, 'W', p, 4)}"
                                        f" 적{cnt(u, op, 'W', p, 2)}/{cnt(u, op, 'W', p, 4)} 적F{cnt(u, op, 'F', p, 2)}")
                        rows.append((cls, side))
                        if not a.quiet:
                            if not head:
                                print(f"\n### {os.path.basename(d)}/{os.path.basename(path)} {res}")
                                head = True
                            print(f"  {turn}턴 {bt}{side}{p} → {own[i]}  [{cls}] 전체 W 우{mwT} 적{ewT} · 2칸 우{mw2} 적{ew2}"
                                  f" · 우리 W 중심까지 {dcen:.1f}칸")
                            print("     " + " | ".join(hist))
                prev_own = own
    print("\n== 분류(상실 건수)")
    for (cls, side), n in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {cls:<10} {side}  {n}")


if __name__ == "__main__":
    main()
