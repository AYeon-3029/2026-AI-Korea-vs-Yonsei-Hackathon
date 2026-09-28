"""GPU 자기대전 PPO — 벡터화 엔진(`vecgame.py`)으로 수천 판을 동시에 돌린다. 규칙과 보상만으로 처음부터 학습한다.

- 판의 --self-frac 은 학습 정책이 양쪽을 모두 둔다(한 판에서 표본 2개). 나머지는 과거 스냅샷(풀에서 반복마다 하나)이 상대.
- 정책망·관측·행동은 `Model/sparring/rlbot` 과 같다 → 체크포인트를 그대로 공식 엔진에서 대전시킬 수 있다.
- --eval-every 반복마다 체크포인트를 저장하고 백그라운드로 공식 엔진 평가(`eval_ckpt.py`, 기준 봇 상대)를 띄운다.
- 보상: 승 +1 / 패 −1 / 무 0, 점수 차 변화 × --shape.

사용 (WSL, 프로젝트 루트): python3 tools/vec/selfplay.py --name vs1 --envs 1024 --hours 10
"""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "BaseLines/yk-development-tools"))
sys.path.insert(0, str(ROOT / "Model/sparring/rlbot"))
sys.path.insert(0, str(ROOT / "tools/vec"))

from model import Net  # noqa: E402
from vecgame import VecGame, gen_maps  # noqa: E402


def sample_moves(logits, cnt):
    """유닛별 방향 표본(이항 분해). 반환 (인원 (B,2,5,H,W), 칸별 유닛당 평균 log π (B,2,H,W))."""
    p = torch.softmax(logits, 2)
    rem = cnt.float()
    out, acc = [], torch.zeros_like(rem)
    for d in range(4):
        rel = (p[:, :, d] / (1 - acc).clamp_min(1e-6)).clamp(0, 1)
        k = torch.distributions.Binomial(total_count=rem, probs=rel).sample()
        out.append(k)
        rem = rem - k
        acc = acc + p[:, :, d]
    out.append(rem)
    mv = torch.stack(out, 2)
    return mv, move_logp(logits, mv, cnt)


def move_logp(logits, mv, cnt):
    return (mv * torch.log_softmax(logits, 2)).sum(2) / cnt.float().clamp_min(1)


def fwd(net, obs, valid):
    """bf16 자동 혼합 정밀도로 추론·학습(표본·확률 계산은 float32)."""
    with torch.autocast("cuda", dtype=torch.bfloat16):
        ml, fl, wl, v = net(obs, valid)
    return ml.float(), fl.float(), wl.float(), v.float()


def prop_act(net, obs, cnt, valid):
    """결정적 확률 비례 분할 + 최빈 생산(대전용 RL_PROP=1 과 같음) — 고정 상대(모방 신경망)를 v10 에 가깝게 두게 한다."""
    ml, fl, wl, _ = fwd(net, obs, valid)
    q = torch.softmax(ml, 2)                                    # (B,2,5,H,W)
    n = cnt.float().unsqueeze(2)
    base = torch.floor(n * q)
    frac = n * q - base
    rem = (n.squeeze(2) - base.sum(2)).unsqueeze(2)            # 남은 인원
    rank = frac.argsort(2, descending=True).argsort(2)
    mv = base + (rank < rem).float()
    return mv, fl.argmax(1), wl.argmax(1)


