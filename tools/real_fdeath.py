"""실제 리플레이: 우리 F 손실(적 W 에 잡힘)·F 지출·응답 시간.

F 는 점령해도 소모되지 않으므로 (이전 F + 생산 − 현재 F) = 잡힌 F.
사용 (WSL): python3 tools/real_fdeath.py 'Real Match Replay/V14_0929_8pm'
"""
from __future__ import annotations

import glob
import json
import os
import sys


def fdeath(path):
    r = json.load(open(path, encoding="utf-8"))
    me = r["side"]
    T = [t for t in r["turns"] if t.get("observation")]
    prevF, prod, deaths, ms = 0, 0, [], []
    for t in T:
        o = t["observation"]
        f = sum(u[4] for u in o["units"] if u[0] == me and u[1] == "F")
        pending = 0   # 관측 = 이번 턴 명령 처리 후 상태
        for ln in (t.get("command") or {}).get("lines", []):
            p = ln.split()
            if p[:2] == ["SPAWN", "F"]:
                pending += int(p[2])
        prod += pending
        if prevF is not None:
            d = prevF + pending - f
            if d > 0:
                deaths.append((o["turn"], d))
        ms.append(o.get("myResponseMs") or 0)
        prevF = f
    res = r["result"]
    wl = "무" if res.get("winner") is None else ("승" if res["winner"] == me else "패")
    n = sum(d for _, d in deaths)
    early = sum(d for tt, d in deaths if tt <= 40)
    return wl, prod, n, early, deaths, max(ms), sorted(ms)[len(ms) // 2]


def main():
    for p in sorted(glob.glob(os.path.join(sys.argv[1], "*.json"))):
        wl, prod, n, early, deaths, mx, med = fdeath(p)
        print(f"{os.path.basename(p):28s} {wl} F생산 {prod:2d} 잡힘 {n:2d}(40턴 전 {early}) 응답 최대 {mx}ms 중앙 {med}ms  "
              + " ".join(f"{t}:{d}" for t, d in deaths[:14]))


if __name__ == "__main__":
    main()
