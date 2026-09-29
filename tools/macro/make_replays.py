"""v16 과 평가 상대(대리 봇)의 공식 엔진 대전 리플레이를 만든다(tools/viewer.html 로 본다).

대리 봇은 branch.OPPS 의 (버전, 파라미터)를 BOT_PARAMS 환경변수로 넘겨 별도 프로세스로 돈다.
사용 (WSL): python3 tools/macro/make_replays.py --me v16 --opps p_lodge,p_press --seeds 90000-90001 --out out/replays/v16_eval
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
from branch import OPPS, parse_range  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from arena import play  # noqa: E402

PY = sys.executable


def cmd_of(name):
    if name in OPPS:
        ver, params = OPPS[name]
    else:
        ver, params = name, {}
    c = f"{PY} {ROOT}/Model/history/{ver}/main.py"
    if params:
        c = f"BOT_PARAMS={shlex.quote(json.dumps(params))} {c}"
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--me", default="v16")
    ap.add_argument("--opps", required=True)
    ap.add_argument("--seeds", default="90000-90001")
    ap.add_argument("--out", default="out/replays/v16_eval")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    jobs = []
    for opp in a.opps.split(","):
        for s in parse_range(a.seeds):
            for side in "YK":
                me, op = cmd_of(a.me), cmd_of(opp)
                cy, ck = (me, op) if side == "Y" else (op, me)
                jobs.append((s, cy, ck, side, os.path.join(ROOT, a.out, opp)))
    with ProcessPoolExecutor(a.workers) as ex:
        for (seed, side, result, ms), job in zip(ex.map(play, jobs), jobs):
            opp = os.path.basename(job[4])
            w = result.get("winner")
            r = "승" if w == side else "패" if w in ("Y", "K") else "무"
            print(f"{opp:<14} seed {seed} v16={side} {r} {result.get('reason')}  maxms {ms}", flush=True)


if __name__ == "__main__":
    main()
