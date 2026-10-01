"""시드(맵)별 전략 선택의 효용: 두 버전(기본 v22 수비형 · v27 공격형)을 같은 맵·상대에서 돌려 맵마다 어느 쪽이 나은지 기록하고,
① 그 우열이 상대 묶음 둘에서 일관되는지(맵 효과인가 운인가), ② 맵 특징 문턱 규칙으로 처음 보는 맵에서 고를 수 있는지 잰다.
사용 (WSL): python3 tools/macro/seed_choice.py run --seeds 300000-300299 [--vers v22,v27]   → out/macro/seed_choice.json
            python3 tools/macro/seed_choice.py fit
"""
import json, os, sys, time
from collections import defaultdict
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, value  # noqa: E402
from branch import MIMIC, OPPS, PUSH_POOL, parse_range  # noqa: E402
from map_adapt import feats  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "../../out/macro/seed_choice.json")
OPPS_USE = MIMIC["mc22"] + PUSH_POOL + ["semi14", "semi14_press", "srv14_press", "v14", "tp_yagu", "tp_aiku", "tg_f", "cv-14"]
VERS = ["v22", "v27"]


def one(a):
    seed, opp, side, vers = a
    res = {}
    for v in vers:
        me = Agent(v)
        o = Agent(*OPPS[opp]) if opp in OPPS else Agent(opp)
        g = Game(seed, *((me, o) if side == "Y" else (o, me)))
        g.run()
        res[v] = value(g.result, side)
    return seed, opp, res


def run(seeds, vers):
    jobs = [(s, o, side, vers) for s in seeds for o in OPPS_USE for side in "YK"]
    t0 = time.time()
    agg = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    with Pool(30) as pool:
        for k, (seed, opp, res) in enumerate(pool.imap_unordered(one, jobs, chunksize=8)):
            for v, x in res.items():
                agg[seed][opp][v].append(x)
            if k % 5000 == 0:
                print(f"  {k}/{len(jobs)} {time.time() - t0:.0f}s", flush=True)
    out = {"vers": vers, "data": {s: {o: {v: sum(x) / len(x) for v, x in r.items()} for o, r in om.items()} for s, om in agg.items()}}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"저장 {OUT} ({time.time() - t0:.0f}s)")


def fit():
    J = json.load(open(OUT, encoding="utf-8"))
    a, b = J["vers"]
    D = {int(s): om for s, om in J["data"].items()}
    seeds = sorted(D)
    mean = lambda L: sum(L) / len(L) if L else 0.0
    opps = sorted(next(iter(D.values())))
    g1 = opps[0::2]; g2 = opps[1::2]
    d = lambda s, G: mean([D[s][o][b] - D[s][o][a] for o in G if o in D[s]])
    dall = {s: d(s, opps) for s in seeds}
    print(f"맵 {len(seeds)}개, 상대 {len(opps)}개 · 평균 {a} {mean([mean([D[s][o][a] for o in opps]) for s in seeds]):.3f} "
          f"{b} {mean([mean([D[s][o][b] for o in opps]) for s in seeds]):.3f}  차 {mean(list(dall.values())):+.4f}")
    # ① 맵 효과의 일관성: 상대 묶음 둘에서 맵별 차이의 상관
    x = [d(s, g1) for s in seeds]; y = [d(s, g2) for s in seeds]
    mx, my = mean(x), mean(y)
    cov = mean([(p - mx) * (q - my) for p, q in zip(x, y)])
    sx = mean([(p - mx) ** 2 for p in x]) ** 0.5; sy = mean([(q - my) ** 2 for q in y]) ** 0.5
    print(f"① 맵별 우열의 일관성(상대 묶음 둘의 상관): r = {cov / (sx * sy):+.3f}  (0 이면 맵 효과 없음 = 운)")
    pos = sum(1 for s in seeds if dall[s] > 0); neg = sum(1 for s in seeds if dall[s] < 0)
    print(f"   {b} 가 나은 맵 {pos} · {a} 가 나은 맵 {neg} · 같음 {len(seeds) - pos - neg}")
    # 묶음 1 로 고르고 묶음 2 에서 이득(같은 맵, 다른 상대) — 맵 효과만으로 얻는 이득의 정직한 추정
    pick = [b if d(s, g1) > 0 else a for s in seeds]
    base2 = mean([mean([D[s][o][a] for o in g2]) for s in seeds])
    got2 = mean([mean([D[s][o][p] for o in g2]) for s, p in zip(seeds, pick)])
    best2 = max(base2, mean([mean([D[s][o][b] for o in g2]) for s in seeds]))
    print(f"   같은 맵을 상대 묶음 1 결과로 골랐을 때 묶음 2 성적: {got2:.4f} (항상 {a} {base2:.4f} · 항상 더 나은 쪽 {best2:.4f})")
    # ② 맵 특징 → 선택 규칙: 짝수 맵 학습, 홀수 맵 검증
    F = {s: feats(s) for s in seeds}
    A = [s for s in seeds if s % 2 == 0]; Bs = [s for s in seeds if s % 2 == 1]
    val = lambda s, v: mean([D[s][o][v] for o in opps])
    perf = lambda S, rule: mean([val(s, rule(s)) for s in S])
    alwaysA = lambda S: mean([val(s, a) for s in S]); alwaysB = lambda S: mean([val(s, b) for s in S])
    print(f"② 처음 보는 맵 B: 항상 {a} {alwaysA(Bs):.4f} · 항상 {b} {alwaysB(Bs):.4f} · 맵별 완벽 선택(상한) {mean([max(val(s, a), val(s, b)) for s in Bs]):.4f}")
    cands = []
    for f in F[seeds[0]]:
        vals = sorted(set(F[s][f] for s in A))
        for t in vals[1:]:
            lo = [s for s in A if F[s][f] < t]; hi = [s for s in A if F[s][f] >= t]
            if len(lo) < 20 or len(hi) < 20:
                continue
            pl = max((a, b), key=lambda v: mean([val(s, v) for s in lo]))
            ph = max((a, b), key=lambda v: mean([val(s, v) for s in hi]))
            if pl == ph:
                continue
            rule = lambda s, f=f, t=t, pl=pl, ph=ph: pl if F[s][f] < t else ph
            cands.append((perf(A, rule), perf(Bs, rule), f, t, pl, ph))
    cands.sort(reverse=True)
    best_single = max(alwaysA(A), alwaysB(A))
    print(f"   학습 맵 A 의 단일 최선 {best_single:.4f}. A 상위 규칙 8개의 처음 보는 맵 B 성적:")
    for pA, pB, f, t, pl, ph in cands[:8]:
        print(f"     {f:12s} < {t:<4} → {pl} / {ph}   A {pA:.4f}  B {pB:.4f}")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        args = sys.argv[2:]
        seeds = parse_range(args[args.index("--seeds") + 1]) if "--seeds" in args else parse_range("300000-300299")
        vers = args[args.index("--vers") + 1].split(",") if "--vers" in args else VERS
        run(seeds, vers)
    else:
        fit()
