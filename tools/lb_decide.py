"""판단 단위 스타일 비교: 리더보드 변환 리플레이에서 양 팀의 점령 시도를 추적한다.
시도 = F 가 자기 것이 아닌 건물 칸에 새로 들어온 순간. 성공 = 4턴 안 그 팀의 capture 이벤트(그 칸).
진입 순간 국지 병력: 그 칸 1칸 안 자기 W · 상대 W, 2칸 안 자기 W · 상대 W.
사용: python3 tools/lb_decide.py 'out/replays/leaderboard/*/*.json' --top tAIger,야구사랑했단,AIKU,붉은산호초,치명ㄷ,참새튀김기,우주류,ACE"""
import glob, json, sys
from collections import Counter, defaultdict

SH = {"HALL": "학", "ENG": "공", "LIBRARY": "도", "PLAZA": "광", "STATION": "역", "HOSPITAL": "병", "WATCH": "방", "DEPOT": "보"}
d = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
args = [a for a in sys.argv[1:] if not a.startswith("--")]
top = sys.argv[sys.argv.index("--top") + 1].split(",") if "--top" in sys.argv else []
files = [p for a in args for p in sorted(glob.glob(a))]
A = {"us": defaultdict(list), "top": defaultdict(list)}
G = {"us": 0, "top": 0}
for path in files:
    nm = path.replace("\\", "/").split("/")[-1][2:-5]
    if top and not any(t.replace(" ", "") in nm.replace(" ", "") for t in top):
        continue
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    B = {(b["x"], b["y"]): b for b in r["map"]["buildings"]}
    base = {t: tuple(r["map"]["bases"][t]) for t in ("Y", "K")}
    T = [t for t in r["turns"] if t["turn"] <= 160]
    for who, tm in (("us", me), ("top", op)):
        G[who] += 1
        ot = op if tm == me else me
        for k in range(1, len(T)):
            a, b = T[k - 1]["state"], T[k]["state"]
            own = {(B2["x"], B2["y"]): x["owner"] for x in b["buildings"] for B2 in [next(v for v in r["map"]["buildings"] if v["id"] == x["id"])]} if k == 1 or True else None
            Fa = {(u[2], u[3]) for u in a["units"] if u[0] == tm and u[1] == "F"}
            for u in b["units"]:
                if u[0] != tm or u[1] != "F": continue
                c = (u[2], u[3])
                if c not in B or c in Fa or own.get(c) == tm: continue
                W = lambda team, R: sum(x[4] for x in b["units"] if x[0] == team and x[1] == "W" and d((x[2], x[3]), c) <= R)
                ok = any(e.get("type") == "capture" and e.get("team") == tm and (e["x"], e["y"]) == c
                         for j in range(k, min(len(T), k + 5)) for e in T[j]["events"])
                kind = "적" if own.get(c) == ot else "중립"
                side = "적진" if d(c, base[ot]) < d(c, base[tm]) else "자기쪽"
                A[who]["att"].append((T[k]["turn"], B[c]["type"], kind, side, W(tm, 1), W(ot, 1), W(tm, 2), W(ot, 2), ok))

def summ(who):
    L = A[who]["att"]; n = G[who]
    print(f"[{'우리' if who == 'us' else '상위팀'}] {n}경기 · 점령 시도 {len(L) / n:.1f}/경기 · 성공률 {sum(x[8] for x in L) / max(1, len(L)):.0%}")
    for lab, f in (("중립 건물", lambda x: x[2] == "중립"), ("상대 건물", lambda x: x[2] == "적"),
                   ("상대 건물·적진", lambda x: x[2] == "적" and x[3] == "적진"), ("상대 건물·우리쪽(탈환)", lambda x: x[2] == "적" and x[3] == "자기쪽")):
        s = [x for x in L if f(x)]
        if not s: continue
        m = lambda i: sum(x[i] for x in s) / len(s)
        succ = [x for x in s if x[8]]; fail = [x for x in s if not x[8]]
        ms = lambda S, i: sum(x[i] for x in S) / max(1, len(S))
        print(f"  {lab:14s} {len(s) / n:4.1f}/경기 성공 {len(succ) / len(s):4.0%} | 진입 시 1칸 자기W {m(4):4.1f} 적W {m(5):4.1f} · 2칸 자기W {m(6):4.1f} 적W {m(7):4.1f}"
              f" | 성공 시 2칸 {ms(succ, 6):.1f}:{ms(succ, 7):.1f} · 실패 시 {ms(fail, 6):.1f}:{ms(fail, 7):.1f}")
    for ph in ((1, 30), (31, 80), (81, 160)):
        s = [x for x in L if ph[0] <= x[0] <= ph[1] and x[2] == "적"]
        c = Counter(SH[x[1]] for x in s if x[8])
        print(f"  {ph[0]:3d}~{ph[1]:3d}턴 상대 건물 탈취 {sum(c.values()) / n:4.1f}/경기 종류 {dict(c.most_common(5))}")
    # 엄호 없는 진입(1칸 자기 W 0) 비율과 성공률
    s = [x for x in L if x[2] == "적"]
    bare = [x for x in s if x[4] == 0]
    print(f"  상대 건물 시도 중 1칸 엄호 0명 {len(bare) / max(1, len(s)):.0%} (성공 {sum(x[8] for x in bare) / max(1, len(bare)):.0%}) · 2칸 우세(자기>적) {sum(1 for x in s if x[6] > x[7]) / max(1, len(s)):.0%}")
summ("top"); summ("us")

# 중립화(상대 건물 → 중립)와 그 뒤 재점령, 시기별 시도·성공
print()
N = {"us": Counter(), "top": Counter()}; P = {"us": Counter(), "top": Counter()}
for path in files:
    nm = path.replace("\\", "/").split("/")[-1][2:-5]
    if top and not any(t.replace(" ", "") in nm.replace(" ", "") for t in top):
        continue
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    B = {(b["x"], b["y"]): b for b in r["map"]["buildings"]}
    base = {t: tuple(r["map"]["bases"][t]) for t in ("Y", "K")}
    for t in r["turns"]:
        if t["turn"] > 160: break
        for e in t["events"]:
            if e.get("type") == "neutral" and e.get("team") in (me, op):
                who = "us" if e["team"] == me else "top"; ot = op if e["team"] == me else me
                c = (e["x"], e["y"]); ty = SH.get(B[c]["type"], "?") if c in B else "?"
                ph = "1~30" if t["turn"] <= 30 else "31~80" if t["turn"] <= 80 else "81~160"
                N[who][(ph, "적진" if d(c, base[ot]) < d(c, base[e["team"]]) else "자기쪽")] += 1
                P[who][ty] += 1
for who in ("top", "us"):
    n = G[who]
    print(f"[{'상위팀' if who == 'top' else '우리'}] 중립화(상대 건물 끊기) {sum(N[who].values()) / n:.1f}/경기 · " +
          " · ".join(f"{k[0]} {k[1]} {v / n:.1f}" for k, v in sorted(N[who].items())) + f" · 종류 {dict(P[who].most_common(6))}")
    L = A[who]["att"]
    for ph in ((1, 30), (31, 80), (81, 160)):
        s = [x for x in L if ph[0] <= x[0] <= ph[1]]
        print(f"   {ph[0]:3d}~{ph[1]:3d}턴 점령 시도 {len(s) / n:4.1f} 성공 {sum(x[8] for x in s) / max(1, len(s)):4.0%} · 진입 1칸 자기W {sum(x[4] for x in s) / max(1, len(s)):.1f} 적W {sum(x[5] for x in s) / max(1, len(s)):.1f}")
