"""새 봇(v24 계열) 빠른 평가: 여러 상대 묶음과 양 진영으로 붙여 묶음별 승점률(승 1·무 0.5)을 보인다.
사용 (WSL): python3 tools/macro/e24.py --ver v24 [--p '{"main_c": 6}'] --seeds 50000-50019 [--groups strong,real,push,mimic]
"""
import argparse, json, os, sys, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, value  # noqa: E402
from branch import MIMIC, OPPS, PUSH_POOL, REAL_POOL, parse_range  # noqa: E402

GROUPS = {
    "strong": ["v22", "cv-3", "v20"],
    "old": ["v5", "v6", "v7"],
    "early": ["v1", "v2", "v3", "v4"],
    "real": REAL_POOL,
    "push": PUSH_POOL,
    "mimic": (MIMIC.get("mc16", []) + MIMIC.get("m16", [])),
    "mc22": MIMIC.get("mc22", []),
    "weak": ["v9", "v10", "v14"],
}


def one(a):
    seed, opp, side, ver, p = a
    me = Agent(ver, p)
    o = Agent(*OPPS[opp]) if opp in OPPS else Agent(opp, {})
    g = Game(seed, *((me, o) if side == "Y" else (o, me)))
    g.run()
    return opp, value(g.result, side), g.result["reason"], me.errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ver", default="v24")
    ap.add_argument("--p", default="{}")
    ap.add_argument("--seeds", default="50000-50019")
    ap.add_argument("--groups", default="strong,real,push,mimic")
    ap.add_argument("--workers", type=int, default=28)
    a = ap.parse_args()
    p = json.loads(a.p)
    gs = a.groups.split(",")
    opps = sorted({o for g in gs for o in GROUPS[g]})
    jobs = [(s, o, side, a.ver, p) for s in parse_range(a.seeds) for o in opps for side in "YK"]
    t0 = time.time()
    res, err = {}, 0
    with Pool(a.workers) as pool:
        for opp, v, why, e in pool.imap_unordered(one, jobs, chunksize=2):
            res.setdefault(opp, []).append(v)
            err += e
    out = []
    for g in gs:
        vs = [v for o in GROUPS[g] for v in res.get(o, [])]
        out.append(f"{g} {sum(vs) / max(1, len(vs)):.3f}")
    print(f"{a.ver} {a.p}  " + "  ".join(out) + f"  예외 {err}  {time.time() - t0:.0f}s")
    if "-v" in sys.argv or len(gs) == 1:
        for o in opps:
            print(f"   {o:<16} {sum(res[o]) / len(res[o]):.3f}")


if __name__ == "__main__":
    main()
