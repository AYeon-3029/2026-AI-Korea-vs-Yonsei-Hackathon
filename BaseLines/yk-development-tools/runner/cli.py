"""매치 러너 CLI (SPEC 13절).

runner --seed <int> --bot-y "<cmd>" --bot-k "<cmd>" \
       --replay out/replay.json --result out/result.json \
       [--turn-timeout-ms 300] [--config config/balance.json] [--max-turns N]

종료 코드: 정상 0 / 러너 자체 오류 ≠0.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
import sys

from engine.config import load_config
from .bots import SubprocessBot
from .match import run_match
from .validation import require_positive_int, validate_run_options


def _write_json(path: str, obj: dict) -> None:
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="runner", description="깃발 대항전 매치 러너")
    p.add_argument("--seed", type=int, default=None, help="로컬 대전 맵 시드(필수)")
    p.add_argument("--bot-y", default=None, help="연세(Y) 봇 실행 커맨드")
    p.add_argument("--bot-k", default=None, help="고려(K) 봇 실행 커맨드")
    p.add_argument("--name-y", default=None, help="연세(Y) 표시명(참가팀명). 기본=봇 파일명")
    p.add_argument("--name-k", default=None, help="고려(K) 표시명(참가팀명). 기본=봇 파일명")
    p.add_argument("--replay", default=None, help="리플레이 JSON 출력 경로")
    p.add_argument("--result", default=None, help="결과 JSON 출력 경로")
    p.add_argument("--turn-timeout-ms", type=int, default=300, help="턴 제한 시간(ms, 양의 정수)")
    p.add_argument("--config", default=None, help="balance.json 경로")
    p.add_argument("--max-turns", type=int, default=None, help="일반 대전 테스트/단축용 턴 상한(양의 정수)")
    p.add_argument("--on-bot-error", choices=["forfeit", "continue"], default="forfeit",
                   help="봇 오류(타임아웃/크래시/END누락) 처리: forfeit(즉시 몰수, 기본) / continue")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.max_turns is not None:
            require_positive_int("max_turns", args.max_turns)
        validate_run_options(config, args.turn_timeout_ms,
                             args.max_turns)

        # ── 일반 1판 대전 ──
        if args.seed is None or not args.bot_y or not args.bot_k:
            print("[runner error] --seed, --bot-y, --bot-k 가 필요합니다", file=sys.stderr)
            return 1
        with ExitStack() as cleanup:
            bot_y = SubprocessBot(args.bot_y, name=args.bot_y)
            cleanup.callback(bot_y.close)
            bot_k = SubprocessBot(args.bot_k, name=args.bot_k)
            cleanup.callback(bot_k.close)
            replay, result = run_match(
                args.seed, config, bot_y, bot_k,
                turn_timeout_ms=args.turn_timeout_ms, max_turns=args.max_turns,
                names={"Y": args.name_y, "K": args.name_k},
                on_bot_error=args.on_bot_error,
            )
        if args.replay:
            _write_json(args.replay, replay)
        if args.result:
            _write_json(args.result, result)
        # 요약은 stderr 로(파일 출력과 분리)
        ff = f" forfeit={result['forfeit']}" if result.get("forfeit") else ""
        print(f"winner={result['winner']} reason={result['reason']} "
              f"score Y={result['score']['Y']} K={result['score']['K']} "
              f"turns={result['turns']} seed={result['seed']}{ff}", file=sys.stderr)
        return 0
    except Exception as e:  # 러너 자체 오류
        print(f"[runner error] {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
