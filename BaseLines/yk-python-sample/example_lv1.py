"""전략을 수정할 봇. 보조 모듈을 함께 제출 ZIP에 넣는다."""
# 디버깅 stderr는 게임당 1 MiB 이내로 사용하세요.
# 미공개 점수 -1은 실제 음수 점수가 아닙니다.
from protocol import BALANCE, DIRS, spawn, move, run
from search import bfs, capture_reserve

def decide(view, init):
    # 미공개 점수 -1을 낮은 실제 점수로 취급하지 않는다. 이 예제는 점수를 쓰지 않는다.
    targets = {(b["x"], b["y"]) for b in view.buildings if b["owner"] == "N"}
    commands = []
    n = max(0, (view.my_resource - capture_reserve(view)) // BALANCE["units"]["F"]["cost"])
    if n:
        commands.append(spawn("F", n))
    for u in sorted(view.my_units("F"), key=lambda u: (u["y"], u["x"])):
        step = bfs((u["x"], u["y"]), targets, init)
        if step:
            commands.append(move(u["x"], u["y"], "F", u["count"], step))
    return commands


if __name__ == "__main__":
    run(decide)
