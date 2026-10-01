"""LLM 사냥 덧씌우기 대전: 시험 봇(prey) 대 상대 봇(기본 cv-52) + LLM 사냥꾼.
상대 봇이 기본 수를 두고, 시험 봇의 F 3칸 안에 상대 W 가 있는 턴에만 LLM 이 그 근처 상대 W 이동을 직접 덮어쓴다.
목적: 시뮬 봇이 재현하지 못하는 'F 사냥'(실제 상위 팀: F 1칸 옆 W 의 덮침 71%, 경기당 우리 F 사망 9~30)을 중립적으로 재현해
F 수정판의 F 사망 수를 비교한다. 봇이 결정론적이므로 매 호출마다 0턴부터 저장된 덮어쓰기를 다시 적용해 재현한다.

사용 (WSL):
  python3 tools/macro/hunt_match.py new  --game h1 --seed 160001 --side K --ver v32 [--params '{}'] [--opp cv-52] [--until 100]
  python3 tools/macro/hunt_match.py step --game h1      # 다음 사냥 기회 턴까지 진행 → out/llm/hunt/h1/state_<턴>.txt
  (사냥꾼이 out/llm/hunt/h1/ovr_<턴>.json 작성: {"moves": ["MOVE x y W n D", ...], "note": "..."}; 덮어쓰지 않으려면 {"moves": []})
  python3 tools/macro/hunt_match.py export --game h1    # 끝난 경기 → out/replays/llm/hunt-<game>-seed<시드>.json
덮어쓰기 규칙: 덮어쓰기 줄이 있는 출발 칸의 상대 봇 W 이동은 모두 지우고 덮어쓰기 줄로 바꾼다(언급 안 한 W 는 그 칸에 머문다).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, TOTAL, CFG, value  # noqa: E402
from engine.pipeline import run_turn, team_score  # noqa: E402
from mapgen import generate  # noqa: E402
from runner.protocol import parse_commands, serialize_turn  # noqa: E402
from runner.replay import new_replay, turn_entry  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
R_OPP = int(os.environ.get("HUNT_R", 2))          # 사냥 기회: 시험 봇 F 에서 이 거리 안에 상대 W(본진·자기 건물 위 F 제외)
DIRS = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}

GUIDE = """당신은 사냥꾼(상대 {hs} 진영)이다. 목표: 시험 봇({ps} 진영)의 F(깃발병)를 최대한 많이 잡는 것, 단 당신 W 를 헛되이 잃지 않는다.
규칙: 모든 유닛은 동시에 1칸(상하좌우) 움직인다. 같은 칸에서 W 끼리 1:1 상쇄, 그 칸에 당신 W 가 남으면 그 칸의 상대 F 는 모두 죽는다.
F 는 싸우지 못한다. 상대 F 는 이번 턴에 제자리 또는 1칸 움직인다(어느 쪽일지 예측하라). 상대 W 가 같은 칸에 오면 상쇄된다.
요령: F 가 갈 만한 칸(목표 건물 방향)과 도망칠 칸을 넓게 막아라. 한 칸에 몰지 말고 여러 칸에 1~2명씩 퍼뜨려 퇴로를 끊어라.
출력: JSON 하나. {{"moves": ["MOVE x y W n D", ...], "note": "한 줄 이유"}}  (D = U/D/L/R, x y 는 출발 칸, n 은 그 칸 W 수 이하)
덮어쓰기 줄이 있는 출발 칸은 봇의 W 이동이 전부 지워지고 당신 줄로 바뀐다. 줄이 없는 칸은 봇 제안대로 움직인다."""


def gdir(game):
    return os.path.join(ROOT, "out/llm/hunt", game)


def load_meta(game):
    return json.load(open(os.path.join(gdir(game), "meta.json"), encoding="utf-8"))


def cells(s, team, kind):
    o = {}
    for (x, y, t, k), n in s.units.items():
        if t == team and k == kind and n > 0:
            o[(x, y)] = o.get((x, y), 0) + n
    return o


def opportunity(s, ps, hs):
    F = cells(s, ps, "F"); E = cells(s, hs, "W"); PW = cells(s, ps, "W")
    own = {(b.x, b.y) for b in s.buildings.values() if b.owner == ps} | {tuple(s.bases[ps])}
    out = []
    for f in F:
        if f in own: continue
        en = sum(n for e, n in E.items() if abs(f[0] - e[0]) + abs(f[1] - e[1]) <= R_OPP)
        my = sum(n for e, n in PW.items() if abs(f[0] - e[0]) + abs(f[1] - e[1]) <= 1)
        if en > my: out.append(f)       # 엄호보다 많은 적 W 가 가까이 있는 F 만(잡을 가능성이 있는 장면)
    return out


def apply_override(lines, ovr):
    origins = set()
    for l in ovr:
        p = l.split()
        if len(p) == 6 and p[0] == "MOVE" and p[3] == "W":
            origins.add((int(p[1]), int(p[2])))
    kept = [l for l in lines if not (l.startswith("MOVE ") and l.split()[3] == "W" and (int(l.split()[1]), int(l.split()[2])) in origins)]
    return kept + [l for l in ovr if l.startswith("MOVE ")]


def state_text(g, ps, hs, prey_moves, bot_moves, deaths):
    s = g.state
    lines = [(GUIDE.format(hs=hs, ps=ps) + "\n") if os.environ.get("HUNT_GUIDE") else "",
             f"턴 {s.turn + 1} 결정 (지금까지 시험 봇 F 사망 {deaths})   점수 사냥꾼 {team_score(s, hs)} · 시험 봇 {team_score(s, ps)}"]
    F = cells(s, ps, "F"); PW = cells(s, ps, "W"); HW = cells(s, hs, "W")
    bpos = {(b.x, b.y): b for b in s.buildings.values()}
    for f in sorted(opportunity(s, ps, hs)):
        lines.append(f"\n■ 시험 봇 F {F[f]}명 @ {f}" + (f" (직전 이동 {prey_moves[f]})" if f in prey_moves else ""))
        x0, y0 = f
        lines.append("   지도 (x→, 칸 표기: F=시험F, 숫자/문자: h3=당신W3, p2=시험W2, #=장애물, B=건물 소유 표시 [Y/K/N])")
        for y in range(max(0, y0 - 4), min(15, y0 + 5)):
            row = []
            for x in range(max(0, x0 - 4), min(15, x0 + 5)):
                c = (x, y); tag = ""
                if s.terrain[y][x] in ("#", "X"):
                    tag = "#"
                else:
                    if c in F: tag += f"F{F[c]}"
                    if c in HW: tag += f"h{HW[c]}"
                    if c in PW: tag += f"p{PW[c]}"
                    if c in bpos: tag += f"[{bpos[c].btype[:2]}{bpos[c].owner}]"
                    if c == tuple(s.bases[hs]): tag += "[당신본진]"
                    if c == tuple(s.bases[ps]): tag += "[시험본진]"
                row.append(f"{tag or '.':>9s}")
            lines.append(f"   y{y:2d} " + "".join(row))
        lines.append("   x  " + "".join(f"{x:>9d}" for x in range(max(0, x0 - 4), min(15, x0 + 5))))
        near = sorted((e, n) for e, n in HW.items() if abs(e[0] - x0) + abs(e[1] - y0) <= R_OPP + 1)
        lines.append("   근처 당신 W: " + " ".join(f"{e}:{n}" for e, n in near))
        bm = [l for l in bot_moves if l.startswith("MOVE ") and l.split()[3] == "W"
              and (int(l.split()[1]), int(l.split()[2])) in dict(near)]
        lines.append("   봇 제안(그 W 들): " + ("; ".join(bm) if bm else "없음(제자리)"))
    return "\n".join(lines)


def run(game, export=False):
    meta = load_meta(game)
    ps = meta["side"]; hs = "K" if ps == "Y" else "Y"
    prey = Agent(meta["ver"], meta.get("params") or {})
    hunter = Agent(meta.get("opp", "cv-52"), {})
    g = Game(meta["seed"], *((prey, hunter) if ps == "Y" else (hunter, prey)))
    until = meta.get("until", TOTAL)
    deaths = 0; prey_moves = {}; n_ovr = 0
    rp = None
    if export:
        teams = {ps: {"name": f"시험 봇 {meta['ver']} {json.dumps(meta.get('params') or {})}", "command": f"Model/history/{meta['ver']}/main.py"},
                 hs: {"name": f"LLM 사냥꾼 + {meta.get('opp', 'cv-52')}", "command": "tools/macro/hunt_match.py"}}
        rp = new_replay(meta["seed"], CFG, generate(meta["seed"], CFG), teams)
        rp["llm_overrides"] = {}
    while g.result is None and g.state.turn < until:
        t = g.state.turn + 1
        raw = {tm: g.agents[tm].decide(serialize_turn(g.state, tm, t)) for tm in ("Y", "K")}
        if opportunity(g.state, ps, hs):
            p = os.path.join(gdir(game), f"ovr_{t:03d}.json")
            if os.environ.get("HUNT_AUTO"):
                n_ovr += 1          # 자동(덮어쓰기 없음) 모드: 기회 턴 수만 센다
            elif not os.path.exists(p):
                if export:
                    raise SystemExit(f"{t}턴 덮어쓰기 없음 — 경기가 끝나지 않았다")
                return g, t, state_text(g, ps, hs, prey_moves, raw[hs], deaths), deaths, n_ovr
            ov = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
            if ov.get("moves"):
                raw[hs] = apply_override(raw[hs], ov["moves"]); n_ovr += 1
                if rp is not None:
                    rp["llm_overrides"][str(t)] = ov
        before = sum(cells(g.state, ps, "F").values())
        spawned = sum(int(l.split()[2]) for l in raw[ps] if l.startswith("SPAWN F"))
        prey_moves = {}
        for l in raw[ps]:
            q = l.split()
            if q[0] == "MOVE" and q[3] == "F":
                d = DIRS[q[5]]; prey_moves[(int(q[1]) + d[0], int(q[2]) + d[1])] = q[5]
        cy, ck = parse_commands(raw["Y"]), parse_commands(raw["K"])
        events = []
        g.state, g.result = run_turn(g.state, cy, ck, events)
        deaths += max(0, before + spawned - sum(cells(g.state, ps, "F").values()))
        if rp is not None:
            rp["turns"].append(turn_entry(t, raw["Y"], raw["K"], cy, ck, g.state, events))
    if rp is not None:
        res = dict(g.result or {"winner": None, "reason": f"cut@{g.state.turn}"})
        res["seed"] = meta["seed"]; res["prey_f_deaths"] = deaths
        res["score"] = {tm: team_score(g.state, tm) for tm in ("Y", "K")}
        rp["result"] = res
        out = os.path.join(ROOT, "out/replays/llm", f"hunt-{game}-seed{meta['seed']}.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w", encoding="utf-8").write(json.dumps(rp, ensure_ascii=False))
        return out
    return g, None, None, deaths, n_ovr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["new", "step", "export"])
    ap.add_argument("--game", required=True)
    ap.add_argument("--seed", type=int, default=160001)
    ap.add_argument("--side", default="K")
    ap.add_argument("--ver", default="v32")
    ap.add_argument("--params", default="{}")
    ap.add_argument("--opp", default="cv-52")
    ap.add_argument("--until", type=int, default=TOTAL)
    a = ap.parse_args()
    d = gdir(a.game)
    if a.cmd == "export":
        print("리플레이 저장:", run(a.game, export=True))
        return
    if a.cmd == "new":
        os.makedirs(d, exist_ok=True)
        json.dump({"seed": a.seed, "side": a.side, "ver": a.ver, "params": json.loads(a.params), "opp": a.opp, "until": a.until},
                  open(os.path.join(d, "meta.json"), "w"))
    g, t, text, deaths, n_ovr = run(a.game)
    meta = load_meta(a.game); ps = meta["side"]; hs = "K" if ps == "Y" else "Y"
    if t is not None:
        open(os.path.join(d, f"state_{t:03d}.txt"), "w", encoding="utf-8").write(text)
        print(text)
        print(f"\n>>> 결정 필요: {d}/ovr_{t:03d}.json")
    else:
        r = g.result
        info = {"turn": g.state.turn, "prey_f_deaths": deaths, "overrides": n_ovr,
                "score": {"prey": team_score(g.state, ps), "hunter": team_score(g.state, hs)},
                "winner": (r or {}).get("winner"), "reason": (r or {}).get("reason")}
        json.dump(info, open(os.path.join(d, "result.json"), "w"))
        print("경기 끝:", info)


if __name__ == "__main__":
    main()
