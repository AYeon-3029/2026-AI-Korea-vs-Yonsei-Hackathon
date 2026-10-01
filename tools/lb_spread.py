"""W 배치 분산(망) 비교: 칸 수·칸당 W·최대 스택·통제 면적(자기 W 1칸/2칸 안 통행 가능 칸 비율)·
우리 F 사망 순간 포위(2칸 안 적 W 칸 수와 방향 수).
사용: python3 tools/lb_spread.py 'out/replays/leaderboard/V29_1001_3pm/*.json' [팀 이름 조각…]"""
import glob, json, sys
from collections import defaultdict
pats = [a for a in sys.argv[1:] if "/" in a]
names = [a for a in sys.argv[1:] if "/" not in a]
files = sorted({p for a in pats for p in glob.glob(a)})
PH = [(1, 30), (31, 80), (81, 160)]
d = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
rows = []
for f in files:
    nm = f.replace("\\", "/").split("/")[-1][2:-5]
    if names and not any(n in nm for n in names):
        continue
    r = json.load(open(f, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    terr = r["map"]["terrain"]; H = len(terr); Wd = len(terr[0])
    pas = [(x, y) for y in range(H) for x in range(Wd) if terr[y][x] != "#"]
    T = [t for t in r["turns"] if t["turn"] <= 160]
    S = {tm: {p: defaultdict(float) for p in PH} for tm in (me, op)}
    enc = []
    for k, t in enumerate(T):
        st = t["state"]
        ph = next(p for p in PH if p[0] <= t["turn"] <= p[1]) if t["turn"] >= 1 else PH[0]
        for tm in (me, op):
            W = {}
            for u in st["units"]:
                if u[0] == tm and u[1] == "W":
                    W[(u[2], u[3])] = W.get((u[2], u[3]), 0) + u[4]
            if not W: continue
            P = S[tm][ph]; P["n"] += 1
            P["cells"] += len(W); P["per"] += sum(W.values()) / len(W); P["max"] += max(W.values()) / sum(W.values())
            P["c1"] += sum(1 for c in pas if any(d(c, w) <= 1 for w in W)) / len(pas)
            P["c2"] += sum(1 for c in pas if any(d(c, w) <= 2 for w in W)) / len(pas)
        # 우리 F 사망 순간 포위도
        if k:
            a = T[k - 1]["state"]
            Fa = {(u[2], u[3]): u[4] for u in a["units"] if u[0] == me and u[1] == "F"}
            Fb = {(u[2], u[3]): u[4] for u in st["units"] if u[0] == me and u[1] == "F"}
            Ea = {(u[2], u[3]): u[4] for u in a["units"] if u[0] == op and u[1] == "W"}
            for c, n in Fa.items():
                if Fb.get(c, 0) < n and not any(Fb.get(x, 0) > Fa.get(x, 0) for x in [(c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)]):
                    near = [w for w in Ea if d(w, c) <= 2]
                    dirs = {(1 if w[0] > c[0] else -1 if w[0] < c[0] else 0, 1 if w[1] > c[1] else -1 if w[1] < c[1] else 0) for w in near}
                    enc.append((len(near), len(dirs), sum(Ea[w] for w in near)))
    rows.append((nm, r["result"].get("winner") == me, S, me, op, enc))

def show(sel, lab):
    for who, key in (("상대", 4), ("우리", 3)):
        out = []
        for p in PH:
            n = sum(S[x[key]][p]["n"] for x in sel for S in [x[2]])
            if not n: continue
            g = lambda k: sum(x[2][x[key]][p][k] for x in sel) / n
            out.append(f"{p[0]}~{p[1]} 칸 {g('cells'):4.1f} 칸당W {g('per'):3.1f} 최대스택 {g('max'):3.0%} 통제1칸 {g('c1'):3.0%} 2칸 {g('c2'):3.0%}")
        print(f"  [{lab} {who}] " + " | ".join(out))
    enc = [e for x in sel for e in x[5]]
    if enc:
        print(f"  [{lab}] 우리 F 사망 {len(enc)}건: 2칸 안 적 W 칸 수 평균 {sum(e[0] for e in enc) / len(enc):.1f} · 방향 수 {sum(e[1] for e in enc) / len(enc):.1f} · 적 W {sum(e[2] for e in enc) / len(enc):.1f} · 3방향 이상 {sum(1 for e in enc if e[1] >= 3) / len(enc):.0%}")

for x in rows:
    if names:
        print(f"### {x[0]} ({'우리 승' if x[1] else '우리 패'})"); show([x], "경기")
if not names:
    show([x for x in rows if not x[1]], "진 경기"); show([x for x in rows if x[1]], "이긴 경기")
