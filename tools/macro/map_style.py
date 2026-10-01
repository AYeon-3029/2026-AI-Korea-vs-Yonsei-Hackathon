"""건물 몰림(군집) 기준 맵 분류 → 맵별 전략(스타일) 선택의 효용.
v33 위 스타일 변형 6개를 같은 맵·상대(V29 상위 흉내 mc29 10팀)·양 진영에서 돌려 맵마다 성적을 기록하고,
① 맵마다 최선 스타일이 운이 아닌 맵 효과인지(상대 묶음 둘의 일관성), ② 건물 몰림 특징 규칙으로 처음 보는 맵에서 고를 수 있는지 잰다.
사용 (WSL): python3 tools/macro/map_style.py run --seeds 230000-230399   → out/macro/map_style.json
            python3 tools/macro/map_style.py fit
"""
import json, os, sys, time
from collections import defaultdict
from itertools import combinations
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, value, CFG  # noqa: E402
from branch import MIMIC, OPPS, parse_range  # noqa: E402
from mapgen import generate, to_state  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "../../out/macro/map_style.json")
VER = "v33"
STYLES = {
    "기본": {},
    "수비": {"w_margin": 29, "guard_radius": 19, "siege_bld_bonus": 10.2, "eco_block_extra": 3},
    "공세": {"w_margin": 15, "guard_radius": 11, "siege_bld_bonus": 22.0, "risk_local_w": 0.32},
    "확장": {"max_f": 6},
    "중앙": {"plaza_bonus": 4.0, "center_expect": 2.5},
    "경제": {"hall_bonus": 20.0, "eng_bonus": 18.0},
}
OPPS_USE = list(MIMIC["mc29"])
d = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])


def feats(seed):
    """건물 몰림 특징(Y 기준; 맵이 180° 대칭이라 K 도 같다)."""
    st = to_state(generate(seed, CFG))
    by, bk = tuple(st.bases["Y"]), tuple(st.bases["K"])
    B = [(b.x, b.y, b.btype) for b in st.buildings.values()]
    P = [(x, y) for x, y, _ in B]
    f = {}
    f["중앙3칸"] = sum(1 for p in P if d(p, (7, 7)) <= 3)
    f["본진5칸"] = sum(1 for p in P if d(p, by) <= 5)
    f["본진7칸"] = sum(1 for p in P if d(p, by) <= 7)
    f["경합건물"] = sum(1 for p in P if abs(d(p, by) - d(p, bk)) <= 2)
    f["최근접평균"] = round(sum(min(d(p, q) for q in P if q != p) for p in P) / len(P), 2)
    # 2칸 이내로 이은 군집
    seen, comps = set(), []
    for p in P:
        if p in seen: continue
        st_, comp = [p], []
        seen.add(p)
        while st_:
            c = st_.pop(); comp.append(c)
            for q in P:
                if q not in seen and d(c, q) <= 2:
                    seen.add(q); st_.append(q)
        comps.append(comp)
    f["군집수"] = len(comps)
    f["최대군집"] = max(len(c) for c in comps)
    eco = [(x, y) for x, y, t in B if t in ("HALL", "ENG") and d((x, y), by) < d((x, y), bk)]
    f["경제본진거리"] = round(sum(d(p, by) for p in eco) / max(1, len(eco)), 1)
    f["경제쌍거리"] = min((d(a, b) for a, b in combinations(eco, 2)), default=0)
    f["본진거리"] = d(by, bk)
    return f


def one(a):
    seed, opp, side = a
    res = {}
    for nm, prm in STYLES.items():
        me = Agent(VER, prm); o = Agent(*OPPS[opp])
        g = Game(seed, *((me, o) if side == "Y" else (o, me)))
        g.run()
        res[nm] = value(g.result, side)
    return seed, opp, res


def run(seeds):
    jobs = [(s, o, side) for s in seeds for o in OPPS_USE for side in "YK"]
    t0 = time.time()
    agg = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    with Pool(30) as pool:
        for k, (seed, opp, res) in enumerate(pool.imap_unordered(one, jobs, chunksize=4)):
            for nm, x in res.items():
                agg[seed][opp][nm].append(x)
            if k % 2000 == 0:
                print(f"  {k}/{len(jobs)} {time.time() - t0:.0f}s", flush=True)
    out = {s: {o: {nm: sum(x) / len(x) for nm, x in r.items()} for o, r in om.items()} for s, om in agg.items()}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"저장 {OUT} ({time.time() - t0:.0f}s)")


