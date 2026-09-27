// 두 예제가 공유하는 길찾기와 점령 비용 계산이다.
#pragma once
#include "protocol.hpp"
#include <queue>
#include <set>

using namespace std;

vector<string> directions(const p::Init& init) {
    // 같은 거리의 목표가 여러 개이면 자기 본진 기준 방향 순서를 따른다.
    if (init.base().first * 2 > init.width - 1) {
        return {"D", "U", "R", "L"};
    }
    return {"U", "D", "L", "R"};
}

string bfs(pair<int, int> start, const set<pair<int, int>>& targets, const p::Init& init) {
    // 너비 우선 탐색은 가까운 칸부터 방문하여 최단 경로의 첫 방향을 찾는다.
    if (targets.count(start)) {
        return "";
    }
    queue<pair<pair<int, int>, string>> pending;
    set<pair<int, int>> seen{start};
    pending.push({start, ""});

    while (!pending.empty()) {
        auto [position, first] = pending.front();
        pending.pop();
        for (const auto& direction : directions(init)) {
            auto [dx, dy] = p::delta(direction);
            pair<int, int> next{position.first + dx, position.second + dy};
            if (seen.count(next) || !init.passable(next.first, next.second)) {
                continue;
            }
            string step = first.empty() ? direction : first;
            if (targets.count(next)) {
                return step;
            }
            seen.insert(next);
            pending.push({next, step});
        }
    }
    return "";
}

int capture_reserve(const p::View& view, const p::Init& init) {
    bool library = false;
    for (const auto& building : view.buildings) {
        library |= building.owner == init.team && building.type == "LIBRARY";
    }
    int reserve = contract::CAPTURE_COST;
    for (const auto& unit : view.my_units(init, "F")) {
        auto building = view.building_at(unit.x, unit.y);
        if (building && building->owner != init.team) {
            int multiplier = building->type == "PLAZA" ? contract::PLAZA_MULTIPLIER : 1;
            int discount = library ? contract::LIBRARY_DISCOUNT : 0;
            int cost = max(contract::MIN_CAPTURE, contract::CAPTURE_COST * multiplier - discount);
            reserve = max(reserve, cost);
        }
    }
    return reserve;
}

vector<p::Unit> sorted_units(const p::View& view, const p::Init& init, const string& kind) {
    auto units = view.my_units(init, kind);
    sort(units.begin(), units.end(), [](const auto& left, const auto& right) {
        return pair<int, int>{left.y, left.x} < pair<int, int>{right.y, right.x};
    });
    return units;
}
