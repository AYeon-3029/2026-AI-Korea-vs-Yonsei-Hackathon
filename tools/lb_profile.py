"""리더보드 변환 리플레이에서 상대(또는 우리) 팀의 전략 지문을 뽑는다.

항목(구간 1~20 · 21~50 · 51~100 · 101~160 평균 또는 누계):
- 생산: 턴당 W 생산(W 상쇄가 대칭이라 정확), F 수, 병원 칸 W 증가 비율(병원 생산 근사)
- 초반: 1~20턴 점령 순서(종류·턴)
- 기습: 상대 진영 쪽이 아닌(우리 쪽·중앙) 건물을 처음 점령한 턴들과 그때 2칸 안 W
- 병력: W 무리 수(3명 이상), 최대 무리 비율, 적진(상대 본진이 더 가까운 칸) 비율, 자기 건물 위 비율
- F: 호위율(1칸 안 자기 W), 사망(우리 W 와 같은 칸에서 사라진 F 근사: 수 감소분)
- TELE: 자기 역 칸 W 가 이웃에서 설명되지 않게 늘어난 턴 수
- 수비 반응: 우리 W 가 그들 학관·공학관 2칸 안에 처음 들어온 순간 → 3턴 안 그 건물 3칸 안 그들 W 증가
- 막판: 141~160 F 수·중앙(4~10) W 비율·점령 수
사용: python3 tools/lb_profile.py <파일…> [--us]   (--us 면 우리 쪽 지문)
"""
import json
import os
import sys

PH = [(1, 20), (21, 50), (51, 100), (101, 160)]
SH = {"HALL": "학", "ENG": "공", "LIBRARY": "도", "PLAZA": "광", "STATION": "역", "HOSPITAL": "병", "WATCH": "방", "DEPOT": "보"}


