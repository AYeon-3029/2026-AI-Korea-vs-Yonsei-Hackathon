"""학관·공학관 손실과 경기 결과의 관계(사용자 가설: 뺏기는 순간 결과가 정해진다).
사용 (WSL): python3 tools/macro/eco_outcome.py --ver v20 --seeds 100000-100019 [--opps mimic]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
import bldloss  # noqa: E402
import branch  # noqa: E402
from branch import REAL_POOL, parse_range  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ver", default="v20")
    p.add_argument("--params", default="{}")
    p.add_argument("--seeds", default="100000-100019")
    p.add_argument("--opps", default="mimic")
    a = p.parse_args()
    opps = branch.MIMIC["mc16"] if a.opps == "mimic" else REAL_POOL if a.opps == "real" else a.opps.split(",")
    jobs = [(s, o, side, a.ver, json.loads(a.params)) for s in parse_range(a.seeds) for o in opps for side in "YK"]
    with Pool(20) as pool:
        rows = pool.map(bldloss.run, jobs, chunksize=2)
    n = len(rows)
    base = sum(r["v"] for r in rows) / n
    print(f"{n}경기 전체 승점 {base:.3f}")

    def grp(title, key):
        g = {}
        for r in rows:
            g.setdefault(key(r), []).append(r["v"])
        print(title)
        for k in sorted(g):
            v = g[k]
            print(f"   {k:28s} {len(v):5d}경기 ({len(v) / n:5.1%})  승점 {sum(v) / len(v):.3f}")

    def eco(r):
        return [e for e in r["loss"] if e["btype"] in ("HALL", "ENG")]

    def first(r):
        e = eco(r)
        return min((x["turn"] for x in e), default=None)
    grp("첫 학관·공학관 손실 시점", lambda r: "안 잃음" if first(r) is None else f"{(first(r) - 1) // 20 * 20 + 1:3d}-{(first(r) - 1) // 20 * 20 + 20}턴")
    grp("40턴까지 첫 손실의 탈환 속도", lambda r: "40턴까지 안 잃음" if first(r) is None or first(r) > 40 else
        (lambda e: "미탈환" if e["back"] is None else "≤5턴 탈환" if e["back"] <= 5 else "6-15턴" if e["back"] <= 15 else ">15턴")(
            min((x for x in eco(r)), key=lambda x: x["turn"])))
    grp("학관·공학관 잃은 건물-턴(경기 전체)", lambda r: (lambda s: "0" if s == 0 else "1-20" if s <= 20 else "21-60" if s <= 60 else "61-120" if s <= 120 else ">120")(
        sum((e["back"] if e["back"] is not None else 160 - e["turn"]) for e in eco(r))))


if __name__ == "__main__":
    main()
