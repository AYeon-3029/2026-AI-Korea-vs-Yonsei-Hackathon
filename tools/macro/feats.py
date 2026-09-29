"""방침 선택 모형의 입력 특징.

map_features: 첫 턴(INIT)에 봇이 아는 정보만 쓴다 — 지형, 건물 종류·위치, 본진. 점수는 광장 외 비공개라 쓰지 않는다.
  같은 함수(map_feats_raw)를 봇에 그대로 옮겨 쓸 수 있도록 엔진 객체에 의존하지 않는 부분을 분리했다.
state_features: 경기 중 판세(분기 턴 t 의 상태).
"""
from __future__ import annotations

from collections import deque

W = H = 15
TYPES = ["HALL", "LIBRARY", "ENG", "HOSPITAL", "STATION", "WATCH", "DEPOT", "PLAZA"]


def _bfs(passable, s):
    d = [99] * (W * H)
    d[s] = 0
    q = deque([s])
    while q:
        u = q.popleft()
        x, y = u % W, u // W
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H:
                v = ny * W + nx
                if passable[v] and d[v] == 99:
                    d[v] = d[u] + 1
                    q.append(v)
    return d


def map_feats_raw(passable, buildings, my_base, opp_base):
    """passable: 225 bool, buildings: [(type, x, y)], my_base/opp_base: (x, y). → 특징 dict (이름 → 실수).

    진영 대칭 맵이므로 '내 쪽' 건물 = 내 본진에 더 가까운 쪽 짝(동률이면 x 기준)으로 정한다.
    """
    mb, ob = my_base[1] * W + my_base[0], opp_base[1] * W + opp_base[0]
    dm, do = _bfs(passable, mb), _bfs(passable, ob)
    f = {"base_dist": dm[ob] / 20.0}
    adv_all, contested, n = 0.0, 0, 0
    for t in TYPES:
        cells = [y * W + x for (bt, x, y) in buildings if bt == t]
        if not cells:
            continue
        near = min(dm[c] for c in cells)
        f[f"d_{t}"] = near / 15.0                                  # 내 본진에서 그 종류 중 가장 가까운 것
        f[f"race_{t}"] = max((do[c] - dm[c]) for c in cells) / 10.0  # 그 종류에서 내가 가장 앞서는 정도
    for (bt, x, y) in buildings:
        c = y * W + x
        adv = do[c] - dm[c]
        n += 1
        adv_all += abs(adv)
        contested += abs(adv) <= 2
    f["contested"] = contested / max(1, n)                          # 양쪽 도착 차 2 이하 건물 비율(격전지 수)
    f["spread"] = adv_all / max(1, n) / 10.0
    # 중앙 개방도: 중앙 5×5 의 통과 가능 칸 비율, 본진 간 최단 경로 수 근사(두 본진 거리 합이 최단인 칸 수)
    f["center_open"] = sum(passable[y * W + x] for y in range(5, 10) for x in range(5, 10)) / 25.0
    f["paths"] = sum(1 for i in range(W * H) if passable[i] and dm[i] + do[i] == dm[ob]) / 30.0
    # 건물 밀도: 내 본진 6칸 안 건물 수, 중앙 건물까지 평균 거리
    f["home_bld"] = sum(1 for (bt, x, y) in buildings if dm[y * W + x] <= 6) / 6.0
    cen = [dm[y * W + x] for (bt, x, y) in buildings if 5 <= x <= 9]
    f["center_mean"] = (sum(cen) / len(cen) / 15.0) if cen else 0.0
    return f


def map_features(state, side):
    opp = "K" if side == "Y" else "Y"
    passable = [state.terrain[i // W][i % W] != "#" for i in range(W * H)]
    blds = [(b.btype, b.x, b.y) for b in state.buildings.values()]
    return map_feats_raw(passable, blds, state.bases[side], state.bases[opp])


def state_features(state, side):
    opp = "K" if side == "Y" else "Y"
    f = {"turn": state.turn / 160.0}
    sc = {side: 0, opp: 0}
    nb = {side: 0, opp: 0}
    eco = {side: 0, opp: 0}
    for b in state.buildings.values():
        if b.owner in sc:
            sc[b.owner] += b.score
            nb[b.owner] += 1
            eco[b.owner] += b.btype in ("ENG", "HALL")
    units = {(side, "F"): 0, (side, "W"): 0, (opp, "F"): 0, (opp, "W"): 0}
    fwd = {side: 0, opp: 0}
    mb, ob = state.bases[side], state.bases[opp]
    for (x, y, t, k), c in state.units.items():
        if (t, k) in units:
            units[(t, k)] += c
        if k == "W":
            # 상대 본진 쪽 절반에 있는 W(전진 병력)
            dmy = abs(x - mb[0]) + abs(y - mb[1])
            dop = abs(x - ob[0]) + abs(y - ob[1])
            if (t == side and dop < dmy) or (t == opp and dmy < dop):
                fwd[t] += c
    occ = state.occupation_score_turns
    f.update({
        "score_me": sc[side] / 20.0, "score_opp": sc[opp] / 20.0, "score_diff": (sc[side] - sc[opp]) / 10.0,
        "bld_me": nb[side] / 10.0, "bld_opp": nb[opp] / 10.0, "eco_me": eco[side] / 2.0, "eco_opp": eco[opp] / 2.0,
        "occ_diff": (occ.get(side, 0) - occ.get(opp, 0)) / max(1, state.turn) / 10.0,
        "f_me": units[(side, "F")] / 5.0, "f_opp": units[(opp, "F")] / 5.0,
        "w_me": units[(side, "W")] / 20.0, "w_opp": units[(opp, "W")] / 20.0,
        "fwd_me": fwd[side] / 10.0, "fwd_opp": fwd[opp] / 10.0,
        "res_me": state.resources[side] / 40.0, "res_opp": state.resources[opp] / 40.0,
    })
    return f
