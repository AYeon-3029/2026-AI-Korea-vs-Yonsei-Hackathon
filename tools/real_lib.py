"""실제 리플레이: 건물 종류별 평균 보유(우리:상대)를 승·패로 나눠 비교 — 도서관 영향 점검.

사용 (WSL): python3 tools/real_lib.py 'Real Match Replay/V16_0930_8am' 'Real Match Replay/V14_0929_8pm' ...
"""
from __future__ import annotations

import glob
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from real_analyze import load  # noqa: E402

TYPES = ["HALL", "ENG", "LIBRARY", "PLAZA", "STATION", "HOSPITAL", "WATCH", "DEPOT"]


def main():
    agg = defaultdict(lambda: defaultdict(list))
    first_lib = defaultdict(list)
    for d in sys.argv[1:]:
        for path in sorted(glob.glob(os.path.join(d, "*.json"))):
            r, me, op, T, terr, blds0, score = load(path)
            w = r["result"]["winner"]
            res = "승" if w == me else "무" if w == "DRAW" else "패"
            btype = {b["id"]: b["type"] for b in blds0}
            cnt = defaultdict(lambda: [0, 0])
            n = 0
            lib_me = lib_op = None
            for t in T:
                o = t["observation"]
                if o["turn"] < 1:
                    continue
                n += 1
                for b in o["buildings"]:
                    ty = btype[b["id"]]
                    if b["owner"] == me:
                        cnt[ty][0] += 1
                        if ty == "LIBRARY" and lib_me is None:
                            lib_me = o["turn"]
                    elif b["owner"] == op:
                        cnt[ty][1] += 1
                        if ty == "LIBRARY" and lib_op is None:
                            lib_op = o["turn"]
            for ty in TYPES:
                agg[res][ty].append((cnt[ty][0] / n, cnt[ty][1] / n))
            first_lib[res].append((lib_me or 999, lib_op or 999))
            libdiff = cnt["LIBRARY"][0] / n - cnt["LIBRARY"][1] / n
            agg[res]["_libany"].append((1 if cnt["LIBRARY"][0] / n > 0.5 else 0, 1 if cnt["LIBRARY"][1] / n > 0.5 else 0))
    for res in ("승", "패", "무"):
        if res not in agg:
            continue
        k = len(agg[res]["HALL"])
        line = "  ".join(f"{ty[:4]} {sum(a for a, _ in agg[res][ty]) / k:.2f}:{sum(b for _, b in agg[res][ty]) / k:.2f}" for ty in TYPES)
        fl = first_lib[res]
        print(f"{res} {k:3d}경기  {line}  | 첫 도서관 턴 중앙 우 {sorted(a for a, _ in fl)[k // 2]} : 상 {sorted(b for _, b in fl)[k // 2]}")


if __name__ == "__main__":
    main()