def act(net, obs, cnt, valid):
    ml, fl, wl, v = fwd(net, obs, valid)
    mv, lpm = sample_moves(ml, cnt)
    fd, wd = torch.distributions.Categorical(logits=fl), torch.distributions.Categorical(logits=wl)
    fi, wi = fd.sample(), wd.sample()
    return mv, fi, wi, lpm, fd.log_prob(fi), wd.log_prob(wi), v


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True)
    p.add_argument("--envs", type=int, default=1024)
    p.add_argument("--steps", type=int, default=64)
    p.add_argument("--hours", type=float, default=10)
    p.add_argument("--ch", type=int, default=64)
    p.add_argument("--blocks", type=int, default=8)
    p.add_argument("--resume", default="")
    p.add_argument("--maps", type=int, default=20000)
    p.add_argument("--self-frac", type=float, default=0.5)
    p.add_argument("--snap-every", type=int, default=20)
    p.add_argument("--pool-max", type=int, default=30)
    p.add_argument("--eval-every", type=int, default=100)
    p.add_argument("--eval-opps", default="mid,v3,v6,v10")
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--gamma", type=float, default=0.995)
    p.add_argument("--lam", type=float, default=0.95)
    p.add_argument("--clip", type=float, default=0.2)
    p.add_argument("--ent", type=float, default=0.01)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--mb", type=int, default=4096)
    p.add_argument("--target-kl", type=float, default=0.03)
    p.add_argument("--move-norm", type=float, default=16.0)
    p.add_argument("--shape", type=float, default=0.02)
    p.add_argument("--fixed", default="", help="고정 상대 체크포인트(쉼표) — 예: v10 모방 신경망. 확률 비례 분할로 둔다")
    p.add_argument("--fixed-frac", type=float, default=0.5, help="반복마다 고정 상대를 고를 확률")
    args = p.parse_args()
    dev = torch.device("cuda")
    out = ROOT / "out/rl" / args.name
    out.mkdir(parents=True, exist_ok=True)

    # 맵 풀(처음 쓰는 시드 5·10^6 이상, 캐시)
    cache = ROOT / f"out/rl/maps_{args.maps}.npz"
    if cache.exists():
        maps = dict(np.load(cache))
    else:
        t0 = time.time()
        maps = gen_maps(list(range(5_000_000, 5_000_000 + args.maps)), workers=24)
        np.savez(cache, **maps)
        print(f"맵 {args.maps}개 생성 {time.time() - t0:.0f}s", flush=True)

    net = Net(ch=args.ch, blocks=args.blocks).to(dev)
    opt_state = None
    if args.resume:
        ck = torch.load(ROOT / args.resume, map_location=dev)
        net = Net(**ck.get("arch", {})).to(dev)
        net.load_state_dict(ck["net"])
        opt_state = ck.get("opt")
    opt = torch.optim.Adam(net.parameters(), lr=args.lr)
    if opt_state:
        opt.load_state_dict(opt_state)
    opp = copy.deepcopy(net).eval()
    pool = [copy.deepcopy(net.state_dict())]
    fixed = []
    for f in [x for x in args.fixed.split(",") if x]:
        ckf = torch.load(ROOT / f, map_location=dev)
        fn = Net(**ckf.get("arch", {})).to(dev)
        fn.load_state_dict(ckf["net"])
        fixed.append((Path(f).parent.name, fn.eval()))
    wr = {}                                                        # 상대별 최근 승점률(PFSP·기록)

    n = args.envs
    vg = VecGame(maps, n, dev, rng=torch.Generator().manual_seed(1))
    n_self = int(n * args.self_frac)
    ar = torch.arange(n, device=dev)
    # 학습 정책이 두는 (판, 팀) 흐름: 자기대전 판은 양쪽, 스냅샷 판은 판 번호 홀짝으로 한쪽
    L = [ar[(ar < n_self) | ((ar >= n_self) & (ar % 2 == t))] for t in (0, 1)]
    O = [ar[(ar >= n_self) & (ar % 2 != t)] for t in (0, 1)]
    S = len(L[0]) + len(L[1])
    phi = torch.zeros(S, device=dev)
    stream_env = torch.cat(L)
    stream_team = torch.cat([torch.zeros(len(L[0]), dtype=torch.long, device=dev),
                             torch.ones(len(L[1]), dtype=torch.long, device=dev)])
    t_start = time.time()
    it = 0
    games = 0
    hist = {"snap_win": [], "len": [], "instant": 0, "ended": 0}
    evals = []
    while time.time() - t_start < args.hours * 3600:
        # 상대 선택: 고정(모방) 상대 또는 스냅샷(PFSP: (1 − 승점률)² + 0.05)
        if fixed and np.random.rand() < args.fixed_frac:
            k = np.random.randint(len(fixed))
            opp_name, opp_net, opp_prop = fixed[k][0], fixed[k][1], True
        else:
            w_ = np.array([(1 - wr.get(f"snap{j}", 0.5)) ** 2 + 0.05 for j in range(len(pool))])
            j = np.random.choice(len(pool), p=w_ / w_.sum())
            opp.load_state_dict(pool[j])
            opp_name, opp_net, opp_prop = f"snap{j}", opp, False
        it_res = []
        T = args.steps
        B = {k: [] for k in ("obs", "cnt", "val", "mv", "fi", "wi", "lpm", "lpf", "lpw", "v", "r", "d")}
        t0 = time.time()
        net.eval()
        with torch.no_grad():
            for _ in range(T):
                ob = [vg.observe(t) for t in (0, 1)]
                lo = torch.cat([ob[0][0][L[0]], ob[1][0][L[1]]])
                lc = torch.cat([ob[0][1][L[0]], ob[1][1][L[1]]])
                lv = torch.cat([ob[0][2][L[0]], ob[1][2][L[1]]])
                mv, fi, wi, lpm, lpf, lpw, v = act(net, lo, lc, lv)
                acts = []
                for t in (0, 1):
                    mt = torch.zeros(n, 2, 5, 15, 15, device=dev)
                    ft = torch.zeros(n, dtype=torch.long, device=dev)
                    wt = torch.zeros(n, dtype=torch.long, device=dev)
                    sl = slice(0, len(L[0])) if t == 0 else slice(len(L[0]), S)
                    mt[L[t]], ft[L[t]], wt[L[t]] = mv[sl], fi[sl], wi[sl]
                    if len(O[t]):
                        if opp_prop:
                            om, of, ow = prop_act(opp_net, ob[t][0][O[t]], ob[t][1][O[t]], ob[t][2][O[t]])
                        else:
                            om, of, ow, *_ = act(opp_net, ob[t][0][O[t]], ob[t][1][O[t]], ob[t][2][O[t]])
                        mt[O[t]], ft[O[t]], wt[O[t]] = om, of, ow
                    acts.append((mt, ft, wt))
                res = vg.step(acts)
                sc = vg.score[stream_env]
                me = sc.gather(1, stream_team.unsqueeze(1)).squeeze(1)
                op = sc.gather(1, (1 - stream_team).unsqueeze(1)).squeeze(1)
                nphi = args.shape * (me - op).float()
                r = nphi - phi
                rs = res[stream_env]
                done = rs >= 0
                r = r + torch.where(done, torch.where(rs == stream_team, 1.0, torch.where(rs == 2, 0.0, -1.0)), 0.0)
                phi = torch.where(done, torch.zeros_like(nphi), nphi)
                B["obs"].append(lo); B["cnt"].append(lc.to(torch.int16)); B["val"].append(lv)
                B["mv"].append(mv.to(torch.int16)); B["fi"].append(fi); B["wi"].append(wi)
                B["lpm"].append(lpm); B["lpf"].append(lpf); B["lpw"].append(lpw); B["v"].append(v)
                B["r"].append(r); B["d"].append(done.float())
                ended = (res >= 0).nonzero().squeeze(1)
                if len(ended):
                    games += len(ended)
                    hist["ended"] += len(ended)
                    hist["instant"] += int((vg.turn[ended] < 160).sum())
                    hist["len"] += vg.turn[ended].tolist()
                    for e in ended.tolist():
                        if e >= n_self:
                            side = e % 2
                            rr = int(res[e])
                            hist["snap_win"].append(1.0 if rr == side else 0.5 if rr == 2 else 0.0)
                            it_res.append(hist["snap_win"][-1])
                    vg.reset(ended)
            ob = [vg.observe(t) for t in (0, 1)]
            _, _, _, v_last = fwd(net, torch.cat([ob[0][0][L[0]], ob[1][0][L[1]]]),
                                  torch.cat([ob[0][2][L[0]], ob[1][2][L[1]]]))
        t_roll = time.time() - t0

        adv = torch.zeros(T, S, device=dev)
        last = torch.zeros(S, device=dev)
        for t in reversed(range(T)):
            nv = v_last if t == T - 1 else B["v"][t + 1]
            nt = 1 - B["d"][t]
            delta = B["r"][t] + args.gamma * nv * nt - B["v"][t]
            last = delta + args.gamma * args.lam * nt * last
            adv[t] = last
        ret = adv + torch.stack(B["v"])
        F = {k: torch.stack(v_).flatten(0, 1) for k, v_ in B.items() if k not in ("r", "d")}
        F["adv"], F["ret"] = adv.flatten(), ret.flatten()
        del B

        net.train()
        N = T * S
        st = {"pl": 0.0, "vl": 0.0, "ent": 0.0, "kl": 0.0}
        nb = 0
        stop = False
        for _ in range(args.epochs):
            perm = torch.randperm(N, device=dev)
            for s0 in range(0, N, args.mb):
                idx = perm[s0:s0 + args.mb]
                cnt = F["cnt"][idx].long()
                ml, fl, wl, v = fwd(net, F["obs"][idx], F["val"][idx])
                a = F["adv"][idx]
                a = (a - a.mean()) / (a.std() + 1e-8)
                actv = (cnt > 0).float()
                lpm = move_logp(ml, F["mv"][idx].float(), cnt)
                rm = torch.exp(lpm - F["lpm"][idx])
                am = a.view(-1, 1, 1, 1)
                pl_m = -(torch.min(rm * am, rm.clamp(1 - args.clip, 1 + args.clip) * am) * actv).sum((1, 2, 3)) / args.move_norm
                fd, wd = torch.distributions.Categorical(logits=fl), torch.distributions.Categorical(logits=wl)
                pl_s = 0
                for dist, ai, old in ((fd, F["fi"][idx], F["lpf"][idx]), (wd, F["wi"][idx], F["lpw"][idx])):
                    r_ = torch.exp(dist.log_prob(ai) - old)
                    pl_s = pl_s - torch.min(r_ * a, r_.clamp(1 - args.clip, 1 + args.clip) * a)
                pol = (pl_m + pl_s).mean()
                pm = torch.softmax(ml, 2)
                ent_m = (-(pm * torch.log_softmax(ml, 2)).sum(2) * actv).sum((1, 2, 3)) / actv.sum((1, 2, 3)).clamp_min(1)
                ent = (ent_m + fd.entropy() + wd.entropy()).mean()
                vloss = ((v - F["ret"][idx]) ** 2).mean()
                loss = pol + 0.5 * vloss - args.ent * ent
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(net.parameters(), 0.5)
                opt.step()
                with torch.no_grad():
                    kl = ((F["lpm"][idx] - lpm) * actv).sum() / actv.sum().clamp_min(1)
                st["kl"] += kl.item(); st["pl"] += pol.item(); st["vl"] += vloss.item(); st["ent"] += ent.item()
                nb += 1
            if args.target_kl and st["kl"] / nb > args.target_kl:
                break
        st = {k: round(v_ / nb, 4) for k, v_ in st.items()}
        del F

        if it_res:
            wr[opp_name] = 0.7 * wr.get(opp_name, 0.5) + 0.3 * (sum(it_res) / len(it_res))
        it += 1
        if it % args.snap_every == 0:
            pool.append(copy.deepcopy(net.state_dict()))
            del pool[:-args.pool_max]
        sw = hist["snap_win"][-400:]
        ln = hist["len"][-400:]
        rec = {"it": it, "games": games, "sps": round(T * n / (time.time() - t0)), "roll_s": round(t_roll, 1),
               "vs_snap": round(sum(sw) / len(sw), 3) if sw else None, "len": round(sum(ln) / len(ln), 1) if ln else None,
               "instant": round(hist["instant"] / max(1, hist["ended"]), 3), "pool": len(pool), **st,
               "opp": opp_name, "vs_fixed": {k_: round(v_, 2) for k_, v_ in wr.items() if not k_.startswith("snap")}}
        hist["instant"] = hist["ended"] = 0
        print(json.dumps(rec), flush=True)
        if it % args.eval_every == 0:
            ck = out / f"it{it:05d}.pt"
            torch.save({"net": net.state_dict(), "arch": net.arch, "iter": it}, ck)
            torch.save({"net": net.state_dict(), "arch": net.arch, "iter": it, "opt": opt.state_dict()}, out / "latest.pt")
            # 이전 평가가 끝났으면 새 평가를 띄운다(CPU 과부하 방지: 한 번에 하나)
            evals = [e for e in evals if e.poll() is None]
            if not evals:
                evals.append(subprocess.Popen(
                    [sys.executable, str(ROOT / "tools/vec/eval_ckpt.py"), "--ckpt", str(ck.relative_to(ROOT)),
                     "--opps", args.eval_opps, "--out", str((out / "eval.jsonl").relative_to(ROOT)), "--tag", f"it{it}"],
                    cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    torch.save({"net": net.state_dict(), "arch": net.arch, "iter": it, "opt": opt.state_dict()}, out / "latest.pt")


if __name__ == "__main__":
    main()
