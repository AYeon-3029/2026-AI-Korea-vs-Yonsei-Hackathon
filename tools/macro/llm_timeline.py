"""LLM 지휘 경기를 cv-3 쪽에서 본 타임라인: 10턴마다 점수·W·자원·건물 수, 그리고 cv-3 F 전사(주변 아군 W 유무)·건물 득실.
사용 (WSL): python3 tools/macro/llm_timeline.py b150005 [b150007 ...]
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import llm_match as L  # noqa: E402
from sim import Agent, Game  # noqa: E402
from engine.pipeline import team_score  # noqa: E402

SH = {"HALL": "학", "ENG": "공", "LIBRARY": "도", "PLAZA": "광", "STATION": "역", "HOSPITAL": "병", "WATCH": "방", "DEPOT": "보"}


def main(game):
    meta = json.load(open(os.path.join(L.gdir(game), "meta.json"), encoding="utf-8"))
    cv = "K" if meta["side"] == "Y" else "Y"
    op = meta["side"]
    llm, o = Agent(L.LLM_VER, {}), Agent(L.OPP_VER, {})
    g = Game(meta["seed"], *((llm, o) if meta["side"] == "Y" else (o, llm)))
    m = L.module(L.LLM_VER)
    cmd = None
    print(f"##### {game} 시드 {meta['seed']}  cv-3={cv} 본진 {g.state.bases[cv]}  LLM={op} 본진 {g.state.bases[op]}")
    prev_own = {(b.x, b.y): b.owner for b in g.state.buildings.values()}
    while g.result is None:
        t = g.state.turn
        p = os.path.join(L.gdir(game), f"cmd_{t:03d}.json")
        if t % L.EVERY == 0 and os.path.exists(p):
            cmd = json.load(open(p, encoding="utf-8"))
            llm.set_params({**L.posture_params(cmd.get("posture", "balanced")),
                            **({"max_f": int(cmd["max_f"])} if cmd.get("max_f") else {})})
        m.CMD = {"focus": cmd.get("focus", []), "defend": cmd.get("defend", [])} if cmd else None
        before = dict(g.state.units)
        g.step()
        s = g.state
        ev = []
        for b in s.buildings.values():
            po = prev_own[(b.x, b.y)]
            if po != b.owner:
                who = "cv" if b.owner == cv else "LLM" if b.owner == op else ("cv잃음" if po == cv else "LLM잃음")
                ev.append(f"{SH[b.btype]}{b.score}({b.x},{b.y}){who}")
            prev_own[(b.x, b.y)] = b.owner
        # cv-3 F 전사
        for (x, y, tm, k), n in before.items():
            if tm != cv or k != "F" or n <= 0:
                continue
        fl = sum(n for (x, y, tm, k), n in before.items() if tm == cv and k == "F") \
            - sum(n for (x, y, tm, k), n in s.units.items() if tm == cv and k == "F")
        if ev:
            print(f"  {s.turn:3d}턴 " + " ".join(ev))
        if s.turn % 10 == 0 or g.result:
            W = {tm: sum(n for (x, y, t2, k), n in s.units.items() if t2 == tm and k == "W") for tm in (cv, op)}
            F = {tm: sum(n for (x, y, t2, k), n in s.units.items() if t2 == tm and k == "F") for tm in (cv, op)}
            nb = {tm: sum(1 for b in s.buildings.values() if b.owner == tm) for tm in (cv, op)}
            print(f"== {s.turn:3d}턴 점수 cv {team_score(s, cv)}:{team_score(s, op)} LLM  W {W[cv]}:{W[op]}  F {F[cv]}:{F[op]}  "
                  f"건물 {nb[cv]}:{nb[op]}  자원 {s.resources[cv]}:{s.resources[op]}  "
                  f"학·공 {sum(1 for b in s.buildings.values() if b.owner == cv and b.btype in ('HALL', 'ENG'))}:"
                  f"{sum(1 for b in s.buildings.values() if b.owner == op and b.btype in ('HALL', 'ENG'))}")
    print(f"결과 {g.result}")


if __name__ == "__main__":
    for gm in sys.argv[1:]:
        main(gm)
