"""리더보드 변환 리플레이: 우리 진영 학생회관·공학관 소유 변화 순간과 직전 1~3턴 주변(3칸) 병력.
사용: python3 tools/lb_hall.py <파일…>
"""
import json, os, sys


def near(st, team, kind, x, y, r):
    return sum(u[4] for u in st["units"] if u[0] == team and u[1] == kind and abs(u[2] - x) + abs(u[3] - y) <= r)


for path in sys.argv[1:]:
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    B = {b["id"]: b for b in r["map"]["buildings"]}
    bx, by = r["map"]["bases"][me]
    ox, oy = r["map"]["bases"][op]
    T = r["turns"]
    print(f"#### {os.path.basename(path)} 우리={me} 결과 {r['result'].get('winner')} {r['result'].get('reason')}")
    for i, b in B.items():
        if b["type"] not in ("HALL", "ENG"):
            continue
        mine_side = abs(b["x"] - bx) + abs(b["y"] - by) < abs(b["x"] - ox) + abs(b["y"] - oy)
        tl = "".join({me: "U", op: "x", "N": "."}[next(x["owner"] for x in t["state"]["buildings"] if x["id"] == i)] for t in T)
        print(f"  {b['type']}({b['x']},{b['y']}) {'우리쪽' if mine_side else '상대쪽'} 본진거리 {abs(b['x'] - bx) + abs(b['y'] - by)}/{abs(b['x'] - ox) + abs(b['y'] - oy)}")
        print("    " + tl[:160])
        prev = "N"
        for k, t in enumerate(T):
            o = next(x["owner"] for x in t["state"]["buildings"] if x["id"] == i)
            if prev == me and o != me:
                a = T[k - 1]["state"]
                print(f"    턴 {t['turn']} 상실: 직전 3칸 적W {near(a, op, 'W', b['x'], b['y'], 3)} 적F {near(a, op, 'F', b['x'], b['y'], 3)} "
                      f"우리W {near(a, me, 'W', b['x'], b['y'], 3)} 위 {near(a, me, 'W', b['x'], b['y'], 0)} | 전체 W {near(a, me, 'W', 7, 7, 99)}:{near(a, op, 'W', 7, 7, 99)}")
            prev = o
