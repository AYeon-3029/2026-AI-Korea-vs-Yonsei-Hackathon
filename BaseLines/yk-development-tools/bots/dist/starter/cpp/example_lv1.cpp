// 예제 전략. 보조 헤더를 제출 ZIP에 함께 넣는다.
// stderr는 게임당 1 MiB 이내로 사용한다.
#include "search.hpp"

vector<string> decide(const p::View& view, const p::Init& init) {
    // 미공개 점수 -1은 실제 점수로 쓰지 않는다. 이 예제의 평가는 거리만 사용한다.
    set<pair<int, int>> targets;
    for (const auto& building : view.buildings) {
        if (building.owner == "N") {
            targets.insert({building.x, building.y});
        }
    }

    vector<string> commands;
    int count = max(0, (view.my_resource - capture_reserve(view, init)) / contract::F_COST);
    if (count > 0) {
        commands.push_back(p::spawn("F", count));
    }
    for (const auto& unit : sorted_units(view, init, "F")) {
        string step = bfs({unit.x, unit.y}, targets, init);
        if (!step.empty()) {
            commands.push_back(p::move(unit.x, unit.y, "F", unit.count, step));
        }
    }
    return commands;
}

int main() {
    return p::run(decide);
}
