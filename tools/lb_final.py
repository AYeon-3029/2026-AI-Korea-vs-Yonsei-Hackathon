"""리더보드 변환 리플레이: 마지막 20턴 점령·중립화 이벤트(턴·팀·건물)와 140·150·155턴 양쪽 W 배치(중앙 7×7 안 비율).
사용: python3 tools/lb_final.py <파일…>
"""
import json, os, sys
SH = {"HALL": "학", "ENG": "공", "LIBRARY": "도", "PLAZA": "광", "STATION": "역", "HOSPITAL": "병", "WATCH": "방", "DEPOT": "보"}
for path in sys.argv[1:]:
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    pos = {(b["x"], b["y"]): b for b in r["map"]["buildings"]}
    T = r["turns"]
    print(f"#### {os.path.basename(path)[2:-5]} 결과 {r['result'].get('score')}")
    ev = []
    for t in T:
        if t["turn"] < 141:
            continue
        for e in t["events"]:
            if e.get("type") in ("capture", "neutralize") and (e["x"], e["y"]) in pos:
                b = pos[(e["x"], e["y"])]
                ev.append(f"{t['turn']}{'우' if e['team'] == me else '상'}{'점' if e['type'] == 'capture' else '중'}{SH[b['type']]}{b['score']}")
    print("  " + " ".join(ev))
    for t in T:
        if t["turn"] in (140, 150, 155, 160):
            st = t["state"]
            for s, nm in ((me, "우리"), (op, "상대")):
                W = [(u[2], u[3], u[4]) for u in st["units"] if u[0] == s and u[1] == "W"]
                tot = sum(n for _, _, n in W) or 1
                cen = sum(n for x, y, n in W if 4 <= x <= 10 and 4 <= y <= 10)
                F = sum(u[4] for u in st["units"] if u[0] == s and u[1] == "F")
                print(f"  턴 {t['turn']} {nm} W {tot} 중앙 {cen * 100 // tot}% F {F}", end="")
            print()
