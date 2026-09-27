"""예제의 너비 우선 탐색과 점령 자원 예약."""
from collections import deque
from protocol import DIRS, BALANCE

def directions(init):
    """같은 거리라면 자기 본진 기준의 고정 방향 순서로 결정한다."""
    order = ("U", "D", "L", "R")
    flip = {"U": "D", "D": "U", "L": "R", "R": "L"}
    return tuple(flip[d] for d in order) if init.bases[init.team][0] * 2 > init.width - 1 else order


def bfs(start, targets, init):
    """너비 우선 탐색은 가까운 칸부터 방문하여 가장 가까운 목표의 첫 이동을 찾는다."""
    if start in targets:
        return None
    queue = deque([(start, None)])
    seen = {start}
    while queue:
        (x, y), first = queue.popleft()
        for direction in directions(init):
            dx, dy = DIRS[direction]
            pos = (x + dx, y + dy)
            if pos in seen or not init.passable(*pos):
                continue
            step = first or direction
            if pos in targets:
                return step
            seen.add(pos)
            queue.append((pos, step))
    return None


def capture_reserve(view):
    """점령 비용을 남겨 생산이 점령을 방해하지 않게 한다."""
    cfg = BALANCE
    owns = any(b["type"] == "LIBRARY" and b["owner"] == view.team for b in view.buildings)
    base = cfg["capture"]["capture_cost"]
    costs = [base]
    for u in view.my_units("F"):
        b = view.building_at(u["x"], u["y"])
        if b and b["owner"] != view.team:
            cost = base * (cfg["capture"]["plaza_multiplier"] if b["type"] == "PLAZA" else 1)
            costs.append(
                max(
                    cfg["capture"]["min_capture_cost"],
                    cost - (cfg["buildings"]["library_discount"] if owns else 0),
                )
            )
    return max(costs)



