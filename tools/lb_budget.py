"""리더보드 변환 리플레이: 특정 턴까지 양쪽 자원 장부 분해.
수입(10 + 2×학관, 상한 40 넘친 손실 포함) + 보급소 = W 생산비 + 그 밖의 지출(F·점령·정찰) + 잔고 변화 + 상한 손실
- 우리: 명령(SPAWN)과 점령 이벤트로 정확히. 상대: W 생산 수는 정확(W 상쇄 대칭), 나머지는 자원 잔고로 역산.
사용: python3 tools/lb_budget.py <파일> <턴…>
"""
import json, sys


def cnt(st, t, k):
    return sum(u[4] for u in st["units"] if u[0] == t and u[1] == k)


path = sys.argv[1]
r = json.load(open(path, encoding="utf-8"))
me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
B = {b["id"]: b for b in r["map"]["buildings"]}
pos = {(b["x"], b["y"]): b for b in r["map"]["buildings"]}
T = r["turns"]
ends = sorted(int(x) for x in sys.argv[2:])
L = {t: dict(inc=0, cap=0, dep=0, wsp=0, wcost=0, fsp=0, fcost=0, capcost=0, other=0, fdie=0) for t in (me, op)}
got = {me: set(), op: set()}
out = []
for k in range(1, len(T)):
    a, b = T[k - 1]["state"], T[k]["state"]
    own = {t: [B[x["id"]]["type"] for x in a["buildings"] if x["owner"] == t] for t in (me, op)}
    sp = {"W": 0, "F": 0, "S": 0}
    for line in T[k]["commands"].get(me, []):
        p = line.split()
        if p and p[0] == "SPAWN" and p[1] in sp:
            sp[p[1]] += int(p[2])
    wd = max(0, cnt(a, me, "W") + sp["W"] - cnt(b, me, "W"))
    spawnW = {me: sp["W"], op: cnt(b, op, "W") - cnt(a, op, "W") + wd}
    for t in (me, op):
        h = own[t].count("HALL")
        cost = 2 if "ENG" in own[t] else 3
        lib = "LIBRARY" in own[t]
        income = 10 + 2 * h
        # 점령 비용·보급소
        capc = 0; dep = 0
        for e in T[k]["events"]:
            bb = pos.get((e.get("x"), e.get("y")))
            if e.get("team") == t and bb and e.get("type") in ("capture", "neutralize"):
                capc += max(1, 2 * (2 if bb["type"] == "PLAZA" else 1) - (1 if lib else 0))
                if e.get("type") == "capture" and bb["type"] == "DEPOT" and bb["id"] not in got[t]:
                    got[t].add(bb["id"]); dep += 15
        L[t]["inc"] += income; L[t]["dep"] += dep
        L[t]["wsp"] += spawnW[t]; L[t]["wcost"] += spawnW[t] * cost
        if t == me:
            L[t]["fsp"] += sp["F"]; L[t]["fcost"] += sp["F"] * 5 + sp["S"] * 2
            L[t]["capcost"] += capc
        # 상한 손실 근사: (이전 잔고 − 생산비 + 수입) > 40 이면 넘친 만큼
        before = a["resources"][t]
        spend_w = spawnW[t] * cost + (sp["F"] * 5 + sp["S"] * 2 if t == me else 0)
        over = max(0, before - spend_w + income - 40)
        L[t]["cap"] += over
    if T[k]["turn"] in ends:
        snap = {t: dict(L[t]) for t in (me, op)}
        res = {t: b["resources"][t] for t in (me, op)}
        out.append((T[k]["turn"], snap, res))
start = {t: 10 for t in (me, op)}
for turn, S, res in out:
    print(f"== {turn}턴까지  (우리 {me} | 상대 {op})")
    for t, nm in ((me, "우리"), (op, "상대")):
        s = S[t]
        total_in = start[t] + s["inc"] + s["dep"] - s["cap"]
        rest = total_in - s["wcost"] - res[t]       # W 외 지출(F·점령·정찰) — 상대는 이 값이 추정
        print(f"  {nm}: 수입 {s['inc']} 보급소 {s['dep']} 상한손실 {s['cap']} | W {s['wsp']}명 비용 {s['wcost']} (평균 {s['wcost'] / max(1, s['wsp']):.2f}) | "
              f"W 외 지출 {rest}" + (f" (F {s['fsp']}명 {s['fcost']}·점령 {s['capcost']})" if t == me else "") + f" | 잔고 {res[t]}")
