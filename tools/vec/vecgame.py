"""GPU 벡터화 게임 엔진 — 공식 엔진(`engine/pipeline.py`)과 같은 규칙으로 수천 판을 한꺼번에 진행한다(자기대전 학습용).

강화학습 정책(`Model/sparring/rlbot`)이 쓰는 명령만 지원한다: 본진 생산(F·W), F·W 1칸 이동. 순간이동·정찰병·병원 생산·
PRIORITY 는 쓰지 않으므로 없다. 점령 순서(공개 점수 내림차순 → 본진 기준 좌표), 도서관 할인 스냅샷, 보급소 보너스 후지급,
중립화 표시 노후화, 즉시 승리·타이브레이커는 공식 엔진과 같다. `tools/vec/test_engine.py` 가 공식 엔진과 턴마다 대조한다.

좌표: 텐서는 [y, x]. 팀 0 = Y(본진 왼쪽), 1 = K(점대칭). 관측·행동은 각 팀 frame(K 는 180° 회전)이며 `enc.encode` 와 같다.
"""
from __future__ import annotations

import numpy as np
import torch

TYPES = ["PLAZA", "HALL", "ENG", "HOSPITAL", "LIBRARY", "DEPOT", "STATION", "WATCH"]
T = {t: i for i, t in enumerate(TYPES)}
H = W = 15
NB = 17
C = 30
F_CHOICES = [0, 1, 2]
W_FRACS = [0.0, 1 / 3, 2 / 3, 1.0]
# 이동 방향 U·D·L·R 별 (출발 칸, 도착 칸, 맵 밖으로 나가는 칸) 슬라이스 — 마지막 두 축 [y, x]
MOVES = (
    (np.s_[1:, :], np.s_[:-1, :], np.s_[:1, :]),
    (np.s_[:-1, :], np.s_[1:, :], np.s_[-1:, :]),
    (np.s_[:, 1:], np.s_[:, :-1], np.s_[:, :1]),
    (np.s_[:, :-1], np.s_[:, 1:], np.s_[:, -1:]),
)


# ---------------------------------------------------------------------------- 맵

def map_arrays(gstates):
    """공식 GameState 목록(초기 상태) → 정적 맵 배열(numpy)."""
    n = len(gstates)
    out = {
        "passable": np.zeros((n, H, W), bool),
        "by": np.zeros((n, NB), np.int64), "bx": np.zeros((n, NB), np.int64),
        "btype": np.zeros((n, NB), np.int64), "bscore": np.zeros((n, NB), np.int64),
        "base": np.zeros((n, 2, 2), np.int64),              # [팀][y, x]
    }
    for i, s in enumerate(gstates):
        for y in range(H):
            for x in range(W):
                out["passable"][i, y, x] = s.terrain[y][x] != "#"
        for j, b in enumerate(s.sorted_buildings()):
            out["bx"][i, j], out["by"][i, j] = b.x, b.y
            out["btype"][i, j] = T[b.btype]
            out["bscore"][i, j] = b.score
        for t, team in enumerate("YK"):
            out["base"][i, t] = (s.bases[team][1], s.bases[team][0])
    return out


def gen_maps(seeds, workers=16):
    from concurrent.futures import ProcessPoolExecutor
    chunks = [seeds[i::workers] for i in range(workers)]
    with ProcessPoolExecutor(workers) as ex:
        parts = list(ex.map(_gen_chunk, chunks))
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def _gen_chunk(seeds):
    from engine.config import load_config
    from mapgen import generate, to_state
    cfg = load_config()
    return map_arrays([to_state(generate(s, cfg)) for s in seeds])


# ---------------------------------------------------------------------------- 게임 묶음

