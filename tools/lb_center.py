"""리더보드 변환 리플레이: 중앙 건물(광장·방송국·보급소·중앙 역) 소유 흐름(10턴=10글자)과 막판 30턴 W 수.
사용: python3 tools/lb_center.py <파일…>
"""
import json, os, sys
for path in sys.argv[1:]:
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    B = {b["id"]: b for b in r["map"]["buildings"]}
    T = r["turns"]
    print(f"#### {os.path.basename(path)} 결과 {r['result'].get('score')}")
    for i, b in sorted(B.items()):
        if not (4 <= b["x"] <= 10) or b["type"] in ("HALL", "ENG", "LIBRARY", "HOSPITAL"):
            continue
        tl = "".join({me: "U", op: "x", "N": "."}[next(x["owner"] for x in t["state"]["buildings"] if x["id"] == i)] for t in T)
        print(f"  {b['type'][:4]}{b['score']}({b['x']},{b['y']}) 100~160턴 {tl[99:160]}")
    for t in T[-31::10]:
        st = t["state"]
        w = {s: sum(u[4] for u in st["units"] if u[0] == s and u[1] == "W") for s in (me, op)}
        print(f"  턴 {t['turn']} W {w[me]}:{w[op]}")
