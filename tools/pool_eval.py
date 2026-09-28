"""봇 하나를 상대 풀(공식 예제 3종 + 자체 이전 버전) 전체와 대전시켜 승점률을 집계한다.

v5 개발에 쓴 평가 방식이다. 단일 상대 대전은 시드마다 진영이 승패를 결정하는 경우가 섞여
노이즈가 크고, 최종 평가는 처음 보는 여러 팀과 1경기씩 치르므로 여러 스타일에 대한
평균 성적이 더 나은 지표다.

사용 (WSL, 프로젝트 루트에서):
  python3 tools/pool_eval.py --seeds 100-179
  python3 tools/pool_eval.py --params '{"max_f": 7}' --opps v3,v4 --seeds 0-39
  python3 tools/pool_eval.py --bot "python3 Model/history/v4/main.py" --seeds 100-179
  python3 tools/pool_eval.py --opps league --seeds 0-79     # 신호가 남은 상대(자기 대전 리그)

`--params` 는 평가 대상 봇에만 `BOT_PARAMS` 로 전달한다(상대 봇은 기본값 유지).
상대 이름에 `v5atk`·`v5def` 처럼 VARIANTS 에 정의한 변형을 쓰면 그 상대에만 파라미터를 준다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARENA = ROOT / "tools/arena.py"
POOL = ["lv1", "lv2", "main", "v1", "v2", "v3", "v4", "rusher", "turtle", "mid"]
# v1~v4 풀은 0.94 이상으로 포화. 개선이 보이는 상대: 제출본 v5 와 그 스타일 변형, v4, 중간형
LEAGUE = ["v5s", "v5atk", "v5def", "v4", "mid"]
# v6 이후 기준 리그: 제출본 v6 와 그 스타일 변형 + 이전 세대
LEAGUE6 = ["v6", "v6atk", "v6def", "v5s", "v4"]
TALLY = re.compile(r"(\d+)승 (\d+)무 (\d+)패")

SPARRING = ("rusher", "turtle", "mid", "presser", "raider", "econ", "reactive")
# 이름 → (기반 버전, 파라미터). 스타일 실험(HANDOFF §7)의 돌격형·수비형
# PLAN-frontier.md 의 이름 → 이 도구의 이름
# 탐색·확률·학습형 스파링 봇(제출물 아님). mcts_uct 는 턴당 최대 1.5초라 ARENA_TIMEOUT_MS 를 늘려 평가한다.
# rl:<이름> 은 out/rl/<이름>/latest.pt 가중치의 강화학습 봇.
SEARCH = {"mcts_uct": "mcts/main.py uct", "mcts_ts": "mcts/main.py thompson", "mixbot": "mcts/main.py mix"}
ALIASES = {"v5ref": "v5", "s_rush": "v5atk", "s_turtle": "v5def"}
VARIANTS = {
    "v5atk": ("v5s", {"guard_radius": 0}),
    "v5def": ("v5s", {"siege": False, "guard_radius": 14}),
    "v6atk": ("v6", {"guard_radius": 0}),
    "v6def": ("v6", {"siege": False, "guard_radius": 20}),
}


def opp_cmd(name: str) -> str:
    name = ALIASES.get(name, name)
    if name in ("lv1", "lv2", "main"):
        return name                       # arena.py 의 공식 예제 봇 별칭
    if name in SEARCH:
        return f"python3 {ROOT}/Model/sparring/{SEARCH[name]}"
    if name.startswith("rl:"):
        return f"RL_CKPT={ROOT}/out/rl/{name[3:]}/latest.pt python3 {ROOT}/Model/sparring/rlbot/main.py"
    if name in SPARRING:
        return f"python3 {ROOT}/Model/sparring/{name}.py"
    if name in VARIANTS:
        base, params = VARIANTS[name]
        return wrap(opp_cmd(base), json.dumps(params))
    if (ROOT / "Model/league" / name).is_dir():
        return f"python3 {ROOT}/Model/league/{name}/main.py"
    return f"python3 {ROOT}/Model/history/{name}/main.py"


def wrap(bot: str, params: str | None, stats: str = "") -> str:
    """BOT_PARAMS·BOT_STATS 를 특정 봇에만 적용하기 위한 임시 실행 스크립트."""
    if not params and not stats:
        return bot
    env = ""
    if params:
        env += f"BOT_PARAMS='{params}'\nexport BOT_PARAMS\n"
    if stats:
        Path(stats).mkdir(parents=True, exist_ok=True)
        env += f"BOT_STATS='{stats}'\nexport BOT_STATS\n"
    fd, path = tempfile.mkstemp(suffix=".sh", prefix="pool_eval_")
    with os.fdopen(fd, "w", newline="\n") as f:
        f.write(f"#!/bin/sh\n{env}exec {bot}\n")
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


def evaluate(bot: str, opps: list[str], seeds: str, workers: int,
             params: str = "", stats: str = "") -> dict[str, tuple[int, int, int]]:
    """상대별 (승, 무, 패). stats 가 있으면 상대별 하위 폴더에 BOT_STATS 기록을 남긴다."""
    return {opp: run(wrap(bot, params, f"{stats}/{opp}" if stats else ""), opp, seeds, workers)
            for opp in opps}


def rate(wdl: tuple[int, int, int]) -> float:
    w, d, l = wdl
    return (w + 0.5 * d) / (w + d + l)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bot", default="python3 Model/main.py", help="평가할 봇 실행 명령")
    p.add_argument("--params", default="", help="평가 대상 봇에만 줄 BOT_PARAMS JSON")
    p.add_argument("--opps", default=",".join(POOL), help="상대 목록(쉼표) 또는 league")
    p.add_argument("--seeds", default="0-39")
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--stats", default="", help="BOT_STATS 기록 폴더(비우고 시작). 끝에 상대별 요약 출력")
    args = p.parse_args()

    opps = {"league": LEAGUE, "league6": LEAGUE6}.get(args.opps) or args.opps.split(",")
    if args.stats:
        shutil.rmtree(args.stats, ignore_errors=True)
    res = evaluate(args.bot, opps, args.seeds, args.workers, args.params, args.stats)
    tw, td, tl = (sum(r[k] for r in res.values()) for k in range(3))
    cols = [f"{opp}={rate(r):.3f}" for opp, r in res.items()]
    n = tw + td + tl
    print(f"전체 {(tw + 0.5 * td) / n:.3f}  ({tw}승 {td}무 {tl}패 / {n}경기)  |  " + "  ".join(cols))
    if args.stats:
        from stats_agg import summarize
        for opp in opps:
            print("  " + summarize(Path(args.stats) / opp))


if __name__ == "__main__":
    main()
