"""두 봇을 여러 시드에서 진영을 바꿔가며 대전시키고 결과를 집계한다.

사용 예 (WSL, 프로젝트 루트에서):
  python3 tools/arena.py --a "python3 Model/main.py" --b lv2 --seeds 0-9
  --b / --a 에 lv1, lv2, main 을 주면 공식 예제 봇을 뜻한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "BaseLines/yk-development-tools"
sys.path.insert(0, str(DEV))

from engine.config import load_config  # noqa: E402
from runner import SubprocessBot, run_match  # noqa: E402

STARTER = DEV / "bots/dist/starter/python"
ALIASES = {
    "lv1": f"python3 {STARTER}/example_lv1.py",
    "lv2": f"python3 {STARTER}/example_lv2.py",
    "main": f"python3 {STARTER}/main.py",
}


def resolve(cmd: str) -> str:
    return ALIASES.get(cmd, cmd)


def parse_seeds(text: str) -> list[int]:
    seeds = []
    for part in text.split(","):
        if "-" in part:
            lo, hi = part.split("-")
            seeds.extend(range(int(lo), int(hi) + 1))
        else:
            seeds.append(int(part))
    return seeds


def play(job):
    seed, cmd_y, cmd_k, a_side, replay_dir = job
    cfg = load_config()
    cfg["first_turn_timeout_ms"] = 3000
    bots = [SubprocessBot(cmd_y, name=cmd_y), SubprocessBot(cmd_k, name=cmd_k)]
    try:
        replay, result = run_match(seed, cfg, *bots, turn_timeout_ms=300)
    finally:
        for b in bots:
            b.close()
    max_ms = {t: round(b.max_turn_ms, 1) for t, b in zip("YK", bots)}
    if replay_dir:
        path = Path(replay_dir) / f"seed{seed}-A{a_side}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(replay, ensure_ascii=False), encoding="utf-8")
    return seed, a_side, result, max_ms


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--a", required=True, help="평가할 봇 실행 명령")
    p.add_argument("--b", required=True, help="상대 봇 실행 명령 (lv1/lv2/main 별칭 가능)")
    p.add_argument("--seeds", default="0-9")
    p.add_argument("--sides", default="YK", help="A가 맡을 진영: Y, K, YK")
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--replays", default="", help="리플레이 저장 폴더(선택)")
    args = p.parse_args()

    a, b = resolve(args.a), resolve(args.b)
    jobs = []
    for seed in parse_seeds(args.seeds):
        for side in args.sides:
            cy, ck = (a, b) if side == "Y" else (b, a)
            jobs.append((seed, cy, ck, side, args.replays))

    win = draw = loss = 0
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for seed, side, r, max_ms in ex.map(play, jobs):
            opp = "K" if side == "Y" else "Y"
            if r["winner"] == side:
                outcome, win = "WIN ", win + 1
            elif r["winner"] == "DRAW":
                outcome, draw = "DRAW", draw + 1
            else:
                outcome, loss = "LOSS", loss + 1
            extra = f" forfeit={r['forfeit']}" if r.get("forfeit") else ""
            rows.append((seed, side, f"seed {seed:>3} A={side} {outcome} {r['reason']:<16} "
                         f"turn {r['turns']:>3}  A {r['score'][side]:>2} : {r['score'][opp]:<2} B"
                         f"  maxms A={max_ms[side]} B={max_ms[opp]}{extra}"))
    for _, _, line in sorted(rows):
        print(line)
    n = win + draw + loss
    print(f"\nA 전적: {win}승 {draw}무 {loss}패 / {n}경기  승점률 {(win + 0.5 * draw) / n:.3f}")


if __name__ == "__main__":
    main()
