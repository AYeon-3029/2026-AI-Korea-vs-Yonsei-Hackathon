"""일반 대결 한 판의 타임라인(llm_timeline.py 와 같은 형식): 10턴마다 점수·W·자원·건물, 건물 득실.
사용 (WSL): python3 tools/macro/tl_game.py v21 mc16_신촌을못가 181032 Y [최대 턴]
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game  # noqa: E402
from branch import OPPS  # noqa: E402
from engine.pipeline import team_score  # noqa: E402
SH = {"HALL": "학", "ENG": "공", "LIBRARY": "도", "PLAZA": "광", "STATION": "역", "HOSPITAL": "병", "WATCH": "방", "DEPOT": "보"}
ver, opp, seed, side = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
T = int(sys.argv[5]) if len(sys.argv) > 5 else 160
me = Agent(ver, {}); o = Agent(*OPPS[opp]) if opp in OPPS else Agent(opp, {})
g = Game(seed, *((me, o) if side == "Y" else (o, me)))
op = "K" if side == "Y" else "Y"
bm, bo = g.state.bases[side], g.state.bases[op]
dd = lambda b, p: abs(b.x - p[0]) + abs(b.y - p[1])
print(f"#### {ver}={side} 본진 {bm} vs {opp} 본진 {bo} 시드 {seed}")
print("  우리 쪽 건물:", " ".join(f"{SH[b.btype]}{b.score}({b.x},{b.y})" for b in g.state.buildings.values() if dd(b, bm) < dd(b, bo)))
print("  중앙 건물:", " ".join(f"{SH[b.btype]}{b.score}({b.x},{b.y})" for b in g.state.buildings.values() if dd(b, bm) == dd(b, bo)))
prev = {(b.x, b.y): b.owner for b in g.state.buildings.values()}
while g.result is None and g.state.turn < T:
    g.step(); s = g.state; ev = []
    for b in s.buildings.values():
        p = prev[(b.x, b.y)]
        if p != b.owner:
            who = "우리" if b.owner == side else "적" if b.owner == op else ("우리잃음" if p == side else "적잃음")
            ev.append(f"{SH[b.btype]}{b.score}({b.x},{b.y}){who}")
        prev[(b.x, b.y)] = b.owner
    if ev:
        print(f"  {s.turn:3d}턴 " + " ".join(ev))
    if s.turn % 10 == 0 or g.result:
        W = {t: sum(n for (x, y, t2, k), n in s.units.items() if t2 == t and k == "W") for t in (side, op)}
        F = {t: sum(n for (x, y, t2, k), n in s.units.items() if t2 == t and k == "F") for t in (side, op)}
        print(f"== {s.turn:3d}턴 점수 {team_score(s, side)}:{team_score(s, op)}  W {W[side]}:{W[op]}  F {F[side]}:{F[op]}  자원 {s.resources[side]}:{s.resources[op]}")
print("결과", g.result)
