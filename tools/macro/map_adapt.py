"""맵별 대응의 실제 효용: 여러 설정(프로필)을 같은 맵·상대에서 돌려 맵마다 최선 프로필을 기록하고,
맵 절반(A)에서 "맵 특징 → 프로필" 규칙(특징 하나 · 문턱 하나 · 양쪽 프로필)을 학습해 나머지 절반(B, 처음 보는 맵)에서 기준(v21) 대비 이득을 잰다.
사용 (WSL): python3 tools/macro/map_adapt.py run --seeds 183000-183299   → out/macro/map_adapt.json
            python3 tools/macro/map_adapt.py fit
"""
import json, os, sys, time
from collections import defaultdict
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from sim import CFG, Agent, Game, value  # noqa: E402
from branch import MIMIC, OPPS, PUSH_POOL, REAL_POOL, parse_range  # noqa: E402
from mapgen import generate, to_state  # noqa: E402

VER = "v21"
PROFILES = {
    "기본": {},
    "F5": {"max_f": 5},
    "공성↓": {"siege_bld_bonus": 10.0},
    "공성↑": {"siege_bld_bonus": 25.0},
    "W여유↑": {"w_margin": 27},
    "W여유↓": {"w_margin": 15},
    "경계↓": {"guard_radius": 10},
    "공격대↑": {"eco_strike": 8},
    "광장↑": {"plaza_bonus": 6.0},
}
OPPS_USE = MIMIC["mc16"] + PUSH_POOL + ["semi14", "semi14_press", "srv14_press", "srv14_eco", "v14", "x_press"]
OUT = os.path.join(os.path.dirname(__file__), "../../out/macro/map_adapt.json")


def one(a):
    seed, opp, side = a
    res = {}
    for name, p in PROFILES.items():
        me, o = Agent(VER, p), Agent(*OPPS[opp])
        g = Game(seed, *((me, o) if side == "Y" else (o, me)))
        g.run()
        res[name] = value(g.result, side)
    return seed, res


def feats(seed):
    st = to_state(generate(seed, CFG))
    by, bk = st.bases["Y"], st.bases["K"]
    d = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
    B = list(st.buildings.values())
    mine = [b for b in B if d((b.x, b.y), by) < d((b.x, b.y), bk)]
    mid = [b for b in B if d((b.x, b.y), by) == d((b.x, b.y), bk)]
    f = {"본진거리": d(by, bk), "우리쪽건물수": len(mine), "중앙건물수": len(mid), "우리쪽점수": sum(b.score for b in mine),
         "중앙점수": sum(b.score for b in mid)}
    for t in ("HALL", "ENG", "HOSPITAL", "STATION", "LIBRARY", "DEPOT", "PLAZA", "WATCH"):
        ds = [d((b.x, b.y), by) for b in B if b.btype == t]
        f[f"{t}최소거리"] = min(ds) if ds else 99
    eco = [b for b in mine if b.btype in ("HALL", "ENG")]
    f["우리쪽경제수"] = len(eco)
    f["경제최대거리"] = max((d((b.x, b.y), by) for b in eco), default=0)
    f["경제-적본진최소"] = min((d((b.x, b.y), bk) for b in eco), default=0)
    f["역수"] = sum(1 for b in B if b.btype == "STATION")
    return f


def run(seeds):
    jobs = [(s, o, side) for s in seeds for o in OPPS_USE for side in "YK"]
    t0 = time.time()
    agg = defaultdict(lambda: defaultdict(list))
    with Pool(22) as pool:
        for k, (seed, res) in enumerate(pool.imap_unordered(one, jobs, chunksize=4)):
            for n, v in res.items():
                agg[seed][n].append(v)
            if k % 2000 == 0:
                print(f"  {k}/{len(jobs)} {time.time() - t0:.0f}s", flush=True)
    out = {s: {n: sum(v) / len(v) for n, v in r.items()} for s, r in agg.items()}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"저장 {OUT} ({time.time() - t0:.0f}s)")


def fit():
    data = {int(s): r for s, r in json.load(open(OUT, encoding="utf-8")).items()}
    seeds = sorted(data)
    F = {s: feats(s) for s in seeds}
    names = list(PROFILES)
    A = [s for s in seeds if s % 2 == 0]
    Bs = [s for s in seeds if s % 2 == 1]
    mean = lambda L: sum(L) / len(L)
    print(f"맵 {len(seeds)}개 (학습 A {len(A)} / 검증 B {len(Bs)})")
    print("프로필별 평균 승점(전체):", "  ".join(f"{n} {mean([data[s][n] for s in seeds]):.3f}" for n in names))
    base = lambda S: mean([data[s]["기본"] for s in S])
    ora = lambda S: mean([max(data[s].values()) for s in S])
    print(f"맵별 완벽 선택 상한: A {ora(A) - base(A):+.4f}  B {ora(Bs) - base(Bs):+.4f}  (같은 맵 결과로 고름 = 과대평가)")
    # 규칙: 특징 f 문턱 t 로 나눠 양쪽에 A 에서 가장 좋은 프로필
    best = None
    for f in F[seeds[0]]:
        vals = sorted(set(F[s][f] for s in A))
        for t in vals[1:]:
            lo = [s for s in A if F[s][f] < t]
            hi = [s for s in A if F[s][f] >= t]
            if len(lo) < 20 or len(hi) < 20:
                continue
            pl = max(names, key=lambda n: mean([data[s][n] for s in lo]))
            ph = max(names, key=lambda n: mean([data[s][n] for s in hi]))
            gain = mean([data[s][pl if F[s][f] < t else ph] for s in A]) - base(A)
            if best is None or gain > best[0]:
                best = (gain, f, t, pl, ph)
    gain, f, t, pl, ph = best
    gB = mean([data[s][pl if F[s][f] < t else ph] for s in Bs]) - base(Bs)
    print(f"학습 규칙: {f} < {t} → {pl}, 아니면 {ph}   A 이득 {gain:+.4f} → 처음 보는 맵 B {gB:+.4f}")
    # 단일 프로필 최선(A) → B
    p1 = max(names, key=lambda n: mean([data[s][n] for s in A]))
    print(f"단일 최선 프로필(A): {p1}  A {mean([data[s][p1] for s in A]) - base(A):+.4f} → B {mean([data[s][p1] for s in Bs]) - base(Bs):+.4f}")
    # 상위 규칙 5개의 B 성적
    cands = []
    for f in F[seeds[0]]:
        vals = sorted(set(F[s][f] for s in A))
        for t in vals[1:]:
            lo = [s for s in A if F[s][f] < t]; hi = [s for s in A if F[s][f] >= t]
            if len(lo) < 20 or len(hi) < 20:
                continue
            pl = max(names, key=lambda n: mean([data[s][n] for s in lo]))
            ph = max(names, key=lambda n: mean([data[s][n] for s in hi]))
            gA = mean([data[s][pl if F[s][f] < t else ph] for s in A]) - base(A)
            gb = mean([data[s][pl if F[s][f] < t else ph] for s in Bs]) - base(Bs)
            cands.append((gA, gb, f, t, pl, ph))
    cands.sort(reverse=True)
    print("A 상위 규칙 10개의 B 성적:")
    for gA, gb, f, t, pl, ph in cands[:10]:
        print(f"   {f:12s} < {t:<4} → {pl:5s} / {ph:5s}   A {gA:+.4f}  B {gb:+.4f}")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(parse_range(sys.argv[3] if len(sys.argv) > 3 else "183000-183299"))
    else:
        fit()
