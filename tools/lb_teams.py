"""상위 팀별 운용 방식과 약점: 리더보드 변환 리플레이(우리 대 그 팀) 전체.
지문(lb_profile 정의 평균) + 약점 지표:
- 그 팀 건물 상실(우리 중립화·점령): 종류·시기, 상실 직전 그 칸 2칸 안 그 팀 W(얇은 수비)
- 그 팀 학관·공학관 상실 횟수 · 우리 진영 기습 실패(그 팀 F 가 우리 쪽에서 사라진 수 근사)
- 수비 반응: 우리 W ≥3 이 그 팀 학관·공학관 2칸 안 진입 → 3턴 안 3칸 안 그 팀 W 증가
- 막판: 141~160턴 그 팀 점수 변화, 경기 결과
사용: python3 tools/lb_teams.py 'out/replays/leaderboard/*/*.json' tAIger 야구사랑했단 AIKU 붉은산호초 치명ㄷ 참새튀김기 우주류 ACE"""
import glob, json, sys
from collections import Counter, defaultdict
sys.path.insert(0, "tools")
from lb_profile import profile, PH, SH

d = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
teams = [a for a in sys.argv[1:] if "/" not in a]
files = sorted({p for a in sys.argv[1:] if "/" in a for p in glob.glob(a)})
for team in teams:
    fs = [f for f in files if team.replace(" ", "") in f.replace("\\", "/").split("/")[-1].replace(" ", "")]
    if not fs:
        continue
    res = []; agg = defaultdict(float); n_ph = Counter()
    loss_types = Counter(); loss_def = []; eco_loss = 0; home_loss = Counter(); home_def = []; late = []; react = []; open_seq = []; fdead = 0
    for f in fs:
        r = json.load(open(f, encoding="utf-8"))
        me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
        win = r["result"].get("winner") == op
        res.append(("승" if win else "패") + f"({f.replace(chr(92), '/').split('/')[-2][:3]},{r['result'].get('reason', '')[:4]})")
        P = profile(f)
        # 지문 수치: profile 텍스트 대신 다시 계산하기 번거로우므로 텍스트에서 구간 줄을 모은다
        for line in P["text"].split("\n"):
            line = line.strip()
            if line[:1].isdigit() and "W생산" in line:
                ph = line.split("W생산")[0].strip()
                vals = line.split()
                def grab(key):
                    i = vals.index(key); return float(vals[i + 1].rstrip("%").replace("/턴", ""))
                for key in ("F", "무리", "최대", "적진", "주둔", "호위"):
                    agg[(ph, key)] += grab(key)
                agg[(ph, "W")] += float(vals[vals.index("W생산/턴") + 1])
                n_ph[ph] += 1
            if line.startswith("초반 점령"):
                open_seq.append(line.replace("초반 점령", "").strip())
        B = {(b["x"], b["y"]): b for b in r["map"]["buildings"]}
        bid = {b["id"]: b for b in r["map"]["buildings"]}
        T = [t for t in r["turns"] if t["turn"] <= 160]
        for k in range(1, len(T)):
            a, b = T[k - 1]["state"], T[k]["state"]
            oa = {x["id"]: x["owner"] for x in a["buildings"]}
            for x in b["buildings"]:
                if oa.get(x["id"]) == op and x["owner"] != op:
                    bb = bid[x["id"]]; c = (bb["x"], bb["y"])
                    ph = "1~30" if T[k]["turn"] <= 30 else "31~80" if T[k]["turn"] <= 80 else "81~160"
                    loss_types[(ph, SH[bb["type"]])] += 1
                    loss_def.append(sum(u[4] for u in a["units"] if u[0] == op and u[1] == "W" and d((u[2], u[3]), c) <= 2))
                    if bb["type"] in ("HALL", "ENG"):
                        eco_loss += 1
                    home = d(c, tuple(r["map"]["bases"][op])) < d(c, tuple(r["map"]["bases"][me]))
                    home_loss[(ph, "자기진영" if home else "우리진영")] += 1
                    if home: home_def.append(loss_def[-1])
            # 그 팀 F 사망 근사: 우리 W 와 같은 칸에서 그 팀 F 수 감소
            Fa = {(u[2], u[3]): u[4] for u in a["units"] if u[0] == op and u[1] == "F"}
            Fb = {(u[2], u[3]): u[4] for u in b["units"] if u[0] == op and u[1] == "F"}
            Wm = {(u[2], u[3]) for u in b["units"] if u[0] == me and u[1] == "W"}
            for c, nF in Fa.items():
                if Fb.get(c, 0) < nF and any(d(c, w) <= 1 for w in Wm) and not any(d(c, x) == 1 and Fb.get(x, 0) > Fa.get(x, 0) for x in Fb):
                    fdead += nF - Fb.get(c, 0)
        sc = [t.get("state", {}).get("occupation") for t in T]
        def pts(st, tm):
            return sum(bid[x["id"]].get("score", 0) or 0 for x in st["buildings"] if x["owner"] == tm)
        if len(T) > 150:
            late.append(pts(T[-1]["state"], op) - pts(T[-21]["state"], op) - (pts(T[-1]["state"], me) - pts(T[-21]["state"], me)))
        for rt in P["text"].split("\n"):
            if "수비 반응" in rt:
                for item in eval(rt.split(")", 1)[1].strip() or "[]"):
                    react.append(item)
    n = len(fs)
    print(f"\n######## {team}  ({n}경기: {' '.join(res)})")
    print("  초반 점령: " + " | ".join(open_seq))
    for ph in ("1~ 20", "21~ 50", "51~100", "101~160"):
        m = n_ph[ph]
        if not m: continue
        g = lambda k: agg[(ph, k)] / m
        print(f"  {ph:>7}턴 W생산 {g('W'):4.1f} F {g('F'):3.1f} 무리 {g('무리'):3.1f} 최대 {g('최대'):3.0f}% 적진 {g('적진'):3.0f}% 주둔 {g('주둔'):3.0f}% 호위 {g('호위'):3.0f}%  ({m}경기)")
    lt = Counter(); 
    for (ph, ty), c in loss_types.items(): lt[ph] += c
    print(f"  약점) 건물 상실 {sum(loss_types.values()) / n:.1f}/경기 [" + ", ".join(f"{ph} {lt[ph] / n:.1f}" for ph in ("1~30", "31~80", "81~160")) + "] "
          f"종류 {dict(Counter({ty: c for (ph, ty), c in loss_types.items()}).most_common(5)) if False else dict(sum((Counter({ty: c}) for (ph, ty), c in loss_types.items()), Counter()).most_common(6))}")
    if loss_def:
        thin = sum(1 for x in loss_def if x <= 1) / len(loss_def)
        print(f"        상실 직전 2칸 수비 W 평균 {sum(loss_def) / len(loss_def):.1f} · 수비 1명 이하 {thin:.0%} · 학관·공학관 상실 {eco_loss / n:.1f}/경기 · F 사망(근사) {fdead / n:.1f}/경기")
    print("        상실 위치: " + ", ".join(f"{k[0]} {k[1]} {v / n:.1f}" for k, v in sorted(home_loss.items())) +
          (f" · 자기 진영 상실 직전 2칸 수비 W 평균 {sum(home_def) / len(home_def):.1f}, 1명 이하 {sum(1 for x in home_def if x <= 1) / len(home_def):.0%}" if home_def else ""))
    if react:
        inc = [a2 - b2 for _, _, b2, a2 in react]
        print(f"        수비 반응 {len(react)}건: 우리 접근 W 평균 {sum(x[1] for x in react) / len(react):.1f} → 3턴 안 그 팀 W {sum(x[2] for x in react) / len(react):.1f}→{sum(x[3] for x in react) / len(react):.1f} (증원 없음 {sum(1 for x in inc if x <= 0) / len(inc):.0%})")
    if late:
        print(f"        막판 20턴 점수 차 변화(그 팀 기준) 평균 {sum(late) / len(late):+.1f}")
