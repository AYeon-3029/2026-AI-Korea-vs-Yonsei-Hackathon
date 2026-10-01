"""도서관(점령 비용 2→1, 광장 4→3, 중첩 없음)의 실제 가치: 리더보드 변환 리플레이 전체.
경기별: 도서관 보유 턴(우리·상대) · 점령/중립화 단계 수와 도서관 할인으로 아낀 자원 · 학관 턴 차 · 결과.
도서관 상실 사건: 우리가 도서관을 모두 잃은 순간 → 그 뒤 20턴 W 차 변화(같은 경기 다른 구간 평균과 비교).
사용: python3 tools/lb_library.py out/replays/leaderboard/*/*.json"""
import json, sys
from collections import defaultdict

def units(st, team, kind):
    return sum(u[4] for u in st["units"] if u[0] == team and u[1] == kind)

rows = []; events = []
import glob
for path in [p for a in sys.argv[1:] for p in sorted(glob.glob(a))]:
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    win = r["result"].get("winner") == me
    B = {b["id"]: b for b in r["map"]["buildings"]}
    pos = {(b["x"], b["y"]): b for b in r["map"]["buildings"]}
    T = r["turns"]
    S = defaultdict(float)
    has_prev = {me: False, op: False}
    wgap = []
    for k, t in enumerate(T):
        st = t["state"]; turn = t["turn"]
        if turn > 160: break
        own = {x["id"]: x["owner"] for x in st["buildings"]}
        lib = {tm: any(B[i]["type"] == "LIBRARY" and o == tm for i, o in own.items()) for tm in (me, op)}
        for tm, nm in ((me, "me"), (op, "op")):
            S[f"lib_{nm}"] += lib[tm]
            S[f"hall_{nm}"] += sum(1 for i, o in own.items() if B[i]["type"] == "HALL" and o == tm)
        for e in t["events"]:
            if e["type"] in ("capture", "neutral") and e.get("team") in (me, op):
                bb = pos.get((e["x"], e["y"]))
                base = 4 if bb and bb["type"] == "PLAZA" else 2
                nm = "me" if e["team"] == me else "op"
                S[f"steps_{nm}"] += 1
                S[f"cost_{nm}"] += base - (1 if has_prev[e["team"]] else 0)
                S[f"save_{nm}"] += 1 if has_prev[e["team"]] else 0
        wgap.append(units(st, me, "W") - units(st, op, "W"))
        # 우리가 도서관을 (하나라도 가졌다가) 모두 잃은 순간
        if has_prev[me] and not lib[me] and k + 20 < len(T):
            events.append((path.split("/")[-2][:3] + "/" + path.split("/")[-1][2:-5], turn, win, wgap[-1], units(T[k + 20]["state"], me, "W") - units(T[k + 20]["state"], op, "W")))
        has_prev = lib
    rows.append((path.split("/")[-2][:3] + "/" + path.split("/")[-1][2:-5], win, S))

print(f"{'경기':28s} 결과 | 도서관턴 우리·상대 | 점령단계 우리·상대 | 할인 절약 우리·상대 | 학관턴 우리·상대")
for nm, win, S in rows:
    print(f"{nm:28s} {'승' if win else '패'}  | {S['lib_me']:4.0f} {S['lib_op']:4.0f} | {S['steps_me']:3.0f} {S['steps_op']:3.0f} | {S['save_me']:3.0f} {S['save_op']:3.0f} | {S['hall_me']:4.0f} {S['hall_op']:4.0f}")
for lab, sel in (("승", [x for x in rows if x[1]]), ("패", [x for x in rows if not x[1]])):
    n = max(1, len(sel)); m = lambda k: sum(S[k] for _, _, S in sel) / n
    print(f"[{lab} {len(sel)}경기 평균] 도서관턴 {m('lib_me'):.0f}:{m('lib_op'):.0f} (차 {m('lib_me') - m('lib_op'):+.0f}) · 할인 절약 {m('save_me'):.1f}:{m('save_op'):.1f} (차 {m('save_me') - m('save_op'):+.1f} 자원) · 학관턴 차 {m('hall_me') - m('hall_op'):+.0f} (자원 {2 * (m('hall_me') - m('hall_op')):+.0f})")
# 도서관 턴 차가 학관과 독립적으로 승패와 관련되는가: 학관턴 차가 비슷한 경기끼리
print("\n학관 턴 차 |≤20| 인 경기(학관 영향 통제):")
sel = [x for x in rows if abs(x[2]["hall_me"] - x[2]["hall_op"]) <= 20]
for lab, ss in (("승", [x for x in sel if x[1]]), ("패", [x for x in sel if not x[1]])):
    n = max(1, len(ss)); print(f"  {lab} {len(ss)}경기: 도서관턴 차 평균 {sum(S['lib_me'] - S['lib_op'] for _, _, S in ss) / n:+.0f} · 할인 절약 차 {sum(S['save_me'] - S['save_op'] for _, _, S in ss) / n:+.1f}")
print(f"\n우리가 도서관을 모두 잃은 순간 {len(events)}건: 그때 W 차 → 20턴 뒤 W 차 (평균 변화 {sum(b - a for *_, a, b in events) / max(1, len(events)):+.1f})")
for e in events[:25]:
    print("  ", e[0], f"{e[1]}턴", "승" if e[2] else "패", f"W차 {e[3]:+d} → {e[4]:+d}")

# 비교 기준: 같은 경기들의 임의 시점 20턴 W 차 변화 / 같은 시점(±3턴)에 학관·공학관도 잃었는지
base = []; conf = 0; pure = []
for path in [p for a in sys.argv[1:] for p in sorted(glob.glob(a))]:
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    T = [t for t in r["turns"] if t["turn"] <= 160]
    g = [units(t["state"], me, "W") - units(t["state"], op, "W") for t in T]
    base += [g[k + 20] - g[k] for k in range(10, len(g) - 20)]
    B = {b["id"]: b for b in r["map"]["buildings"]}
    nm = path.split("/")[-2][:3] + "/" + path.split("/")[-1][2:-5]
    for e in [x for x in events if x[0] == nm]:
        k = next(i for i, t in enumerate(T) if t["turn"] == e[1])
        lost_eco = False
        for j in range(max(1, k - 3), min(len(T), k + 4)):
            a = {x["id"]: x["owner"] for x in T[j - 1]["state"]["buildings"]}
            b = {x["id"]: x["owner"] for x in T[j]["state"]["buildings"]}
            if any(B[i]["type"] in ("HALL", "ENG") and a[i] == me and b[i] != me for i in a):
                lost_eco = True
        conf += lost_eco
        if not lost_eco:
            pure.append(e[4] - e[3])
print(f"\n비교 기준(임의 시점 20턴 W 차 변화) 평균 {sum(base) / len(base):+.1f} (n={len(base)})")
print(f"도서관 상실 83건 중 ±3턴 안에 학관·공학관도 잃은 경우 {conf}건 → 도서관만 잃은 {len(pure)}건의 20턴 W 차 변화 평균 {sum(pure) / max(1, len(pure)):+.1f}")
