"""매치 오케스트레이션.

맵 생성 → 초기 상태 → 봇 init → 매 턴 (입력 생성·봇 구동·엔진 전이·리플레이 기록)
→ 승리 판정까지 진행하고 (replay, result) 를 반환한다.

봇 드라이버는 SubprocessBot / InProcessBot 어느 쪽이든 무방(동일 인터페이스).
"""
from __future__ import annotations

import copy
import os
from typing import Dict, Optional, Tuple

from engine.pipeline import run_turn, team_score
from engine.state import TEAMS
from mapgen import generate, to_state
from mapgen.generator import CENTER_PAIR_TYPES
from .protocol import parse_commands, serialize_init, serialize_turn
from .replay import new_replay, turn_entry
from .validation import validate_run_options

# 중앙 지역(x 5~9)에 등장할 수 있는 건물 종류 — 소속 진영이 없어 진영별 이름 불가
_CENTRAL_TYPES = set(CENTER_PAIR_TYPES) | {"PLAZA"}


def validate_building_display_names(config: dict) -> None:
    """진영별 표시명({Y,K})은 소속 지역이 있는 종류(신촌/안암 전용)에만 허용.

    중앙에 등장 가능한 종류(PLAZA/STATION/WATCH/DEPOT)에 진영별 이름이 지정되면 오류.
    표시명은 소유자가 아니라 건물 소속 지역(x)으로 결정되기 때문(SPEC 10/12절).
    """
    names = config.get("building_display_names", {})
    for btype in sorted(names):
        if isinstance(names[btype], dict) and btype in _CENTRAL_TYPES:
            raise ValueError(
                f"building_display_names['{btype}']: 중앙 등장 가능 종류에는 진영별 이름을 "
                f"지정할 수 없습니다(소속 진영 없음). 공통명(문자열)만 허용."
            )


def _filename_from_command(command: str) -> str:
    """봇 커맨드에서 표시용 파일명 추출(예: 'python3 bots/main.py' → 'main.py')."""
    toks = command.split()
    for tok in toks:
        if tok.endswith(".py"):
            return os.path.basename(tok)
    return os.path.basename(toks[-1]) if toks else command


def _team_info(bot, display: Optional[str]) -> dict:
    """리플레이 teams 항목: 표시명(name) + 전체 커맨드(command)."""
    command = bot.name
    return {"name": display or _filename_from_command(command), "command": command}


def _effective_config(config: dict, max_turns: Optional[int]) -> dict:
    if max_turns is None:
        return config
    cfg = copy.deepcopy(config)
    cfg["total_turns"] = max_turns   # 엔진 승리판정이 이 턴에서 종료
    return cfg


def _send(bot, text: str, timeout_s: float) -> None:
    """턴 입력 전달 + deadline 시작. 양 봇에 먼저 보낸 뒤 수집한다(동시 계산)."""
    if not bot.dead:
        bot.send_turn(text, timeout_s)


def _collect(bot):
    """봇 응답 수집 → (원본 라인, 오류사유|None). 파싱·정리는 양쪽 판정 후 수행.

    오류사유 ∈ {"timeout","crash","invalid_output"}. 개별 명령 규격 위반은 오류가 아니며
    parse_commands 가 그 줄만 무시한다(SPEC 13다). END 누락 등 턴 응답 미성립만 오류.
    """
    if bot.dead:
        return [], None
    lines, status = bot.collect_turn()
    if status != "ok" or lines is None:
        bot.dead = True
        return [], status
    return lines, None


def _forfeit_result(err_y, err_k, state, cfg) -> dict:
    """몰수 결과: 오류 낸 팀 패, 상대 승. 양쪽 동시 오류면 무승부."""
    scores = {t: team_score(state, t) for t in TEAMS}
    if err_y and err_k:
        winner, loser, cause = "DRAW", "both", f"Y:{err_y},K:{err_k}"
    elif err_y:
        winner, loser, cause = "K", "Y", err_y
    else:
        winner, loser, cause = "Y", "K", err_k
    return {"winner": winner, "reason": "forfeit", "score": scores, "turns": state.turn,
            "forfeit": {"team": loser, "cause": cause}}


