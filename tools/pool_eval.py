"""봇 하나를 상대 풀(공식 예제 3종 + 자체 이전 버전) 전체와 대전시켜 승점률을 집계한다.

v5 개발에 쓴 평가 방식이다. 단일 상대 대전은 시드마다 진영이 승패를 결정하는 경우가 섞여
노이즈가 크고, 최종 평가는 처음 보는 여러 팀과 1경기씩 치르므로 여러 스타일에 대한
평균 성적이 더 나은 지표다.

사용 (WSL, 프로젝트 루트에서):
  python3 tools/pool_eval.py --seeds 100-179
  python3 tools/pool_eval.py --params '{"max_f": 7}' --opps v3,v4 --seeds 0-39
  python3 tools/pool_eval.py --bot "python3 Model/history/v4/main.py" --seeds 100-179

`--params` 는 평가 대상 봇에만 `BOT_PARAMS` 로 전달한다(상대 봇은 기본값 유지).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARENA = ROOT / "tools/arena.py"
POOL = ["lv1", "lv2", "main", "v1", "v2", "v3", "v4", "rusher", "turtle", "mid"]
TALLY = re.compile(r"(\d+)승 (\d+)무 (\d+)패")


SPARRING = ("rusher", "turtle", "mid")


def opp_cmd(name: str) -> str:
    if name in ("lv1", "lv2", "main"):
        return name                       # arena.py 의 공식 예제 봇 별칭
    if name in SPARRING:
        return f"python3 {ROOT}/Model/sparring/{name}.py"
    return f"python3 {ROOT}/Model/history/{name}/main.py"


def wrap(bot: str, params: str | None) -> str:
    """BOT_PARAMS 를 평가 대상 봇에만 적용하기 위한 임시 실행 스크립트."""
    if not params:
        return bot
    fd, path = tempfile.mkstemp(suffix=".sh", prefix="pool_eval_")
    with os.fdopen(fd, "w", newline="\n") as f:
        f.write(f"#!/bin/sh\nBOT_PARAMS='{params}'\nexport BOT_PARAMS\nexec {bot}\n")
    return f"sh {path}"


def run(bot: str, opp: str, seeds: str, workers: int) -> tuple[int, int, int]:
    out = subprocess.run([sys.executable, str(ARENA), "--a", bot, "--b", opp_cmd(opp),
                          "--seeds", seeds, "--workers", str(workers)],
                         cwd=ROOT, capture_output=True, text=True).stdout
    m = TALLY.search(out)
    if not m:
        print(out[-2000:], file=sys.stderr)
        raise SystemExit(f"{opp}: 결과를 읽지 못했다")
    if "forfeit" in out:
        print(f"  경고: {opp} 전에서 몰수 발생", file=sys.stderr)
    return tuple(int(v) for v in m.groups())


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bot", default="python3 Model/main.py", help="평가할 봇 실행 명령")
    p.add_argument("--params", default="", help="평가 대상 봇에만 줄 BOT_PARAMS JSON")
    p.add_argument("--opps", default=",".join(POOL), help="상대 목록(쉼표)")
    p.add_argument("--seeds", default="0-39")
    p.add_argument("--workers", type=int, default=6)
    args = p.parse_args()

    bot = wrap(args.bot, args.params)
    tw = td = tl = 0
    cols = []
    for opp in args.opps.split(","):
        w, d, l = run(bot, opp, args.seeds, args.workers)
        tw, td, tl = tw + w, td + d, tl + l
        cols.append(f"{opp}={(w + 0.5 * d) / (w + d + l):.3f}")
    n = tw + td + tl
    print(f"전체 {(tw + 0.5 * td) / n:.3f}  ({tw}승 {td}무 {tl}패 / {n}경기)  |  " + "  ".join(cols))


if __name__ == "__main__":
    main()
