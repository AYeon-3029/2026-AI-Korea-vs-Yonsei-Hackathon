"""깃발 대항전 전략 봇 v3.

전략 요약
1. 공개된 점수는 대칭 짝까지 함께 기억한다. 미공개 점수는 지역별 기댓값으로 추정한다.
2. 건물 가치 = 점수 + 기능 보너스. 적 소유 기능 건물(공학관·도서관·학생회관·병원·역)은
   상대가 누리는 효과를 빼앗는 '탈취 보너스'를 더한다.
3. 역 가치는 첫 턴 맵 분석으로 계산한다(역 경로로 본진→건물 거리가 얼마나 줄어드는가).
   아군 역이 2개 이상이면 TELE 로 병력을 전방으로 보낸다.
4. 깃발병(F)은 점령 후 곧바로 다음 목표로 이동하고, 적 전투병 위협 칸은 피한다.
   F 최소 인원을 먼저 확보해 전투병 군비 경쟁 중에도 재점령 인력을 잃지 않는다.
5. 전투병(W)은 적 깃발병의 다음 목표 건물을 예측해 적보다 먼저(또는 동시에) 도착하도록
   보내고, 점령 중인 아군 F 엄호, 위협받는 건물 경계, 남는 인원은 공성(적 건물·생산 거점 포위).
6. 정찰병은 쓰지 않는다.
"""
import json
import os
import sys
import traceback
from collections import deque

from protocol import BALANCE, DIRS, spawn, move, tele, priority, run

CFG = BALANCE
INF = 10 ** 9
F_COST = CFG["units"]["F"]["cost"]
TOTAL_TURNS = CFG["total_turns"]
TELE_MAX = CFG["tele"]["max_units"]
TELE_MIN_ST = CFG["tele"]["min_stations"]

# 튜닝 파라미터(오프라인 대전으로 조정)
P = {
    "center_expect": 3.0,      # 중앙 건물 미공개 점수 기댓값(2~4)
    "side_expect": 1.5,        # 신촌·안암 건물 미공개 점수 기댓값(1~2)
    "hall_bonus": 2.5,         # 학생회관 기능 가치(남은 턴 비율을 곱함)
    "depot_bonus": 3.0,        # 아직 받지 않은 보급소 보너스 가치
    "hosp_bonus": 1.0,         # 병원 전진 생산 가치(남은 턴 비율을 곱함)
    "eng_bonus": 0.5,
    "lib_bonus": 0.5,
    "watch_bonus": 0.2,
    "station_scale": 0.0,      # 역 가치 = 맵 분석 단축 칸수 합 × scale (실험 결과 0.08은 역효과)
    "station_cap": 4.0,
    "station_solo": 0.5,       # 짝 역이 없을 때 역 가치 반영 비율
    # 적 소유 건물 탈취 보너스(상대가 누리던 효과를 빼앗는 가치)
    "deny": {"ENG": 2.0, "LIBRARY": 1.5, "HALL": 2.0, "HOSPITAL": 1.0},
    "enemy_owned_mult": 1.3,   # 적 건물은 빼앗으면 상대 점수도 줄어든다
    "enemy_f_penalty": 0.3,    # 적 깃발병이 서 있는 건물(경합) 감점
    "dist_offset": 2.0,        # 가치 / (거리 + offset)
    "max_f": 7,                # 동시에 유지할 깃발병 상한
    "min_f": 3,                # 전투병보다 먼저 확보할 깃발병 수
    "min_w": 2,                # 3턴 이후 최소 전투병 수
    "w_margin": 1,             # 적 전투병 총수 대비 여유분
    "escort_radius": 2,        # 적 F 호위 전투병으로 볼 거리
    "predict_top": 2,          # 적 F 목표 후보 수(가까운 순)
    "late_penalty": 0.5,       # 제때 도착 못 하는 요격 가치 배율
    "guard_radius": 4,         # 적 유닛이 이 거리 안에 있는 아군 건물만 경계
    "siege_bld_bonus": 5.0,    # 공성 우선순위: 적 소유 건물
    "siege_ring_value": 2.0,   # 공성 우선순위: 적 생산 거점 둘레 칸
    "tele_min_gain": 2,        # TELE 가 일반 이동보다 이만큼 이상 가까워야 사용
    "use_tele": True,          # 역 경유 경로 탐색 + TELE (v4: 경로 탐색 수정 후 사용)
    "predict": False,          # 실험 스위치: 적 F 목표 예측 요격(False 면 v2 방식, 예측은 역효과)
    "pred_need_threat": False, # 예측 요격 인원에 목표 칸 위협도 반영
    "pred_deadline": True,     # 예측 요격에서 제때 도착 가능한 인원 우선
    "pred_chase": True,        # 예측 요격과 별도로 현재 위치 추격 작업 추가
    "chase_mult": 0.8,         # 추격 작업 가치 = 가장 가까운 목표 가치 × chase_mult
    "pred_mult": 1.0,          # 예측(선점) 작업 가치 배율
}

