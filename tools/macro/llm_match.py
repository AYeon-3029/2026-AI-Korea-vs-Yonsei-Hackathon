"""LLM 지휘관 대 cv-3: 지휘관 쪽은 dev24(= cv-3 + 지휘 창구)이고, 10턴마다 전략(focus·defend·posture·max_f)을 받는다.

봇이 결정론적이므로 매 호출마다 0턴부터 저장된 명령을 다시 적용해 재현한다(상태 저장 불필요).
지휘 명령이 없으면 dev24 = cv-3 이라 거울전 = 무승부 → 지휘관이 이기면 그 전략이 cv-3 의 약점이다.

사용 (WSL):
  python3 tools/macro/llm_match.py new  --game g1 --seed 150001 --side Y     # 지휘관 = Y
  python3 tools/macro/llm_match.py step --game g1      # 다음 결정 턴까지 진행 → out/llm/g1/state_<턴>.txt 출력
  (지휘관이 out/llm/g1/cmd_<턴>.json 작성)
  python3 tools/macro/llm_match.py api  --game g1 --model claude-opus-5-5   # API 지휘관으로 끝까지(ANTHROPIC_API_KEY 필요)
명령 JSON: {"focus": [[x,y],...], "defend": [[x,y],...], "posture": "attack|balanced|defend", "max_f": 4, "note": "..."}
"""
from __future__ import annotations

import argparse
import copy
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent, Game, TOTAL, module, value  # noqa: E402
from engine.pipeline import run_turn, team_score  # noqa: E402
from mapgen import generate  # noqa: E402
from runner.protocol import parse_commands, serialize_turn  # noqa: E402
from runner.replay import new_replay, turn_entry  # noqa: E402
from sim import CFG  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
EVERY = 10
LLM_VER = "dev24"
OPP_VER = "cv-3"
NAMES = {"HALL": "학생회관(+2/턴)", "ENG": "공학관(W 비용 -1)", "LIBRARY": "도서관(점령 비용 -1)", "PLAZA": "중앙광장",
         "STATION": "역(TELE)", "HOSPITAL": "병원(전진 생산)", "WATCH": "방송국", "DEPOT": "보급소(+15 1회)"}


def posture_params(p: str, ver: str = LLM_VER) -> dict:
    b = module(ver).P
    if p == "attack":
        return {"w_margin": max(8, b["w_margin"] - 6), "siege_bld_bonus": b["siege_bld_bonus"] * 1.3,
                "guard_radius": max(4, b["guard_radius"] - 4), "risk_local_w": b["risk_local_w"] * 0.7}
    if p == "defend":
        return {"w_margin": b["w_margin"] + 8, "siege_bld_bonus": b["siege_bld_bonus"] * 0.6,
                "guard_radius": b["guard_radius"] + 4, "eco_block_extra": b["eco_block_extra"] + 1}
    return {}


def gdir(game):
    return os.path.join(ROOT, "out/llm", game)


def vers(meta):
    """경기별 (지휘관 봇, 상대 봇). meta.json 에 없으면 처음 12경기 설정(dev24 대 cv-3)."""
    return meta.get("llm", LLM_VER), meta.get("opp", OPP_VER)


def summary(g: Game, side: str, prev_owner: dict) -> str:
    s = g.state
    op = "K" if side == "Y" else "Y"
    lines = [f"턴 {s.turn}/{TOTAL}  당신 = {side} (본진 {s.bases[side]}), 상대 = {op} (본진 {s.bases[op]})",
             f"자원 당신 {s.resources[side]} · 상대 {s.resources[op]}   점수(보유 건물 점수 합) 당신 {team_score(s, side)} · 상대 {team_score(s, op)}"]
    W = {side: 0, op: 0}
    F = {side: 0, op: 0}
    cells = {side: {}, op: {}}
    for (x, y, t, k), n in s.units.items():
        if n <= 0 or t not in W:
            continue
        if k == "W":
            W[t] += n
        if k == "F":
            F[t] += n
        c = cells[t].setdefault((x, y), [0, 0])
        c[0 if k == "W" else 1] += n if k in ("W", "F") else 0
    lines.append(f"병력 W 당신 {W[side]} · 상대 {W[op]}   F 당신 {F[side]} · 상대 {F[op]}")
    lines.append("건물 (좌표 종류 소유 점수 [직전 결정 이후 변화]):")
    for b in sorted(s.buildings.values(), key=lambda b: (b.y, b.x)):
        own = "당신" if b.owner == side else "상대" if b.owner == op else "중립"
        ch = ""
        pv = prev_owner.get((b.x, b.y))
        if pv is not None and pv != b.owner:
            ch = f" [{('당신' if pv == side else '상대' if pv == op else '중립')}→{own}]"
        d_me = abs(b.x - s.bases[side][0]) + abs(b.y - s.bases[side][1])
        d_op = abs(b.x - s.bases[op][0]) + abs(b.y - s.bases[op][1])
        lines.append(f"  ({b.x},{b.y}) {NAMES.get(b.btype, b.btype)} {own} 점수 {b.score} · 본진거리 당신 {d_me}/상대 {d_op}{ch}")
    for t, who in ((side, "당신"), (op, "상대")):
        top = sorted(cells[t].items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:14]
        lines.append(f"{who} 유닛 칸(좌표:W/F): " + " ".join(f"({x},{y}):{w}/{f}" for (x, y), (w, f) in top))
    rows = []
    bpos = {(b.x, b.y): b for b in s.buildings.values()}
    for y in range(15):
        r = ""
        for x in range(15):
            if (x, y) in bpos:
                b = bpos[(x, y)]
                ch = b.btype[0]
                r += ch.upper() if b.owner == side else ch.lower() if b.owner == op else "?"
            elif s.terrain[y][x] in ("#", "X"):
                r += "#"
            elif (x, y) == s.bases[side]:
                r += "@"
            elif (x, y) == s.bases[op]:
                r += "&"
            else:
                r += "."
        rows.append(f"  {y:2d} {r}")
    lines.append("지도(x 0→14, 대문자=당신 건물, 소문자=상대, ?=중립, @=당신 본진, &=상대 본진, #=장애물):")
    lines += rows
    return "\n".join(lines)


