"""여러 LLM 지휘 경기를 한꺼번에 진행하고 결정 턴마다 짧은 전황 요약을 출력한다(지휘관이 한 번에 여러 경기 명령을 쓰도록).

사용 (WSL):
  python3 tools/macro/llm_batch.py new  --prefix b --seeds 150003-150012      # 진영은 Y/K 번갈아
  python3 tools/macro/llm_batch.py step --prefix b                             # 명령이 있는 경기는 다음 결정 턴까지 진행
각 경기의 명령은 out/llm/<prefix><시드>/cmd_<턴>.json (llm_match.py 와 같은 형식). 끝난 경기는 리플레이 자동 저장.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import llm_match as L  # noqa: E402
from branch import parse_range  # noqa: E402
from engine.pipeline import team_score  # noqa: E402

SHORT = {"HALL": "학", "ENG": "공", "LIBRARY": "도", "PLAZA": "광", "STATION": "역", "HOSPITAL": "병", "WATCH": "방", "DEPOT": "보"}


def brief(g, side, prev_owner):
    s = g.state
    op = "K" if side == "Y" else "Y"
    W = {side: 0, op: 0}
    enF, myW = [], {}
    for (x, y, t, k), n in s.units.items():
        if n <= 0:
            continue
        if k == "W":
            W[t] += n
            if t == side:
                myW[(x, y)] = myW.get((x, y), 0) + n
        if k == "F" and t == op:
            enF.append((x, y))
    bm, bo = s.bases[side], s.bases[op]

    def fmt(b):   # * = 우리 본진이 더 가까운 건물
        near = abs(b.x - bm[0]) + abs(b.y - bm[1]) < abs(b.x - bo[0]) + abs(b.y - bo[1])
        return f"{SHORT[b.btype]}{b.score}({b.x},{b.y}){'*' if near else ''}"
    mine = [fmt(b) for b in s.buildings.values() if b.owner == side]
    theirs = [fmt(b) for b in s.buildings.values() if b.owner == op]
    neut = [fmt(b) for b in s.buildings.values() if b.owner == "N"]
    ch = [f"{fmt(b)}:{'우' if prev_owner.get((b.x, b.y)) == side else '적' if prev_owner.get((b.x, b.y)) == op else 'N'}→"
          f"{'우' if b.owner == side else '적' if b.owner == op else 'N'}"
          for b in s.buildings.values() if prev_owner.get((b.x, b.y)) not in (None, b.owner)]
    thr = []
    for (x, y) in enF:
        near = [b for b in s.buildings.values() if b.owner == side and abs(b.x - x) + abs(b.y - y) <= 2]
        if near:
            thr.append(f"적F({x},{y})→" + ",".join(fmt(b) for b in near))
    top = sorted(myW.items(), key=lambda kv: -kv[1])[:3]
    return (f"  점수 {team_score(s, side)}:{team_score(s, op)}  W {W[side]}:{W[op]}  자원 {s.resources[side]}:{s.resources[op]}  "
            f"본진 우{s.bases[side]} 적{s.bases[op]}\n"
            f"  우리 {' '.join(sorted(mine))}\n  적 {' '.join(sorted(theirs))}\n  중립 {' '.join(sorted(neut))}\n"
            f"  변화 {' '.join(ch) or '-'}   위협 {' '.join(thr) or '-'}   우리 W 뭉치 {top}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["new", "step"])
    ap.add_argument("--prefix", default="b")
    ap.add_argument("--seeds", default="150003-150012")
    ap.add_argument("--llm", default=L.LLM_VER, help="지휘관 봇 (v20 상대면 dev27 = v20 + 지휘)")
    ap.add_argument("--opp", default=L.OPP_VER)
    a = ap.parse_args()
    if a.cmd == "new":
        for k, sd in enumerate(parse_range(a.seeds)):
            d = L.gdir(f"{a.prefix}{sd}")
            os.makedirs(d, exist_ok=True)
            json.dump({"seed": sd, "side": "YK"[k % 2], "llm": a.llm, "opp": a.opp}, open(os.path.join(d, "meta.json"), "w"))
    games = sorted(os.path.basename(p) for p in glob.glob(os.path.join(L.ROOT, "out/llm", f"{a.prefix}[0-9]*")))
    done = 0
    for game in games:
        d = L.gdir(game)
        if os.path.exists(os.path.join(d, "result.json")):
            r = json.load(open(os.path.join(d, "result.json")))
            print(f"[{game}] 끝: {r['turn']}턴 {r['winner']} ({r['reason']}) 지휘관 {r['llm_value']}")
            done += 1
            continue
        g, side, t, _ = L.replay(game)
        if t is None:
            r = g.result
            json.dump({"turn": g.state.turn, "winner": r["winner"], "reason": r["reason"], "llm_value": L.value(r, side)},
                      open(os.path.join(d, "result.json"), "w"))
            out, _ = L.export(game)
            print(f"[{game}] 끝: {g.state.turn}턴 {r['winner']} ({r['reason']}) 지휘관 {L.value(r, side)} · 리플레이 {os.path.basename(out)}")
            done += 1
            continue
        prevs = sorted(glob.glob(os.path.join(d, "cmd_*.json")))
        prev_owner = {}
        if prevs:
            # 직전 결정 시점의 소유 = 그 턴 state 파일이 아니라 재현이 필요하므로 간단히 직전 명령 턴까지 다시 돈다
            pass
        last = json.load(open(prevs[-1], encoding="utf-8")) if prevs else None
        print(f"[{game}] {t}턴 당신={side}  직전 명령 {json.dumps(last, ensure_ascii=False) if last else '-'}")
        pv = json.load(open(os.path.join(d, "owners.json"))) if os.path.exists(os.path.join(d, "owners.json")) else {}
        prev_owner = {tuple(map(int, k.split(","))): v for k, v in pv.items()}
        print(brief(g, side, prev_owner))
        json.dump({f"{b.x},{b.y}": b.owner for b in g.state.buildings.values()}, open(os.path.join(d, "owners.json"), "w"))
        open(os.path.join(d, f"state_{t:03d}.txt"), "w", encoding="utf-8").write(L.summary(g, side, prev_owner))
    print(f"== 끝난 경기 {done}/{len(games)}")


if __name__ == "__main__":
    main()
