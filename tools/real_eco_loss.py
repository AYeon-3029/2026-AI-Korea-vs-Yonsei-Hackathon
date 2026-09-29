"""실제 리플레이: 경제 건물(학생회관·공학관) 소유 구간과, 적이 쥐고 있는 동안 주변 병력·우리 탈환 시도.

사용 (WSL): python3 tools/real_eco_loss.py 'Real Match Replay/V12_0929_8am' [파일 이름 조각]
"""
from __future__ import annotations

import glob
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from real_analyze import load, man  # noqa: E402


def main():
    files = sorted(glob.glob(os.path.join(sys.argv[1], "*.json")))
    if len(sys.argv) > 2:
        files = [f for f in files if sys.argv[2] in f]
    for path in files:
        r, me, op, T, terr, blds0, score = load(path)
        res = "승" if r["result"]["winner"] == me else "패"
        hs = [(x, y) for y, row in enumerate(terr) for x, ch in enumerate(row) if ch == "H"]
        first = [(u[2], u[3]) for t in T for u in t["observation"]["units"] if u[0] == me][:1]
        base_me = min(hs, key=lambda h: man(h, first[0]))
        base_op = [h for h in hs if h != base_me][0]
        print(f"\n### {os.path.basename(path)} {res} ({r['result']['reason']})")
        for b in blds0:
            if b["type"] not in ("HALL", "ENG"):
                continue
            p = (b["x"], b["y"])
            side = "우리쪽" if man(p, base_me) < man(p, base_op) else "상대쪽"
            segs = []
            cur, start = None, 0
            stats = defaultdict(list)
            for t in T:
                o = t["observation"]
                own = next(x["owner"] for x in o["buildings"] if x["id"] == b["id"])
                if own != cur:
                    if cur is not None:
                        segs.append((cur, start, o["turn"] - 1, stats))
                    cur, start, stats = own, o["turn"], defaultdict(list)
                ew = sum(n for tm, k, x, y, n in o["units"] if tm == op and k == "W" and man((x, y), p) <= 2)
                mw = sum(n for tm, k, x, y, n in o["units"] if tm == me and k == "W" and man((x, y), p) <= 2)
                mf = sum(n for tm, k, x, y, n in o["units"] if tm == me and k == "F" and man((x, y), p) <= 2)
                eon = sum(n for tm, k, x, y, n in o["units"] if tm == op and k == "W" and (x, y) == p)
                stats["ew"].append(ew)
                stats["mw"].append(mw)
                stats["mf"].append(mf)
                stats["eon"].append(eon)
            segs.append((cur, start, T[-1]["observation"]["turn"], stats))
            desc = []
            for own, s, e, st in segs:
                if e - s < 2 and own == "N":
                    continue
                who = "우" if own == me else "상" if own == op else "N"
                avg = lambda k: sum(st[k]) / max(1, len(st[k]))
                desc.append(f"{who}{s}-{e}(적W {avg('ew'):.0f}/칸위 {avg('eon'):.0f} 우W {avg('mw'):.0f} 우F {avg('mf'):.1f})")
            print(f"  {b['type']:<4}{side} {p}: " + " → ".join(desc))


if __name__ == "__main__":
    main()