def d(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def comps(cells):
    cs = set(cells); seen = set(); out = []
    for c in cells:
        if c in seen:
            continue
        st = [c]; seen.add(c); grp = []
        while st:
            x = st.pop(); grp.append(x)
            for dd in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                y = (x[0] + dd[0], x[1] + dd[1])
                if y in cs and y not in seen:
                    seen.add(y); st.append(y)
        out.append(grp)
    return out


def units(st, team, kind):
    o = {}
    for u in st["units"]:
        if u[0] == team and u[1] == kind:
            o[(u[2], u[3])] = o.get((u[2], u[3]), 0) + u[4]
    return o


def profile(path, us=False):
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    T_, O_ = (me, op) if us else (op, me)          # T_ = 분석 대상 팀, O_ = 그 상대
    B = {b["id"]: b for b in r["map"]["buildings"]}
    pos = {(b["x"], b["y"]): b for b in r["map"]["buildings"]}
    bt = tuple(r["map"]["bases"][T_]); bo = tuple(r["map"]["bases"][O_])
    T = r["turns"]
    out = {"name": os.path.basename(path)[2:-5], "res": ("승" if r["result"].get("winner") == me else "패"), "turns": len(T)}
    ph = {p: dict(n=0, wsp=0, F=0, grp=0, top=0, enemy=0, gar=0, esc=0, escn=0, hospw=0, tele=0) for p in PH}
    caps_early, raids, late_caps = [], [], 0
    react = []
    reacted = set()
    for k in range(1, len(T)):
        a, b = T[k - 1]["state"], T[k]["state"]
        turn = T[k]["turn"]
        p = next((x for x in PH if x[0] <= turn <= x[1]), None)
        if p is None:
            continue
        P = ph[p]; P["n"] += 1
        Wa, Wb = units(a, T_, "W"), units(b, T_, "W")
        Oa = units(a, O_, "W"); Ob = units(b, O_, "W")
        # 대상 팀 W 생산 = 증가 + 사망(사망은 상대 W 사망과 같다 — 상대 쪽 생산을 알아야 하므로, 우리 명령이 있는 쪽으로 계산)
        sp_me = sum(int(l.split()[2]) for l in T[k]["commands"].get(me, []) if l.startswith("SPAWN W"))
        wd_me = max(0, sum(units(a, me, "W").values()) + sp_me - sum(units(b, me, "W").values()))
        if T_ == me:
            wsp = sp_me
        else:
            wsp = sum(Wb.values()) - sum(Wa.values()) + wd_me
        P["wsp"] += wsp
        Fb = units(b, T_, "F")
        P["F"] += sum(Fb.values())
        tw = sum(Wb.values())
        own = [(B[x["id"]]["x"], B[x["id"]]["y"]) for x in b["buildings"] if x["owner"] == T_]
        if tw:
            cs = comps(list(Wb))
            sizes = sorted((sum(Wb[c] for c in g) for g in cs), reverse=True)
            P["grp"] += len([s for s in sizes if s >= 3])
            P["top"] += sizes[0] / tw
            P["enemy"] += sum(n for c, n in Wb.items() if d(c, bo) < d(c, bt)) / tw
            P["gar"] += sum(n for c, n in Wb.items() if c in own) / tw
        tf = sum(Fb.values())
        if tf:
            P["esc"] += sum(n for c, n in Fb.items() if any(d(c, w) <= 1 for w in Wb)) / tf
            P["escn"] += 1
        # 병원·역 칸 W 증가(이웃에서 설명되지 않는 증가)
        hosp = [(B[x["id"]]["x"], B[x["id"]]["y"]) for x in a["buildings"] if x["owner"] == T_ and B[x["id"]]["type"] == "HOSPITAL"]
        stat = [(B[x["id"]]["x"], B[x["id"]]["y"]) for x in a["buildings"] if x["owner"] == T_ and B[x["id"]]["type"] == "STATION"]
        for c in hosp:
            nb = sum(Wa.get((c[0] + dx, c[1] + dy), 0) for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)))
            inc = Wb.get(c, 0) - nb
            if inc > 0:
                P["hospw"] += inc
        if len(stat) >= 2:
            for c in stat:
                nb = sum(Wa.get((c[0] + dx, c[1] + dy), 0) for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)))
                if Wb.get(c, 0) - nb >= 2:
                    P["tele"] += 1
                    break
        # 점령 이벤트
        for e in T[k]["events"]:
            if e.get("team") != T_ or e.get("type") != "capture":
                continue
            bb = pos.get((e["x"], e["y"]))
            if not bb:
                continue
            c = (bb["x"], bb["y"])
            w2 = sum(n for x, n in units(a, T_, "W").items() if d(x, c) <= 2)
            if turn <= 20:
                caps_early.append(f"{turn}{SH[bb['type']]}")
            if d(c, bo) < d(c, bt) and len(raids) < 8:
                raids.append(f"{turn}{SH[bb['type']]}w{w2}")
            if turn > 140:
                late_caps += 1
        # 수비 반응: 상대 W 가 대상 팀 학관·공학관 2칸 안에 처음 들어온 순간
        for x in a["buildings"]:
            bb = B[x["id"]]
            if x["owner"] != T_ or bb["type"] not in ("HALL", "ENG") or bb["id"] in reacted:
                continue
            c = (bb["x"], bb["y"])
            o_near = sum(n for y, n in Ob.items() if d(y, c) <= 2)
            if o_near >= 3:
                reacted.add(bb["id"])
                before = sum(n for y, n in Wb.items() if d(y, c) <= 3)
                after = before
                for j in range(k + 1, min(len(T), k + 4)):
                    after = max(after, sum(n for y, n in units(T[j]["state"], T_, "W").items() if d(y, c) <= 3))
                react.append((turn, o_near, before, after))
    lines = []
    for p in PH:
        P = ph[p]
        if not P["n"]:
            continue
        n = P["n"]
        lines.append(f"  {p[0]:3d}~{p[1]:3d} W생산/턴 {P['wsp'] / n:4.1f} F {P['F'] / n:3.1f} 무리 {P['grp'] / n:3.1f} 최대 {P['top'] / n:4.0%} "
                     f"적진 {P['enemy'] / n:4.0%} 주둔 {P['gar'] / n:4.0%} 호위 {P['esc'] / max(1, P['escn']):4.0%} "
                     f"병원W {P['hospw']:3d} TELE턴 {P['tele']:2d}")
    late = [t for t in T if t["turn"] >= 141]
    lf = sum(sum(units(t["state"], T_, "F").values()) for t in late) / max(1, len(late))
    lc = 0.0
    for t in late:
        Wt = units(t["state"], T_, "W"); tw = sum(Wt.values()) or 1
        lc += sum(n for c, n in Wt.items() if 4 <= c[0] <= 10 and 4 <= c[1] <= 10) / tw
    lc /= max(1, len(late))
    out["text"] = (f"#### {out['name']} ({'우리' if us else '상대'} 지문, 경기 {out['res']}, {out['turns']}턴)\n"
                   + "\n".join(lines)
                   + f"\n  초반 점령 {' '.join(caps_early)}\n  상대 진영·중앙 점령(앞 8개) {' '.join(raids)}"
                   + (f"\n  막판(141~) F {lf:.1f} 중앙W {lc:.0%} 점령 {late_caps}" if late else "")
                   + f"\n  수비 반응(턴, 접근 W, 3칸 안 자기 W 전→3턴 안 최대) {react[:6]}")
    return out


if __name__ == "__main__":
    us = "--us" in sys.argv
    for f in [a for a in sys.argv[1:] if not a.startswith("--")]:
        print(profile(f, us)["text"])
