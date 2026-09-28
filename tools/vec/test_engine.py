"""벡터화 엔진 대조 검증: 같은 맵·같은 무작위 행동을 공식 엔진과 벡터 엔진에 넣고 매 턴 모든 상태를 비교한다.

비교: 관측(enc.encode 와 텐서 전체), 유닛 배치, 건물 소유·단계, 자원, 점수 공개, 점령-턴 누적, 승패.
행동은 적 방향(frame 오른쪽)으로 치우친 무작위 이동 + 무작위 생산이라 전투·점령·중립화·보급소·즉시 승리가 두루 나온다.

사용 (WSL, 프로젝트 루트): python3 tools/vec/test_engine.py --games 40
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "BaseLines/yk-development-tools"))
sys.path.insert(0, str(ROOT / "Model/sparring/rlbot"))
sys.path.insert(0, str(ROOT / "tools/vec"))

from engine.config import load_config  # noqa: E402
from engine.pipeline import run_turn  # noqa: E402
from mapgen import generate, to_state  # noqa: E402
from runner.protocol import parse_commands, serialize_init, serialize_turn  # noqa: E402

import enc  # noqa: E402
from vecgame import VecGame, map_arrays  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--games", type=int, default=40)
    p.add_argument("--seed0", type=int, default=5_900_000)
    p.add_argument("--device", default="cuda")
    p.add_argument("--bias", type=float, default=3.0, help="적 방향(frame 오른쪽) 이동 가중")
    args = p.parse_args()
    cfg = load_config()
    n = args.games
    states = [to_state(generate(args.seed0 + i, cfg)) for i in range(n)]
    vg = VecGame(map_arrays(states), n, args.device)
    vg.reset(torch.arange(n, device=args.device), map_ids=torch.arange(n, device=args.device))
    inis = [[enc.Init(serialize_init(s, t).splitlines()) for t in "YK"] for s in states]
    rng = np.random.default_rng(0)
    done = [False] * n
    mism = 0
    checks = 0
    stats = {"combat_turns": 0, "captures": 0, "results": {}}
    for turn in range(1, 161):
        acts = []
        per_env_cmds = [[None, None] for _ in range(n)]
        for t in (0, 1):
            ov, cv, vv = vg.observe(t)
            ov, cv, vv = ov.cpu().numpy(), cv.cpu().numpy(), vv.cpu().numpy()
            moves = np.zeros((n, 2, 5, 15, 15), np.int64)
            fi = rng.integers(0, 3, n)
            wi = rng.integers(0, 4, n)
            for i in range(n):
                if done[i]:
                    continue
                s = states[i]
                team = "YK"[t]
                view = enc.parse_turn(serialize_turn(s, team, s.turn + 1).splitlines())
                o, c, v, res, wcost = enc.encode(inis[i][t], view)
                checks += 1
                if not (np.allclose(o, ov[i]) and (c == cv[i]).all() and (v == vv[i]).all()):
                    mism += 1
                    bad = [k for k in range(enc.C) if not np.allclose(o[k], ov[i][k])]
                    print(f"[관측 불일치] 판 {i} 턴 {turn} 팀 {team} 채널 {bad} cnt {(c == cv[i]).all()} valid {(v == vv[i]).all()}")
                for k, fy, fx in zip(*np.nonzero(c)):
                    w = np.array([1.0, 1, 1, 1, args.bias]) * np.concatenate([[1], v[:, fy, fx]])
                    moves[i, k, :, fy, fx] = rng.multinomial(int(c[k, fy, fx]), w / w.sum())
                per_env_cmds[i][t] = parse_commands(enc.commands(inis[i][t], moves[i], int(fi[i]), int(wi[i]), res, wcost))
            acts.append((torch.as_tensor(moves, device=args.device), torch.as_tensor(fi, device=args.device),
                         torch.as_tensor(wi, device=args.device)))
        result = vg.step(acts).cpu().numpy()
        for i in range(n):
            if done[i]:
                continue
            ev = []
            states[i], r = run_turn(states[i], per_env_cmds[i][0], per_env_cmds[i][1], ev)
            stats["combat_turns"] += any(e["type"] == "combat" for e in ev)
            stats["captures"] += sum(e["type"] == "capture" for e in ev)
            s = states[i]
            u = np.zeros((2, 2, 15, 15), np.int64)
            for (x, y, team, kind), c in s.units.items():
                if kind in "FW":
                    u["YK".index(team), "FW".index(kind), y, x] = c
            ok = (u == vg.units[i].cpu().numpy()).all()
            bl = s.sorted_buildings()
            ok &= [(-1 if b.owner == "N" else "YK".index(b.owner)) for b in bl] == vg.owner[i].tolist()
            ok &= [b.stage for b in bl] == vg.stage[i].tolist()
            ok &= [s.resources["Y"], s.resources["K"]] == vg.res[i].tolist()
            ok &= [[b.id in s.revealed[tm] for b in bl] for tm in "YK"] == vg.revealed[i].tolist()
            ok &= [s.occupation_score_turns["Y"], s.occupation_score_turns["K"]] == vg.occ[i].tolist()
            want = -1 if r is None else {"Y": 0, "K": 1, "DRAW": 2}[r["winner"]]
            ok &= want == int(result[i])
            checks += 1
            if not ok:
                mism += 1
                print(f"[상태 불일치] 판 {i} 턴 {turn} 결과 {want}/{result[i]} 자원 {s.resources}/{vg.res[i].tolist()}")
            if r is not None:
                done[i] = True
                key = f"{r['winner']}:{r['reason']}"
                stats["results"][key] = stats["results"].get(key, 0) + 1
        if all(done):
            break
    print(f"비교 {checks}회, 불일치 {mism}회. 전투 발생 턴 {stats['combat_turns']}, 점령 {stats['captures']}, 결과 {stats['results']}")
    sys.exit(1 if mism else 0)


if __name__ == "__main__":
    main()
