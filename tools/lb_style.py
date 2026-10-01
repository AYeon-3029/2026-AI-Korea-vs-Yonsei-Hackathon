"""리더보드 변환 리플레이에서 양쪽 운용 방식 정량화(구간별 평균).
- W총: 전체 W, 무리: W 무리 수(4-이웃 연결 칸 묶음), 최대%: 가장 큰 무리 비율, 적진%: 상대 본진이 더 가까운 칸의 W 비율,
  주둔%: 자기 건물 칸 위 W 비율, 전선%: 자기 건물에서 3칸 넘게 떨어진 W 비율
- F: F 수, F호위%: 1칸 안에 자기 W 가 있는 F 비율, 병원생산: 자기 병원 칸에 새로 나타난 유닛 수(누계)
사용: python3 tools/lb_style.py <파일…>
"""
import json, os, sys
PH = [(1, 20), (21, 50), (51, 100), (101, 160)]


def comps(cells):
    cs = set(cells); seen = set(); out = []
    for c in cells:
        if c in seen:
            continue
        st = [c]; seen.add(c); grp = []
        while st:
            x = st.pop(); grp.append(x)
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                y = (x[0] + d[0], x[1] + d[1])
                if y in cs and y not in seen:
                    seen.add(y); st.append(y)
        out.append(grp)
    return out


def stats(st, team, B, base_t, base_o):
    W = {}
    F = {}
    for u in st["units"]:
        if u[0] != team:
            continue
        (W if u[1] == "W" else F if u[1] == "F" else {})[(u[2], u[3])] = (W if u[1] == "W" else F if u[1] == "F" else {}).get((u[2], u[3]), 0) + u[4]
    tw = sum(W.values())
    own = [(B[x["id"]]["x"], B[x["id"]]["y"]) for x in st["buildings"] if x["owner"] == team]
    d = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
    if tw:
        cs = comps(list(W))
        sizes = sorted((sum(W[c] for c in g) for g in cs), reverse=True)
        enemy = sum(n for c, n in W.items() if d(c, base_o) < d(c, base_t)) / tw
        gar = sum(n for c, n in W.items() if c in own) / tw
        front = sum(n for c, n in W.items() if min((d(c, o) for o in own), default=99) > 3) / tw
        top = sizes[0] / tw
        ng = len([s for s in sizes if s >= 3])
    else:
        enemy = gar = front = top = 0; ng = 0
    tf = sum(F.values())
    esc = sum(n for c, n in F.items() if any(d(c, w) <= 1 for w in W)) / tf if tf else 0
    return dict(W=tw, grp=ng, top=top, enemy=enemy, gar=gar, front=front, F=tf, esc=esc)


for path in sys.argv[1:]:
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    B = {b["id"]: b for b in r["map"]["buildings"]}
    bases = {k: tuple(v) for k, v in r["map"]["bases"].items()}
    T = r["turns"]
    hosp = {t: 0 for t in (me, op)}
    for k in range(1, len(T)):
        a, b = T[k - 1]["state"], T[k]["state"]
        for t in (me, op):
            hs = {(B[x["id"]]["x"], B[x["id"]]["y"]) for x in a["buildings"] if x["owner"] == t and B[x["id"]]["type"] == "HOSPITAL"}
            pa = {(u[2], u[3]): u[4] for u in a["units"] if u[0] == t}
            pb = {(u[2], u[3]): u[4] for u in b["units"] if u[0] == t}
            for h in hs:
                # 병원 칸 인원이 늘었는데 이웃에서 들어온 것으로 설명되지 않으면 생산으로 본다(근사)
                inc = pb.get(h, 0) - pa.get(h, 0)
                if inc > 0:
                    hosp[t] += inc
    print(f"#### {os.path.basename(path)[2:-5]}  결과 {r['result'].get('winner') == me and '승' or '패'} {r['result'].get('score')}  턴 {len(T)}")
    for lo, hi in PH:
        rows = [t for t in T if lo <= t["turn"] <= hi]
        if not rows:
            continue
        for team, nm in ((op, "상대"), (me, "우리")):
            S = [stats(t["state"], team, B, bases[team], bases[op if team == me else me]) for t in rows]
            m = {k: sum(s[k] for s in S) / len(S) for k in S[0]}
            print(f"  {lo:3d}~{hi:3d} {nm} W {m['W']:5.1f} 무리 {m['grp']:.1f} 최대 {m['top'] * 100:3.0f}% 적진 {m['enemy'] * 100:3.0f}% 주둔 {m['gar'] * 100:3.0f}% "
                  f"건물밖 {m['front'] * 100:3.0f}% | F {m['F']:.1f} 호위 {m['esc'] * 100:3.0f}%")
    print(f"  병원 칸 증가(생산 근사) 상대 {hosp[op]} 우리 {hosp[me]}")