GUIDE = """당신은 깃발 대항전 봇의 지휘관이다. 유닛 명령은 실행 봇이 내리고, 당신은 10턴마다 전략만 정한다.
규칙 요약: F(깃발병)가 건물 칸에 살아 있으면 점령(중립→소유 2, 상대 소유는 중립화 2 + 다음 턴 점령 2). W(전투병)는 같은 칸에서 1:1 상쇄,
W 가 남은 쪽이 상대 F 를 제거. 160턴 뒤 보유 건물 점수 합이 높으면 승리, 상대 보유 점수 0 + 내가 총점 과반이면 즉시 승리.
학생회관 = 턴당 자원 +2, 공학관 = W 비용 3→2, 도서관 = 점령 비용 −1, 병원 = 전진 생산, 역 2개 이상 = TELE, 보급소 = 첫 점령 +15.
명령(JSON 한 개만 출력):
  focus  : 우선 점령·공격할 건물 좌표 목록(가치 2배)       defend : 반드시 지킬 당신 건물 좌표 목록(W 주둔)
  posture: "attack"(공세·원정↑) | "balanced"(기본) | "defend"(수비·원정↓)       max_f : 유지할 F 수(2~8, 기본 4)
  note   : 판단 이유 한 줄
예: {"focus": [[12,3]], "defend": [[2,11]], "posture": "balanced", "max_f": 4, "note": "..."}"""


def replay(game):
    meta = json.load(open(os.path.join(gdir(game), "meta.json"), encoding="utf-8"))
    side = meta["side"]
    lv, ov = vers(meta)
    me = Agent(lv, {})
    op = Agent(ov, {})
    g = Game(meta["seed"], *((me, op) if side == "Y" else (op, me)))
    m = module(lv)
    prev_owner = {(b.x, b.y): b.owner for b in g.state.buildings.values()}
    cmd = None
    while g.result is None:
        t = g.state.turn
        if t % EVERY == 0 and t < TOTAL:
            p = os.path.join(gdir(game), f"cmd_{t:03d}.json")
            if not os.path.exists(p):
                return g, side, t, summary(g, side, prev_owner)
            cmd = json.load(open(p, encoding="utf-8"))
            me.set_params({**posture_params(cmd.get("posture", "balanced"), lv),
                           **({"max_f": int(cmd["max_f"])} if cmd.get("max_f") else {})})
            prev_owner = {(b.x, b.y): b.owner for b in g.state.buildings.values()}
        m.CMD = {"focus": [list(v) for v in cmd.get("focus", [])], "defend": [list(v) for v in cmd.get("defend", [])]} if cmd else None
        g.step()
    m.CMD = None
    return g, side, None, None