class VecGame:
    def __init__(self, maps, n, device, rng=None):
        """maps: map_arrays 결과(맵 풀). n 판을 동시에 진행한다. 끝난 판은 reset(idx) 로 풀의 새 맵에서 다시 시작."""
        self.dev = device
        self.n = n
        self.pool = {k: torch.as_tensor(v, device=device) for k, v in maps.items()}
        self.npool = len(maps["btype"])
        self.g = rng or torch.Generator(device="cpu").manual_seed(0)
        z = lambda *s, dt=torch.int64: torch.zeros(*s, dtype=dt, device=device)  # noqa: E731
        self.units = z(n, 2, 2, H, W, dt=torch.int32)            # [팀, 병종 F/W]
        self.owner = z(n, NB) - 1
        self.stage = z(n, NB)
        self.res = z(n, 2)
        self.revealed = z(n, 2, NB, dt=torch.bool)
        self.depot = z(n, 2, NB, dt=torch.bool)
        self.occ = z(n, 2)
        self.turn = z(n)
        self.map_id = z(n)
        self.reset(torch.arange(n, device=device))

    # -------------------------------------------------------------- 초기화
    def reset(self, idx, map_ids=None):
        if len(idx) == 0:
            return
        if map_ids is None:
            map_ids = torch.randint(0, self.npool, (len(idx),), generator=self.g).to(self.dev)
        self.map_id[idx] = map_ids
        self.units[idx] = 0
        self.owner[idx] = -1
        self.stage[idx] = 0
        self.res[idx] = 10
        self.revealed[idx] = False
        self.depot[idx] = False
        self.occ[idx] = 0
        self.turn[idx] = 0
        self._static()

    def _static(self):
        P = self.pool
        m = self.map_id
        self.passable = P["passable"][m]
        self.btype = P["btype"][m]
        self.bscore = P["bscore"][m]
        self.bcell = P["by"][m] * W + P["bx"][m]
        self.base = P["base"][m]
        self.base_cell = self.base[..., 0] * W + self.base[..., 1]          # (n, 2)
        by, bx = P["by"][m], P["bx"][m]
        # 본진 기준 정규화 좌표 순위(점령 동률 처리): 팀 0 은 (y, x), 팀 1 은 180° 회전
        key0 = by * W + bx
        key1 = (H - 1 - by) * W + (W - 1 - bx)
        self.home_rank = torch.stack([key0.argsort(1).argsort(1), key1.argsort(1).argsort(1)], 1)
        # 대칭 짝 건물(점대칭 위치)
        cell = self.bcell
        mir = (H - 1 - by) * W + (W - 1 - bx)
        self.pair = (mir.unsqueeze(2) == cell.unsqueeze(1)).float().argmax(2)
        # 건물 간 체비셰프 거리 ≤ 3 (감시 거점 공개 범위)
        d = torch.maximum((by.unsqueeze(2) - by.unsqueeze(1)).abs(), (bx.unsqueeze(2) - bx.unsqueeze(1)).abs())
        self.near3 = d <= 3
        self.total = self.bscore.sum(1)

    STATE_KEYS = ("units", "owner", "stage", "res", "revealed", "depot", "occ", "turn", "map_id")

    def snapshot(self, idx):
        """판 idx 들의 동적 상태 복사본(탐색용)."""
        return {k: getattr(self, k)[idx].clone() for k in self.STATE_KEYS}

    def restore(self, st, rep=1):
        """snapshot 상태를 판마다 rep 번씩 반복해 이 묶음 전체에 넣는다(판 수 = 상태 수 × rep)."""
        for k in self.STATE_KEYS:
            getattr(self, k).copy_(st[k].repeat_interleave(rep, 0))
        self._static()

    def load_states(self, gstates):
        """공식 GameState(임의 시점) → 이 묶음(테스트용). 맵 풀은 같은 순서의 맵이어야 한다."""
        for i, s in enumerate(gstates):
            self.map_id[i] = i
        self._static()
        self.units.zero_()
        for i, s in enumerate(gstates):
            for (x, y, team, kind), c in s.units.items():
                if kind in "FW":
                    self.units[i, "YK".index(team), "FW".index(kind), y, x] = c
            for j, b in enumerate(s.sorted_buildings()):
                self.owner[i, j] = -1 if b.owner == "N" else "YK".index(b.owner)
                self.stage[i, j] = b.stage
                for t, team in enumerate("YK"):
                    self.revealed[i, t, j] = b.id in s.revealed[team]
                    self.depot[i, t, j] = team in s.depot_claimed.get(b.id, set())
            for t, team in enumerate("YK"):
                self.res[i, t] = s.resources[team]
                self.occ[i, t] = s.occupation_score_turns[team]
            self.turn[i] = s.turn

    # -------------------------------------------------------------- 관측
    def owned_count(self, team, btype):
        return ((self.owner == team) & (self.btype == T[btype])).sum(1)

    def wcost(self, team):
        return torch.clamp(3 - self.owned_count(team, "ENG"), min=2)

    def observe(self, team):
        """(obs (n,C,H,W) float32, cnt (n,2,H,W) int, valid (n,4,H,W) bool) — 팀 frame. enc.encode 와 같다."""
        n, dev = self.n, self.dev
        me, op = team, 1 - team
        obs = torch.zeros(n, C, H * W, device=dev)
        ar = torch.arange(n, device=dev).unsqueeze(1).expand(n, NB)
        cell = self.bcell
        obs[:, 0] = self.passable.view(n, -1).float()
        obs[torch.arange(n), 1, self.base_cell[:, me]] = 1
        obs[torch.arange(n), 2, self.base_cell[:, op]] = 1
        obs[ar, 3 + self.btype, cell] = 1
        mine, neutral = self.owner == me, self.owner == -1
        obs[ar, 11, cell] = mine.float()
        obs[ar, 12, cell] = (~mine & ~neutral).float()
        obs[ar, 13, cell] = neutral.float()
        obs[ar, 14, cell] = (neutral & (self.stage == 1)).float()
        rev = self.revealed[:, me]
        obs[ar, 15, cell] = torch.where(rev, self.bscore.float() / 4, 0.0)
        obs[ar, 16, cell] = (~rev).float()
        u = self.units.view(n, 2, 2, -1).float()
        obs[:, 17] = u[:, me, 0] / 4
        obs[:, 18] = u[:, me, 1] / 10
        obs[:, 19] = u[:, op, 0] / 4
        obs[:, 20] = u[:, op, 1] / 10
        obs[:, 23] = ((self.turn + 1).float() / 160).unsqueeze(1)
        obs[:, 24] = (self.res[:, me].float() / 40).unsqueeze(1)
        obs[:, 25] = (self.res[:, op].float() / 40).unsqueeze(1)
        obs[:, 26] = (self.owned_count(me, "ENG").float() / 2).unsqueeze(1)
        obs[:, 27] = (self.owned_count(op, "ENG").float() / 2).unsqueeze(1)
        known = rev | rev.gather(1, self.pair)
        obs[ar, 28, cell] = torch.where(known, self.bscore.float() / 4, 0.0)
        obs[ar, 29, cell] = known.float()
        obs = obs.view(n, C, H, W)
        cnt = self.units[:, me].clone()
        pas = self.passable
        valid = torch.zeros(n, 4, H, W, dtype=torch.bool, device=dev)
        # 실제 좌표 기준 이동 가능(U,D,L,R) 후 frame 변환
        valid[:, 0, 1:, :] = pas[:, :-1, :]
        valid[:, 1, :-1, :] = pas[:, 1:, :]
        valid[:, 2, :, 1:] = pas[:, :, :-1]
        valid[:, 3, :, :-1] = pas[:, :, 1:]
        if team == 1:
            obs, cnt = obs.flip(-2, -1), cnt.flip(-2, -1)
            valid = valid.flip(-2, -1)[:, [1, 0, 3, 2]]        # 회전하면 U↔D, L↔R
        return obs, cnt, valid

    # -------------------------------------------------------------- 한 턴
    def step(self, acts):
        """acts[팀] = (moves (n,2,5,H,W) frame 인원, f_idx (n,), w_idx (n,)).

        반환 result (n,) : −1 진행 중, 0 Y 승, 1 K 승, 2 무승부. 끝난 판은 상태를 그대로 두며 호출자가 reset 한다.
        """
        n, dev = self.n, self.dev
        self.turn += 1
        self.stage[(self.owner == -1) & (self.stage == 1)] = 0

        # 2. 생산(본진). 새 유닛은 이번 턴 이동하지 않는다(명령 인원은 생산 전 보유 기준).
        spawn = torch.zeros(n, 2, 2, device=dev, dtype=torch.int64)
        fch = torch.tensor(F_CHOICES, device=dev)
        wfr = torch.tensor(W_FRACS, device=dev)
        for t in (0, 1):
            _, fi, wi = acts[t]
            res = self.res[:, t]
            nF = torch.minimum(fch[fi], res // 5)
            left = res - nF * 5
            wc = self.wcost(t)
            nW = torch.floor(left.double() * wfr[wi].double()).long() // wc
            nW = torch.minimum(nW, left // wc)
            self.res[:, t] = left - nW * wc
            spawn[:, t, 0], spawn[:, t, 1] = nF, nW

        # 3. 이동
        pas = self.passable
        new = torch.zeros_like(self.units)
        for t in (0, 1):
            mv = acts[t][0].to(torch.int32)
            if t == 1:
                mv = mv.flip(-2, -1)[:, :, [0, 2, 1, 4, 3]]      # frame → 실제(U↔D, L↔R)
            stay = mv[:, :, 0].clone()
            out = torch.zeros_like(stay)
            # 실제 좌표 이동. 막힌 칸이나 맵 밖으로 가는 인원은 제자리(공식 엔진: 그 명령 무시).
            for d, (src_s, dst_s, edge_s) in enumerate(MOVES):
                m = mv[:, :, d + 1]
                src = m[(Ellipsis,) + src_s]
                ok = pas[(slice(None),) + dst_s].unsqueeze(1)
                out[(Ellipsis,) + dst_s] += torch.where(ok, src, 0)
                stay[(Ellipsis,) + src_s] += torch.where(ok, 0, src)
                stay[(Ellipsis,) + edge_s] += m[(Ellipsis,) + edge_s]
            new[:, t] = stay + out
            bc = self.base_cell[:, t]
            flat = new[:, t].view(n, 2, -1)
            flat[torch.arange(n), 0, bc] += spawn[:, t, 0].to(torch.int32)
            flat[torch.arange(n), 1, bc] += spawn[:, t, 1].to(torch.int32)
        self.units = new

        # 4. 전투
        yW, kW = self.units[:, 0, 1], self.units[:, 1, 1]
        m = torch.minimum(yW, kW)
        yW, kW = yW - m, kW - m
        self.units[:, 0, 1], self.units[:, 1, 1] = yW, kW
        wipe = torch.stack([(kW > 0) & (yW == 0), (yW > 0) & (kW == 0)], 1)   # wipe[:, t] = 팀 t 의 F 전멸
        for t in (0, 1):
            hadF = self.units[:, t, 0].view(n, -1).gather(1, self.bcell) > 0
            wb = wipe[:, t].view(n, -1).gather(1, self.bcell)
            pull = wb & hadF & (self.owner == t)
            self.owner[pull] = -1
            self.stage[pull] = 1
            self.units[:, t, 0][wipe[:, t]] = 0

        # 6. 수입
        for t in (0, 1):
            self.res[:, t] = torch.clamp(self.res[:, t] + 10 + 2 * self.owned_count(t, "HALL"), max=40)

        # 7. 점령
        lib = [self.owned_count(t, "LIBRARY") > 0 for t in (0, 1)]
        pending = torch.zeros(n, 2, dtype=torch.int64, device=dev)
        for t in (0, 1):
            fT = self.units[:, t, 0].view(n, -1).gather(1, self.bcell) > 0
            fO = self.units[:, 1 - t, 0].view(n, -1).gather(1, self.bcell) > 0
            cand = fT & ~fO & ~((self.owner == t) & (self.stage >= 2))
            cost = torch.where(self.btype == T["PLAZA"], 4, 2) - lib[t].long().unsqueeze(1)
            cost = torch.clamp(cost, min=1)
            sc = torch.where(self.revealed[:, t], self.bscore, 0)
            order = (-sc * 100 + self.home_rank[:, t]).argsort(1)
            ar = torch.arange(n, device=dev)
            for j in range(NB):
                b = order[:, j]
                c = cand[ar, b] & (self.res[:, t] >= cost[ar, b])
                if not c.any():
                    continue
                self.res[:, t] -= torch.where(c, cost[ar, b], 0)
                neu = self.owner[ar, b] == -1
                cap = c & neu
                self.owner[ar[cap], b[cap]] = t
                self.stage[ar[cap], b[cap]] = 2
                self.revealed[ar[cap], t, b[cap]] = True
                dep = cap & (self.btype[ar, b] == T["DEPOT"]) & ~self.depot[ar, t, b]
                self.depot[ar[dep], t, b[dep]] = True
                pending[dep, t] += 15
                neut = c & ~neu
                self.owner[ar[neut], b[neut]] = -1
                self.stage[ar[neut], b[neut]] = 1
        self.res = torch.clamp(self.res + pending, max=40)
        for t in (0, 1):
            self.occ[:, t] += torch.where(self.owner == t, self.bscore, 0).sum(1)

        # 8. 정보 공개
        for t in (0, 1):
            here = self.units[:, t].sum(1).view(n, -1).gather(1, self.bcell) > 0
            own = self.owner == t
            watch = own & (self.btype == T["WATCH"])
            seen = (self.near3 & watch.unsqueeze(1)).any(2)
            self.revealed[:, t] |= here | own | seen

        # 9. 승리 판정
        score = torch.stack([torch.where(self.owner == t, self.bscore, 0).sum(1) for t in (0, 1)], 1)
        result = torch.full((n,), -1, dtype=torch.int64, device=dev)
        for t in (0, 1):
            inst = (score[:, 1 - t] == 0) & (score[:, t] * 2 > self.total) & (result == -1)
            result[inst] = t
        end = (self.turn >= 160) & (result == -1)
        if end.any():
            uv = (self.units[:, :, 0].sum((2, 3)) * 5 + self.units[:, :, 1].sum((2, 3)) * 3).long()
            dec = torch.full((n,), 2, dtype=torch.int64, device=dev)
            for metric in (uv, self.occ, score):                 # 뒤에서부터 덮어써 우선순위: 점수 > 점령-턴 > 병력
                ne = metric[:, 0] != metric[:, 1]
                dec = torch.where(ne, (metric[:, 1] > metric[:, 0]).long(), dec)
            result[end] = dec[end]
        self.score = score
        return result
