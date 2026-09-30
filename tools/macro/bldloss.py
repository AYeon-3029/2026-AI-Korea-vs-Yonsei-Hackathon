"""우리 건물이 적 F 에 중립화될 때의 상황을 분류한다(사용자 LLM 경기 관찰: 동수 상쇄 뒤 적 F 생존, 늦은 수비, 느린 탈환).

턴마다 전투·점령 단계를 가로채 '이 턴에 우리 소유 → 중립' 이 된 건물을 잡고, 그 턴 이동 후(전투 전) 건물 칸의 병력과
봇이 본 직전 상태(이동 전)의 주변 병력을 기록한다.
분류(전투 전 건물 칸 기준):
  동수상쇄  아군 W ≥1 이고 아군 W == 적 W  → 상쇄 뒤 적 F 가 홀로 남아 중립화 (사용자 150006 32스텝)
  열세      0 < 아군 W < 적 W
  무방비·인접  아군 W 0, 직전 상태에서 아군 W 가 1칸 안에 있었다(한 칸만 들어오면 막았다)
  무방비·근처  아군 W 0, 2~4칸 안
  무방비·원거리 아군 W 0, 5칸 이상
  F전사     아군 F 가 서 있던 건물에서 전투로 깃발이 뽑힘
탈환: 다시 우리 소유가 될 때까지의 턴(경기 끝까지 못 찾으면 '미탈환').
사용 (WSL):
  python3 tools/macro/bldloss.py --ver cv-3 --seeds 100000-100019 [--opps ...] [--params '{}']
  python3 tools/macro/bldloss.py --llm b150003,b150004,...     # LLM 지휘 경기의 cv-3 쪽
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, deque
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, value  # noqa: E402
from branch import OPPS, REAL_POOL, parse_range  # noqa: E402
import engine.pipeline as pl  # noqa: E402

CTX: dict = {}
LOG: list = []
_orig_combat = pl.step_combat
_orig_capture = pl.step_capture


def _mine(state, side):
    return {(b.x, b.y) for b in state.buildings.values() if b.owner == side}


def _combat(state, events=None):
    side = CTX["side"]
    op = "K" if side == "Y" else "Y"
    CTX["pre"] = {}
    for (x, y) in _mine(state, side):
        CTX["pre"][(x, y)] = (state.get_unit(x, y, side, "W"), state.get_unit(x, y, op, "W"),
                              state.get_unit(x, y, op, "F"), state.get_unit(x, y, side, "F"))
    before = _mine(state, side)
    _orig_combat(state, events)
    CTX["pulled"] = before - _mine(state, side)


def _capture(state, priorities, events=None):
    side = CTX["side"]
    before = _mine(state, side)
    _orig_capture(state, priorities, events)
    lost = (before - _mine(state, side)) | CTX.get("pulled", set())
    if not lost:
        return
    op = "K" if side == "Y" else "Y"
    prev = CTX["hist"][-1]
    W = {side: 0, op: 0}
    for (x, y, t, k), n in prev.items():
        if k == "W" and n > 0:
            W[t] += n
    for (x, y) in lost:
        myw, enw, enf, myf = CTX["pre"].get((x, y), (0, 0, 0, 0))

        def around(team, kind, r, u=prev):
            return sum(n for (px, py, t, k), n in u.items()
                       if t == team and k == kind and n > 0 and abs(px - x) + abs(py - y) <= r)
        dmin = min((abs(px - x) + abs(py - y) for (px, py, t, k), n in prev.items()
                    if t == side and k == "W" and n > 0), default=99)
        # 경고 시간: 몇 턴 전부터 적 F 가 3칸 안에 있었나
        warn = 0
        for h in reversed(CTX["hist"]):
            if around(op, "F", 3, h) > 0:
                warn += 1
            else:
                break
        if (x, y) in CTX.get("pulled", set()):
            cat = "F전사"
        elif myw >= 1 and myw == enw:
            cat = "동수상쇄"
        elif 0 < myw < enw:
            cat = "열세"
        elif around(side, "W", 1) > 0:
            cat = "무방비·인접"
        elif dmin <= 4:
            cat = "무방비·근처"
        else:
            cat = "무방비·원거리"
        b = state.building_at(x, y)
        LOG.append({"turn": state.turn, "x": x, "y": y, "btype": b.btype, "score": b.score, "cat": cat,
                    "myw": myw, "enw": enw, "enf": enf, "w1": around(side, "W", 1), "w2": around(side, "W", 2),
                    "enw2": around(op, "W", 2), "dmin": dmin, "warn": warn, "Wme": W[side], "Wop": W[op],
                    "res": state.resources[side]})


pl.step_combat = _combat
pl.step_capture = _capture


def _drive(g, side, stepper):
    LOG.clear()
    CTX["side"] = side
    CTX["hist"] = deque(maxlen=6)
    own_hist = []
    while g.result is None:
        CTX["hist"].append(dict(g.state.units))
        stepper(g)
        own_hist.append(_mine(g.state, side))
    # 탈환 시간
    for e in LOG:
        t0 = e["turn"]
        back = None
        for k in range(t0, len(own_hist)):   # own_hist[k] = 턴 k+1 후 소유
            if (e["x"], e["y"]) in own_hist[k]:
                back = k + 1 - t0
                break
        e["back"] = back
    return list(LOG)


def run(args):
    seed, opp, side, ver, params = args
    me = Agent(ver, params)
    o = Agent(*OPPS[opp])
    g = Game(seed, *((me, o) if side == "Y" else (o, me)))
    ev = _drive(g, side, lambda g: g.step())
    return {"seed": seed, "opp": opp, "side": side, "v": value(g.result, side), "loss": ev}


def run_llm(game):
    import llm_match as L
    meta = json.load(open(os.path.join(L.gdir(game), "meta.json"), encoding="utf-8"))
    side = "K" if meta["side"] == "Y" else "Y"          # cv-3 쪽
    llm = Agent(meta.get("llm", L.LLM_VER), {})
    op = Agent(meta.get("opp", L.OPP_VER), {})
    g = Game(meta["seed"], *((llm, op) if meta["side"] == "Y" else (op, llm)))
    m = L.module(meta.get("llm", L.LLM_VER))
    st = {"cmd": None}

    def stepper(g):
        t = g.state.turn
        p = os.path.join(L.gdir(game), f"cmd_{t:03d}.json")
        if t % L.EVERY == 0 and os.path.exists(p):
            cmd = json.load(open(p, encoding="utf-8"))
            st["cmd"] = cmd
            llm.set_params({**L.posture_params(cmd.get("posture", "balanced"), meta.get("llm", L.LLM_VER)),
                            **({"max_f": int(cmd["max_f"])} if cmd.get("max_f") else {})})
        cmd = st["cmd"]
        m.CMD = {"focus": [list(v) for v in cmd.get("focus", [])], "defend": [list(v) for v in cmd.get("defend", [])]} if cmd else None
        g.step()
    ev = _drive(g, side, stepper)
    m.CMD = None
    return {"seed": meta["seed"], "opp": game, "side": side, "v": value(g.result, side), "loss": ev}


def report(rows, detail=False):
    n = len(rows)
    E = [e for r in rows for e in r["loss"]]
    print(f"{n}경기 승점 {sum(r['v'] for r in rows) / n:.3f}  건물 잃음/경기 {len(E) / n:.2f}")
    for lab, sel in (("승", lambda r: r["v"] == 1), ("무", lambda r: r["v"] == 0.5), ("패", lambda r: r["v"] == 0)):
        rs = [r for r in rows if sel(r)]
        if rs:
            c = Counter(e["cat"] for r in rs for e in r["loss"])
            print(f"  {lab} {len(rs):4d}경기  잃음/경기 {sum(len(r['loss']) for r in rs) / len(rs):.2f}   "
                  + "  ".join(f"{k}:{v / len(rs):.2f}" for k, v in c.most_common()))

    def show(title, key, pool=E):
        c = Counter(key(e) for e in pool)
        print(f"{title:10s}", "  ".join(f"{k}:{v / n:.2f}" for k, v in sorted(c.items(), key=lambda kv: -kv[1])))
    show("분류", lambda e: e["cat"])
    show("종류", lambda e: e["btype"])
    show("구간", lambda e: f"{(e['turn'] - 1) // 40 * 40 + 1}-")
    show("분류×종류", lambda e: f"{e['cat']}/{e['btype']}")
    show("탈환", lambda e: "미탈환" if e["back"] is None else ("≤3" if e["back"] <= 3 else "4-8" if e["back"] <= 8 else "9-20" if e["back"] <= 20 else ">20"))
    show("경고턴", lambda e: str(min(e["warn"], 5)))
    show("W차(전체)", lambda e: "우세" if e["Wme"] > e["Wop"] else "동수" if e["Wme"] == e["Wop"] else "열세")
    lost_turns = sum((e["back"] if e["back"] is not None else 160 - e["turn"]) for e in E)
    print(f"잃은 건물-턴/경기 {lost_turns / n:.1f}   HALL {sum((e['back'] if e['back'] is not None else 160 - e['turn']) for e in E if e['btype'] == 'HALL') / n:.1f}")
    if detail:
        for r in rows:
            print(f"--- {r['opp']} 시드 {r['seed']} cv-3={r['side']} 승점 {r['v']}")
            for e in r["loss"]:
                print(f"  {e['turn']:3d}턴 {e['btype']:8s}({e['x']},{e['y']}) {e['cat']:8s} 칸W {e['myw']}:{e['enw']} 적F {e['enf']}"
                      f"  직전 1칸W {e['w1']} 2칸W {e['w2']} 적W2칸 {e['enw2']} 최근접W {e['dmin']}  경고 {e['warn']}턴"
                      f"  W {e['Wme']}:{e['Wop']} 자원 {e['res']}  탈환 {e['back']}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ver", default="cv-3")
    p.add_argument("--params", default="{}")
    p.add_argument("--seeds", default="100000-100009")
    p.add_argument("--opps", default=",".join(REAL_POOL))
    p.add_argument("--llm", default="")
    p.add_argument("--workers", type=int, default=20)
    p.add_argument("--detail", action="store_true")
    a = p.parse_args()
    t0 = time.time()
    if a.llm:
        with Pool(min(a.workers, 12)) as pool:
            rows = pool.map(run_llm, a.llm.split(","))
    else:
        jobs = [(s, o, side, a.ver, json.loads(a.params)) for s in parse_range(a.seeds) for o in a.opps.split(",") for side in "YK"]
        with Pool(a.workers) as pool:
            rows = list(pool.imap_unordered(run, jobs, chunksize=2))
    report(rows, a.detail)
    print(f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
