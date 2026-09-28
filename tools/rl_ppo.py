"""강화학습(PPO, GPU) 스파링 봇 학습 — `Model/sparring/rlbot`.

v10 계열과 코드를 전혀 공유하지 않는 정책(잔차 CNN)을 처음부터 학습해 v10 이 못 본 전략을 찾게 한다.
제출물에는 학습 가중치를 넣을 수 없으므로(대회 규정) 로컬 스파링 전용이다.

- 환경: 엔진(`run_turn`)을 직접 돌리고 상대는 실제 봇 프로세스(SubprocessBot). 관측은 봇 입력 텍스트를 그대로
  인코딩(`rlbot/enc.py`)해 대전 때와 정확히 같다. 매 판 처음 쓰는 맵(시드 10^6 이상), 진영 무작위.
- 행동: 칸·병종마다 5방향 확률, 인원은 유닛별로 나눠 뽑는다(이항 분해) → 분할 이동 가능. 생산은 F 수·W 비율.
- 보상: 승 +1 / 패 −1, 점수 차 변화 × 0.02 (보조).
- PPO 비율은 칸·병종 단위(유닛당 평균 로그확률)로 계산해 큰 부대에서 비율이 폭주하지 않게 한다.
- 커리큘럼: --tiers 'lv1,lv2|rusher,turtle,mid|v3|v6|v10' — 현재 단계 최근 승점률이 --promote 이상이면 다음 단계.
  상대는 70% 현재 단계, 30% 이전 단계에서 뽑는다(망각 방지).

사용 (WSL, 프로젝트 루트): python3 tools/rl_ppo.py --name rl1 --workers 16 --envs 4
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import random
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "BaseLines/yk-development-tools"
sys.path.insert(0, str(DEV))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "Model/sparring/rlbot"))

from enc import Init, commands, encode, parse_turn  # noqa: E402

SHAPE = 0.02


# ---------------------------------------------------------------------------- 환경(작업 프로세스)

_SELF_NETS = {}


class SelfBot:
    """자기 자신(과거 스냅샷)을 상대로: 이름 self:<체크포인트 경로>. 작업 프로세스 CPU 에서 추론(스냅샷별 캐시)."""

    def __init__(self, path):
        import importlib.util
        import torch
        torch.set_num_threads(1)
        if "mod" not in _SELF_NETS:
            spec = importlib.util.spec_from_file_location("rlbot_main", ROOT / "Model/sparring/rlbot/main.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _SELF_NETS["mod"] = mod
        self.mod = _SELF_NETS["mod"]
        if path not in _SELF_NETS:
            from model import load_net
            net, _ = load_net(path)
            net.eval()
            _SELF_NETS[path] = net
            if len(_SELF_NETS) > 12:                        # 오래된 스냅샷 캐시 정리
                old = [k for k in _SELF_NETS if k not in ("mod", path)][0]
                del _SELF_NETS[old]
        self.net = _SELF_NETS[path]
        self.out = []

    def send_init(self, text):
        self.ini = Init(text.splitlines())

    def send_turn(self, text, timeout_s):
        self.out = self.mod.act(self.net, self.ini, text.splitlines())

    def collect_turn(self):
        return self.out, "ok"

    def close(self):
        pass


class SimBot:
    """프로세스 안에서 도는 v10 상대(`Model/sparring/mcts/sim.py`). 이름 sim:<매크로 번호> 또는 sim:mix.

    별도 프로세스·파이프가 없어 빠르고, 매크로(공세·수세·경제·물량·신중)로 v10 계열 상대를 다양하게 만든다.
    mix 는 판마다 무작위 매크로로 시작해 매 턴 1/15 확률로 바꾼다.
    """

    def __init__(self, spec, rng):
        sys.path.insert(0, str(ROOT / "Model/sparring/mcts"))
        import sim
        self.sim, self.spec, self.rng = sim, spec, rng
        self.out = []

    def send_init(self, text):
        self.pol = self.sim.Policy(text.splitlines())
        self.m = self.rng.randrange(len(self.sim.MACROS)) if self.spec == "mix" else int(self.spec)

    def send_turn(self, text, timeout_s):
        if self.spec == "mix" and self.rng.random() < 1 / 15:
            self.m = self.rng.randrange(len(self.sim.MACROS))
        self.out = self.pol.decide(text, self.m)

    def collect_turn(self):
        return self.out, "ok"

    def close(self):
        pass


class Env:
    def __init__(self, wid, k, opp_list):
        from engine.config import load_config
        self.cfg = load_config()
        self.seed = 1_000_000 + wid * 100_000 + k * 10_000
        self.rng = random.Random(self.seed)
        self.set_opps(opp_list)
        self.bot = None

    def set_opps(self, data):
        """목록 또는 (이름 목록, 가중치 목록)."""
        if isinstance(data, tuple):
            self.opp_list, self.opp_w = data
        else:
            self.opp_list, self.opp_w = data, None

    def reset(self):
        from engine.pipeline import team_score
        from mapgen import generate, to_state
        from runner import SubprocessBot
        from runner.protocol import serialize_init
        from arena import resolve
        from pool_eval import opp_cmd
        if self.bot:
            self.bot.close()
        self.seed += 1
        self.opp = self.rng.choices(self.opp_list, weights=self.opp_w)[0] if self.opp_w else self.rng.choice(self.opp_list)
        self.side = self.rng.choice("YK")
        self.oside = "K" if self.side == "Y" else "Y"
        self.state = to_state(generate(self.seed, self.cfg))
        if self.opp.startswith("self:"):
            self.bot = SelfBot(self.opp[5:])
        elif self.opp.startswith("sim:"):
            self.bot = SimBot(self.opp[4:], self.rng)
        else:
            self.bot = SubprocessBot(resolve(opp_cmd(self.opp)), name=self.opp)
        self.bot.send_init(serialize_init(self.state, self.oside))
        self.ini = Init(serialize_init(self.state, self.side).splitlines())
        self.turn = 0
        self.phi = 0.0
        self._ts = team_score
        return self._observe()

    def _observe(self):
        from runner.protocol import serialize_turn
        self.turn += 1
        self.bot.send_turn(serialize_turn(self.state, self.oside, self.turn), 30.0)
        obs, cnt, valid, res, wcost = encode(self.ini, parse_turn(serialize_turn(self.state, self.side, self.turn).splitlines()))
        self.res, self.wcost = res, wcost
        return obs, cnt, valid

    def step(self, moves, f_idx, w_idx):
        from engine.pipeline import run_turn
        from runner.protocol import parse_commands
        mine = parse_commands(commands(self.ini, moves, f_idx, w_idx, self.res, self.wcost))
        raw, status = self.bot.collect_turn()
        theirs = parse_commands(raw or [])
        broken = status != "ok"
        cy, ck = (mine, theirs) if self.side == "Y" else (theirs, mine)
        self.state, result = run_turn(self.state, cy, ck)
        phi = SHAPE * (self._ts(self.state, self.side) - self._ts(self.state, self.oside))
        r = phi - self.phi
        self.phi = phi
        info = None
        if result is not None or broken:
            w = result["winner"] if result else "BROKEN"
            out = 1.0 if w == self.side else 0.0 if w in ("DRAW", "BROKEN") else -1.0
            r += out
            info = {"opp": self.opp, "win": 1.0 if w == self.side else 0.5 if w == "DRAW" else 0.0,
                    "broken": broken, "turns": self.turn}
            return self.reset(), r, True, info
        return self._observe(), r, False, info


def worker(wid, n_env, conn, opp_list):
    envs = [Env(wid, k, opp_list) for k in range(n_env)]
    try:
        while True:
            msg, data = conn.recv()
            if msg == "reset":
                outs = [e.reset() for e in envs]
                conn.send(([o[0] for o in outs], [o[1] for o in outs], [o[2] for o in outs]))
            elif msg == "step":
                obs, cnt, val, rew, done, infos = [], [], [], [], [], []
                for e, (mv, fi, wi) in zip(envs, data):
                    (o, c, v), r, d, info = e.step(mv, fi, wi)
                    obs.append(o); cnt.append(c); val.append(v); rew.append(r); done.append(d)
                    infos.append(info)
                conn.send((obs, cnt, val, rew, done, infos))
            elif msg == "opps":
                for e in envs:
                    e.set_opps(data)
            elif msg == "close":
                break
    finally:
        for e in envs:
            if e.bot:
                e.bot.close()


# ---------------------------------------------------------------------------- 정책 표본·확률

def sample_moves(torch, logits, cnt):
    """logits (B,2,5,H,W), cnt (B,2,H,W) → 인원 배분 (B,2,5,H,W) int, 칸별 유닛당 평균 log π (B,2,H,W)."""
    p = torch.softmax(logits, 2)
    rem = cnt.float()
    out = []
    acc = torch.zeros_like(rem)
    for d in range(4):
        rel = (p[:, :, d] / (1 - acc).clamp_min(1e-6)).clamp(0, 1)
        n = torch.distributions.Binomial(total_count=rem, probs=rel).sample()
        out.append(n)
        rem = rem - n
        acc = acc + p[:, :, d]
    out.append(rem)
    moves = torch.stack(out, 2)
    return moves, move_logp(torch, logits, moves, cnt)


def move_logp(torch, logits, moves, cnt):
    lp = torch.log_softmax(logits, 2)
    return (moves * lp).sum(2) / cnt.float().clamp_min(1)


# ---------------------------------------------------------------------------- 학습

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True)
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--envs", type=int, default=4, help="작업 프로세스당 동시 경기 수")
    p.add_argument("--steps", type=int, default=128, help="반복당 경기별 턴 수")
    p.add_argument("--iters", type=int, default=100000)
    p.add_argument("--hours", type=float, default=0, help="이 시간이 지나면 종료(0 = 반복 수만)")
    p.add_argument("--tiers", default="lv1,lv2|rusher,turtle,mid|presser,raider,econ,reactive|v3|v5s|v6|v8|v10")
    p.add_argument("--promote", type=float, default=0.75)
    p.add_argument("--window", type=int, default=200)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--gamma", type=float, default=0.995)
    p.add_argument("--lam", type=float, default=0.95)
    p.add_argument("--clip", type=float, default=0.2)
    p.add_argument("--ent", type=float, default=0.01)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--mb", type=int, default=1024)
    p.add_argument("--resume", default="")
    p.add_argument("--ch", type=int, default=64, help="새로 시작할 때 망 채널")
    p.add_argument("--blocks", type=int, default=6, help="새로 시작할 때 잔차 블록 수")
    p.add_argument("--league", default="", help="리그 모드: 고정 상대 목록(쉼표). 설정하면 --tiers 대신 자기대전 + PFSP")
    p.add_argument("--snap-every", type=int, default=20, help="리그: 이 반복마다 현재 가중치를 스냅샷 풀에 추가")
    p.add_argument("--pool-max", type=int, default=15)
    p.add_argument("--pool-init", default="", help="리그: 이 폴더의 snap*.pt 로 스냅샷 풀을 채우고 시작(이어 학습용)")
    p.add_argument("--self-frac", type=float, default=0.5, help="리그: 자기 스냅샷 상대 비율(그중 절반은 최신)")
    p.add_argument("--move-norm", type=float, default=16.0, help="이동 손실 = 칸 합 / 이 값(0 = rl1 방식 칸 평균)")
    p.add_argument("--kl-bc", type=float, default=0.0, help="이어 받은 가중치(BC) 정책과의 KL 벌점 계수")
    p.add_argument("--vwarm", type=int, default=0, help="처음 이 반복 수 동안 가치만 학습")
    p.add_argument("--target-kl", type=float, default=0.03)
    p.add_argument("--tier0", type=int, default=-1, help="이어 학습 시 시작 단계(−1 = 체크포인트 값)")
    args = p.parse_args()

    import torch
    from model import Net
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out = ROOT / "out/rl" / args.name
    out.mkdir(parents=True, exist_ok=True)
    tiers = [t.split(",") for t in args.tiers.split("|")]
    tier = 0

    league_fixed = [x for x in args.league.split(",") if x]
    pool = [f"self:{f}" for f in sorted((ROOT / args.pool_init).glob("snap*.pt"))][-args.pool_max:] if args.pool_init else []
    recent = {}

    def pfsp(names):
        """우선순위 가상 자기대전: 최근 승점률 w 인 상대의 가중치 (1 − w)² + 0.05. 기록이 적으면 0.5 로 본다."""
        out_w = []
        for n_ in names:
            h = recent.get(n_)
            w_ = sum(h) / len(h) if h and len(h) >= 10 else 0.5
            out_w.append((1 - w_) ** 2 + 0.05)
        return out_w

    def league_mix():
        names, weights = [], []
        fw = pfsp(league_fixed)
        tot = sum(fw)
        fixed_mass = 1.0 - (args.self_frac if pool else 0.0)
        names += league_fixed
        weights += [fixed_mass * x / tot for x in fw]
        if pool:
            names.append(pool[-1])                                # 최신 자기 자신
            weights.append(args.self_frac * 0.5)
            past = pool[:-1] or pool
            pw = pfsp(past)
            names += past
            weights += [args.self_frac * 0.5 * x / sum(pw) for x in pw]
        return names, weights

    def opp_mix(t):
        if league_fixed:
            return league_mix()
        cur = tiers[t]
        old = [o for tt in tiers[:t] for o in tt]
        # 70% 현재 단계, 30% 이전 단계 → 목록 가중 복제
        return cur * 7 + (old * 3 if old else [])

    ctx = mp.get_context("fork")
    conns, procs = [], []
    for w in range(args.workers):
        a, b = ctx.Pipe()
        pr = ctx.Process(target=worker, args=(w, args.envs, b, opp_mix(tier)), daemon=True)
        pr.start()
        conns.append(a)
        procs.append(pr)
    arch = (torch.load(args.resume, map_location="cpu").get("arch", {}) if args.resume
            else {"ch": args.ch, "blocks": args.blocks})
    net = Net(**arch).to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=args.lr)
    it0 = 0
    if args.resume:
        ck = torch.load(args.resume, map_location=dev)
        net.load_state_dict(ck["net"])
        opt.load_state_dict(ck["opt"])
        for g in opt.param_groups:                       # BC 체크포인트의 스케줄 학습률을 덮어쓴다
            g["lr"] = args.lr
        tier, it0 = ck.get("tier", 0), ck.get("iter", 0)
        if args.tier0 >= 0:
            tier = args.tier0
    ref = None
    if args.resume and args.kl_bc > 0:
        ref = Net(**arch).to(dev)
        ref.load_state_dict(torch.load(args.resume, map_location=dev)["net"])
        ref.eval()

    for c in conns:
        c.send(("opps", opp_mix(tier)))
        c.send(("reset", None))
    obs, cnt, val = [], [], []
    for c in conns:
        o, n, v = c.recv()
        obs += o; cnt += n; val += v
    B = len(obs)
    tier_hist = deque(maxlen=args.window)
    t_start = time.time()
    games = 0

    for it in range(it0, it0 + args.iters):
        T = args.steps
        buf = {k: [] for k in ("obs", "cnt", "val", "mv", "fi", "wi", "lpm", "lpf", "lpw", "v", "r", "d")}
        t0 = time.time()
        net.eval()
        for _ in range(T):
            o = torch.from_numpy(np.stack(obs)).to(dev)
            n = torch.from_numpy(np.stack(cnt)).to(dev)
            vl = torch.from_numpy(np.stack(val)).to(dev)
            with torch.no_grad():
                ml, fl, wl, v = net(o, vl)
                mv, lpm = sample_moves(torch, ml, n)
                fd = torch.distributions.Categorical(logits=fl)
                wd = torch.distributions.Categorical(logits=wl)
                fi, wi = fd.sample(), wd.sample()
            mv_np = mv.to(torch.int16).cpu().numpy()
            fi_np, wi_np = fi.cpu().numpy(), wi.cpu().numpy()
            k = 0
            for c in conns:
                c.send(("step", [(mv_np[k + j], int(fi_np[k + j]), int(wi_np[k + j])) for j in range(args.envs)]))
                k += args.envs
            nobs, ncnt, nval, rew, done = [], [], [], [], []
            for c in conns:
                o2, n2, v2, r2, d2, infos = c.recv()
                nobs += o2; ncnt += n2; nval += v2; rew += r2; done += d2
                for info in infos:
                    if info:
                        games += 1
                        recent.setdefault(info["opp"], deque(maxlen=100)).append(info["win"])
                        if info["opp"] in tiers[tier]:
                            tier_hist.append(info["win"])
            buf["obs"].append(o); buf["cnt"].append(n.to(torch.int16)); buf["val"].append(vl)
            buf["mv"].append(mv.to(torch.int16)); buf["fi"].append(fi); buf["wi"].append(wi)
            buf["lpm"].append(lpm); buf["lpf"].append(fd.log_prob(fi)); buf["lpw"].append(wd.log_prob(wi))
            buf["v"].append(v)
            buf["r"].append(torch.tensor(rew, device=dev, dtype=torch.float32))
            buf["d"].append(torch.tensor(done, device=dev, dtype=torch.float32))
            obs, cnt, val = nobs, ncnt, nval
        t_roll = time.time() - t0

        # GAE
        with torch.no_grad():
            _, _, _, v_last = net(torch.from_numpy(np.stack(obs)).to(dev), torch.from_numpy(np.stack(val)).to(dev))
        adv = torch.zeros(T, B, device=dev)
        last = torch.zeros(B, device=dev)
        for t in reversed(range(T)):
            nv = v_last if t == T - 1 else buf["v"][t + 1]
            nonterm = 1 - buf["d"][t]
            delta = buf["r"][t] + args.gamma * nv * nonterm - buf["v"][t]
            last = delta + args.gamma * args.lam * nonterm * last
            adv[t] = last
        ret = adv + torch.stack(buf["v"])
        flat = {k: torch.stack(v).flatten(0, 1) for k, v in buf.items() if k not in ("r", "d")}
        flat["adv"] = adv.flatten()
        flat["ret"] = ret.flatten()

        net.train()
        N = T * B
        stats = {"pl": 0.0, "vl": 0.0, "ent": 0.0, "kl": 0.0}
        nb = 0
        for _ in range(args.epochs):
            perm = torch.randperm(N, device=dev)
            for s in range(0, N, args.mb):
                idx = perm[s:s + args.mb]
                o = flat["obs"][idx].float()
                n = flat["cnt"][idx].long()
                ml, fl, wl, v = net(o, flat["val"][idx])
                a = flat["adv"][idx]
                a = (a - a.mean()) / (a.std() + 1e-8)
                act = (n > 0).float()                                   # (b,2,H,W)
                lpm = move_logp(torch, ml, flat["mv"][idx].float(), n)
                rm = torch.exp(lpm - flat["lpm"][idx])
                am = a.view(-1, 1, 1, 1)
                sm = torch.min(rm * am, rm.clamp(1 - args.clip, 1 + args.clip) * am)
                if args.move_norm > 0:
                    pl_m = -(sm * act).sum((1, 2, 3)) / args.move_norm   # 칸 합 / 상수: 병력이 많은 판일수록 신호가 크다
                else:
                    pl_m = -(sm * act).sum((1, 2, 3)) / act.sum((1, 2, 3)).clamp_min(1)
                fd = torch.distributions.Categorical(logits=fl)
                wd = torch.distributions.Categorical(logits=wl)
                pl_s = 0
                for dist, act_i, old in ((fd, flat["fi"][idx], flat["lpf"][idx]), (wd, flat["wi"][idx], flat["lpw"][idx])):
                    r_ = torch.exp(dist.log_prob(act_i) - old)
                    pl_s = pl_s - torch.min(r_ * a, r_.clamp(1 - args.clip, 1 + args.clip) * a)
                pol = (pl_m + pl_s).mean()
                pm = torch.softmax(ml, 2)
                ent_m = (-(pm * torch.log_softmax(ml, 2)).sum(2) * act).sum((1, 2, 3)) / act.sum((1, 2, 3)).clamp_min(1)
                ent = (ent_m + fd.entropy() + wd.entropy()).mean()
                vloss = ((v - flat["ret"][idx]) ** 2).mean()
                if it - it0 < args.vwarm:
                    pol = pol * 0                                           # 가치 예열: 정책은 그대로 두고 가치만 맞춘다
                loss = pol + 0.5 * vloss - args.ent * ent
                if ref is not None and args.kl_bc > 0:
                    with torch.no_grad():
                        rml, rfl, rwl, _ = ref(o, flat["val"][idx])
                    kl_m = (torch.softmax(rml, 2) * (torch.log_softmax(rml, 2) - torch.log_softmax(ml, 2))).sum(2)
                    kl_m = (kl_m * act).sum((1, 2, 3)) / act.sum((1, 2, 3)).clamp_min(1)
                    kl_s = sum((torch.softmax(r_, 1) * (torch.log_softmax(r_, 1) - torch.log_softmax(c_, 1))).sum(1)
                               for r_, c_ in ((rfl, fl), (rwl, wl)))
                    loss = loss + args.kl_bc * (kl_m + kl_s).mean()
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(net.parameters(), 0.5)
                opt.step()
                with torch.no_grad():
                    stats["kl"] += ((flat["lpm"][idx] - lpm) * act).sum().item() / act.sum().clamp_min(1).item()
                stats["pl"] += pol.item(); stats["vl"] += vloss.item(); stats["ent"] += ent.item()
                nb += 1
            if args.target_kl and stats["kl"] / max(nb, 1) > args.target_kl:
                break                                                       # 목표 KL 초과 → 이번 반복 갱신 중단
        stats = {k: round(v / nb, 4) for k, v in stats.items()}

        # 리그: 스냅샷 추가 + PFSP 가중치 갱신
        if league_fixed:
            if (it - it0) % args.snap_every == 0:
                (out / "pool").mkdir(exist_ok=True)
                snap = out / "pool" / f"snap{it:05d}.pt"
                torch.save({"net": net.state_dict(), "arch": net.arch}, snap)
                pool.append(f"self:{snap}")
                del pool[:-args.pool_max]
            for c in conns:
                c.send(("opps", league_mix()))
        # 커리큘럼
        rate = sum(tier_hist) / len(tier_hist) if tier_hist else 0.0
        promoted = False
        if not league_fixed and len(tier_hist) >= args.window and rate >= args.promote and tier + 1 < len(tiers):
            tier += 1
            tier_hist.clear()
            for c in conns:
                c.send(("opps", opp_mix(tier)))
            promoted = True
        rec = {"it": it, "games": games, "sps": round(T * B / (time.time() - t0)), "roll_s": round(t_roll, 1),
               "tier": tier, "tier_rate": round(rate, 3), "promoted": promoted, **stats,
               "rates": {(o.rsplit("/", 1)[-1] if o.startswith("self:") else o): round(sum(h) / len(h), 2)
                         for o, h in recent.items() if len(h) >= 10}}
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        if it % 10 == 0 or promoted:
            ck = {"net": net.state_dict(), "opt": opt.state_dict(), "tier": tier, "iter": it + 1, "arch": net.arch}
            torch.save(ck, out / "latest.pt")
            if promoted or it % 50 == 0:
                torch.save(ck, out / f"it{it:05d}_t{tier}.pt")
        if args.hours and time.time() - t_start > args.hours * 3600:
            break
    torch.save({"net": net.state_dict(), "opt": opt.state_dict(), "tier": tier, "iter": it + 1, "arch": net.arch}, out / "latest.pt")
    for c in conns:
        c.send(("close", None))


if __name__ == "__main__":
    main()
