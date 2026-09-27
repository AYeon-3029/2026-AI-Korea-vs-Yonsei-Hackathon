"""깃발 대항전 게임 엔진 (M1).

순수 상태 전이 엔진. 텍스트 프로토콜/타임아웃은 러너 계층(M3) 담당.
"""
from .commands import Move, Move2, Priority, Spawn, Tele
from .config import load_config
from .pipeline import (
    capture_cost,
    run_turn,
    step_capture,
    step_combat,
    step_income,
    step_move,
    step_reveal,
    step_spawn,
    step_victory,
    team_score,
    unit_cost,
    unit_value,
)
from .state import Building, GameState, TEAMS, new_game

__all__ = [
    "load_config",
    "GameState",
    "Building",
    "TEAMS",
    "new_game",
    "Spawn",
    "Move",
    "Move2",
    "Tele",
    "Priority",
    "run_turn",
    "step_spawn",
    "step_move",
    "step_combat",
    "step_income",
    "step_capture",
    "step_reveal",
    "step_victory",
    "unit_cost",
    "capture_cost",
    "team_score",
    "unit_value",
]