def export(game):
    """끝난 경기를 공식 리플레이 형식(tools/viewer.html)으로 저장한다. 지휘관 명령·판단 이유는 llm_commands 에 턴별로 넣는다.
    저장 위치: out/replays/llm/<game>-seed<시드>-LLM<진영>.json"""
    meta = json.load(open(os.path.join(gdir(game), "meta.json"), encoding="utf-8"))
    side, seed = meta["side"], meta["seed"]
    lv, ov = vers(meta)
    me = Agent(lv, {})
    op = Agent(ov, {})
    g = Game(seed, *((me, op) if side == "Y" else (op, me)))
    gmap = generate(seed, CFG)
    base = {"dev24": "cv-3", "dev27": "v20", "dev34": "cv-14", "dev41": "v27"}.get(lv, lv)
    teams = {side: {"name": f"LLM 지휘관 ({lv} = {base} + 지휘)", "command": "tools/macro/llm_match.py"},
             ("K" if side == "Y" else "Y"): {"name": ov, "command": f"Model/history/{ov}/main.py"}}
    rp = new_replay(seed, CFG, gmap, teams)
    rp["llm_commands"] = {}
    m = module(lv)
    cmd = None
    while g.result is None:
        t = g.state.turn
        if t % EVERY == 0 and t < TOTAL:
            p = os.path.join(gdir(game), f"cmd_{t:03d}.json")
            if not os.path.exists(p):
                raise SystemExit(f"{game}: {t}턴 명령이 없다 — 경기가 끝나지 않았다")
            cmd = json.load(open(p, encoding="utf-8"))
            rp["llm_commands"][str(t)] = cmd
            me.set_params({**posture_params(cmd.get("posture", "balanced"), lv),
                           **({"max_f": int(cmd["max_f"])} if cmd.get("max_f") else {})})
        m.CMD = {"focus": [list(v) for v in cmd.get("focus", [])], "defend": [list(v) for v in cmd.get("defend", [])]} if cmd else None
        turn = t + 1
        raw = {tm: g.agents[tm].decide(serialize_turn(g.state, tm, turn)) for tm in ("Y", "K")}
        cy, ck = parse_commands(raw["Y"]), parse_commands(raw["K"])
        events = []
        g.state, g.result = run_turn(g.state, cy, ck, events)
        rp["turns"].append(turn_entry(turn, raw["Y"], raw["K"], cy, ck, g.state, events))
    m.CMD = None
    res = dict(g.result)
    res["seed"] = seed
    rp["result"] = res
    out = os.path.join(ROOT, "out/replays/llm", f"{game}-seed{seed}-LLM{side}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(json.dumps(rp, ensure_ascii=False))
    return out, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["new", "step", "api", "export"])
    ap.add_argument("--game", required=True)
    ap.add_argument("--seed", type=int, default=150001)
    ap.add_argument("--side", default="Y")
    ap.add_argument("--model", default="claude-opus-5-5")
    a = ap.parse_args()
    d = gdir(a.game)
    if a.cmd == "export":
        out, res = export(a.game)
        print(f"리플레이 저장: {out}  (승자 {res['winner']}, {res['reason']})")
        return
    if a.cmd == "new":
        os.makedirs(d, exist_ok=True)
        json.dump({"seed": a.seed, "side": a.side}, open(os.path.join(d, "meta.json"), "w"))
        a.cmd = "step"
    if a.cmd == "step":
        g, side, t, text = replay(a.game)
        if t is not None:
            open(os.path.join(d, f"state_{t:03d}.txt"), "w", encoding="utf-8").write(text)
            print(text)
            print(f"\n>>> 결정 필요: {d}/cmd_{t:03d}.json")
        else:
            r = g.result
            print(f"경기 끝 {g.state.turn}턴: 승자 {r['winner']} ({r['reason']}) · 지휘관 {side} 결과 {value(r, side)}")
            json.dump({"turn": g.state.turn, **{k: v for k, v in r.items() if k in ("winner", "reason")},
                       "llm_value": value(r, side)}, open(os.path.join(d, "result.json"), "w"))
            print("리플레이 저장:", export(a.game)[0])
        return
    if a.cmd == "api":
        import anthropic
        key = os.environ.get("ANTHROPIC_API_KEY")
        kf = os.path.expanduser("~/.anthropic_key")      # 환경변수가 없으면 WSL 홈의 키 파일(저장소 밖)을 읽는다
        if not key and os.path.exists(kf):
            key = open(kf).read().strip()
        if not key:
            sys.exit("API 키 없음: WSL 에서  echo '<키>' > ~/.anthropic_key && chmod 600 ~/.anthropic_key")
        client = anthropic.Anthropic(api_key=key)
        while True:
            g, side, t, text = replay(a.game)
            if t is None:
                r = g.result
                print(f"경기 끝 {g.state.turn}턴: 승자 {r['winner']} ({r['reason']}) · 지휘관 결과 {value(r, side)}")
                json.dump({"turn": g.state.turn, **{k: v for k, v in r.items() if k in ("winner", "reason")},
                           "llm_value": value(r, side)}, open(os.path.join(d, "result.json"), "w"))
                print("리플레이 저장:", export(a.game)[0])
                return
            hist = []
            for p in sorted(glob.glob(os.path.join(d, "cmd_*.json")))[-3:]:
                hist.append(os.path.basename(p) + " " + open(p, encoding="utf-8").read())
            msg = client.messages.create(
                model=a.model, max_tokens=2000, system=GUIDE,
                messages=[{"role": "user", "content": text + "\n\n직전 명령:\n" + "\n".join(hist) + "\n\nJSON 한 개만 출력."}])
            out = "".join(b.text for b in msg.content if b.type == "text")
            js = json.loads(out[out.index("{"): out.rindex("}") + 1])
            json.dump(js, open(os.path.join(d, f"cmd_{t:03d}.json"), "w", encoding="utf-8"), ensure_ascii=False)
            print(f"{t}턴 명령 {js}")


if __name__ == "__main__":
    main()