def run_match(
    seed: int,
    config: dict,
    bot_y,
    bot_k,
    *,
    turn_timeout_ms: int = 300,
    max_turns: Optional[int] = None,
    names: Optional[Dict[str, str]] = None,
    on_bot_error: str = "forfeit",
) -> Tuple[dict, dict]:
    """한 경기를 끝까지 진행해 (replay, result) 반환.

    on_bot_error 기본값은 **CLI 와 동일하게 "forfeit"** 이다. 채점 서버가 CLI 대신
    이 함수를 직접 호출해도 타임아웃·크래시·END 누락이 몰수패로 처리된다.
    "continue"(오류 봇을 이후 턴 "명령 없음"으로 두고 속행)는 테스트·골든 리플레이
    전용이며 명시적으로 넘겨야 한다. 내부 I/O 오류는 이 모드에서도 전파한다.
    전달받은 양 봇의 수명을 소유하며 초기 검증 실패를 포함한 모든 종료에서 close한다.
    """
    active_error = None
    try:
        validate_run_options(config, turn_timeout_ms, max_turns)
        if on_bot_error not in ("forfeit", "continue"):
            raise ValueError(
                f'on_bot_error 는 "forfeit" 또는 "continue" 여야 합니다: {on_bot_error!r}'
            )
        cfg = _effective_config(config, max_turns)
        validate_building_display_names(cfg)
        names = names or {}
        teams = {"Y": _team_info(bot_y, names.get("Y")), "K": _team_info(bot_k, names.get("K"))}
        first_timeout_ms = cfg.get("first_turn_timeout_ms", turn_timeout_ms)

        gmap = generate(seed, cfg)
        state = to_state(gmap)

        bot_y.send_init(serialize_init(state, "Y"))
        bot_k.send_init(serialize_init(state, "K"))

        replay = new_replay(seed, cfg, gmap, teams)
        result = None
        turn = 0
        while result is None:
            turn += 1
            timeout_s = (first_timeout_ms if turn == 1 else turn_timeout_ms) / 1000.0
            # 1) 같은 턴 상태를 양 봇에 먼저 전달(각자 deadline 시작) → 2) 응답 수집.
            # 순차 구동이면 K 는 Y 가 끝난 뒤에야 계산을 시작한다(SPEC 1절 동시 턴 위배).
            _send(bot_y, serialize_turn(state, "Y", turn), timeout_s)
            _send(bot_k, serialize_turn(state, "K", turn), timeout_s)
            raw_y, err_y = _collect(bot_y)
            raw_k, err_k = _collect(bot_k)
            # 양쪽 수신 판정 후 정리한다. 종료 지연/파싱 비용이 상대 판정을 방해하지 않는다.
            for bot, err in ((bot_y, err_y), (bot_k, err_k)):
                if err:
                    bot.close()
            if on_bot_error == "forfeit" and (err_y or err_k):
                # 몰수: 그 즉시 경기 종료, 오류 낸 팀 패(SPEC 13절). 이 턴은 처리하지 않음.
                result = _forfeit_result(err_y, err_k, state, cfg)
                break
            cmds_y, cmds_k = parse_commands(raw_y), parse_commands(raw_k)
            events = []
            state, result = run_turn(state, cmds_y, cmds_k, events)
            replay["turns"].append(turn_entry(turn, raw_y, raw_k, cmds_y, cmds_k, state, events))

        result = dict(result)
        result["seed"] = seed
        replay["result"] = result
        return replay, result
    except BaseException as exc:
        active_error = exc
        raise
    finally:
        # 양쪽 정리를 시도하되 정리 예외가 최초 실행 오류를 숨기지 않게 한다.
        cleanup_error = None
        for bot in (bot_y, bot_k):
            try:
                bot.close()
            except BaseException as exc:
                if active_error is not None:
                    active_error.add_note(f"bot cleanup failed: {exc!r}")
                elif cleanup_error is None:
                    cleanup_error = exc
                else:
                    cleanup_error.add_note(f"additional bot cleanup failure: {exc!r}")
        if active_error is None and cleanup_error is not None:
            raise cleanup_error
