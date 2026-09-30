"""리더보드(서버) 리플레이 JSON → 우리 뷰어(tools/viewer.html) 형식 변환.

서버 파일은 우리 봇 시점 기록이다: 턴마다 우리가 받은 관측(observation: 지형·건물 소유·양쪽 유닛·자원·이벤트)과
우리가 낸 명령(command.lines). 상대 명령은 없다. 건물 점수는 우리에게 공개된 것만 있으므로,
맵이 180° 대칭인 점을 이용해 짝 건물의 공개 점수로 채우고, 그래도 모르면 0 으로 둔다(뷰어에서 숨김 표시).

사용:
  python3 tools/lb_to_replay.py "Real Match Replay/V21_0930_8am"          # 폴더 안 vs*.json 전부
  python3 tools/lb_to_replay.py "Real Match Replay/V21_0930_8am/vs1026.json" [--team 어잌후]
결과: out/replays/leaderboard/<폴더 이름>/<원래 파일 이름>  (뷰어에서 여러 파일을 한 번에 열 수 있다)
"""
from __future__ import annotations

import argparse
import ast
import glob
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _val(v):
    """관측 값이 문자열로 저장된 경우(파이썬 표기)를 되살린다."""
    if isinstance(v, str):
        try:
            return ast.literal_eval(v)
        except (ValueError, SyntaxError):
            return v
    return v


def convert(path: str, team: str) -> tuple[str, dict]:
    src = json.load(open(path, encoding="utf-8"))
    side = src["side"]
    opp = "K" if side == "Y" else "Y"
    turns = src["turns"]
    obs0 = {k: _val(v) for k, v in turns[0]["observation"].items()}
    terrain = obs0["map"]
    h, w = len(terrain), len(terrain[0])
    blds = obs0["buildings"]

    # 공개 점수 모으기(관측의 score, revealed.buildingScores) + 180° 대칭 짝으로 채우기
    score = {}
    for t in turns:
        rv = (t.get("revealed") or {}).get("buildingScores") or {}
        for k, v in rv.items():
            score[int(k)] = v
        for b in _val(t["observation"].get("buildings", [])) or []:
            if b.get("score") is not None:
                score[b["id"]] = b["score"]
    pos = {(b["x"], b["y"]): b["id"] for b in blds}
    for b in blds:
        if b["id"] not in score:
            mid = pos.get((w - 1 - b["x"], h - 1 - b["y"]))
            if mid in score:
                score[b["id"]] = score[mid]

    name = os.path.splitext(os.path.basename(path))[0]
    opp_name = name[2:] if name.startswith("vs") else name
    rp = {
        "seed": src.get("gameId", name),
        "config": {"resource": {"start_resource": 10}},
        "map": {"width": w, "height": h, "terrain": terrain,
                "buildings": [{"id": b["id"], "x": b["x"], "y": b["y"], "type": b["type"], "score": score.get(b["id"], 0)}
                              for b in blds]},
        "teams": {side: {"name": f"{team} (우리)", "command": "리더보드"}, opp: {"name": opp_name, "command": "리더보드"}},
        "turns": [],
        "result": dict(src.get("result") or {}),
        "source": {"file": os.path.relpath(path, ROOT), "evaluationId": src.get("evaluationId"), "gameId": src.get("gameId"),
                   "note": "리더보드 우리 봇 시점 기록 변환(상대 명령 없음, 미공개 점수는 대칭 짝으로 채우거나 0)"},
    }
    revealed = set()
    last_scores = {}
    for t in turns[1:]:
        o = {k: _val(v) for k, v in t["observation"].items()}
        revealed |= {int(i) for i in ((t.get("revealed") or {}).get("buildingIds") or [])}
        bl = o.get("buildings") or []
        units = [list(u) for u in (o.get("units") or [])]
        res = o.get("resources") or {}
        occ = o.get("occTurns") or {}
        ev = []
        for e in o.get("events") or []:
            e = dict(e)
            if "kind" in e and "type" not in e:
                e["type"] = e.pop("kind")
            ev.append(e)
        sc = o.get("scores") or {}
        last_scores = sc or last_scores
        rp["turns"].append({
            "turn": int(o.get("turn", t.get("turn", 0))),
            "commands": {side: (t.get("command") or {}).get("lines", []), opp: []},
            "events": ev,
            "state": {
                "resources": {"Y": res.get("Y") or 0, "K": res.get("K") or 0},
                "units": units,
                "buildings": [{"id": b["id"], "owner": b.get("owner", "N"), "stage": b.get("stage", 0)} for b in bl],
                "revealed": {side: sorted(revealed), opp: []},
                "occupation": {"Y": occ.get("Y") or 0, "K": occ.get("K") or 0},
            },
        })
    # 서버 결과에 점수가 없으면 마지막 턴 소유로 계산(공개/대칭 점수 기준)
    if "score" not in rp["result"] and rp["turns"]:
        st = rp["turns"][-1]["state"]
        sm = {b["id"]: b["score"] for b in rp["map"]["buildings"]}
        rp["result"]["score"] = {tm: sum(sm[b["id"]] for b in st["buildings"] if b["owner"] == tm) for tm in ("Y", "K")}
    rp["result"]["our_side"] = side
    rp["result"]["turns"] = len(rp["turns"])
    out_dir = os.path.join(ROOT, "out/replays/leaderboard", os.path.basename(os.path.dirname(os.path.abspath(path))))
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.basename(path))
    json.dump(rp, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    return out, rp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--team", default="어잌후")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.path, "vs*.json"))) if os.path.isdir(a.path) else [a.path]
    for f in files:
        out, rp = convert(f, a.team)
        r = rp["result"]
        me = r["our_side"]
        verdict = "승" if r.get("winner") == me else "패" if r.get("winner") in ("Y", "K") else "무"
        print(f"{os.path.basename(f):32s} 우리={me} {verdict} ({r.get('reason')}) 점수 {r.get('score')} 턴 {r['turns']} → {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main()
