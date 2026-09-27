// 참가자가 전략을 수정할 진입 파일. 보조 헤더를 함께 제출한다.
// stderr는 게임당 1 MiB 이내이며 미공개 점수 -1은 실제 음수 점수가 아니다.
#include "protocol.hpp"

std::vector<std::string> decide(const p::View& view, const p::Init& init) {
    std::vector<std::string> commands;
    // TODO: 점령에 남길 자원과 생산할 병종을 선택하세요.
    if (view.my_resource >= contract::F_COST) commands.push_back(p::spawn("F", 1));
    for (const auto& unit : view.my_units(init, "F")) {
        auto building = view.building_at(unit.x, unit.y);
        if (building && building->owner != init.team) continue;
        // TODO: 첫 통행 가능 방향 대신 목표까지의 경로를 선택하세요.
        for (std::string direction : {"U", "D", "L", "R"}) {
            auto [dx, dy] = p::delta(direction);
            if (init.passable(unit.x + dx, unit.y + dy)) {
                commands.push_back(p::move(unit.x, unit.y, "F", unit.count, direction));
                break;
            }
        }
    }
    return commands;
}

int main() { return p::run(decide); }
