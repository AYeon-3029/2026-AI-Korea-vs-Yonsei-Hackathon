"""내 봇과 예제 봇을 기존 참조 러너로 대전시키고 리플레이를 저장한다."""

import argparse
import json
import shlex
import sys
from pathlib import Path
from _support import ROOT, KIT, turn_timeout_ms, first_turn_timeout_ms
from engine.config import load_config
from runner import SubprocessBot, run_match


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--bot",
        default=shlex.join([sys.executable, str(KIT / "python/main.py")]),
        help="내 봇 실행 명령",
    )
    p.add_argument(
        "--opponent",
        default=shlex.join([sys.executable, str(KIT / "python/example_lv1.py")]),
        help="상대 봇 실행 명령",
    )
    p.add_argument("--seed", type=int, default=0, help="맵 시드")
    p.add_argument("--replay", default="out/local-replay.json", help="리플레이 저장 경로")
    args = p.parse_args()
    bots = []
    try:
        for command in (args.bot, args.opponent):
            bots.append(SubprocessBot(command, name=command))
        cfg = load_config()
        cfg["first_turn_timeout_ms"] = first_turn_timeout_ms()
        replay, result = run_match(
            args.seed, cfg, *bots, turn_timeout_ms=turn_timeout_ms()
        )
    finally:
        for bot in bots:
            bot.close()
    path = Path(args.replay)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(replay, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"승자={result['winner']} 종료={result['reason']} 턴={result['turns']} 점수={result['score']}"
    )
    print(f"리플레이: {path.resolve()}")
    return 1 if result["reason"] == "forfeit" else 0


if __name__ == "__main__":
    raise SystemExit(main())
