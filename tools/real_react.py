"""실제 리플레이: 상대가 위협에 반응해 수비를 보내는가(미끼 전술의 전제 확인).

위협 사건: 적(상대) 건물 옆 1칸 안에 우리 W 가 새로 생기고(직전 턴 0), 그 순간 건물 2칸 안 적 W 가 0.
반응: 이후 1·2턴 안에 그 건물 1칸 안 적 W 가 우리 W 수 이상 모임.
대조: 같은 턴, 우리 W 가 3칸 안에 없는 다른 적 건물에서 1·2턴 안에 적 W 가 1칸 안에 새로 모이는 비율.

사용 (WSL): python3 tools/real_react.py 'Real Match Replay/V12_0929_8am' 'Real Match Replay/V10_0928_8pm'
"""
from __future__ import annotations

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from real_analyze import load, man  # noqa: E402


KIND = os.environ.get("REACT_KIND", "W")   # 위협을 만드는 우리 유닛: W 또는 F
RADIUS = int(os.environ.get("REACT_R", "1"))  # 우리 유닛이 이 거리 안에 새로 오면 위협 사건


def main():
    tot = {"ev": 0, "resp1": 0, "resp2": 0, "ctl": 0, "ctl1": 0, "ctl2": 0}
    per_game = []
    for d in sys.argv[1:]:
        for path in sorted(glob.glob(os.path.join(d, "*.json"))):
            r, me, op, T, terr, blds0, score = load(path)
            frames = []
            for t in T:
                o = t["observation"]
                w = {tm: {} for tm in (me, op)}
                th = {}
                for tm, k, x, y, n in o["units"]:
                    if k == "W":
                        w[tm][(x, y)] = w[tm].get((x, y), 0) + n
                    if tm == me and k == KIND:
                        th[(x, y)] = th.get((x, y), 0) + n
                own = {(b["x"], b["y"]): b["owner"] for b in o["buildings"]}
                frames.append((w, own, th))

            def cnt(wd, p, R):
                return sum(n for c, n in wd.items() if man(c, p) <= R)

            g = {"ev": 0, "resp": 0}
            for i in range(1, len(frames) - 3):
                w, own, th = frames[i]
                pth = frames[i - 1][2]
                for p, o in own.items():
                    if o != op:
                        continue
                    mine = cnt(th, p, RADIUS)
                    if mine and not cnt(pth, p, RADIUS):
                        tot["arr"] = tot.get("arr", 0) + 1
                        tot["arr_taken"] = tot.get("arr_taken", 0) + any(frames[i + k][1][p] != op for k in (1, 2, 3))
                    if mine and not cnt(pth, p, RADIUS) and cnt(w[op], p, 2) == 0:
                        tot["ev"] += 1
                        g["ev"] += 1
                        need = mine if KIND == "W" else 1      # F 는 W 1명에도 죽는다
                        r1 = cnt(frames[i + 1][0][op], p, 1) >= need
                        r2 = r1 or cnt(frames[i + 2][0][op], p, 1) >= need
                        tot["resp1"] += r1
                        tot["resp2"] += r2
                        g["resp"] += r2
                        if not r2:
                            tot["taken"] = tot.get("taken", 0) + any(frames[i + k][1][p] != op for k in (1, 2, 3))
                    elif cnt(w[me], p, 3) == 0 and cnt(w[op], p, 1) == 0:
                        tot["ctl"] += 1
                        tot["ctl1"] += cnt(frames[i + 1][0][op], p, 1) > 0
                        tot["ctl2"] += cnt(frames[i + 1][0][op], p, 1) > 0 or cnt(frames[i + 2][0][op], p, 1) > 0
            per_game.append((os.path.basename(d), os.path.basename(path), g["ev"], g["resp"],
                             "승" if r["result"]["winner"] == me else "패"))
    e = max(1, tot["ev"])
    c = max(1, tot["ctl"])
    no = max(1, tot["ev"] - tot["resp2"])
    print(f"[{KIND} 위협, 반경 {RADIUS}] 반응 없을 때 3턴 안 중립화·탈취 {tot.get('taken', 0) / no:.2f}"
          f" | 조건 없이 도착 {tot.get('arr', 0)}건 → 3턴 안 탈취·중립화 {tot.get('arr_taken', 0) / max(1, tot.get('arr', 0)):.2f}")
    print(f"위협 사건 {tot['ev']}건: 1턴 안 반응 {tot['resp1'] / e:.2f}, 2턴 안 {tot['resp2'] / e:.2f}"
          f"  |  대조(위협 없는 적 건물) {tot['ctl']}건: 1턴 {tot['ctl1'] / c:.2f}, 2턴 {tot['ctl2'] / c:.2f}")
    for d, f, ev, rs, res in per_game:
        if ev:
            print(f"  {d[:14]:<14} {f:<17} {res} 사건 {ev:>3} 반응 {rs / ev:.2f}")


if __name__ == "__main__":
    main()
