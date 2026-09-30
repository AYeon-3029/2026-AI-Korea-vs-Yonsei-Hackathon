"""구조 개편 시제품: 롤아웃 기반 방침 선택(MPC). 규칙 봇 위에 '짧은 미래를 직접 돌려 보고 고르는' 층을 얹는다.

매 K 턴마다 봇이 자기 관측만으로 엔진 상태를 재구성하고(미공개 점수는 추정값),
방침 후보(MODES)마다 H 턴을 끝까지 시뮬레이션해 점수 차가 가장 좋은 방침을 다음 K 턴 동안 쓴다.
상대는 '그림자 봇'(우리 규칙 봇을 상대 관측으로 매 턴 돌려 기억을 쌓은 것)으로 흉내 낸다.
관측 밖 정보(상대 기억·실제 점수)는 쓰지 않으므로 그대로 제출 봇에 옮길 수 있다.

평가 (WSL): python3 tools/macro/mpc.py --seeds 40000-40019 --opps p_rush,semi14 [--modes base,atk,allin,def] [--K 5 --H 15]
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from sim import CFG, Agent, Game, value  # noqa: E402
from branch import OPPS, parse_range  # noqa: E402
from engine.pipeline import run_turn, team_score  # noqa: E402
from engine.state import Building, GameState  # noqa: E402
from runner.protocol import parse_commands, serialize_init, serialize_turn  # noqa: E402

import campus_bot  # noqa: E402

MODES = {
    "base": {},
    "atk": {"siege_bld_bonus": 30.0, "enemy_owned_mult": 2.5, "risk_local_w": 0.2, "guard_radius": 10, "w_margin": 12},
    "allin": {"siege_bld_bonus": 40.0, "siege_ring_value": 4.0, "risk_local_w": 0.0, "guard_radius": 6, "f_block": 1,
              "w_margin": 5, "max_f": 6},
    "def": {"w_margin": 32, "guard_radius": 25, "siege_bld_bonus": 4.0, "siege_ring_value": 1.5},
    "eco": {"eco_strike": 8, "eco_def_w": 3.0, "hall_bonus": 12.0, "eng_bonus": 10.0},
    "blob": {"blob": True},
}


# 상대 모델 후보(그림자 봇). 매 턴 각자의 한 턴 예측을 실제 관측과 비교해 오차가 가장 작은 것으로 롤아웃한다.
SHADOWS = {
    "d": {},
    "semi": {"f_block": 0, "eco_block_extra": 0},
    "noreact": {"react": False},
    "press": {"guard_radius": 8, "siege_bld_bonus": 30.0, "siege_ring_value": 6.0, "w_margin": 34},
    "eco": {"eng_bonus": 16.0, "hall_bonus": 16.0},
    "rush": {"guard_radius": 4, "siege_ring_value": 9.0, "w_margin": 44, "risk_local_w": 0.0, "max_f": 4, "min_f": 3},
}


class MPCAgent:
    """sim.Agent 와 같은 인터페이스(start/decide/errors). 입력 텍스트만 본다."""

    def __init__(self, ver="v22", modes=("base", "atk", "allin", "def"), K=5, H=15, start=10, eps=0.5, stop=150,
                 shadows=("d",), decay=0.9):
        self.ver, self.K, self.H, self.start_turn, self.eps, self.stop = ver, K, H, start, eps, stop
        self.modes = list(modes)
        self.inner = Agent(ver)
        self.shadows = {n: Agent(ver, SHADOWS[n]) for n in shadows}
        self.serr = {n: 0.0 for n in shadows}
        self.decay = decay
        self.shadow = self.shadows[shadows[0]]
        self.prev = None        # (직전 재구성 상태, 우리 명령, 그림자별 명령)
        self.pick = {}
        self.errors = 0
        self.mode = "base"
        self.log = []
        self.oracle = None      # 진단용: 실제 상대 Agent(우리가 Y 일 때만 — 상대가 이번 턴 결정 전)

    # --- 관측 → 엔진 상태 ---
    def start(self, init_text):
        self.inner.start(init_text)
        self.init = campus_bot.parse_init(init_text.splitlines())
        self.me = self.init.team
        self.opp = "K" if self.me == "Y" else "Y"
        self.depot = {}
        self.occ = {"Y": 0, "K": 0}
        st = self._state_from(None)
        for a in self.shadows.values():
            a.start(serialize_init(st, self.opp))

    def _est_score(self, bid):
        m = self.inner.mem
        mod = self.inner.mod
        if m is not None and bid in m.scores:
            return m.scores[bid]
        if m is not None:
            return int(round(mod.P["center_expect"] if m.central[bid] else mod.P["side_expect"]))
        return 3

    def _state_from(self, view):
        ini = self.init
        blds = {}
        for b in ini.buildings:
            blds[b["id"]] = Building(b["id"], b["x"], b["y"], b["type"], self._est_score(b["id"]))
        res = {"Y": 10, "K": 10}
        units = {}
        turn = 0
        if view is not None:
            for b in view.buildings:
                x = blds[b["id"]]
                x.owner, x.stage = b["owner"], b["stage"]
                if b["score"] >= 0:
                    x.score = b["score"]
            res = {self.me: view.my_resource, self.opp: view.opp_resource}
            for u in view.units:
                k = (u["x"], u["y"], u["team"], u["kind"])
                units[k] = units.get(k, 0) + u["count"]
            turn = view.turn - 1
        s = GameState(config=CFG, terrain=[list(r) for r in ini.terrain], buildings=blds, bases=dict(ini.bases),
                      resources=res, units=units, turn=turn,
                      depot_claimed={k: set(v) for k, v in self.depot.items()},
                      revealed={"Y": set(blds), "K": set(blds)},
                      occupation_score_turns=dict(self.occ))
        return s

    def decide(self, text):
        view = campus_bot.parse_turn(text.splitlines(), self.init)
        for b in view.buildings:
            if b["type"] == "DEPOT" and b["owner"] in ("Y", "K"):
                self.depot.setdefault(b["id"], set()).add(b["owner"])
        st = self._state_from(view)
        try:
            self._score_shadows(st)
        except Exception:  # noqa: BLE001
            self.errors += 1
        for t in ("Y", "K"):
            self.occ[t] += sum(b.score for b in st.buildings.values() if b.owner == t)
        if self.start_turn <= view.turn <= self.stop and (view.turn - self.start_turn) % self.K == 0:
            try:
                self._choose(st, view.turn)
            except Exception:  # noqa: BLE001
                self.errors += 1
        # 그림자 상대: 상대 시점 입력으로 기억을 쌓고, 이번 턴 명령을 다음 턴 예측 오차 계산에 쓴다
        sc = {n: parse_commands(a.decide(serialize_turn(st, self.opp, view.turn))) for n, a in self.shadows.items()}
        out = self.inner.decide(text)
        self.prev = (st, parse_commands(out), sc)
        return out

    def _score_shadows(self, st):
        """직전 턴 상태에서 각 그림자 명령으로 한 턴을 돌려 실제 상대 유닛·자원과 비교한다."""
        if self.prev is None or len(self.shadows) == 1:
            return
        ps, mc, sc = self.prev
        opp = self.opp
        real = {k: c for k, c in st.units.items() if k[2] == opp}
        for n, oc in sc.items():
            ns, _ = run_turn(ps, *((mc, oc) if self.me == "Y" else (oc, mc)))
            pred = {k: c for k, c in ns.units.items() if k[2] == opp}
            e = sum(abs(pred.get(k, 0) - real.get(k, 0)) for k in set(pred) | set(real))
            e += abs(ns.resources[opp] - st.resources[opp]) / 5
            self.serr[n] = self.serr[n] * self.decay + e
        best = min(self.serr, key=lambda n: (self.serr[n], n != "d"))
        self.shadow = self.shadows[best]

    def _rollout(self, st, turn, params):
        me, opp = self.me, self.opp
        a = self.inner.clone()
        a.set_params(params)
        b = (self.oracle or self.shadow).clone()
        s = st
        res = None
        end = min(160, turn + self.H - 1)
        while res is None and s.turn < end:
            t = s.turn + 1
            cm = parse_commands(a.decide(serialize_turn(s, me, t)))
            co = parse_commands(b.decide(serialize_turn(s, opp, t)))
            s, res = run_turn(s, *((cm, co) if me == "Y" else (co, cm)))
        if res and res.get("reason") == "instant_win":
            return 30.0 if res["winner"] == me else -30.0
        occ = s.occupation_score_turns
        return team_score(s, me) - team_score(s, opp) + (occ[me] - occ[opp]) / 160

    def _choose(self, st, turn):
        sc = {m: self._rollout(st, turn, MODES[m]) for m in self.modes}
        best = max(sc, key=lambda m: sc[m])
        cur = sc.get(self.mode, sc["base"])
        if sc[best] > cur + self.eps:
            self.mode = best
        self.inner.set_params(MODES[self.mode])
        self.log.append((turn, self.mode, {k: round(v, 1) for k, v in sc.items()}))
        sh = next(n for n, a in self.shadows.items() if a is self.shadow)
        self.pick[sh] = self.pick.get(sh, 0) + 1


def one(seed, opp, side, kw):
    o = Agent(*OPPS[opp])
    kw = dict(kw)
    oracle = kw.pop("oracle", False)
    me = MPCAgent(**kw)
    if oracle:
        me.oracle = o
    g = Game(seed, *((me, o) if side == "Y" else (o, me)))
    t0 = time.time()
    g.run()
    dt = (time.time() - t0) / max(1, g.turn)
    o2 = Agent(*OPPS[opp])
    base = Agent(kw.get("ver", "v22"))
    g2 = Game(seed, *((base, o2) if side == "Y" else (o2, base)))
    g2.run()
    modes = {}
    for _, m, _ in me.log:
        modes[m] = modes.get(m, 0) + 1
    for n, c in me.pick.items():
        modes["sh_" + n] = modes.get("sh_" + n, 0) + c
    return opp, value(g2.result, side), value(g.result, side), dt, modes, me.errors


def job(a):
    return one(*a)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", required=True)
    p.add_argument("--opps", required=True)
    p.add_argument("--modes", default="base,atk,allin,def")
    p.add_argument("--K", type=int, default=5)
    p.add_argument("--H", type=int, default=15)
    p.add_argument("--eps", type=float, default=0.5)
    p.add_argument("--ver", default="v22")
    p.add_argument("--workers", type=int, default=26)
    p.add_argument("--oracle", action="store_true", help="진단: 실제 상대로 롤아웃(Y 진영만)")
    p.add_argument("--shadows", default="d")
    a = p.parse_args()
    kw = dict(ver=a.ver, modes=a.modes.split(","), K=a.K, H=a.H, eps=a.eps, oracle=a.oracle, shadows=tuple(a.shadows.split(",")))
    jobs = [(s, o, side, kw) for s in parse_range(a.seeds) for o in a.opps.split(",") for side in ("Y" if a.oracle else "YK")]
    t0 = time.time()
    rows, modes, err, dts = [], {}, 0, []
    with Pool(a.workers) as pool:
        for opp, vb, vm, dt, md, e in pool.imap_unordered(job, jobs):
            rows.append((opp, vb, vm))
            dts.append(dt)
            err += e
            for k, v in md.items():
                modes[k] = modes.get(k, 0) + v
    v = np.array([(r[1], r[2]) for r in rows])
    d = v[:, 1] - v[:, 0]
    print(f"{len(v)}쌍 base {v[:, 0].mean():.3f} MPC {v[:, 1].mean():.3f} 차 {d.mean():+.4f} ± {d.std() / np.sqrt(len(d)):.4f}"
          f"  턴당 {np.mean(dts) * 1000:.1f}ms(최대 {np.max(dts) * 1000:.1f})  방침 {modes}  예외 {err}  {time.time() - t0:.0f}s")
    for o in sorted({r[0] for r in rows}):
        vv = np.array([(r[1], r[2]) for r in rows if r[0] == o])
        print(f"  {o:<14} base {vv[:, 0].mean():.3f}  MPC {vv[:, 1].mean():.3f}  {(vv[:, 1] - vv[:, 0]).mean():+.3f}")


if __name__ == "__main__":
    main()
