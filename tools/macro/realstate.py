"""실제 서버 리플레이의 한 턴 상태를 엔진 상태로 복원해, 그 지점부터 우리 봇 변형 A/B 를 끝까지 두어 비교한다.

로컬 풀이 만들지 못하는 실제 패배 장면(장기 교착·학생회관 요새·초반 러시)에서 대책을 재기 위한 평가기다.
- 복원: 지형·건물(점수 = 공개값 + 180° 대칭 짝, 끝까지 모르는 것은 지역 기댓값 반올림)·소유·단계·모든 유닛·양쪽 자원·
  보급소 수령 이력(관측 이력으로 정확히)·누적 점령-턴(우리는 관측값, 상대는 관측 이력으로 계산)·공개 목록(양쪽 전부 공개로 둔다).
- 상대 봇은 알 수 없으므로 대리 봇 여러 종으로 둔다. 같은 상태·같은 대리 봇에서 A/B 의 차이만 본다.
- 봇 메모리는 복원 시점부터 새로 시작한다(점수는 공개 목록으로 곧바로 안다).

사용 (WSL): python3 tools/macro/realstate.py --b '{"tele_queue": true}' [--games 'Real Match Replay/V12_0929_8am'] [--turns 40,60,80,100,120]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from sim import CFG, Agent, Game, value  # noqa: E402
from branch import OPPS  # noqa: E402
from engine.state import Building, GameState  # noqa: E402
from runner.protocol import serialize_init  # noqa: E402

N = 15
PROXIES = ["v13", "srv12_press", "srv12_eco", "b72", "x_press", "x_eco"]


def restore(path, t):
    """리플레이의 관측 턴 t(그 턴 입력 = t−1 턴 처리 후 상태) → (GameState, 우리 진영, 결과 정보)."""
    r = json.load(open(path, encoding="utf-8"))
    me = r["side"]
    op = "Y" if me == "K" else "K"
    T = [x for x in r["turns"] if x.get("observation")]
    obs = {x["observation"]["turn"]: x for x in T}
    if t not in obs:
        return None
    o0 = T[0]["observation"]
    terrain = [list(row) for row in o0["map"]]
    blds0 = o0["buildings"]
    pos = {(b["x"], b["y"]): b["id"] for b in blds0}
    mirror = {b["id"]: pos.get((N - 1 - b["x"], N - 1 - b["y"]), b["id"]) for b in blds0}
    score = {}
    for x in T:
        for b in x["observation"]["buildings"]:
            if b.get("score") is not None and b["score"] >= 0:
                score[b["id"]] = b["score"]
        for k, v in (x.get("revealed") or {}).get("buildingScores", {}).items():
            score[int(k)] = v
    for i, j in list(mirror.items()):
        if i in score and j not in score:
            score[j] = score[i]
    for b in blds0:
        if b["id"] not in score:
            score[b["id"]] = 3 if 5 <= b["x"] <= 9 else 1 + (b["id"] % 2)   # 모르는 점수: 중앙 3, 양 진영 1~2
    # 본진: 첫 유닛 위치에 가까운 H
    hs = [(x, y) for y, row in enumerate(o0["map"]) for x, ch in enumerate(row) if ch == "H"]
    bases = {}
    for team in ("Y", "K"):
        first = next(((u[2], u[3]) for x in T for u in x["observation"]["units"] if u[0] == team), None)
        bases[team] = min(hs, key=lambda h: abs(h[0] - first[0]) + abs(h[1] - first[1])) if first else None
    if bases["Y"] == bases["K"] or None in bases.values():
        other = [h for h in hs if h != (bases["Y"] or bases["K"])][0]
        if bases["Y"] is None or bases["Y"] == bases["K"]:
            bases["Y"] = other if bases["K"] != other else hs[0]
        if bases["K"] is None:
            bases["K"] = [h for h in hs if h != bases["Y"]][0]
    o = obs[t]["observation"]
    blds = {b["id"]: Building(id=b["id"], x=b["x"], y=b["y"], btype=b["type"], score=int(score[b["id"]]),
                              owner=b["owner"], stage=b["stage"]) for b in o["buildings"]}
    s = GameState(config=CFG, terrain=terrain, buildings=blds, bases=bases,
                  resources={"Y": o["resources"]["Y"], "K": o["resources"]["K"]})
    for team, kind, x, y, n in o["units"]:
        s.units[(x, y, team, kind)] = s.units.get((x, y, team, kind), 0) + n
    s.turn = t - 1
    claimed, occ_op = {}, 0
    for tt in range(1, t + 1):
        if tt not in obs:
            continue
        ob = obs[tt]["observation"]
        for b in ob["buildings"]:
            if b["type"] == "DEPOT" and b["owner"] in ("Y", "K"):
                claimed.setdefault(b["id"], set()).add(b["owner"])
            if b["owner"] == op:
                occ_op += score[b["id"]]
    s.depot_claimed = claimed
    s.revealed = {"Y": set(blds), "K": set(blds)}
    occ_me = o["occTurns"].get(me) or 0
    s.occupation_score_turns = {me: occ_me, op: occ_op}
    return s, me, r["result"]


def play_from(state, me, my_agent, opp_agent):
    g = Game.__new__(Game)
    g.seed = -1
    g.state = state.clone()
    g.agents = {me: my_agent, ("Y" if me == "K" else "K"): opp_agent}
    for team, a in g.agents.items():
        a.start(serialize_init(g.state, team))
    g.result = None
    g.run()
    return g


def play_track(state, me, my_agent, opp_agent, horizon=30):
    """play_from 과 같되 분기 후 horizon 턴 동안 우리 공학관·학생회관 보유 턴 수(건물 수 합)를 센다."""
    g = Game.__new__(Game)
    g.seed = -1
    g.state = state.clone()
    g.agents = {me: my_agent, ("Y" if me == "K" else "K"): opp_agent}
    for team, a in g.agents.items():
        a.start(serialize_init(g.state, team))
    g.result = None
    eco = {"ENG": 0, "HALL": 0}
    t0 = g.state.turn
    while g.result is None:
        g.step()
        if g.state.turn - t0 <= horizon:
            for b in g.state.buildings.values():
                if b.owner == me and b.btype in eco:
                    eco[b.btype] += 1
    return g, eco


def job(args):
    path, t, proxy, vers, pa, pb = args
    rs = restore(path, t)
    if rs is None:
        return None
    s, me, _ = rs
    out, ecos = [], []
    if proxy.startswith("SELF"):
        # 그 경기 상대 팀의 흉내 봇(SELF = mc22_<상대>, SELF:eg = eg22_<상대>)
        nm = "".join(ch for ch in os.path.basename(path)[:-5].removeprefix("vs") if ch.isalnum())
        proxy = ("eg22_" if proxy == "SELF:eg" else "mc22_") + nm
    for ver, params in zip(vers, (pa, pb)):
        g, eco = play_track(s, me, Agent(ver, params), Agent(*OPPS[proxy]) if proxy in OPPS else Agent(proxy))
        assert not sum(agent.errors for agent in g.agents.values()), (path, t, proxy, ver)
        out.append(value(g.result, me))
        ecos.append(eco)
    return path, t, proxy, out, ecos


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--games", default="Real Match Replay/V12_0929_8am,Real Match Replay/V10_0928_8pm")
    p.add_argument("--turns", default="30,50,70,90,110,130")
    p.add_argument("--proxies", default=",".join(PROXIES))
    p.add_argument("--ver", default="dev")
    p.add_argument("--aver", default="", help="A 쪽 봇 버전(기본 --ver)")
    p.add_argument("--bver", default="", help="B 쪽 봇 버전(기본 --ver)")
    p.add_argument("--files", default="", help="파일 이름 조각(쉼표) — 지정하면 그 경기만")
    p.add_argument("--a", default="{}")
    p.add_argument("--b", default="{}")
    p.add_argument("--workers", type=int, default=24)
    p.add_argument("--out", default="")
    a = p.parse_args()
    files = [f for d in a.games.split(",") for f in sorted(glob.glob(os.path.join(d, "*.json")))]
    if a.files:
        files = [f for f in files if any(os.path.basename(f) == x for x in a.files.split(","))]
    turns = [int(x) for x in a.turns.split(",")]
    pa, pb = json.loads(a.a), json.loads(a.b)
    vers = (a.aver or a.ver, a.bver or a.ver)
    jobs = [(f, t, px, vers, pa, pb) for f in files for t in turns for px in a.proxies.split(",")]
    t0 = time.time()
    rows = []
    with Pool(a.workers) as pool:
        for r in pool.imap_unordered(job, jobs):
            if r:
                rows.append(r)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
    assert rows, "No replay states matched"
    V = np.array([x[3] for x in rows])
    d = V[:, 1] - V[:, 0]
    by_replay = {}
    for path, _, _, vs, _ in rows:
        by_replay.setdefault(path, []).append(vs[1] - vs[0])
    # Repeated turns/proxies from one replay are correlated; cluster the SE by replay.
    residual = np.array([sum(v - d.mean() for v in ds) for ds in by_replay.values()])
    n_replays = len(residual)
    se = np.sqrt(n_replays / (n_replays - 1) * np.sum(residual ** 2)) / len(rows) if n_replays > 1 else float("nan")
    print(f"{len(rows)}쌍  A {V[:, 0].mean():.3f}  B {V[:, 1].mean():.3f}  차 {d.mean():+.4f} ± {se:.4f} (SE: {n_replays} replays)"
          f"  (다름 {np.mean(d != 0):.2f})  {time.time() - t0:.0f}s")
    E = lambda k, j: np.mean([x[4][j][k] for x in rows])
    print(f"  분기 후 30턴 우리 공학관 보유 A {E('ENG', 0):.1f} B {E('ENG', 1):.1f} · 학생회관 A {E('HALL', 0):.1f} B {E('HALL', 1):.1f} (건물-턴)")
    by = {}
    for f, t, px, v, _ in rows:
        by.setdefault((f, t), []).append(v)
    if len({f for f, _ in by}) <= 3:
        for key in sorted(by):
            v = np.array(by[key])
            print(f"  {key[0]:<18} {key[1]:>3}턴  A {v[:, 0].mean():.3f}  B {v[:, 1].mean():.3f}  {np.mean(v[:, 1] - v[:, 0]):+.3f}")


if __name__ == "__main__":
    main()
