"""체크포인트를 공식 엔진에서 기준 봇들과 대전시켜 승점률을 파일에 한 줄(JSON)로 덧붙인다(자기대전 학습 중 백그라운드 평가).

사용: python3 tools/vec/eval_ckpt.py --ckpt out/rl/sp/it00100.pt --opps mid,v3,v6,v10 --seeds 3400-3419 --out out/rl/sp/eval.jsonl
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ckpt", required=True)
    p.add_argument("--opps", default="mid,v3,v6,v10")
    p.add_argument("--seeds", default="3400-3419")
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--out", required=True)
    p.add_argument("--tag", default="")
    args = p.parse_args()
    os.environ.setdefault("ARENA_TIMEOUT_MS", "20000")
    from arena import parse_seeds, play
    from pool_eval import opp_cmd
    me = f"RL_PROP=1 RL_CKPT={ROOT / args.ckpt} python3 {ROOT}/Model/sparring/rlbot/main.py"
    jobs, owner = [], []
    for o in args.opps.split(","):
        oc = opp_cmd(o)
        for s in parse_seeds(args.seeds):
            jobs.append((s, me, oc, "Y", ""))
            jobs.append((s, oc, me, "K", ""))
            owner += [o, o]
    score = {}
    with ProcessPoolExecutor(args.workers) as ex:
        for o, (_, side, r, _) in zip(owner, ex.map(play, jobs)):
            v = 1.0 if r["winner"] == side else 0.5 if r["winner"] == "DRAW" else 0.0
            score.setdefault(o, []).append(v)
    rec = {"tag": args.tag, "ckpt": args.ckpt, **{o: round(sum(v) / len(v), 3) for o, v in score.items()}}
    with open(ROOT / args.out, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec))


if __name__ == "__main__":
    main()