def fit():
    D = {int(s): om for s, om in json.load(open(OUT, encoding="utf-8")).items()}
    seeds = sorted(D); names = list(STYLES)
    mean = lambda L: sum(L) / len(L) if L else 0.0
    opps = sorted(next(iter(D.values())))
    g1, g2 = opps[0::2], opps[1::2]
    val = lambda s, nm, G=opps: mean([D[s][o][nm] for o in G if o in D[s]])
    print(f"맵 {len(seeds)} · 상대 {len(opps)} · 스타일 평균: " + " · ".join(f"{nm} {mean([val(s, nm) for s in seeds]):.3f}" for nm in names))
    base = "기본"
    # ① 맵 효과 일관성: 각 스타일의 (스타일 − 기본) 맵별 차이가 상대 묶음 둘에서 상관되는가
    print("① 맵 효과 일관성 r(상대 묶음 1 vs 2, 맵별 '스타일−기본'):")
    for nm in names[1:]:
        x = [val(s, nm, g1) - val(s, base, g1) for s in seeds]; y = [val(s, nm, g2) - val(s, base, g2) for s in seeds]
        mx, my = mean(x), mean(y)
        cov = mean([(p - mx) * (q - my) for p, q in zip(x, y)])
        sx = mean([(p - mx) ** 2 for p in x]) ** 0.5; sy = mean([(q - my) ** 2 for q in y]) ** 0.5
        print(f"   {nm}: r = {cov / (sx * sy + 1e-12):+.3f}")
    # 정직한 맵 선택 이득: 묶음 1 로 맵마다 고르고 묶음 2 에서 성적(반대 방향도)
    for ga, gb, lab in ((g1, g2, "1→2"), (g2, g1, "2→1")):
        pick = {s: max(names, key=lambda nm: val(s, nm, ga)) for s in seeds}
        got = mean([val(s, pick[s], gb) for s in seeds]); bb = mean([val(s, base, gb) for s in seeds])
        best1 = max(names, key=lambda nm: mean([val(s, nm, gb) for s in seeds]))
        print(f"   맵별 선택({lab}): {got:.4f} vs 항상 기본 {bb:.4f} (차 {got - bb:+.4f}) · 항상 최선({best1}) {mean([val(s, best1, gb) for s in seeds]):.4f}")
    print(f"   맵별 완벽 선택 상한(같은 결과로 고름, 운 포함): {mean([max(val(s, nm) for nm in names) for s in seeds]):.4f}")
    # ② 건물 몰림 특징 규칙: 짝수 맵 학습 → 홀수 맵 검증. 규칙 = 특징 문턱 하나로 두 스타일 중 고르기
    F = {s: feats(s) for s in seeds}
    A = [s for s in seeds if s % 2 == 0]; Bs = [s for s in seeds if s % 2 == 1]
    perf = lambda S, rule: mean([val(s, rule(s)) for s in S])
    print(f"② 특징 규칙(짝수 맵 학습 → 홀수 맵 검증): 홀수 맵 항상 기본 {perf(Bs, lambda s: base):.4f}")
    # 특징과 '스타일 − 기본' 의 상관(전체 맵) — 어떤 맵에서 어떤 스타일이 나은가
    print("   특징별 상관(전체 맵, 스타일−기본):")
    for fn in F[seeds[0]]:
        row = []
        xs = [F[s][fn] for s in seeds]; mx = mean(xs); sx = mean([(x - mx) ** 2 for x in xs]) ** 0.5
        for nm in names[1:]:
            ys = [val(s, nm) - val(s, base) for s in seeds]; my = mean(ys); sy = mean([(y - my) ** 2 for y in ys]) ** 0.5
            r = mean([(x - mx) * (y - my) for x, y in zip(xs, ys)]) / (sx * sy + 1e-12)
            row.append(f"{nm} {r:+.2f}")
        print(f"     {fn:8s} " + " ".join(row))
    cands = []
    for fn in F[seeds[0]]:
        vals = sorted(set(F[s][fn] for s in A))
        for t in vals[1:]:
            lo = [s for s in A if F[s][fn] < t]; hi = [s for s in A if F[s][fn] >= t]
            if len(lo) < 30 or len(hi) < 30: continue
            pl = max(names, key=lambda nm: mean([val(s, nm) for s in lo]))
            ph = max(names, key=lambda nm: mean([val(s, nm) for s in hi]))
            if pl == ph: continue
            rule = lambda s, fn=fn, t=t, pl=pl, ph=ph: pl if F[s][fn] < t else ph
            cands.append((perf(A, rule), perf(Bs, rule), fn, t, pl, ph))
    cands.sort(reverse=True)
    bestA = max(names, key=lambda nm: mean([val(s, nm) for s in A]))
    print(f"   학습 맵 단일 최선 {bestA} {mean([val(s, bestA) for s in A]):.4f} (홀수 맵 {mean([val(s, bestA) for s in Bs]):.4f}). 학습 맵 상위 규칙 10개의 홀수 맵 성적:")
    for pA, pB, fn, t, pl, ph in cands[:10]:
        print(f"     {fn:8s} < {t:<5} → {pl} / 이상 → {ph}   학습 {pA:.4f}  검증 {pB:.4f}")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        a = sys.argv[2:]
        run(parse_range(a[a.index("--seeds") + 1]) if "--seeds" in a else parse_range("230000-230399"))
    else:
        fit()
