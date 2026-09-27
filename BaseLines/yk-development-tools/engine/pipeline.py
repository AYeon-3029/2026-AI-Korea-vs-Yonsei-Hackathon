"""9단계 턴 파이프라인 (SPEC 6절).

순수 상태 전이: run_turn 은 입력 상태를 복제한 뒤 순서대로 각 단계를 적용하고
새 상태와 (승리 판정) 결과를 반환한다. I/O 없음.

파이프라인 순서(엄격):
  1 명령 수신 → 2 생산 → 3 이동 → 4 전투 → 5 건물효과 갱신 →
  6 수입 → 7 점령 → 8 정보공개 → 9 승리판정
5단계(건물 효과)는 소유권에서 파생 계산하므로 별도 저장 상태가 없다.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .commands import DIRECTIONS, KINDS, Move, Move2, Priority, Spawn, Tele
from .state import TEAMS, Building, GameState


def other_team(team: str) -> str:
    return "K" if team == "Y" else "Y"


def _cheby(x1: int, y1: int, x2: int, y2: int) -> int:
    return max(abs(x1 - x2), abs(y1 - y2))


# ------------------------------------------------------------------ 파생 효과

def eng_count(state: GameState, team: str) -> int:
    return sum(1 for b in state.sorted_buildings() if b.btype == "ENG" and b.owner == team)


def owns_library(state: GameState, team: str) -> bool:
    """도서관 1개 이상 소유 여부. (SPEC 9절: 중첩 없음)"""
    return any(b.btype == "LIBRARY" and b.owner == team for b in state.sorted_buildings())


def unit_cost(state: GameState, team: str, kind: str) -> int:
    """생산 비용. 공학관은 전투병(W) 비용 -1/개, 하한 config.eng_cost_floor."""
    base = state.config["units"][kind]["cost"]
    if kind == "W":
        disc = eng_count(state, team) * state.config["buildings"]["eng_discount_per"]
        floor = state.config["buildings"]["eng_cost_floor"]
        return max(base - disc, floor)
    return base


def add_resource(state: GameState, team: str, amount: int) -> None:
    """자원 증가 후 상한 적용(SPEC 4절: 모든 자원 획득에 상한 40)."""
    cap = state.config["resource"]["resource_cap"]
    state.resources[team] = min(state.resources[team] + amount, cap)


# ------------------------------------------------------------------ 2. 생산

def step_spawn(state: GameState, spawns: Dict[str, List[Spawn]]) -> None:
    for team in TEAMS:  # 결정적 순회
        for cmd in spawns[team]:
            if cmd.kind not in KINDS or cmd.count <= 0:
                continue
            if cmd.x is None or cmd.y is None:
                bx, by = state.bases[team]
                valid = True
            else:
                bx, by = cmd.x, cmd.y
                # RULEBOOK §6: 좌표를 명시하면 소유 병원에서만 생산한다.
                b = state.building_at(bx, by)
                valid = b is not None and b.btype == "HOSPITAL" and b.owner == team
            if not valid:
                continue  # 잘못된 명령 → 그 줄 무시
            cost = unit_cost(state, team, cmd.kind)
            afford = state.resources[team] // cost
            n = min(cmd.count, afford)  # 자원 부족 시 가능한 인원까지만
            if n <= 0:
                continue
            state.resources[team] -= n * cost
            state.add_unit(bx, by, team, cmd.kind, n)


# ------------------------------------------------------------------ 3. 이동

def step_move(state: GameState, moves: Dict[str, List[object]]) -> None:
    """MOVE/MOVE2/TELE 동시 적용.

    이동 전 잔여 풀(movable)에서만 인원을 차감하고 도착분(arrivals)은 별도로 모은다.
    → 같은 턴 도착 유닛은 재이동 불가(2칸 체이닝 방지), 자리 맞바꿈은 양쪽 다 정상.
    인원 검증은 적용 시점 잔여 기준(SPEC 5절): 초과 요청은 가능한 만큼만 부분 이동.
    """
    movable: Dict[Tuple[int, int, str, str], int] = dict(state.units)
    arrivals: Dict[Tuple[int, int, str, str], int] = {}

    def take(x: int, y: int, team: str, kind: str, count: int) -> int:
        key = (x, y, team, kind)
        avail = movable.get(key, 0)
        n = min(max(0, count), avail)
        if n > 0:
            movable[key] = avail - n
        return n

    def arrive(x: int, y: int, team: str, kind: str, n: int) -> None:
        if n <= 0:
            return
        key = (x, y, team, kind)
        arrivals[key] = arrivals.get(key, 0) + n

    for team in TEAMS:
        tele_used = 0
        for cmd in moves[team]:
            if isinstance(cmd, Move):
                if cmd.direction not in DIRECTIONS or cmd.kind not in KINDS:
                    continue
                dx, dy = DIRECTIONS[cmd.direction]
                nx, ny = cmd.x + dx, cmd.y + dy
                if not state.is_passable(nx, ny):
                    continue  # 장애물/맵밖 도착 거부
                arrive(nx, ny, team, cmd.kind, take(cmd.x, cmd.y, team, cmd.kind, cmd.count))
            elif isinstance(cmd, Move2):
                d1 = DIRECTIONS.get(cmd.dir1)
                d2 = DIRECTIONS.get(cmd.dir2)
                if d1 is None or d2 is None:
                    continue
                mx, my = cmd.x + d1[0], cmd.y + d1[1]
                nx, ny = mx + d2[0], my + d2[1]
                # 경유 셀도 진입 가능해야 통과(SPEC 19: 장애물 관통 불가)
                if not state.is_passable(mx, my) or not state.is_passable(nx, ny):
                    continue
                arrive(nx, ny, team, "S", take(cmd.x, cmd.y, team, "S", cmd.count))
            elif isinstance(cmd, Tele):
                if tele_used >= state.config["tele"]["per_turn"]:
                    continue
                if cmd.kind not in KINDS or cmd.count <= 0:
                    continue   # 무효 명령은 턴 1회를 소모하지 않는다(SPEC 5절)
                if (cmd.x, cmd.y) == (cmd.tx, cmd.ty):
                    continue   # 같은 역으로의 TELE 는 무의미 → 무시
                src = state.building_at(cmd.x, cmd.y)
                dst = state.building_at(cmd.tx, cmd.ty)
                if src is None or dst is None:
                    continue
                if src.btype != "STATION" or dst.btype != "STATION":
                    continue
                if src.owner != team or dst.owner != team:
                    continue
                stations = sum(
                    1 for b in state.sorted_buildings()
                    if b.btype == "STATION" and b.owner == team
                )
                if stations < state.config["tele"]["min_stations"]:
                    continue
                want = min(cmd.count, state.config["tele"]["max_units"])
                n = take(cmd.x, cmd.y, team, cmd.kind, want)
                if n <= 0:
                    continue  # 해당 병종 부재/앞선 이동으로 소진 → 사용 횟수도 유지
                arrive(cmd.tx, cmd.ty, team, cmd.kind, n)
                tele_used += 1  # 유효 TELE 1회 소모

    # movable(잔류) + arrivals(도착) 병합
    state.units = {k: c for k, c in movable.items() if c > 0}
    for key, c in arrivals.items():
        if c > 0:
            state.units[key] = state.units.get(key, 0) + c


# ------------------------------------------------------------------ 4. 전투

def _wipe_noncombat(state: GameState, x: int, y: int, victim: str, b: Optional[Building]):
    """상대 전투병 우세 시 victim 팀의 깃발병·정찰병 전멸(C2).

    반환 (제거 여부, 깃발 뽑힘 여부).
    """
    had_flag = state.get_unit(x, y, victim, "F") > 0
    removed = had_flag or state.get_unit(x, y, victim, "S") > 0
    state.set_unit(x, y, victim, "F", 0)
    state.set_unit(x, y, victim, "S", 0)
    # 점령 건물 위 내 깃발병이 전투로 제거되면 깃발이 중립으로 뽑힘(SPEC 8절)
    pulled = False
    if b is not None and b.owner == victim and had_flag:
        b.owner = "N"
        b.stage = 1
        pulled = True
    return removed, pulled


def step_combat(state: GameState, events: Optional[list] = None) -> None:
    cells = sorted({(x, y) for (x, y, _t, _k) in state.units})
    for (x, y) in cells:
        y_here = state.team_has_units_at(x, y, "Y")
        k_here = state.team_has_units_at(x, y, "K")
        if not (y_here and k_here):
            continue
        yW = state.get_unit(x, y, "Y", "W")
        kW = state.get_unit(x, y, "K", "W")
        m = min(yW, kW)  # C1: 전투병 상쇄
        removed = m > 0
        if m > 0:
            state.remove_unit(x, y, "Y", "W", m)
            state.remove_unit(x, y, "K", "W", m)
            yW -= m
            kW -= m
        b = state.building_at(x, y)
        pulled = False
        # C2: 상쇄 후 전투병이 남은 팀이 있으면 상대 비전투 유닛 전멸
        if yW > 0 and kW == 0:
            r, pulled = _wipe_noncombat(state, x, y, "K", b)
            removed = removed or r
        elif kW > 0 and yW == 0:
            r, pulled = _wipe_noncombat(state, x, y, "Y", b)
            removed = removed or r
        # C3: 양 팀 전투병 0 → 아무 일 없음. 건물 위 양 팀 깃발병 공존 = 경합(점령에서 처리)
        if events is not None and removed:
            events.append({"type": "combat", "x": x, "y": y})
            if pulled:
                events.append({"type": "neutralize", "x": x, "y": y})


# ------------------------------------------------------------------ 6. 수입

def step_income(state: GameState) -> None:
    base = state.config["resource"]["base_income"]
    hall_bonus = state.config["resource"]["hall_bonus"]
    for team in TEAMS:
        halls = sum(1 for b in state.sorted_buildings() if b.btype == "HALL" and b.owner == team)
        add_resource(state, team, base + halls * hall_bonus)


# ------------------------------------------------------------------ 7. 점령

def capture_cost(state: GameState, team: str, b: Building,
                 has_library: Optional[bool] = None) -> int:
    """점령 1단계 비용. 광장은 배수, 도서관 보유 시 고정 -1(중첩 없음).

    has_library 를 넘기면 현재 소유권 대신 그 값을 쓴다. step_capture 는 7단계
    진입 시점에 스냅샷한 값을 넘겨, 같은 단계 안에서 상대가 내 도서관을 중립화해도
    이번 턴 내 비용이 변하지 않게 한다(SPEC 6절, docs/symmetry-audit.md 결함 ①).
    """
    cap = state.config["capture"]
    cost = cap["capture_cost"]
    if b.btype == "PLAZA":
        cost *= cap["plaza_multiplier"]
    if has_library is None:
        has_library = owns_library(state, team)
    if has_library:
        cost -= state.config["buildings"]["library_discount"]  # 고정 -1(중첩 없음)
    return max(cost, cap["min_capture_cost"])


def _home_key(state: GameState, team: str, b: Building) -> Tuple[int, int]:
    """자기 본진 기준으로 정규화한 (y, x) — 회전 불변 타이브레이크.

    절대좌표 (y, x) 오름차순은 "항상 좌상단(신촌 방향) 우선"이라 180° 회전
    불변이 아니다. 그러면 같은 국면에서도 Y 는 자기 후방을, K 는 적진 깊숙한
    곳을 먼저 고르게 되어 진영 비대칭이 생긴다. 본진이 안암 쪽(x > 중앙)인 팀은
    좌표를 180° 회전해 비교한다 → 두 진영이 자기 본진 기준으로 동일하게 판정한다.
    (docs/symmetry-audit.md 결함 ②)
    """
    w = state.config["grid"]["width"]
    h = state.config["grid"]["height"]
    if state.bases[team][0] * 2 > w - 1:
        return (h - 1 - b.y, w - 1 - b.x)
    return (b.y, b.x)


def _capture_order(
    state: GameState, team: str, candidates: List[Building], priority: List[Tuple[int, int]]
) -> List[Building]:
    by_pos = {(b.x, b.y): b for b in candidates}
    ordered: List[Building] = []
    used = set()
    for (px, py) in priority:  # PRIORITY 지정 순서 우선
        b = by_pos.get((px, py))
        if b is not None and b.id not in used:
            ordered.append(b)
            used.add(b.id)
    # 나머지: 점수 높은 순(미공개=0, SPEC 19-2) → 자기 본진 기준 정규화 (y, x) 오름차순
    rest = [b for b in candidates if b.id not in used]
    rest.sort(key=lambda b: (-(b.score if b.id in state.revealed[team] else 0),
                             _home_key(state, team, b)))
    return ordered + rest


def step_capture(state: GameState, priorities: Dict[str, List[Tuple[int, int]]],
                 events: Optional[list] = None) -> None:
    # 건물 효과 스냅샷: 도서관 할인은 이 단계 진입 시점 소유권으로 고정한다.
    # 루프 안에서 다시 읽으면 먼저 처리되는 Y 만 같은 턴에 상대 할인을 끊을 수 있어
    # 진영 비대칭이 생긴다(SPEC 1절 동시 처리 위반, docs/symmetry-audit.md 결함 ①).
    library = {t: owns_library(state, t) for t in TEAMS}

    # 보급소 보너스는 이 단계가 **전부 끝난 뒤** 지급한다. 루프 안에서 즉시 넣으면
    # 그 자원으로 같은 단계의 뒷 건물을 추가 점령할 수 있어(PRIORITY 순서에 따라
    # 결과가 달라짐) 동시 처리 원칙에 어긋난다.
    depot_pending: Dict[str, int] = {t: 0 for t in TEAMS}

    for team in TEAMS:
        opp = other_team(team)
        candidates: List[Building] = []
        for b in state.sorted_buildings():
            if state.get_unit(b.x, b.y, team, "F") <= 0:
                continue
            if state.get_unit(b.x, b.y, opp, "F") > 0:
                continue  # 경합 → 이번 턴 진행 불가(C3)
            if b.owner == team and b.stage >= 2:
                continue  # 이미 완전 소유
            candidates.append(b)

        for b in _capture_order(state, team, candidates, priorities[team]):
            cost = capture_cost(state, team, b, library[team])
            if state.resources[team] < cost:
                continue  # 자원 부족 → 대기(깃발병 제자리)
            state.resources[team] -= cost
            if b.owner == "N":
                # 중립 → 즉시 내 소유
                b.owner = team
                b.stage = 2
                state.revealed[team].add(b.id)  # 점령 시 점수 영구 공개
                if b.btype == "DEPOT":
                    claimed = state.depot_claimed.setdefault(b.id, set())
                    if team not in claimed:  # 건물당 팀별 1회
                        claimed.add(team)
                        depot_pending[team] += state.config["buildings"]["depot_bonus"]
                if events is not None:
                    events.append({"type": "capture", "x": b.x, "y": b.y, "team": team})
            else:
                # 상대 소유 → 1단계 중립화(완전 중립 리셋, SPEC 8절 확정)
                b.owner = "N"
                b.stage = 1
                if events is not None:
                    events.append({"type": "neutralize", "x": b.x, "y": b.y, "team": team})

    # 보급소 보너스 지급(점령 결과 반영 후, 상한 40 적용)
    for team in TEAMS:
        if depot_pending[team]:
            add_resource(state, team, depot_pending[team])

    # 누적 점령-턴(타이브레이커 ③): 소유 건물 점수 합을 매 턴 누적
    for team in TEAMS:
        state.occupation_score_turns[team] += sum(
            b.score for b in state.sorted_buildings() if b.owner == team
        )


# ------------------------------------------------------------------ 8. 정보 공개

def step_reveal(state: GameState) -> None:
    scout_r = state.config["buildings"]["scout_reveal_range"]
    watch_r = state.config["buildings"]["watch_reveal_range"]
    for team in TEAMS:
        rev = state.revealed[team]
        scouts = sorted(
            (x, y) for (x, y, t, k), c in state.units.items() if t == team and k == "S" and c > 0
        )
        watches = [(b.x, b.y) for b in state.sorted_buildings() if b.btype == "WATCH" and b.owner == team]
        for b in state.sorted_buildings():
            if b.id in rev:
                continue
            if state.team_has_units_at(b.x, b.y, team):       # 유닛 진입
                rev.add(b.id)
            elif b.owner == team:                             # 내가 점령
                rev.add(b.id)
            elif any(_cheby(b.x, b.y, sx, sy) <= scout_r for sx, sy in scouts):  # 정찰병 시야
                rev.add(b.id)
            elif any(_cheby(b.x, b.y, wx, wy) <= watch_r for wx, wy in watches):  # 감시 거점
                rev.add(b.id)


# ------------------------------------------------------------------ 9. 승리 판정

def team_score(state: GameState, team: str) -> int:
    return sum(b.score for b in state.sorted_buildings() if b.owner == team)


def unit_value(state: GameState, team: str) -> int:
    vals = state.config["tiebreak_values"]
    total = 0
    for (x, y, t, k), c in state.units.items():
        if t == team:
            total += vals[k] * c
    return total


def _result(winner: str, reason: str, scores: Dict[str, int], state: GameState) -> dict:
    return {"winner": winner, "reason": reason, "score": dict(scores), "turns": state.turn}


def step_victory(state: GameState) -> Optional[dict]:
    scores = {t: team_score(state, t) for t in TEAMS}
    total = sum(b.score for b in state.sorted_buildings())

    # 즉시 승리: 상대 점령 점수 0 그리고 내가 맵 총점 과반
    for t in TEAMS:
        if scores[other_team(t)] == 0 and scores[t] * 2 > total:
            return _result(t, "instant", scores, state)

    if state.turn < state.config["total_turns"]:
        return None

    # total_turns 도달 → config.tiebreaker_order 순서로 타이브레이커
    metrics = {
        "score": scores,
        "occupation_turns": state.occupation_score_turns,
        "unit_value": {t: unit_value(state, t) for t in TEAMS},
    }
    reason_of = {"score": "score", "occupation_turns": "occupation_turns", "unit_value": "units"}
    order = state.config.get(
        "tiebreaker_order", ["score", "occupation_turns", "unit_value", "draw"]
    )
    for crit in order:
        if crit == "draw":
            break
        m = metrics[crit]
        if m["Y"] != m["K"]:
            return _result("Y" if m["Y"] > m["K"] else "K", reason_of[crit], scores, state)
    return _result("DRAW", "draw", scores, state)


# ------------------------------------------------------------------ 오케스트레이터

def _split(cmds: List[object]):
    spawns = [c for c in cmds if isinstance(c, Spawn)]
    moves = [c for c in cmds if isinstance(c, (Move, Move2, Tele))]
    prio: List[Tuple[int, int]] = []
    for c in cmds:
        if isinstance(c, Priority):
            prio = list(c.coords)  # 마지막 PRIORITY 가 유효
    return spawns, moves, prio


def run_turn(
    state: GameState, cmds_y: List[object], cmds_k: List[object],
    events: Optional[list] = None,
) -> Tuple[GameState, Optional[dict]]:
    """한 턴을 처리해 (새 상태, 결과 or None) 반환. 결과가 None 이면 경기 속행.

    events 리스트를 주면 이번 턴의 전투/점령/중립화 이벤트를 채운다(관전/리플레이용).
    """
    s = state.clone()
    s.turn += 1
    # RULEBOOK §12: 직전 턴의 중립화 표시는 입력에 전달된 뒤 노후화한다.
    # 전투보다 먼저 처리해야 이번 턴 전투의 N 1이 점령 단계에서 지워지지 않는다.
    for b in s.sorted_buildings():
        if b.owner == "N" and b.stage == 1:
            b.stage = 0

    sy, my, py = _split(cmds_y)
    sk, mk, pk = _split(cmds_k)

    step_spawn(s, {"Y": sy, "K": sk})                 # 2
    step_move(s, {"Y": my, "K": mk})                  # 3
    step_combat(s, events)                            # 4
    # 5 건물 효과 갱신: 소유권 파생 계산이라 별도 상태 없음
    step_income(s)                                    # 6
    step_capture(s, {"Y": py, "K": pk}, events)       # 7
    step_reveal(s)                                    # 8
    result = step_victory(s)                          # 9
    return s, result
