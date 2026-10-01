"""리더보드 변환 리플레이: 우리 F 사망 분류.
직전 상태에 우리 F 이동(MOVE·TELE)을 적용해 도착 칸을 구하고, 다음 상태에 그 칸 F 가 모자라면 그 칸에서 죽은 것으로 본다.
분류: 칸(목표 건물 위 머무름 / 이동해 들어감) × 적 W(그 칸에 1턴 안에 닿는 수, 직전 상태) × 우리 W 도착 여부.
사용: python3 tools/lb_fdeath.py <폴더|파일…>
"""
import glob, json, os, sys
from collections import Counter
D = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}

C = Counter(); per = {}
args = [a for a in sys.argv[1:]]
files = []
for p in args:
    files += sorted(glob.glob(os.path.join(p, "vs*.json"))) if os.path.isdir(p) else [p]
for path in files:
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    pos = {(b["x"], b["y"]): b for b in r["map"]["buildings"]}
    T = r["turns"]
    nd = 0
    for k in range(1, len(T)):
        a, b = T[k - 1]["state"], T[k]["state"]
        F = {}
        for u in a["units"]:
            if u[0] == me and u[1] == "F":
                F[(u[2], u[3])] = F.get((u[2], u[3]), 0) + u[4]
        arrive = {}; moved = set(); origin = {}
        stay = dict(F)
        for line in T[k]["commands"].get(me, []):
            p = line.split()
            if len(p) == 6 and p[0] == "MOVE" and p[3] == "F":
                x, y, n = int(p[1]), int(p[2]), int(p[4])
                n = min(n, stay.get((x, y), 0))
                if n <= 0:
                    continue
                dx, dy = D[p[5]]
                stay[(x, y)] -= n
                c = (x + dx, y + dy)
                arrive[c] = arrive.get(c, 0) + n; moved.add(c); origin[c] = (x, y)
            elif len(p) == 7 and p[0] == "TELE" and p[3] == "F":
                x, y, n = int(p[1]), int(p[2]), int(p[4])
                n = min(n, stay.get((x, y), 0))
                if n <= 0:
                    continue
                stay[(x, y)] -= n
                c = (int(p[5]), int(p[6]))
                arrive[c] = arrive.get(c, 0) + n; moved.add(c)
        # 이번 턴 생산 F(본진·병원) 는 계산에서 뺀다(생산 칸 정보가 부정확): 새로 생긴 F 는 사망 판정에서 제외
        for c, n in stay.items():
            if n > 0:
                arrive[c] = arrive.get(c, 0) + n
        Fb = {}
        for u in b["units"]:
            if u[0] == me and u[1] == "F":
                Fb[(u[2], u[3])] = Fb.get((u[2], u[3]), 0) + u[4]
        for c, n in arrive.items():
            lost = n - Fb.get(c, 0)
            if lost <= 0:
                continue
            enw1 = sum(u[4] for u in a["units"] if u[0] == op and u[1] == "W" and abs(u[2] - c[0]) + abs(u[3] - c[1]) <= 1)
            myw = sum(u[4] for u in a["units"] if u[0] == me and u[1] == "W" and abs(u[2] - c[0]) + abs(u[3] - c[1]) <= 1)
            bb = pos.get(c)
            where = ("건물" + ("(우리)" if bb and next(x["owner"] for x in a["buildings"] if x["id"] == bb["id"]) == me else "(남)")) if bb else "길"
            kind = ("진입" if c in moved else "머무름") + "·" + where
            o = origin.get(c, c)
            oe = sum(u[4] for u in a["units"] if u[0] == op and u[1] == "W" and abs(u[2] - o[0]) + abs(u[3] - o[1]) <= 1)
            om = sum(u[4] for u in a["units"] if u[0] == me and u[1] == "W" and abs(u[2] - o[0]) + abs(u[3] - o[1]) <= 1)
            kind += "·출발" + ("위험" if oe > om else "안전")
            thr = "적W없음" if enw1 == 0 else ("적W≤우리W" if enw1 <= myw else "적W>우리W")
            C[(kind, thr)] += lost; nd += lost
    per[os.path.basename(path)[2:-5]] = nd
tot = sum(C.values())
print("F 사망", tot, "| 경기별", per)
for k, v in C.most_common():
    print(f"  {k[0]:<14} {k[1]:<10} {v:4d} ({v / tot:.0%})")
