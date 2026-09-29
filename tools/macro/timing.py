"""공식 러너(별도 프로세스, 제한 시간 판정 그대로)로 봇의 턴별 응답 시간을 잰다. 첫 턴(프로세스 기동 포함, 한도 3000ms)과 이후 턴(한도 300ms)을 나눠 본다.

사용 (WSL): python3 tools/macro/timing.py --me v18 --opps v17,p_lodge,x_press --seeds 99000-99004 --workers 2
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from branch import parse_range  # noqa: E402
from make_replays import cmd_of  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(ROOT, "BaseLines/yk-development-tools"))
from engine.config import load_config  # noqa: E402
from runner import SubprocessBot, run_match  # noqa: E402
import runner.bots as rb  # noqa: E402

_orig = rb.SubprocessBot.collect_turn


def collect_turn(self):
    first = not hasattr(self, "turn_ms")
    if first:
        self.turn_ms = []
    lines, status = _orig(self)
    self.turn_ms.append(((time.monotonic() - self._start) * 1000.0, status))
    return lines, status


rb.SubprocessBot.collect_turn = collect_turn


def play(job):
    seed, cy, ck, side = job
    cfg = load_config()
    cfg["first_turn_timeout_ms"] = 3000
    bots = [SubprocessBot(cy, name="Y"), SubprocessBot(ck, name="K")]
    try:
        _, result = run_match(seed, cfg, *bots, turn_timeout_ms=300)
    finally:
        for b in bots:
            b.close()
    me = bots[0] if side == "Y" else bots[1]
    return me.turn_ms, result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--me", default="v18")
    ap.add_argument("--opps", default="v17,p_lodge,x_press")
    ap.add_argument("--seeds", default="99000-99004")
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    jobs = []
    for opp in a.opps.split(","):
        for s in parse_range(a.seeds):
            for side in "YK":
                me, op = cmd_of(a.me), cmd_of(opp)
                jobs.append((s, *((me, op) if side == "Y" else (op, me)), side))
    first, rest, bad, results = [], [], [], []
    with ProcessPoolExecutor(a.workers) as ex:
        for tm, result in ex.map(play, jobs):
            first.append(tm[0][0])
            rest.extend(ms for ms, _ in tm[1:])
            bad.extend(st for _, st in tm if st != "ok")
            results.append(result.get("reason"))
    rest = np.array(rest)
    print(f"{a.me}: {len(jobs)}경기, 턴 {len(rest) + len(first)}개, 시간 초과·오류 {len(bad)} {set(bad) if bad else ''}")
    print(f"  첫 턴(한도 3000ms): 최대 {max(first):.0f}ms, 중앙 {np.median(first):.0f}ms")
    print(f"  이후 턴(한도 300ms): 중앙 {np.median(rest):.1f}ms, p99 {np.percentile(rest, 99):.1f}ms, 최대 {rest.max():.1f}ms, 100ms 초과 {int((rest > 100).sum())}턴")
    print(f"  종료 사유: {dict((r, results.count(r)) for r in set(results))}")


if __name__ == "__main__":
    main()
