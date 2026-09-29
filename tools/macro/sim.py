"""v11 이후 규칙 봇을 한 프로세스 안에서 양 진영 정책으로 돌리는 시뮬레이터(방침 선택 학습용).

- `Agent(ver, params)`: history/<ver>/main.py 모듈을 진영별 GEO·MEM·P 로 바꿔 끼우며 호출한다.
  `set_params` 로 경기 도중 파라미터 묶음(방침)을 바꿀 수 있다.
- `Game(seed, ay, ak)`: 공식 엔진으로 한 턴씩 진행. `fork()` 는 엔진 상태·양쪽 메모리를 복제한 독립 경기다.
  봇이 결정적이므로 같은 상태에서 갈라진 두 경기의 결과 차이는 순수하게 갈라진 선택의 효과다.

subprocess 대전(`arena.py`)과 결과가 같은지는 `python3 tools/macro/sim.py --check` 로 확인한다.
"""
from __future__ import annotations

import copy
import importlib.util
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
DEV = os.path.join(ROOT, "BaseLines/yk-development-tools")
sys.path.insert(0, DEV)
sys.path.insert(0, os.path.join(ROOT, "Model/history/v13"))   # protocol·campus_bot·tactical(v11~v13 동일)

from engine.config import load_config  # noqa: E402
from engine.pipeline import run_turn, team_score  # noqa: E402
from engine.state import GameState  # noqa: E402
from mapgen import generate, to_state  # noqa: E402
from runner.protocol import parse_commands, serialize_init, serialize_turn  # noqa: E402

import campus_bot  # noqa: E402

CFG = load_config()
TOTAL = CFG["total_turns"]


def _fast_clone(self):
    """엔진 기본 clone(deepcopy, 설정까지 복사)보다 수십 배 빠른 복사. 지형·설정은 공유한다."""
    s = GameState.__new__(GameState)
    s.config = self.config
    s.terrain = self.terrain
    s.buildings = {i: copy.copy(b) for i, b in self.buildings.items()}
    s.bases = self.bases
    s.resources = dict(self.resources)
    s.units = dict(self.units)
    s.turn = self.turn
    s.depot_claimed = {k: set(v) for k, v in self.depot_claimed.items()}
    s.revealed = {k: set(v) for k, v in self.revealed.items()}
    s.occupation_score_turns = dict(self.occupation_score_turns)
    return s


GameState.clone = _fast_clone

_MODS: dict[str, object] = {}
_BASE_P: dict[str, dict] = {}


def module(ver: str):
    if ver not in _MODS:
        path = os.path.join(ROOT, "Model/history", ver, "main.py")
        spec = importlib.util.spec_from_file_location(f"bot_{ver}", path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _MODS[ver] = m
        _BASE_P[ver] = copy.deepcopy(m.P)
    return _MODS[ver]


class Agent:
    """한 진영의 규칙 봇 인스턴스. params 는 그 버전 기본 P 위에 덮어쓴다."""

    def __init__(self, ver: str = "v13", params: dict | None = None):
        self.ver = ver
        self.mod = module(ver)
        self.params = dict(params or {})
        self.init = None
        self.geo = None
        self.mem = None
        self.errors = 0
        self.hook = None        # history/v13h 의 F_HOOK(F 목표 배정 훅)

    def set_params(self, params: dict | None):
        self.params = dict(params or {})

    def start(self, init_text: str):
        self.init = campus_bot.parse_init(init_text.splitlines())

    def decide(self, text: str) -> list[str]:
        m = self.mod
        view = campus_bot.parse_turn(text.splitlines(), self.init)
        m.GEO, m.MEM = self.geo, self.mem
        if hasattr(m, "F_HOOK"):
            m.F_HOOK = self.hook
        m.P.clear()
        m.P.update(copy.deepcopy(_BASE_P[self.ver]) if "deny" in self.params else _BASE_P[self.ver])
        m.P.update(self.params)
        try:
            out = m.decide(view, self.init)
        except Exception:  # noqa: BLE001
            self.errors += 1
            out = []
        self.geo, self.mem = m.GEO, m.MEM
        return out

    def clone(self) -> "Agent":
        a = Agent.__new__(Agent)
        a.ver, a.mod, a.params, a.init, a.geo = self.ver, self.mod, dict(self.params), self.init, self.geo
        a.mem = copy.deepcopy(self.mem)
        a.errors = self.errors
        a.hook = self.hook
        return a


class Game:
    def __init__(self, seed: int, ay: Agent, ak: Agent):
        self.seed = seed
        self.state = to_state(generate(seed, CFG))
        self.agents = {"Y": ay, "K": ak}
        ay.start(serialize_init(self.state, "Y"))
        ak.start(serialize_init(self.state, "K"))
        self.result = None

    @property
    def turn(self) -> int:
        return self.state.turn

    def step(self):
        t = self.state.turn + 1
        cy = parse_commands(self.agents["Y"].decide(serialize_turn(self.state, "Y", t)))
        ck = parse_commands(self.agents["K"].decide(serialize_turn(self.state, "K", t)))
        self.state, self.result = run_turn(self.state, cy, ck)

    def run(self, until: int = TOTAL):
        while self.result is None and self.state.turn < until:
            self.step()
        return self.result

    def fork(self) -> "Game":
        g = Game.__new__(Game)
        g.seed = self.seed
        g.state = self.state.clone()
        g.agents = {t: a.clone() for t, a in self.agents.items()}
        g.result = self.result
        return g


def value(result: dict, side: str) -> float:
    """승 1 / 무 0.5 / 패 0."""
    w = result["winner"]
    return 1.0 if w == side else 0.5 if w == "DRAW" else 0.0


def margin(game: Game, side: str) -> float:
    """승패 아래 단계 비교용 연속 지표: 점수 차 + 점령-턴 차/160 (판정 ①② 순서를 그대로 따른다)."""
    s = game.state
    opp = "K" if side == "Y" else "Y"
    if game.result and game.result.get("reason") == "instant_win":
        return 30.0 if game.result["winner"] == side else -30.0
    d = team_score(s, side) - team_score(s, opp)
    occ = s.occupation_score_turns
    return d + (occ.get(side, 0) - occ.get(opp, 0)) / TOTAL


def play(seed: int, ay: Agent, ak: Agent) -> dict:
    g = Game(seed, ay, ak)
    return g.run()


if __name__ == "__main__":
    import time
    if "--check" in sys.argv:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from arena import play as arena_play
        bad = 0
        for seed in range(9000, 9006):
            r1 = play(seed, Agent("v13"), Agent("v12"))
            _, _, r2, _ = arena_play((seed, f"python3 {ROOT}/Model/history/v13/main.py",
                                      f"python3 {ROOT}/Model/history/v12/main.py", "Y", ""))
            same = (r1["winner"], r1["score"], r1["turns"]) == (r2["winner"], r2["score"], r2["turns"])
            bad += not same
            print(seed, r1["winner"], r1["score"], r1["turns"], "|", r2["winner"], r2["score"], r2["turns"], "OK" if same else "DIFF")
        print("불일치", bad)
    else:
        t0 = time.time()
        r = play(9000, Agent("v13"), Agent("v12"))
        print(r, f"{time.time() - t0:.2f}s")
