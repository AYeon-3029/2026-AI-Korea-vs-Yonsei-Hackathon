"""우리 쪽 역이 얼마나 오래 비어 있나(사용자: 거점 앞 역을 늦게 잡는다). 건물 종류별 첫 점령 턴·1~60턴 소유 비율.
사용 (WSL): python3 tools/macro/station_own.py --ver v21 --seeds 100000-100009 [--opps mimic|real|a,b]
"""
import argparse, json, os, sys
from collections import defaultdict
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, value  # noqa: E402
import branch  # noqa: E402
from branch import OPPS, REAL_POOL, parse_range  # noqa: E402


def run(a):
    seed, opp, side, ver, params = a
    me, o = Agent(ver, params), Agent(*OPPS[opp])
    g = Game(seed, *((me, o) if side == "Y" else (o, me)))
    op = "K" if side == "Y" else "Y"
    bm, bo = g.state.bases[side], g.state.bases[op]
    info = {}
    for b in g.state.buildings.values():
        dm = abs(b.x - bm[0]) + abs(b.y - bm[1])
        do = abs(b.x - bo[0]) + abs(b.y - bo[1])
        zone = "우리쪽" if dm < do else "중앙" if dm == do else "적쪽"
        info[b.id] = {"type": b.btype, "zone": zone, "dm": dm, "first": None, "own60": 0, "neu60": 0}
    while g.result is None:
        g.step()
        t = g.state.turn
        for b in g.state.buildings.values():
            r = info[b.id]
            if b.owner == side and r["first"] is None:
                r["first"] = t
            if t <= 60:
                r["own60"] += b.owner == side
                r["neu60"] += b.owner == "N"
    return value(g.result, side), list(info.values())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ver", default="v21")
    p.add_argument("--seeds", default="100000-100009")
    p.add_argument("--opps", default="mimic")
    a = p.parse_args()
    opps = branch.MIMIC["mc16"] if a.opps == "mimic" else REAL_POOL if a.opps == "real" else a.opps.split(",")
    jobs = [(s, o, side, a.ver, {}) for s in parse_range(a.seeds) for o in opps for side in "YK"]
    with Pool(20) as pool:
        rows = pool.map(run, jobs, chunksize=2)
    agg = defaultdict(list)
    for v, info in rows:
        for r in info:
            agg[(r["type"], r["zone"])].append((r, v))
    print(f"{len(rows)}경기  (첫 점령 = 우리가 처음 가진 턴, 1~60턴 비율 = 60턴 중 우리 소유 / 중립)")
    for (t, z), L in sorted(agg.items()):
        if t in ("STATION", "HALL", "ENG", "LIBRARY", "DEPOT", "PLAZA"):
            f = sorted(r["first"] if r["first"] is not None else 999 for r, _ in L)
            never = sum(1 for x in f if x == 999) / len(f)
            print(f"  {t:8s} {z:4s} {len(L):5d}개  첫 점령 중앙값 {f[len(f)//2] if f[len(f)//2] < 999 else '없음':>4}  "
                  f"못 가짐 {never:5.1%}  1~60턴 우리 {sum(r['own60'] for r, _ in L)/len(L)/60:5.1%}  중립 {sum(r['neu60'] for r, _ in L)/len(L)/60:5.1%}")
    # 우리 쪽 역을 30턴 안에 잡은 경기 vs 못 잡은 경기 승점
    for lab, cond in (("우리쪽 역 모두 30턴 안 점령", lambda info: all(r["first"] is not None and r["first"] <= 30 for r in info if r["type"] == "STATION" and r["zone"] == "우리쪽")),):
        yes = [v for v, info in rows if cond(info)]
        no = [v for v, info in rows if not cond(info)]
        print(f"  {lab}: {len(yes)}경기 승점 {sum(yes)/max(1,len(yes)):.3f}  /  아님 {len(no)}경기 승점 {sum(no)/max(1,len(no)):.3f}")


if __name__ == "__main__":
    main()
