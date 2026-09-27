"""전략을 수정할 봇. 보조 모듈을 함께 제출 ZIP에 넣는다."""
# 디버깅 stderr는 게임당 1 MiB 이내로 사용하세요.
# 미공개 점수 -1은 실제 음수 점수가 아닙니다.
from protocol import BALANCE, DIRS, spawn, move, run

def decide(view, init):
    commands = []
    # TODO: 점령에 남길 자원과 필요한 병종을 결정해 보세요.
    if view.my_resource >= BALANCE["units"]["F"]["cost"]:
        commands.append(spawn("F", 1))
    # TODO: 단순한 첫 방향 대신 목표 건물로 가는 경로를 선택해 보세요.
    for unit in view.my_units("F"):
        building = view.building_at(unit["x"], unit["y"])
        if building and building["owner"] != view.team:
            continue
        for direction, (dx, dy) in DIRS.items():
            if init.passable(unit["x"] + dx, unit["y"] + dy):
                commands.append(move(unit["x"], unit["y"], "F", unit["count"], direction))
                break
    return commands


if __name__ == "__main__":
    run(decide)
