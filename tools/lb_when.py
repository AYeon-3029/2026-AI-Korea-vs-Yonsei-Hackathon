"""패배 경기 분해: 언제 자원이 밀리고 언제 병력이 밀렸는가.
턴마다 양쪽 누적: 수입(10 + 2×학관 + 보급소 첫 점령 15), W 생산(상대 = W 증가 + 우리 W 사망, 상쇄 대칭),
W 외 지출(= 수입 − 잔고 변화 − W 생산비; 우리는 명령으로 정확히, 상대는 역산), 현재 W 차.
갈림: 누적 수입 차 ≤ −10 이 그 뒤 계속 유지되는 첫 턴 / W 차 ≤ −10 이 5턴 이상 유지되는 첫 턴.
사용: python3 tools/lb_when.py 'out/replays/leaderboard/V29_1001_3pm/*.json' [--all]"""
import glob, json, sys
args = [a for a in sys.argv[1:] if not a.startswith("--")]
files = sorted({p for a in args for p in glob.glob(a)})
show_all = "--all" in sys.argv

def W(st, tm): return sum(u[4] for u in st["units"] if u[0] == tm and u[1] == "W")
def F(st, tm): return sum(u[4] for u in st["units"] if u[0] == tm and u[1] == "F")

for f in files:
    r = json.load(open(f, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    win = r["result"].get("winner") == me
    if win and not show_all: continue
    B = {b["id"]: b for b in r["map"]["buildings"]}
    T = [t for t in r["turns"] if t["turn"] <= 160]
    eng_cost = lambda st, tm: 2 if any(B[x["id"]]["type"] == "ENG" and x["owner"] == tm for x in st["buildings"]) else 3
    C = {tm: dict(inc=0, wp=0, wcost=0, other=0, dep=0, hall=0) for tm in (me, op)}
    seen_dep = {me: set(), op: set()}
    rows = []
    for k in range(1, len(T)):
        a, b = T[k - 1]["state"], T[k]["state"]
        cm = T[k]["commands"].get(me, [])
        sw = sum(int(l.split()[2]) for l in cm if l.startswith("SPAWN W"))
        wd = max(0, W(a, me) + sw - W(b, me))              # 우리 W 사망 = 상대 W 사망
        for tm in (me, op):
            h = sum(1 for x in a["buildings"] if B[x["id"]]["type"] == "HALL" and x["owner"] == tm)
            inc = 10 + 2 * h
            for x in b["buildings"]:
                if B[x["id"]]["type"] == "DEPOT" and x["owner"] == tm and x["id"] not in seen_dep[tm]:
                    seen_dep[tm].add(x["id"]); inc += 15; C[tm]["dep"] += 15
            wp = sw if tm == me else max(0, W(b, op) - W(a, op) + wd)
            cost = eng_cost(a, tm)
            spent = a["resources"][tm] + inc - b["resources"][tm]
            C[tm]["inc"] += inc; C[tm]["wp"] += wp; C[tm]["wcost"] += wp * cost; C[tm]["other"] += max(0, spent - wp * cost); C[tm]["hall"] += h
        rows.append((T[k]["turn"], dict((tm, dict(C[tm])) for tm in (me, op)), W(b, me) - W(b, op), b))
    def first(cond, hold):
        for i in range(len(rows)):
            if all(cond(rows[j]) for j in range(i, min(len(rows), i + hold))):
                return i
        return None
    i_inc = first(lambda x: x[1][me]["inc"] - x[1][op]["inc"] <= -10, 10**6)
    i_w = first(lambda x: x[2] <= -10, 5)
    nm = f.replace("\\", "/").split("/")[-1][2:-5]
    print(f"\n### {nm} ({'승' if win else '패'}, {r['result']['reason']}, 점수 {r['result'].get('score')})")
    def at(i, lab):
        t, c, wg, st = rows[i]
        m, o = c[me], c[op]
        dW = m["wp"] - o["wp"]
        print(f"  {lab} {t:3d}턴 | W 차 {wg:+4d} (생산 누계 {m['wp']}:{o['wp']} = {dW:+d}) | 수입 누계 {m['inc']}:{o['inc']} ({m['inc'] - o['inc']:+d}, 그중 학관 {2 * (m['hall'] - o['hall']):+d} 보급소 {m['dep'] - o['dep']:+d})"
              f" | W 외 지출 {m['other']}:{o['other']} ({m['other'] - o['other']:+d}) | W 단가 {m['wcost'] / max(1, m['wp']):.2f}:{o['wcost'] / max(1, o['wp']):.2f} | F {F(st, me)}:{F(st, op)}")
    at(i_inc, "자원 갈림") if i_inc is not None else print("  자원 갈림 없음(누적 수입 차가 −10 이하로 계속 유지된 적 없음)")
    at(i_w, "병력 갈림") if i_w is not None else print("  병력 갈림 없음")
    for t0 in (30, 60, 100, 140):
        i = next((j for j, x in enumerate(rows) if x[0] == t0), None)
        if i is not None:
            at(i, "   시점")
    at(len(rows) - 1, "   최종")
