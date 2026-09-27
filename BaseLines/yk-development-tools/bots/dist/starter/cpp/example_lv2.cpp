// 예제 전략. 보조 헤더를 제출 ZIP에 함께 넣는다.
// stderr는 게임당 1 MiB 이내로 사용한다.
#include "search.hpp"

vector<string> decide(const p::View& view, const p::Init& init) {
    vector<string> commands;
    auto flags = sorted_units(view, init, "F");
    auto warriors = sorted_units(view, init, "W");
    set<pair<int, int>> enemy_flags, live_targets;
    for (const auto& unit : view.units) {
        if (unit.team == init.opp && unit.kind == "F") {
            enemy_flags.insert({unit.x, unit.y});
        }
    }
    for (const auto& building : view.buildings) {
        if (building.owner != init.team && !enemy_flags.count({building.x, building.y})) {
            live_targets.insert({building.x, building.y});
        }
    }

    // 왜: 미공개 점수는 실제 가치가 아니므로 거리만으로 목표를 고른다.
    // 바꿔보기: 공개 점수 가중치와 미공개 목표 탐색 보너스를 분리할 수 있다.
    // 왜: 점령 비용을 먼저 남겨 생산으로 인해 점령이 지연되지 않게 한다.
    // 바꿔보기: 당일 도착할 모든 건물의 점령 비용을 합쳐 예약할 수 있다.
    int budget = max(0, view.my_resource - capture_reserve(view, init));
    int engineering = 0, flag_count = 0, warrior_count = 0;
    for (const auto& building : view.buildings) {
        engineering += building.type == "ENG" && building.owner == init.team;
    }
    for (const auto& unit : flags) flag_count += unit.count;
    for (const auto& unit : warriors) warrior_count += unit.count;
    int warrior_cost = max(contract::ENG_FLOOR,
                           contract::W_COST - engineering * contract::ENG_DISCOUNT);

    // 왜: 소수 전투병이 상대 깃발병을 제거하고 경합을 풀 수 있다.
    // 바꿔보기: 전략상 세 명 상한을 상대 병력에 따라 조절할 수 있다.
    int make_warriors = 0;
    if (flag_count > 0 || budget >= contract::F_COST + warrior_cost) {
        make_warriors = min(max(0, 3 - warrior_count), budget / warrior_cost);
    }
    budget -= make_warriors * warrior_cost;
    if (make_warriors > 0) commands.push_back(p::spawn("W", make_warriors));
    int make_flags = budget / contract::F_COST;
    if (make_flags > 0) commands.push_back(p::spawn("F", make_flags));

    // 왜: 적 깃발병 저지를 우선하고 적이 없으면 점령 목표를 호위한다.
    // 바꿔보기: 목표 점수와 위험도를 함께 고려하는 휴리스틱을 만들 수 있다.
    const auto& warrior_goals = enemy_flags.empty() ? live_targets : enemy_flags;
    for (const auto& unit : warriors) {
        string step = bfs({unit.x, unit.y}, warrior_goals, init);
        if (!step.empty()) commands.push_back(p::move(unit.x, unit.y, "W", unit.count, step));
    }
    // 왜: 깃발병만 경합한 칸에서는 점령이 진행되지 않는다.
    // 바꿔보기: 전투병과의 동시 도착을 기다리거나 안전한 우회 경로를 선택할 수 있다.
    for (const auto& unit : flags) {
        string step = bfs({unit.x, unit.y}, live_targets, init);
        if (!step.empty()) commands.push_back(p::move(unit.x, unit.y, "F", unit.count, step));
    }
    return commands;
}

int main() {
    return p::run(decide);
}
