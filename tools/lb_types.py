"""리더보드 변환 리플레이: 건물 종류별 평균 보유(우리:상대)와 마지막 턴 보유 점수.
사용: python3 tools/lb_types.py <파일…>
"""
import json, os, sys
SH = {"HALL": "학", "ENG": "공", "LIBRARY": "도", "PLAZA": "광", "STATION": "역", "HOSPITAL": "병", "WATCH": "방", "DEPOT": "보"}
for path in sys.argv[1:]:
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    B = {b["id"]: b for b in r["map"]["buildings"]}
    T = r["turns"]
    acc = {}
    for t in T:
        for x in t["state"]["buildings"]:
            k = B[x["id"]]["type"]
            a = acc.setdefault(k, [0, 0])
            if x["owner"] == me:
                a[0] += 1
            elif x["owner"] == op:
                a[1] += 1
    n = len(T)
    last = T[-1]["state"]["buildings"]
    lm = [f"{SH[B[x['id']]['type']]}{B[x['id']]['score']}" for x in last if x["owner"] == me]
    lo = [f"{SH[B[x['id']]['type']]}{B[x['id']]['score']}" for x in last if x["owner"] == op]
    print(f"#### {os.path.basename(path)} 결과 {r['result'].get('score')}")
    print("  평균 보유 " + " ".join(f"{SH[k]} {v[0] / n:.2f}:{v[1] / n:.2f}" for k, v in sorted(acc.items())))
    print(f"  마지막 우리 {lm}  상대 {lo}")
