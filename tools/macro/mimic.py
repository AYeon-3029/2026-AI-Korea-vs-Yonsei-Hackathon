"""실전 상대 흉내 봇 맞추기: 실제 경기 맵에서 (우리 = 그때 제출한 봇) 대 (공격자 봇 dev11 + 파라미터)를 다시 두고,
경기 흐름(양쪽 W·건물·경제 건물 수, 상대 전진 비율·F 수, 결과)이 실제 리플레이와 가장 비슷한 파라미터를 Optuna 로 찾는다.

찾은 파라미터는 out/tune/mimic/<회차>[-바탕]/<상대>.json 에 저장되고 branch.py 가 OPPS["m16_<상대>"](바탕 dev11)·OPPS["mc16_<상대>"](바탕 cv-3)로 등록한다.
사용 (WSL):
  python3 tools/macro/mimic.py realmap --games 'Real Match Replay/V16_0930_8am' --vers v16,v19,cv-3   # 실제 맵 재대결
  python3 tools/macro/mimic.py fit --games 'Real Match Replay/V16_0930_8am' --ours v16 --trials 250
  python3 tools/macro/mimic.py show --games 'Real Match Replay/V16_0930_8am' --ours v16      # 맞춘 봇의 재현 흐름 vs 실제
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from multiprocessing import Pool

import numpy as np
import optuna

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, CFG, Game, TOTAL, value  # noqa: E402
from realstate import restore  # noqa: E402
from exploit import space  # noqa: E402
from runner.protocol import serialize_init  # noqa: E402
from engine.pipeline import team_score  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
CHECK = [10, 20, 30, 40, 60, 80, 100, 120, 140]
ATTACKER = "dev11"


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def feat_from_units(units, owners, btype, me, op, base_me, base_op):
    """units: [(team, kind, x, y, n)], owners: {id: owner}. 한 턴의 지표."""
    W = {me: 0, op: 0}
    F = {me: 0, op: 0}
    fwd = 0
    cells = set()
    for tm, k, x, y, n in units:
        if k == "W":
            W[tm] = W.get(tm, 0) + n
            if tm == op:
                cells.add((x, y))
            if tm == op and man((x, y), base_me) < man((x, y), base_op):
                fwd += n
        elif k == "F":
            F[tm] = F.get(tm, 0) + n
    nb = {me: 0, op: 0}
    eco = {me: 0, op: 0}
    for i, o in owners.items():
        if o in nb:
            nb[o] += 1
            if btype[i] in ("HALL", "ENG"):
                eco[o] += 1
    return {"Wm": W[me], "Wo": W[op], "Fo": F[op], "Bm": nb[me], "Bo": nb[op], "Em": eco[me], "Eo": eco[op],
            "fwd": fwd / max(1, W[op]), "Co": len(cells)}


def real_traj(path):
    r = json.load(open(path, encoding="utf-8"))
    me = r["side"]
    op = "Y" if me == "K" else "K"
    T = {t["observation"]["turn"]: t["observation"] for t in r["turns"] if t.get("observation")}
    b0 = T[min(T)]["buildings"]
    btype = {b["id"]: b["type"] for b in b0}
    hs = [(x, y) for y, row in enumerate(T[min(T)]["map"]) for x, ch in enumerate(row) if ch == "H"]
    first = next(((u[2], u[3]) for t in sorted(T) for u in T[t]["units"] if u[0] == me), hs[0])
    base_me = min(hs, key=lambda h: man(h, first))
    base_op = [h for h in hs if h != base_me][0]
    out = {}
    for t in CHECK:
        if t in T:
            o = T[t]
            out[t] = feat_from_units(o["units"], {b["id"]: b["owner"] for b in o["buildings"]}, btype, me, op, base_me, base_op)
    w = r["result"]["winner"]
    res = 1.0 if w == me else 0.5 if w == "DRAW" else 0.0
    return me, op, out, res, max(T)


def init_game(path, ours, ours_params, opp_params):
    rs = restore(path, 1)
    s, me, _ = rs
    s.turn = 0
    s.units.clear()
    s.resources = {"Y": 10, "K": 10}
    for b in s.buildings.values():
        b.owner, b.stage = "N", 0
    s.depot_claimed = {"Y": set(), "K": set()}
    s.occupation_score_turns = {"Y": 0, "K": 0}
    op = "Y" if me == "K" else "K"
    a_me = Agent(ours, ours_params)
    a_op = Agent(ATTACKER, opp_params)
    g = Game.__new__(Game)
    g.seed = -1
    g.state = s
    g.agents = {me: a_me, op: a_op}
    a_me.start(serialize_init(s, me))
    a_op.start(serialize_init(s, op))
    g.result = None
    return g, me, op


def sim_traj(path, ours, opp_params, ours_params=None):
    g, me, op = init_game(path, ours, ours_params or {}, opp_params)
    btype = {i: b.btype for i, b in g.state.buildings.items()}
    base_me, base_op = g.state.bases[me], g.state.bases[op]
    out = {}
    while g.result is None:
        g.step()
        t = g.state.turn
        if t in CHECK:
            units = [(tm, k, x, y, n) for (x, y, tm, k), n in g.state.units.items() if n > 0]
            owners = {i: b.owner for i, b in g.state.buildings.items()}
            out[t] = feat_from_units(units, owners, btype, me, op, base_me, base_op)
    return out, value(g.result, me), g.state.turn, g.agents[op].errors


SCALE = {"Wm": 20.0, "Wo": 20.0, "Fo": 2.0, "Bm": 3.0, "Bo": 3.0, "Em": 1.0, "Eo": 1.0, "fwd": 0.15}
SPACE = None      # --space v32: 최신 바탕(v32)용 확장 탐색(넓게 깔기·막판 F·초반 F·기습 규모·F 2턴 안전), 상대 W 칸 수(Co)도 맞춘다


def space_v32(trial):
    f, i, c = trial.suggest_float, trial.suggest_int, trial.suggest_categorical
    p = space(trial)
    p.update({
        "w_spread": c("w_spread", ["off", "anti"]), "max_f_early": i("max_f_early", 2, 8), "early_turn": i("early_turn", 0, 40),
        "fesc_min": i("fesc_min", 0, 3), "eco_raid_n": i("eco_raid_n", 2, 14), "eco_raid_t0": i("eco_raid_t0", 10, 40),
        "eco_raid_types": c("eco_raid_types", ["eco", "eco+depot", "depot", "all"]), "raid_soft_a": c("raid_soft_a", [0.0, 1.0]),
        "f_safe2_margin": i("f_safe2_margin", 2, 12),
        "hunt_R": i("hunt_R", 0, 6), "hunt_esc": i("hunt_esc", 0, 3), "hunt_worth": f("hunt_worth", 2.0, 20.0),
        "lib_bonus": f("lib_bonus", 1.0, 8.0),
    })
    return p


def distance(real, sim, rres, sres, rlast, slast):
    d, n = 0.0, 0
    for t, rf in real.items():
        sf = sim.get(t)
        if sf is None:
            # 한쪽만 끝남: 끝난 쪽 지표가 없으면 큰 벌점
            d += 3.0
            n += 1
            continue
        keys = dict(SCALE, Co=6.0) if SPACE == "v32" else SCALE
        for k, sc in keys.items():
            d += ((rf[k] - sf[k]) / sc) ** 2 / len(keys)
        n += 1
    d = d / max(1, n)
    d += 2.0 * abs(rres - sres)
    return d


def fit_one(args):
    path, ours, trials, outdir = args
    name = os.path.basename(path)[:-5]
    me, op, real, rres, rlast = real_traj(path)
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=3, multivariate=True))
    study.enqueue_trial({})

    def obj(trial):
        params = space_v32(trial) if SPACE == "v32" else space(trial)
        sim, sres, slast, err = sim_traj(path, ours, params)
        if err:
            return 99.0
        return distance(real, sim, rres, sres, rlast, slast)
    study.optimize(obj, n_trials=trials)
    best = study.best_trial
    os.makedirs(outdir, exist_ok=True)
    json.dump(best.params, open(os.path.join(outdir, f"{name}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    sim, sres, slast, _ = sim_traj(path, ours, best.params)
    return name, best.value, rres, sres, real, sim


def fmt(f):
    return f"W {f['Wm']:3d}:{f['Wo']:3d} 건물 {f['Bm']:2d}:{f['Bo']:2d} 경제 {f['Em']}:{f['Eo']} 적F {f['Fo']} 전진 {f['fwd']:.2f} 적W칸 {f.get('Co', '-')}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fit", "show", "realmap"])
    ap.add_argument("--games", required=True)
    ap.add_argument("--ours", default="v16")
    ap.add_argument("--trials", type=int, default=250)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--files", default="")
    ap.add_argument("--vers", default="v16,v19,cv-3")
    ap.add_argument("--attacker", default="dev11", help="흉내 봇 바탕 코드(dev11 = v14 계열, cv-3 = 최신)")
    ap.add_argument("--space", default="", help="v32 = 확장 탐색 + 상대 W 칸 수 맞춤")
    a = ap.parse_args()
    global ATTACKER, SPACE
    ATTACKER = a.attacker
    SPACE = a.space
    files = [f for d in a.games.split(",") for f in sorted(glob.glob(os.path.join(d, "*.json")))]
    if a.files:
        files = [f for f in files if any(x in f for x in a.files.split(","))]
    tag = os.path.basename(a.games.split(",")[0].rstrip("/")).split("_")[0] + "_" + os.path.basename(a.games.split(",")[0].rstrip("/")).split("_")[1]
    outdir = os.path.join(ROOT, "out/tune/mimic", tag if a.attacker == "dev11" else f"{tag}-{a.attacker}")
    if a.cmd == "realmap":
        vers = a.vers.split(",")
        tot = {v: 0.0 for v in vers}
        for f in files:
            name = os.path.basename(f)[:-5]
            me, op, real, rres, rlast = real_traj(f)
            params = json.load(open(os.path.join(outdir, f"{name}.json"), encoding="utf-8"))
            line = []
            for v in vers:
                sim, sres, slast, _ = sim_traj(f, v, params)
                tot[v] += sres
                line.append(f"{v} {sres}({slast}턴)")
            print(f"{name:<32} 실제 {rres}  " + "  ".join(line))
        print("합계 " + "  ".join(f"{v} {tot[v]:.1f}/{len(files)}" for v in vers))
        return
    if a.cmd == "fit":
        with Pool(a.workers) as pool:
            rows = pool.map(fit_one, [(f, a.ours, a.trials, outdir) for f in files])
    else:
        rows = []
        for f in files:
            name = os.path.basename(f)[:-5]
            me, op, real, rres, rlast = real_traj(f)
            pj = os.path.join(outdir, f"{name}.json")
            params = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else {}
            sim, sres, slast, _ = sim_traj(f, a.ours, params)
            rows.append((name, distance(real, sim, rres, sres, rlast, slast), rres, sres, real, sim))
    for name, dist, rres, sres, real, sim in rows:
        print(f"### {name}  거리 {dist:.3f}  실제 결과 {rres} · 재현 {sres}")
        for t in CHECK:
            if t in real:
                print(f"   {t:3d}턴 실제 {fmt(real[t])}")
                if t in sim:
                    print(f"         재현 {fmt(sim[t])}")


if __name__ == "__main__":
    main()

