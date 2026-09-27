"""리플레이/결과 직렬화 (SPEC 14절).

턴 종료 시 전체 상태 스냅샷 방식. 결정성 유지를 위해 리플레이에는 벽시계 시간 등
비결정적 값을 절대 넣지 않는다(골든 리플레이 해시 불변 조건).
"""
from __future__ import annotations

import dataclasses
from typing import Dict, List

from engine.state import GameState
from mapgen.generator import GameMap

_TEAM_ORDER = {"Y": 0, "K": 1}
_KIND_ORDER = {"F": 0, "W": 1, "S": 2}


def cmd_to_dict(cmd) -> dict:
    d = {"cmd": type(cmd).__name__}
    d.update(dataclasses.asdict(cmd))
    return d


def snapshot(state: GameState) -> dict:
    """턴 종료 시 전체 상태 스냅샷."""
    units = sorted(
        ([t, k, x, y, c] for (x, y, t, k), c in state.units.items()),
        key=lambda r: (_TEAM_ORDER[r[0]], _KIND_ORDER[r[1]], r[3], r[2]),
    )
    return {
        "resources": {"Y": state.resources["Y"], "K": state.resources["K"]},
        "units": units,
        "buildings": [
            {"id": b.id, "owner": b.owner, "stage": b.stage}
            for b in state.sorted_buildings()
        ],
        "revealed": {"Y": sorted(state.revealed["Y"]), "K": sorted(state.revealed["K"])},
        "occupation": {"Y": state.occupation_score_turns["Y"],
                       "K": state.occupation_score_turns["K"]},
    }


def new_replay(seed: int, config: dict, gmap: GameMap, teams: Dict[str, dict]) -> dict:
    """리플레이 헤더 생성(맵/건물/점수 전체 공개 — 관전자 시점).

    teams[t] = {"name": 표시명, "command": 봇 실행 커맨드} (뷰어 표시/툴팁용).
    """
    return {
        "seed": seed,
        "config": config,
        "map": {
            "width": config["grid"]["width"],
            "height": config["grid"]["height"],
            "terrain": ["".join(row) for row in gmap.terrain],
            "buildings": [
                {"id": b.id, "x": b.x, "y": b.y, "type": b.btype, "score": b.score}
                for b in gmap.buildings
            ],
            "bases": {"Y": list(gmap.bases["Y"]), "K": list(gmap.bases["K"])},
            # 건물 종류 코드 → 표시명(문자열 또는 {"Y":..,"K":..} 진영별). config 에서 지정.
            "building_names": dict(config.get("building_display_names", {})),
        },
        "teams": {t: dict(teams[t]) for t in ("Y", "K")},
        "turns": [],
        "result": None,
    }


def turn_entry(turn: int, raw_y: List[str], raw_k: List[str],
               cmds_y: list, cmds_k: list, state: GameState, events: list) -> dict:
    return {
        "turn": turn,
        "commands": {"Y": list(raw_y), "K": list(raw_k)},          # 봇 원본 출력
        "applied": {"Y": [cmd_to_dict(c) for c in cmds_y],          # 적용된(파싱된) 명령
                    "K": [cmd_to_dict(c) for c in cmds_k]},
        "events": list(events),                                     # 이번 턴 전투/점령 이벤트
        "state": snapshot(state),
    }
