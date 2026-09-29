"""실제 리플레이의 관측을 턴마다 복원해 우리 봇 버전에 차례로 넣고, 실제 명령과 얼마나 같은지·특정 턴의 판단을 본다.

- 매 턴 realstate.restore(관측 → 엔진 상태) → serialize_turn → Agent.decide. 메모리는 1턴부터 쌓이므로 실제 경기의 봇과 거의 같다
  (차이: 복원은 모든 건물 점수를 공개로 둔다).
- --dump T: 그 턴에 봇 모듈의 DBG(있으면) 내용을 찍는다(Model/history/<ver>/main.py 가 DBG 리스트에 작업을 기록할 때).

사용 (WSL): python3 tools/macro/rerun.py <replay.json> --ver v14 [--upto 40] [--dump 35]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from sim import Agent  # noqa: E402
from realstate import restore  # noqa: E402
from runner.protocol import serialize_init, serialize_turn  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replay")
    ap.add_argument("--ver", default="v14")
    ap.add_argument("--params", default="{}")
    ap.add_argument("--upto", type=int, default=160)
    ap.add_argument("--dump", default="")
    ap.add_argument("--as-v14", action="store_true")
    a = ap.parse_args()
    r = json.load(open(a.replay, encoding="utf-8"))
    rec = {t["observation"]["turn"]: (t.get("command") or {}).get("lines", []) for t in r["turns"] if t.get("observation")}
    dumps = set()
    for x in a.dump.split(","):
        if "-" in x:
            lo, hi = map(int, x.split("-"))
            dumps.update(range(lo, hi + 1))
        elif x:
            dumps.add(int(x))
    params = json.loads(a.params)
    if a.as_v14:
        # dev11 이후 코드에 v14 파라미터를 얹고 v15 에서 켠 새 스위치를 끈다(= v14 동작, gate_v15 동치 확인)
        import copy
        from sim import module
        params = {**copy.deepcopy(module("v14").P), "f_own_R": 0, "f_no_station_wait": False, "early_turn": 0, **params}
    ag = Agent(a.ver, params)
    m0 = ag.mod
    if hasattr(m0, "DBG_TURNS"):
        m0.DBG_TURNS.clear()
        m0.DBG_TURNS.update(dumps)
    same = tot = 0
    for t in sorted(rec):
        if t > a.upto:
            break
        # 리플레이의 turns[t] = (t 턴에 낸 명령, t 턴 처리 후 관측) → t 턴 입력은 t−1 턴 관측이다
        rs = restore(a.replay, max(1, t - 1))
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
        m = ag.mod
        if hasattr(m, "DBG"):
            m.DBG.clear()
        out = ag.decide(serialize_turn(s, me, t))
        a_set, b_set = sorted(out), sorted(rec[t])
        tot += 1
        same += a_set == b_set
        if t in dumps:
            print(f"== turn {t}  같은 명령: {a_set == b_set}")
            if a_set != b_set:
                print("  재현:", "; ".join(out))
                print("  실제:", "; ".join(rec[t]))
            for row in getattr(m, "DBG", []):
                print("  ", row)
    print(f"명령 일치 {same}/{tot}")


if __name__ == "__main__":
    main()
