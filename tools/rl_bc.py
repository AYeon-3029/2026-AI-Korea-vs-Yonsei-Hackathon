"""강화학습 스파링 봇의 행동 복제(BC) 사전학습: v10 의 플레이를 정책망(`rlbot/model.py`)이 흉내 내게 한다(GPU).

무작위 초기 정책으로 PPO 를 시작하면 강한 상대에게 보상이 거의 없어 학습이 멈춘다(rl1: 100만 표본 동안 러셔·중간형 0승).
AlphaStar 처럼 먼저 교사(v10)를 지도학습으로 따라 한 뒤 PPO(`rl_ppo.py --resume`)로 교사를 넘어서게 한다.

1) gen: v10 대 여러 상대(리그·스파링) 경기를 돌려 v10 쪽 관측과 명령을 기록한다. 미러전은 양쪽 모두 기록.
   명령 → 목표: 칸·병종별 방향 인원(나머지는 제자리), 생산 F 수(0~2), W 에 쓴 비율(가장 가까운 칸).
2) train: 이동은 인원 가중 교차 엔트로피, 생산은 교차 엔트로피, 가치는 경기 결과(±1) 회귀.

사용 (WSL, 프로젝트 루트):
  python3 tools/rl_bc.py gen --games 1000 --out out/rl/bcdata
  python3 tools/rl_bc.py train --data out/rl/bcdata --out out/rl/bc1 --epochs 6
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "BaseLines/yk-development-tools"
sys.path.insert(0, str(DEV))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "Model/sparring/rlbot"))

from enc import DIRS, F_CHOICES, F_COST, FLIP, W_FRACS, Init, encode, parse_turn  # noqa: E402

TEACHER = "v10"
OPPS = ["v10", "v10", "v9", "v8", "v6", "v6atk", "v3", "rusher", "turtle", "mid", "presser", "raider", "econ", "reactive"]


def targets(ini, cnt, res, wcost, cmds):
    from engine.commands import Move, Spawn
    h, w = cnt.shape[1:]
    mv = np.zeros((2, 5, h, w), np.int16)
    nF = nW = 0
    for c in cmds:
        if isinstance(c, Spawn):
            if c.kind == "F":
                nF += c.count
            elif c.kind == "W":
                nW += c.count
        elif isinstance(c, Move) and c.kind in ("F", "W"):
            k = 0 if c.kind == "F" else 1
            fx, fy = ini.fr(c.x, c.y)
            d = c.direction
            if ini.flip:
                d = FLIP[d]
            mv[k, 1 + DIRS.index(d), fy, fx] += c.count
    moved = mv[:, 1:].sum(1)
    mv[:, 1:] = np.minimum(mv[:, 1:], cnt[:, None])          # 보유보다 많이 보낸 명령은 잘라낸다
    mv[:, 0] = np.maximum(cnt - np.minimum(moved, cnt), 0)
    f_idx = min(nF, F_CHOICES[-1])
    left = res - nF * F_COST
    frac = (nW * wcost / left) if left > 0 else 0.0
    w_idx = int(np.argmin([abs(frac - x) for x in W_FRACS]))
    return mv, f_idx, w_idx


_STUDENT = {}


def student_act(ckpt, ini, lines):
    """DAgger: 학생 정책(CPU, 표본 추출)으로 둘 명령."""
    if ckpt not in _STUDENT:
        import os
        os.environ["RL_CKPT"] = ckpt
        import torch
        torch.set_num_threads(1)
        os.environ["RL_PROP"] = "1"                                  # 학생은 평가와 같은 확률 비례 분할로 둔다
        import importlib.util                                       # 이름이 같은 main.py 가 많아 경로로 불러온다
        spec = importlib.util.spec_from_file_location("rlbot_main", ROOT / "Model/sparring/rlbot/main.py")
        rlmain = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rlmain)
        _STUDENT[ckpt] = (rlmain, rlmain.load())
    rlmain, net = _STUDENT[ckpt]
    return rlmain.act(net, ini, lines)


def play_game(job):
    seed, opp, tside, student, beta = job
    rng = random.Random(seed)
    from engine.config import load_config
    from engine.pipeline import run_turn
    from mapgen import generate, to_state
    from runner import SubprocessBot
    from runner.protocol import parse_commands, serialize_init, serialize_turn
    from arena import resolve
    from pool_eval import opp_cmd
    cfg = load_config()
    state = to_state(generate(seed, cfg))
    oside = "K" if tside == "Y" else "Y"
    cmds_side = {tside: opp_cmd(TEACHER), oside: opp_cmd(opp)}
    record = {tside} | ({oside} if opp == TEACHER else set())
    bots = {s: SubprocessBot(resolve(cmds_side[s]), name=s) for s in "YK"}
    inis = {}
    for s in "YK":
        txt = serialize_init(state, s)
        bots[s].send_init(txt)
        inis[s] = Init(txt.splitlines())
    rows = {s: [] for s in record}
    result = None
    try:
        turn = 0
        while result is None:
            turn += 1
            texts = {s: serialize_turn(state, s, turn) for s in "YK"}
            for s in "YK":
                bots[s].send_turn(texts[s], 30.0)
            raw = {}
            for s in "YK":
                lines, status = bots[s].collect_turn()
                raw[s] = lines or []
                if status != "ok":
                    return None
            parsed = {s: parse_commands(raw[s]) for s in "YK"}
            labels = dict(parsed)
            if student and rng.random() >= beta:
                # 학생이 실제로 두고, 교사(v10)의 명령은 정답 표지로만 쓴다
                parsed[tside] = parse_commands(student_act(student, inis[tside], texts[tside].splitlines()))
            for s in record:
                obs, cnt, valid, res, wcost = encode(inis[s], parse_turn(texts[s].splitlines()))
                mv, fi, wi = targets(inis[s], cnt, res, wcost, labels[s])
                rows[s].append((obs.astype(np.float16), cnt.astype(np.int16), valid, mv, fi, wi))
            state, result = run_turn(state, parsed["Y"], parsed["K"])
    finally:
        for b in bots.values():
            b.close()
    out = []
    for s, rs in rows.items():
        z = 1.0 if result["winner"] == s else 0.0 if result["winner"] == "DRAW" else -1.0
        out += [r + (z,) for r in rs]
    return out, result["winner"] == tside


def gen(args):
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed0)
    student = str(ROOT / args.student) if args.student else ""
    jobs = [(args.seed0 + i, rng.choice(OPPS), rng.choice("YK"), student, args.beta) for i in range(args.games)]
    shard, buf, wins, n = 0, [], 0, 0
    t0 = time.time()

    def flush():
        nonlocal shard, buf
        if not buf:
            return
        cols = list(zip(*buf))
        np.savez(out / f"shard{shard:03d}.npz", obs=np.stack(cols[0]), cnt=np.stack(cols[1]), valid=np.stack(cols[2]),
                 mv=np.stack(cols[3]), fi=np.array(cols[4], np.int8), wi=np.array(cols[5], np.int8),
                 z=np.array(cols[6], np.float32))
        shard += 1
        buf = []

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for res in ex.map(play_game, jobs):
            if res is None:
                continue
            rows, won = res
            buf += rows
            wins += won
            n += 1
            if len(buf) >= 20000:
                flush()
            if n % 50 == 0:
                print(f"games {n} samples_shard {len(buf)} teacher_win {wins / n:.3f} {time.time() - t0:.0f}s", flush=True)
    flush()
    print(f"완료 {n}경기, 조각 {shard}개")


def train(args):
    """교사 모방 학습. --cr 이면 Curious Replay(Kauvar et al., 2023) 우선순위로 표본을 뽑는다.

    우선순위 p_i = c·β^{v_i} + (L_i + ε)^α — v_i 는 표본 i 를 학습에 쓴 횟수, L_i 는 마지막으로 계산한 그 표본의 손실.
    아직 덜 본 표본(개수 항)과 모델이 아직 못 맞히는 표본(호기심 항)을 더 자주 학습한다. 균등 표집(--cr 없음)과 같은 조건으로 비교한다.
    검증은 경기 단위: 데이터 폴더마다 마지막 조각(경기가 조각 사이에 걸치지 않는다)을 떼어 둔다.
    """
    import torch
    import torch.nn.functional as Fn
    from model import Net
    dev = torch.device("cuda")
    keys = ("obs", "cnt", "valid", "mv", "fi", "wi", "z")
    tr_files, va_files = [], []
    for d in args.data.split(","):
        files = sorted((ROOT / d).glob("shard*.npz"))
        tr_files += files[:-1]
        va_files += files[-1:]

    def load(files):
        # 키마다 따로 이어 붙여 최대 메모리를 줄인다(관측이 가장 크다)
        # 미리 할당해 조각마다 채운다: 최대 메모리 = 최종 크기 + 조각 하나
        lens = [len(np.load(f)["z"]) for f in files]
        out_ = {}
        for k in keys:
            first = np.load(files[0])[k]
            arr = np.empty((sum(lens),) + first.shape[1:], first.dtype)
            pos = 0
            for f, n_ in zip(files, lens):
                arr[pos:pos + n_] = np.load(f)[k]
                pos += n_
            out_[k] = torch.from_numpy(arr)
        return out_

    tr, va = load(tr_files), load(va_files)
    N, NV = len(tr["z"]), len(va["z"])
    print(f"학습 {N} / 검증 {NV} (경기 단위 분할)", flush=True)

    torch.manual_seed(args.seed)
    net = Net(ch=args.ch, blocks=args.blocks).to(dev)
    if args.init:
        net.load_state_dict(torch.load(ROOT / args.init, map_location=dev)["net"])
    print(f"망 {args.ch}ch × {args.blocks}블록, 가중치 {sum(p_.numel() for p_ in net.parameters())}", flush=True)
    opt = torch.optim.Adam(net.parameters(), lr=args.lr)
    steps = args.epochs * (N // args.bs)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=steps)
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    def batch(src, ii):
        ii = torch.from_numpy(np.sort(ii))
        return {k: src[k][ii].to(dev, non_blocking=True) for k in src}

    def per_sample(g):
        ml, fl, wl, v = net(g["obs"].float(), g["valid"])
        lp = torch.log_softmax(ml, 2)
        mv = g["mv"].float()
        tot = mv.sum((1, 2, 3, 4)).clamp_min(1)
        l_mv = -(mv * lp).sum((1, 2, 3, 4)) / tot
        l_f = Fn.cross_entropy(fl, g["fi"].long(), reduction="none")
        l_w = Fn.cross_entropy(wl, g["wi"].long(), reduction="none")
        l_v = (v - g["z"]) ** 2
        loss = l_mv + 0.5 * (l_f + l_w) + 0.5 * l_v
        pred = lp.argmax(2, keepdim=True)
        stats = (l_mv.mean(), l_f.mean(), l_w.mean(), l_v.mean(),
                 torch.gather(mv, 2, pred).sum() / mv.sum().clamp_min(1),
                 (fl.argmax(1) == g["fi"].long()).float().mean(), (wl.argmax(1) == g["wi"].long()).float().mean())
        return loss, stats

    rng = np.random.default_rng(args.seed)
    L = np.full(N, np.nan, np.float64)          # 표본별 마지막 손실(아직 안 봤으면 nan)
    visits = np.zeros(N, np.int32)
    for ep in range(args.epochs):
        net.train()
        t0 = time.time()
        if args.cr:
            order = None
        else:
            order = rng.permutation(N)
        for s in range(N // args.bs):
            if args.cr:
                known = np.where(np.isnan(L), 0.0, L)
                pr = args.cr_c * args.cr_beta ** visits + (known + args.cr_eps) ** args.cr_alpha
                ii = rng.choice(N, size=args.bs, replace=False, p=pr / pr.sum())
            else:
                ii = order[s * args.bs:(s + 1) * args.bs]
            g = batch(tr, ii)
            loss, _ = per_sample(g)
            opt.zero_grad()
            loss.mean().backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            sched.step()
            ii_sorted = np.sort(ii)
            L[ii_sorted] = loss.detach().cpu().numpy()
            visits[ii_sorted] += 1
        net.eval()
        acc = np.zeros(7)
        nb = 0
        with torch.no_grad():
            for s in range(0, NV, 1024):
                _, st = per_sample(batch(va, np.arange(s, min(NV, s + 1024))))
                acc += np.array([float(x) for x in st])
                nb += 1
        acc /= nb
        rec = {"epoch": ep, "sec": round(time.time() - t0), "val_move_ce": round(acc[0], 4), "val_f_ce": round(acc[1], 4),
               "val_w_ce": round(acc[2], 4), "val_v_mse": round(acc[3], 4), "unit_acc": round(acc[4], 4),
               "f_acc": round(acc[5], 4), "w_acc": round(acc[6], 4),
               "visit_min_max": [int(visits.min()), int(visits.max())]}
        print(json.dumps(rec), flush=True)
        torch.save({"net": net.state_dict(), "opt": opt.state_dict(), "tier": 0, "iter": 0, "arch": net.arch}, out / "latest.pt")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("--games", type=int, default=1000)
    g.add_argument("--out", default="out/rl/bcdata")
    g.add_argument("--seed0", type=int, default=2_000_000)
    g.add_argument("--workers", type=int, default=24)
    g.add_argument("--student", default="", help="DAgger: 이 체크포인트의 학생이 v10 쪽을 실제로 둔다(표지는 v10)")
    g.add_argument("--beta", type=float, default=0.0, help="DAgger: 턴마다 교사 명령을 그대로 실행할 확률")
    t = sub.add_parser("train")
    t.add_argument("--data", default="out/rl/bcdata")
    t.add_argument("--out", default="out/rl/bc1")
    t.add_argument("--epochs", type=int, default=6)
    t.add_argument("--bs", type=int, default=256)
    t.add_argument("--lr", type=float, default=1e-3)
    t.add_argument("--init", default="", help="이 체크포인트에서 이어 학습")
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--ch", type=int, default=64)
    t.add_argument("--blocks", type=int, default=6)
    t.add_argument("--cr", action="store_true", help="Curious Replay 우선순위 표집")
    t.add_argument("--cr-c", type=float, default=1.0)
    t.add_argument("--cr-beta", type=float, default=0.7)
    t.add_argument("--cr-alpha", type=float, default=0.7)
    t.add_argument("--cr-eps", type=float, default=0.01)
    args = p.parse_args()
    gen(args) if args.cmd == "gen" else train(args)


if __name__ == "__main__":
    main()
