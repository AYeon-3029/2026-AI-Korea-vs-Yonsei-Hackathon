"""한 버전을 여러 상대(흉내 봇 mc16·m16, 현실, 공세, 다른 버전)와 붙여 상대별 승·무·패와 진 경기 시드를 보여 준다.
사용 (WSL): python3 tools/macro/v_eval.py --ver v21 --seeds 181000-181049 [--vers v20,cv-3,...]
"""
import argparse, json, os, sys, time
from collections import defaultdict
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, value  # noqa: E402
from branch import MIMIC, OPPS, PUSH_POOL, REAL_POOL, parse_range  # noqa: E402


def one(a):
    seed, opp, side, ver = a
    me = Agent(ver, {})
    o = Agent(*OPPS[opp]) if opp in OPPS else Agent(opp, {})
    g = Game(seed, *((me, o) if side == "Y" else (o, me)))
    g.run()
    return opp, seed, side, value(g.result, side), g.result["reason"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ver", default="v21")
    p.add_argument("--seeds", default="181000-181049")
    p.add_argument("--vers", default="v20,cv-3,cv-11,v19,v16,v14")
    a = p.parse_args()
    groups = {"흉내 mc16": MIMIC["mc16"], "흉내 m16": MIMIC["m16"], "현실": REAL_POOL, "공세": PUSH_POOL,
              "우리 버전": [v for v in a.vers.split(",") if os.path.isdir(os.path.join(os.path.dirname(__file__), "../../Model/history", v))]}
    opps = [o for g in groups.values() for o in g]
    t0 = time.time()
    with Pool(22) as pool:
        rows = pool.map(one, [(s, o, side, a.ver) for s in parse_range(a.seeds) for o in opps for side in "YK"], chunksize=4)
    by = defaultdict(list)
    for r in rows:
        by[r[0]].append(r)
    out = {}
    for gname, g in groups.items():
        allv = [r[3] for o in g for r in by[o]]
        print(f"== {gname}  {len(allv)}경기  {a.ver} 승점 {sum(allv) / len(allv):.3f}")
        for o in sorted(g, key=lambda o: sum(r[3] for r in by[o]) / len(by[o])):
            v = [r[3] for r in by[o]]
            w, d, l = v.count(1.0), v.count(0.5), v.count(0.0)
            loss = [f"{r[1]}{r[2]}" for r in by[o] if r[3] == 0.0][:4]
            print(f"   {o:28s} 승점 {sum(v) / len(v):.3f}  {w}승 {d}무 {l}패  진 경기 {' '.join(loss)}")
            out[o] = {"v": sum(v) / len(v), "w": w, "d": d, "l": l, "loss": [(r[1], r[2], r[4]) for r in by[o] if r[3] == 0.0]}
    json.dump(out, open(os.path.join(os.path.dirname(__file__), f"../../out/macro/v_eval_{a.ver}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