# 로컬 실험용: BOT_PARAMS='{"min_f": 0}' 처럼 파라미터를 덮어쓴다(제출 환경에서는 미설정)
if os.environ.get("BOT_PARAMS"):
    P.update(json.loads(os.environ["BOT_PARAMS"]))


# ------------------------------------------------------------------ 지형 전처리

class Geo:
    """격자 인덱스(i = y*W + x), 이웃, 전체 쌍 최단거리를 미리 계산한다."""

    def __init__(self, init):
        self.w, self.h = init.width, init.height
        n = self.w * self.h
        self.passable = [init.passable(i % self.w, i // self.w) for i in range(n)]
        self.nbrs = [[] for _ in range(n)]
        for i in range(n):
            if not self.passable[i]:
                continue
            x, y = i % self.w, i // self.w
            for d, (dx, dy) in DIRS.items():
                if init.passable(x + dx, y + dy):
                    self.nbrs[i].append((d, (y + dy) * self.w + x + dx))
        self.dist = [self._bfs(i) if self.passable[i] else None for i in range(n)]

    def _bfs(self, s):
        d = [INF] * (self.w * self.h)
        d[s] = 0
        q = deque([s])
        while q:
            u = q.popleft()
            for _, v in self.nbrs[u]:
                if d[v] == INF:
                    d[v] = d[u] + 1
                    q.append(v)
        return d

    def idx(self, x, y):
        return y * self.w + x

    def xy(self, i):
        return i % self.w, i // self.w

    def near(self, i):
        """i 자신과 한 칸 이웃(다음 턴에 i로 들어올 수 있는 칸)."""
        return [i] + [v for _, v in self.nbrs[i]]


class Memory:
    """턴을 넘어 유지하는 정보와 첫 턴 맵 분석 결과."""

    def __init__(self, init, geo):
        self.scores = {}          # 건물 id → 점수(공개 + 대칭 추론)
        self.depot_got = set()    # 내가 보너스를 받은 보급소 id
        pos = {(b["x"], b["y"]): b["id"] for b in init.buildings}
        self.mirror = {b["id"]: pos.get((geo.w - 1 - b["x"], geo.h - 1 - b["y"]), b["id"])
                       for b in init.buildings}
        lo, hi = CFG["regions"]["center"]
        self.central = {b["id"]: lo <= b["x"] <= hi for b in init.buildings}
        for b in init.buildings:
            if b["type"] == "PLAZA":
                self.scores[b["id"]] = CFG["buildings"]["plaza_score"]
        self.station_cells = [geo.idx(b["x"], b["y"]) for b in init.buildings if b["type"] == "STATION"]
        opp = "K" if init.team == "Y" else "Y"
        self.pair_gain = {t: self._pair_gains(init, geo, t) for t in (init.team, opp)}

    def _pair_gains(self, init, geo, team):
        """team 본진 기준, 역 짝 (a, b) 를 가졌을 때 본진→건물·적 본진 거리 단축 칸수 합.
        a→b 와 b→a 중 큰 값을 쓴다. 키는 정렬된 (a, b)."""
        base = geo.idx(*init.bases[team])
        opp_base = geo.idx(*init.bases["K" if team == "Y" else "Y"])
        goals = [geo.idx(b["x"], b["y"]) for b in init.buildings if b["type"] != "STATION"] + [opp_base]
        db = geo.dist[base]
        out = {}
        for a in self.station_cells:
            for b in self.station_cells:
                if a == b:
                    continue
                total = sum(max(0, db[t] - (db[a] + 1 + geo.dist[b][t])) for t in goals)
                key = (min(a, b), max(a, b))
                out[key] = max(out.get(key, 0), total)
        return out

    def station_worth(self, team, cell, owned_cells):
        """team 이 cell 역을 (추가로) 가질 때의 단축 가치.
        이미 가진 다른 역이 있으면 그 짝의 실제 가치, 없으면 최선 짝 가치의 절반."""
        gains = self.pair_gain[team]
        partners = [s for s in owned_cells if s != cell]
        if partners:
            g = max(gains[(min(cell, s), max(cell, s))] for s in partners)
        else:
            g = P["station_solo"] * max((v for k, v in gains.items() if cell in k), default=0)
        return min(P["station_cap"], g * P["station_scale"])


GEO = None
MEM = None


# ------------------------------------------------------------------ 의사결정

def decide(view, init):
    global GEO, MEM
    if GEO is None:
        GEO = Geo(init)
        MEM = Memory(init, GEO)
    geo, mem = GEO, MEM
    me, opp = view.team, view.opp
    remain = (TOTAL_TURNS - view.turn + 1) / TOTAL_TURNS

    # 1. 점수 기억(대칭 포함), 보급소 수령 기록
    for b in view.buildings:
        if b["score"] >= 0:
            mem.scores[b["id"]] = b["score"]
            mem.scores[mem.mirror[b["id"]]] = b["score"]
        if b["type"] == "DEPOT" and b["owner"] == me:
            mem.depot_got.add(b["id"])

    bld = {geo.idx(b["x"], b["y"]): b for b in view.buildings}

    def score_of(b):
        if b["id"] in mem.scores:
            return mem.scores[b["id"]]
        return P["center_expect"] if mem.central[b["id"]] else P["side_expect"]

    def value(b):
        v = score_of(b)
        t = b["type"]
        if t == "HALL":
            v += P["hall_bonus"] * remain
        elif t == "DEPOT" and b["id"] not in mem.depot_got:
            v += P["depot_bonus"]
        elif t == "HOSPITAL":
            v += P["hosp_bonus"] * remain
        elif t == "ENG":
            v += P["eng_bonus"]
        elif t == "LIBRARY":
            v += P["lib_bonus"]
        elif t == "WATCH":
            v += P["watch_bonus"]
        elif t == "STATION":
            c = geo.idx(b["x"], b["y"])
            v += mem.station_worth(me, c, owned(me, "STATION"))
        if b["owner"] == opp:
            deny = P["deny"].get(t, 0)
            if t in ("HALL", "HOSPITAL"):
                deny *= remain
            elif t == "STATION":
                # 적이 짝을 이룬 역이면 그 수송로를 끊는 가치
                c = geo.idx(b["x"], b["y"])
                others = [s for s in owned(opp, "STATION") if s != c]
                deny = mem.station_worth(opp, c, others) if others else 0
            v += deny
        return v

    # 2. 유닛 집계: cell → count
    myF, myW, enF, enW = {}, {}, {}, {}
    for u in view.units:
        i = geo.idx(u["x"], u["y"])
        table = {("F", True): myF, ("W", True): myW, ("F", False): enF, ("W", False): enW}.get(
            (u["kind"], u["team"] == me))
        if table is not None:
            table[i] = table.get(i, 0) + u["count"]

    def owned(team, btype):
        return [i for i, b in bld.items() if b["owner"] == team and b["type"] == btype]

    def w_cost(team):
        floor = CFG["buildings"]["eng_cost_floor"]
        disc = len(owned(team, "ENG")) * CFG["buildings"]["eng_discount_per"]
        return max(floor, CFG["units"]["W"]["cost"] - disc)

    base_me = geo.idx(*init.bases[me])
    base_opp = geo.idx(*init.bases[opp])
    spawn_me = [base_me] + owned(me, "HOSPITAL")
    spawn_opp = [base_opp] + owned(opp, "HOSPITAL")
    my_stations = owned(me, "STATION")
    can_tele = P["use_tele"] and len(my_stations) >= TELE_MIN_ST

    # 3. 위협 지도: 다음 턴 각 칸에 도달 가능한 적 전투병 수(생산 가능분 포함)
    threat = [0] * (geo.w * geo.h)
    for i, c in enW.items():
        for j in geo.near(i):
            threat[j] += c
    opp_spawnable = view.opp_resource // w_cost(opp)
    if opp_spawnable:
        cells = set()
        for s in spawn_opp:
            cells.update(geo.near(s))
        for j in cells:
            threat[j] += opp_spawnable

    commands = []

    # 4. 생산 결정
    my_w_cost = w_cost(me)
    income = CFG["resource"]["base_income"] + CFG["resource"]["hall_bonus"] * len(owned(me, "HALL"))
    has_lib = bool(owned(me, "LIBRARY"))

    def cap_cost(b):
        c = CFG["capture"]["capture_cost"]
        if b["type"] == "PLAZA":
            c *= CFG["capture"]["plaza_multiplier"]
        if has_lib:
            c -= CFG["buildings"]["library_discount"]
        return max(CFG["capture"]["min_capture_cost"], c)

    # 이번 턴 점령할 수 있는 건물(아군 F가 올라가 있거나 한 칸 옆) 비용 합 - 수입
    reachable = set()
    for i in myF:
        for j in geo.near(i):
            if j in bld and bld[j]["owner"] != me:
                reachable.add(j)
    reserve = max(0, sum(cap_cost(bld[j]) for j in reachable) - income)
    budget = max(0, view.my_resource - reserve)

    targets_all = [i for i, b in bld.items() if b["owner"] != me]
    n_myF, n_myW = sum(myF.values()), sum(myW.values())
    n_enW = sum(enW.values())
    des_F = min(P["max_f"], len(targets_all))
    min_F = min(P["min_f"], des_F)
    des_W = max(P["min_w"] if view.turn > 3 else 0, n_enW + P["w_margin"], len(enF))
    nF = nW = 0
    while True:
        wantW = n_myW + nW < des_W
        wantF = n_myF + nF < des_F
        needF = n_myF + nF < min_F          # 재점령 인력은 군비 경쟁보다 먼저
        behind = n_myW + nW <= n_enW
        if needF:
            if budget < F_COST:
                break                        # 깃발병 비용을 모은다
            nF += 1
            budget -= F_COST
        elif wantW and (behind or not wantF) and budget >= my_w_cost:
            nW += 1
            budget -= my_w_cost
        elif wantF and budget >= F_COST:
            nF += 1
            budget -= F_COST
        elif wantW and budget >= my_w_cost:
            nW += 1
            budget -= my_w_cost
        else:
            break
    # 다음 턴 상한(40) 초과로 버려질 자원은 전투병으로 바꾼다
    cap = CFG["resource"]["resource_cap"]
    while budget >= my_w_cost and budget + income > cap:
        nW += 1
        budget -= my_w_cost

    def best_spawn(goals):
        if not goals:
            return base_me
        return min(spawn_me, key=lambda s: (min(geo.dist[s][g] for g in goals), s != base_me))

    def emit_spawn(kind, n, cell, table):
        if n <= 0:
            return
        if cell == base_me:
            commands.append(spawn(kind, n))
        else:
            commands.append(spawn(kind, n, *geo.xy(cell)))
        table[cell] = table.get(cell, 0) + n

    emit_spawn("F", nF, best_spawn(targets_all), myF)
    emit_spawn("W", nW, best_spawn(list(enF) or [base_opp]), myW)

    # 5. 이동 도우미(일반 이동 + 역 순간이동)
    moves = {}
    tele_cmds = []
    tele_state = {"used": False}

    def add_move(i, kind, n, d):
        key = (i, kind, d)
        moves[key] = moves.get(key, 0) + n

    def step_toward(i, goal, safe=None):
        """goal 쪽 최단 경로 다음 (방향, 칸). safe 가 주어지면 안전한 칸을 우선한다."""
        if i == goal or geo.dist[i][goal] >= INF:
            return None
        cur = geo.dist[i][goal]
        options = [(d, v) for d, v in geo.nbrs[i] if geo.dist[v][goal] == cur - 1]
        if safe is not None:
            good = [(d, v) for d, v in options if safe(v)]
            if good:
                return good[0]
            if safe(i):
                return None          # 안전한 경로가 없으면 제자리 대기
            side = [(d, v) for d, v in geo.nbrs[i] if safe(v)]
            return side[0] if side else (options[0] if options else None)
        return options[0] if options else None

    def tele_route(i, goal, safe=None):
        """역 경유 최선 경로 (총 턴 수, 출발 역 a, 도착 역 b). 걸어가기보다
        tele_min_gain 이상 빠르지 않으면 None. 총 턴 = i→a 걷기 + TELE 1턴 + b→goal 걷기."""
        if not can_tele or i == goal:
            return None
        direct = geo.dist[i][goal]
        best = None
        for a in my_stations:
            da = geo.dist[i][a]
            if da >= INF:
                continue
            for b in my_stations:
                if b == a or (safe is not None and not safe(b)):
                    continue
                via = da + 1 + geo.dist[b][goal]
                if best is None or via < best[0]:
                    best = (via, a, b)
        if best is None or best[0] > direct - P["tele_min_gain"]:
            return None
        return best

    def eff_dist(i, goal):
        """역 순간이동을 고려한 거리(목표 선택용)."""
        r = tele_route(i, goal)
        return min(geo.dist[i][goal], r[0]) if r else geo.dist[i][goal]

    def walk(i, kind, n, goal, safe, out):
        st = step_toward(i, goal, safe)
        if st is None:
            out.append((i, n))
        else:
            add_move(i, kind, n, st[0])
            out.append((st[1], n))

    def advance(i, kind, n, goal, safe=None):
        """n 명을 goal 쪽으로 보내고 [(도착 칸, 인원)] 을 돌려준다.
        역 경유가 빠르면 출발 역으로 걷고, 출발 역 위에서는 TELE(턴당 1회·최대 5명)한다."""
        out = []
        r = tele_route(i, goal, safe)
        if r is None:
            walk(i, kind, n, goal, safe, out)
            return out
        via, a, b = r
        if i != a:
            walk(i, kind, n, a, safe, out)       # 출발 역으로 이동
            return out
        if not tele_state["used"]:
            k = min(n, TELE_MAX)
            tele_cmds.append(tele(*geo.xy(i), kind, k, *geo.xy(b)))
            tele_state["used"] = True
            out.append((b, k))
            n -= k
        if n > 0:
            # 이번 턴 TELE 를 못 쓰면: 한 턴 기다렸다 TELE 하는 편이 여전히 빠르면 대기
            if 2 + geo.dist[b][goal] <= geo.dist[i][goal] - P["tele_min_gain"]:
                out.append((i, n))
            else:
                walk(i, kind, n, goal, safe, out)
        return out

    # 6. 전투병 배치
    w_pool = dict(myW)                 # 아직 명령받지 않은 전투병
    cover = [0] * (geo.w * geo.h)      # 이동 후 칸별 아군 전투병 수

    def send_w(g, need, stage_dist, deadline=INF):
        """w_pool 에서 g 에 가까운 순으로 need 명을 보낸다.
        deadline 안에 도착할 수 있는 인원만으로 need 를 채울 수 있으면 그 인원만 쓴다.
        모인 인원이 need 에 못 미치면 stage_dist 칸 밖에서 대기하며 모은다."""
        near_ws = sorted((eff_dist(i, g), i) for i, c in w_pool.items() if c > 0 and geo.dist[i][g] < INF)
        timely = [(d, i) for d, i in near_ws if d <= deadline]
        if deadline < INF and sum(w_pool[i] for _, i in timely) >= need:
            near_ws = timely
        enough = sum(w_pool[i] for _, i in near_ws) >= need
        left = need
        for d, i in near_ws:
            if left <= 0:
                break
            n = min(left, w_pool[i])
            w_pool[i] -= n
            left -= n
            if not enough and d <= stage_dist:
                cover[i] += n
                continue
            for dest, k in advance(i, "W", n, g):
                cover[dest] += k

    def w_eta(g):
        """g 까지 가장 가까운 대기 전투병의 거리."""
        return min((geo.dist[i][g] for i, c in w_pool.items() if c > 0), default=INF)

    # 적 깃발병 요격: 다음 목표 건물을 예측해 적보다 먼저(또는 동시에) 도착한다
    jobs = []  # (가치, 목표 칸, 필요 인원, 도착 기한, 집결 거리)
    for e, c in enF.items():
        if not P["predict"]:
            # v2 방식: 가장 가까운 비적 건물 + 현재 위치
            cands = [i for i, b in bld.items() if b["owner"] != opp and enF.get(i, 0) == 0]
            g = e if (e in bld and bld[e]["owner"] != opp) else (
                min(cands, key=lambda i: geo.dist[e][i]) if cands else e)
            worth = 2.0 + (value(bld[g]) if g in bld else 0) + (1.0 if g in bld and bld[g]["owner"] == me else 0)
            jobs.append((worth, g, threat[g] + 1, INF, -1))
            if g != e:
                jobs.append((worth * 0.8, e, threat[e] + 1, INF, -1))
            continue
        escort = sum(n for j, n in enW.items() if geo.dist[e][j] <= P["escort_radius"])
        need = escort + 1
        if e in bld and bld[e]["owner"] != opp:
            # 이미 건물 위: 점령·중립화 진행 중이므로 곧바로 제거
            worth = 3.0 + value(bld[e]) + (1.5 if bld[e]["owner"] == me else 0)
            jobs.append((worth, e, max(need, threat[e] + 1), INF, -1))
            continue
        cands = [i for i, b in bld.items() if b["owner"] != opp and enF.get(i, 0) == 0]
        cands.sort(key=lambda i: geo.dist[e][i])
        if P["pred_chase"] and cands:
            g0 = cands[0]
            chase = (2.0 + value(bld[g0]) + (1.0 if bld[g0]["owner"] == me else 0)) * P["chase_mult"]
            jobs.append((chase, e, max(need, threat[e] + 1), INF, -1))   # 적 F 직접 추격
        for rank, g in enumerate(cands[:P["predict_top"]]):
            ta = geo.dist[e][g]
            # 아군 건물은 중립화(1턴) 뒤 점령되므로 한 턴 여유가 있다
            deadline = ta + (1 if bld[g]["owner"] == me else 0)
            worth = P["pred_mult"] * (2.0 + value(bld[g]) + (1.5 if bld[g]["owner"] == me else 0)) / (1 + rank)
            if w_eta(g) > deadline:
                worth *= P["late_penalty"]
            gneed = max(need, threat[g] + 1) if P["pred_need_threat"] else need
            jobs.append((worth, g, gneed, deadline if P["pred_deadline"] else INF, -1))
    # 점령 중인 아군 깃발병 엄호(한 칸 이내 인원만 의미 있음)
    for i, c in myF.items():
        if i in bld and bld[i]["owner"] != me and threat[i] > 0:
            jobs.append((value(bld[i]) + 3.0, i, threat[i] + 1, 1, INF))
    jobs.sort(key=lambda j: -j[0])

    done_goals = set()
    for worth, g, need, deadline, stage in jobs:
        if g in done_goals:
            continue
        pool = sum(c for i, c in w_pool.items() if c > 0 and geo.dist[i][g] <= deadline)
        if deadline <= 1 and pool < need:
            continue
        done_goals.add(g)
        send_w(g, need, stage, deadline)

    # 경계조: 적 유닛이 가까운 아군 건물에만 인원을 둔다
    enemy_cells = list(enF) + list(enW)
    guard_posts = []
    for p, b in bld.items():
        if b["owner"] != me or p in done_goals:
            continue
        danger = min((geo.dist[p][e] for e in enemy_cells), default=INF)
        if danger <= P["guard_radius"]:
            guard_posts.append((value(b), p))
    for _, p in sorted(guard_posts, reverse=True):
        if not any(c > 0 for c in w_pool.values()):
            break
        send_w(p, max(1, threat[p]), 0)

    # 공성조: 적 소유 건물 장악 → 적 생산 거점(본진·병원)과 그 둘레 포위
    siege = []
    for i, b in bld.items():
        if b["owner"] == opp:
            siege.append((P["siege_bld_bonus"] + value(b), i))
    ring = set()
    for s in spawn_opp:
        ring.update(geo.near(s))
    for c in ring:
        if c not in bld or bld[c]["owner"] != opp:
            siege.append((P["siege_ring_value"], c))
    siege.sort(key=lambda t: (-t[0], t[1]))
    for _, g in siege:
        if not any(c > 0 for c in w_pool.values()):
            break
        send_w(g, threat[g] + 1, 2)

    # 그래도 남은 전투병은 가장 가치 높은 공성 목표에 합류
    if siege:
        top = siege[0][1]
        for i in sorted(w_pool):
            if w_pool[i] > 0:
                send_w(top, w_pool[i], -1)

    # 7. 깃발병 배치
    def safe(v):
        return threat[v] == 0 or cover[v] > threat[v]

    f_units = []          # 명령을 기다리는 깃발병 1명 단위(칸)
    holding = set()       # 이번 턴 점령을 위해 머무는 건물
    for i, c in myF.items():
        if i in bld and bld[i]["owner"] != me and safe(i) and enF.get(i, 0) == 0:
            holding.add(i)
            if c > 1:
                f_units.extend([i] * (c - 1))
        else:
            f_units.extend([i] * c)

    targets = {}
    for i in targets_all:
        if i in holding:
            continue
        v = value(bld[i])
        if bld[i]["owner"] == opp:
            v *= P["enemy_owned_mult"]
        if enF.get(i, 0) and cover[i] <= threat[i]:
            v *= P["enemy_f_penalty"]
        targets[i] = v

    final_F = {i: 1 for i in holding}
    free_units = list(f_units)
    while free_units and targets:
        best = None
        for k, u in enumerate(free_units):
            du = geo.dist[u]
            for t, v in targets.items():
                d = du[t]
                if d >= INF:
                    continue
                if can_tele:
                    d = eff_dist(u, t)
                s = v / (d + P["dist_offset"])
                if best is None or s > best[0]:
                    best = (s, k, t)
        if best is None:
            break
        _, k, t = best
        u = free_units.pop(k)
        del targets[t]
        for dest, n in advance(u, "F", 1, t, safe):
            final_F[dest] = final_F.get(dest, 0) + n

    # 목표가 없는 깃발병: 위협받으면 피하고 아니면 대기
    for u in free_units:
        if not safe(u):
            side = [(d, v) for d, v in geo.nbrs[u] if safe(v)]
            if side:
                add_move(u, "F", 1, side[0][0])
                continue
        final_F[u] = final_F.get(u, 0) + 1

    commands.extend(tele_cmds)
    for (i, kind, d), n in moves.items():
        x, y = geo.xy(i)
        commands.append(move(x, y, kind, n, d))

    # 8. 점령 우선순위: 이번 턴 깃발병이 올라갈 건물을 가치 순으로
    caps = [i for i in final_F if i in bld and bld[i]["owner"] != me]
    if caps:
        caps.sort(key=lambda i: -value(bld[i]))
        commands.append(priority([geo.xy(i) for i in caps]))
    return commands


_errors = 0


def safe_decide(view, init):
    """예외가 나도 END는 출력되도록(몰수패 방지) 빈 명령으로 대체한다."""
    global _errors
    try:
        return decide(view, init)
    except Exception:
        _errors += 1
        if _errors <= 5:
            traceback.print_exc(file=sys.stderr)
        return []


if __name__ == "__main__":
    run(safe_decide)
