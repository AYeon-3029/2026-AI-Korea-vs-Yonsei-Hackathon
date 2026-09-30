"""실전 리플레이: 적 F 가 (2칸 안 적 W 없이) 혼자 들어와 우리 건물을 중립화한 장면에서, 봇 버전 X 라면 그 턴 건물 칸에 W 를 올렸을지.

상실 관측 턴 L(= L 턴 처리 후 우리 소유 아님), 판단 턴 L 의 입력 = L−1 관측. 봇 메모리는 1턴부터 실제 관측을 차례로 넣어 쌓는다(rerun.py 방식).
판단한 명령을 우리 쪽만 엔진에 적용(상대 명령 없음)해 이동 후 그 칸 우리 W 를 센다. 1 이상이면 '막음'(적 W 가 없으므로 F 는 제거된다).
사용 (WSL): python3 tools/macro/lonef.py --games 'Real Match Replay/V16_0930_8am,...' --vers 'v16;cv-3;dev22@{"chase_next":true}' [--show]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent  # noqa: E402
from realstate import restore  # noqa: E402
from runner.protocol import parse_commands, serialize_init, serialize_turn  # noqa: E402
from engine.pipeline import step_move, step_spawn, _split  # noqa: E402


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def events(path):
    """[(판단 턴 L, 건물 좌표, 종류)] — 적 F 단독 진입으로 우리 건물이 넘어간 턴."""
    r = json.load(open(path, encoding="utf-8"))
    me = r["side"]
    op = "Y" if me == "K" else "K"
    T = [t for t in r["turns"] if t.get("observation")]
    out = []
    for k in range(1, len(T)):
        prev, cur = T[k - 1]["observation"], T[k]["observation"]
        pown = {b["id"]: b for b in prev["buildings"]}
        for b in cur["buildings"]:
            pb = pown[b["id"]]
            if pb["owner"] != me or b["owner"] == me:
                continue
            p = (b["x"], b["y"])
            ew = sum(n for tm, kk, x, y, n in prev["units"] if tm == op and kk == "W" and man((x, y), p) <= 2)
            ef = sum(n for tm, kk, x, y, n in prev["units"] if tm == op and kk == "F" and man((x, y), p) <= 1)
            if ew == 0 and ef > 0:
                out.append((cur["turn"], p, b["type"]))
    return out


def run(args):
    path, ver = args
    ev = events(path)
    if not ev:
        return path, ver, []
    want = {L: [] for L, _, _ in ev}
    for L, p, ty in ev:
        want[L].append((p, ty))
    name, _, pj = ver.partition("@")
    ag = Agent(name, json.loads(pj) if pj else {})
    res = []
    for t in range(1, max(want) + 1):
        rs = restore(path, max(1, t - 1))
        if rs is None:
            continue
        s, me, _ = rs
        s.turn = t - 1
        if t == 1:
            s.units.clear()
            s.resources = {"Y": 10, "K": 10}
            for b in s.buildings.values():
                b.owner, b.stage = "N", 0
        if ag.init is None:
            ag.start(serialize_init(s, me))
        cmds = ag.decide(serialize_turn(s, me, t))
        if t in want:
            st = s.clone()
            sp, mv, _ = _split(parse_commands(cmds))
            step_spawn(st, {me: sp, ("K" if me == "Y" else "Y"): []})
            step_move(st, {me: mv, ("K" if me == "Y" else "Y"): []})
            for p, ty in want[t]:
                res.append((t, p, ty, st.get_unit(p[0], p[1], me, "W")))
    return path, ver, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", required=True)
    ap.add_argument("--vers", default="v16;cv-3", help="세미콜론 구분, 버전@파라미터JSON")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    files = [f for d in a.games.split(",") for f in sorted(glob.glob(os.path.join(d, "*.json")))]
    vers = a.vers.split(";")
    with Pool(a.workers) as pool:
        rows = pool.map(run, [(f, v) for f in files for v in vers])
    by = {}
    for path, ver, res in rows:
        for t, p, ty, w in res:
            by.setdefault((path, t, p, ty), {})[ver] = w
    n = len(by)
    print(f"적 F 단독 진입으로 잃은 우리 건물 {n}건 ({len(files)}경기)")
    for v in vers:
        blocked = sum(1 for d in by.values() if d.get(v, 0) > 0)
        print(f"  {v:<6} 그 턴 건물 칸에 W 올림 {blocked}/{n}")
    if a.show:
        for (path, t, p, ty), d in sorted(by.items()):
            print(f"  {os.path.basename(os.path.dirname(path))}/{os.path.basename(path)} {t}턴 {ty}{p} " +
                  " ".join(f"{v}:{d.get(v, 0)}" for v in vers))


if __name__ == "__main__":
    main()
