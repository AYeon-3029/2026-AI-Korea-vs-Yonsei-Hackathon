"""전략을 수정할 봇. 보조 모듈을 함께 제출 ZIP에 넣는다."""
# 디버깅 stderr는 게임당 1 MiB 이내로 사용하세요.
# 미공개 점수 -1은 실제 음수 점수가 아닙니다.
from protocol import BALANCE, DIRS, spawn, move, run
from search import bfs, capture_reserve

def decide(view, init):
    cfg = BALANCE
    commands = []
    flags = sorted(view.my_units("F"), key=lambda u: (u["y"], u["x"]))
    warriors = sorted(view.my_units("W"), key=lambda u: (u["y"], u["x"]))
    enemy_flags = {
        (u["x"], u["y"]) for u in view.units if u["team"] == view.opp and u["kind"] == "F"
    }
    targets = {(b["x"], b["y"]) for b in view.buildings if b["owner"] != view.team}
    live = targets - enemy_flags
    # 왜: 미공개 점수 -1은 실제 가치가 아니므로 평가에서 사용하지 않고 거리로 선택한다.
    # 바꿔보기: 공개된 점수에만 가중치를 주고 미공개 목표에는 별도 탐색 보너스를 줄 수 있다.
    # 왜: 점령 비용을 먼저 남기면 병력 생산 뒤에도 건물을 확보할 수 있다.
    # 바꿔보기: 최대 한 건물 비용 대신 이번 턴 도착할 모든 건물 비용을 예약할 수 있다.
    budget = max(0, view.my_resource - capture_reserve(view))
    engineering = sum(b["type"] == "ENG" and b["owner"] == view.team for b in view.buildings)
    wc = max(
        cfg["buildings"]["eng_cost_floor"],
        cfg["units"]["W"]["cost"] - engineering * cfg["buildings"]["eng_discount_per"],
    )
    fc = cfg["units"]["F"]["cost"]
    nf = sum(u["count"] for u in flags)
    nw = sum(u["count"] for u in warriors)
    # 왜: 전투병을 소수 먼저 확보하면 깃발병만 있는 상대의 점령을 끊을 수 있다.
    # 바꿔보기: 세 명 상한은 전략 선택이며, 상대 전투병 수에 따라 동적으로 바꿀 수 있다.
    make_w = min(max(0, 3 - nw), budget // wc) if nf or budget >= fc + wc else 0
    budget -= make_w * wc
    if make_w:
        commands.append(spawn("W", make_w))
    make_f = budget // fc
    if make_f:
        commands.append(spawn("F", make_f))
    # 왜: 상대 깃발병을 먼저 저지하고, 없으면 아군 점령 목표를 향해 호위한다.
    # 바꿔보기: 가까운 적보다 고득점 건물을 위협하는 적에게 우선 대응할 수 있다.
    warrior_goals = enemy_flags or live
    for u in warriors:
        step = bfs((u["x"], u["y"]), warrior_goals, init)
        if step:
            commands.append(move(u["x"], u["y"], "W", u["count"], step))
    # 왜: 양 팀 깃발병만 겹치면 점령이 멈추므로 전투병이 해결할 때까지 다른 목표를 찾는다.
    # 바꿔보기: 안전한 우회 경로나 전투병과의 동시 도착을 고려할 수 있다.
    for u in flags:
        step = bfs((u["x"], u["y"]), live, init)
        if step:
            commands.append(move(u["x"], u["y"], "F", u["count"], step))
    return commands


if __name__ == "__main__":
    run(decide)
