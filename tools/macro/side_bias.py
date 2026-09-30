"""거울전 섭동의 진영 치우침 점검: v20 에 작은 파라미터 변화를 준 쪽이 Y 일 때와 K 일 때 승률이 다른가.
LLM 지휘관이 Y 에서 강하고 K 에서 약했던 것이 지휘 때문인지, 결정론 거울전의 진영 비대칭 때문인지 가른다.
사용 (WSL): python3 tools/macro/side_bias.py --seeds 180000-180199
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, value  # noqa: E402
from branch import parse_range  # noqa: E402

PERT = {
    "max_f5": {"max_f": 5},
    "max_f3": {"max_f": 3},
    "w_margin+2": None,      # 실행 시 v20 기본값 + 2
    "guard_radius+1": None,
}


def one(args):
    seed, side, ver, pa = args
    A, B = Agent(ver, pa), Agent(ver, {})
    g = Game(seed, *((A, B) if side == "Y" else (B, A)))
    g.run()
    return side, value(g.result, side)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ver", default="v20")
    ap.add_argument("--seeds", default="180000-180199")
    a = ap.parse_args()
    from sim import module
    P = module(a.ver).P
    PERT["w_margin+2"] = {"w_margin": P["w_margin"] + 2}
    PERT["guard_radius+1"] = {"guard_radius": P["guard_radius"] + 1}
    seeds = parse_range(a.seeds)
    with Pool(min(30, os.cpu_count() or 4)) as pool:
        for name, pa in PERT.items():
            rows = pool.map(one, [(s, side, a.ver, pa) for s in seeds for side in "YK"])
            y = [v for sd, v in rows if sd == "Y"]
            k = [v for sd, v in rows if sd == "K"]
            n = len(seeds)
            print(f"{name:15s} {json.dumps(pa)}  섭동 쪽이 Y: {sum(y) / n:.3f}   K: {sum(k) / n:.3f}   "
                  f"(무 Y {y.count(0.5)} / K {k.count(0.5)}, {n}시드)")


if __name__ == "__main__":
    main()
