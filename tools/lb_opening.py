"""리더보드 변환 리플레이: 1~40턴 양쪽 점령 순서(턴·건물·점령 직전 주변 W)와 상대의 우리 쪽 첫 진입.
사용: python3 tools/lb_opening.py <파일…>
"""
import json, os, sys
SH = {"HALL": "학", "ENG": "공", "LIBRARY": "도", "PLAZA": "광", "STATION": "역", "HOSPITAL": "병", "WATCH": "방", "DEPOT": "보"}
for path in sys.argv[1:]:
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    B = {b["id"]: b for b in r["map"]["buildings"]}
    pos = {(b["x"], b["y"]): b for b in r["map"]["buildings"]}
    bm = tuple(r["map"]["bases"][me]); bo = tuple(r["map"]["bases"][op])
    d = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
    T = r["turns"]
    seq = {me: [], op: []}
    for k in range(1, len(T)):
        if T[k]["turn"] > 40:
            break
        a = T[k - 1]["state"]
        for e in T[k]["events"]:
            if e.get("type") != "capture":
                continue
            b = pos.get((e["x"], e["y"]))
            if not b:
                continue
            side = "우" if d((b["x"], b["y"]), bm) < d((b["x"], b["y"]), bo) else "상" if d((b["x"], b["y"]), bm) > d((b["x"], b["y"]), bo) else "중"
            if e["team"] == me:
                side = {"우": "자", "상": "적", "중": "중"}[side]
            else:
                side = {"우": "적", "상": "자", "중": "중"}[side]
            w = sum(u[4] for u in a["units"] if u[0] == e["team"] and u[1] == "W" and d((u[2], u[3]), (b["x"], b["y"])) <= 2)
            seq[e["team"]].append(f"{T[k]['turn']}{SH[b['type']]}{b['score']}{side}w{w}")
    print(f"#### {os.path.basename(path)[2:-5]}  결과 {'승' if r['result'].get('winner') == me else '패'}")
    print("  상대 " + " ".join(seq[op]))
    print("  우리 " + " ".join(seq[me]))
