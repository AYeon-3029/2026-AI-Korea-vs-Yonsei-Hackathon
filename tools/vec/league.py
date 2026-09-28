"""리그 강화학습(GPU) — 연구 기반 설계 (사용자 결정 2026-09-29):

1) 전문가 반복 / Sampled·Gumbel MuZero 발상(동시 수 변형): 매 반복 버퍼 상태 --search-states 개에서
   내 후보 N × 상대 후보 M 을 벡터 엔진으로 1턴 진행해 Q = 점수 보상 + γ·V(다음, 내 관점) 행렬을 만들고,
   상대 평균 Q 최대 후보를 정답으로 정책을 증류한다(탐색이 정책을 이기는 만큼 정책이 계속 따라온다).
2) Lux AI 우승작 학습 목표: PPO(GAE λ-수익) + UPGO(G = r + γ·max(V', G')) 정책 항,
   초기 가중치(교사)와의 KL, 점수 보조 보상 — 두 항 모두 --anneal 반복에 걸쳐 0 으로 줄여 결국 승패만 남긴다.
3) AlphaStar 리그 / PSRO: 주 에이전트(M) + 주 착취자(X, M 만 이기도록 학습). X 가 M 을 충분히 이기거나 --x-reset 반복이 지나면
   X 스냅샷을 M 의 상대 풀에 넣고 X 를 초기 가중치로 되돌린다. M 의 상대: 자기 자신, 과거 스냅샷(PFSP),
   고정 상대(v10 모방 신경망, 결정적 분할), X 스냅샷.

판 구성(n 판): G1 = M 대 M(양쪽 학습), G2 = M 대 이번 반복의 상대(판 번호 홀짝으로 M 진영), G3 = X 대 M(양쪽 학습).
정책망·관측·행동은 rlbot 과 같아 체크포인트를 그대로 공식 엔진·C++ 로 쓸 수 있다.

사용 (WSL, 프로젝트 루트):
  python3 tools/vec/league.py --name lg --init out/rl/vs1/latest.pt --fixed out/rl/big0/latest.pt,out/rl/big1/latest.pt,out/rl/big2/latest.pt
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
from selfplay import fwd, move_logp, prop_act, sample_moves  # noqa: E402
from vecgame import VecGame, gen_maps  # noqa: E402

KEYS = ("obs", "cnt", "val", "mv", "fi", "wi", "lpm", "lpf", "lpw", "v", "r", "d")


def act_any(net, obs, cnt, valid, prop=False):
    if prop:
        mv, fi, wi = prop_act(net, obs, cnt, valid)
        return mv, fi, wi, None
    ml, fl, wl, v = fwd(net, obs, valid)
    mv, lpm = sample_moves(ml, cnt)
    fd, wd = torch.distributions.Categorical(logits=fl), torch.distributions.Categorical(logits=wl)
    fi, wi = fd.sample(), wd.sample()
    return mv, fi, wi, (lpm, fd.log_prob(fi), wd.log_prob(wi), v)


class Learner:
    def __init__(self, name, net, lr):
        self.name, self.net = name, net
        self.opt = torch.optim.Adam(net.parameters(), lr=lr)
        self.lr = lr

    def reset_to(self, state_dict):
        self.net.load_state_dict(state_dict)
        self.opt = torch.optim.Adam(self.net.parameters(), lr=self.lr)


# ---------------------------------------------------------------------------- 탐색 증류 목표

def search_targets(net, sg, sb, states, me, N, M, gamma, shape):
    """states(S 개) 각각에서 N×M 표본 탐색 → 정답 (obs, cnt, valid, mv, fi, wi) 와 통계."""
    S = len(me)
    dev = me.device
    sb.restore(states, 1)
    ob = [sb.observe(t) for t in (0, 1)]
    ar = torch.arange(S, device=dev)
    stack = lambda k: torch.stack([ob[0][k], ob[1][k]], 1)  # noqa: E731
    o_all, c_all, v_all = stack(0), stack(1), stack(2)
    mo, mc, mvld = o_all[ar, me], c_all[ar, me], v_all[ar, me]
    oo, oc, ovl = o_all[ar, 1 - me], c_all[ar, 1 - me], v_all[ar, 1 - me]
    with torch.no_grad():
        # 내 후보: 0 = 결정적 분할, 나머지 표본. 상대 후보: 0 = 결정적, 나머지 표본(자기 모형)
        def cands(o, c, vl, k):
            pm, pf, pw = prop_act(net, o, c, vl)
            rep = lambda x: x.repeat_interleave(k - 1, 0)  # noqa: E731
            sm, sf, sw, _ = act_any(net, rep(o), rep(c), rep(vl))
            mv = torch.cat([pm.unsqueeze(1), sm.view(S, k - 1, *sm.shape[1:])], 1)
            fi = torch.cat([pf.unsqueeze(1), sf.view(S, k - 1)], 1)
            wi = torch.cat([pw.unsqueeze(1), sw.view(S, k - 1)], 1)
            return mv, fi, wi
        m_mv, m_fi, m_wi = cands(mo, mc, mvld, N)
        o_mv, o_fi, o_wi = cands(oo, oc, ovl, M)
        sg.restore(states, N * M)                                # 판 e = s·N·M + i·M + j
        n = S * N * M
        mv_t = torch.zeros(n, 2, 2, 5, 15, 15, device=dev)
        fi_t = torch.zeros(n, 2, dtype=torch.long, device=dev)
        wi_t = torch.zeros(n, 2, dtype=torch.long, device=dev)
        e_me = me.repeat_interleave(N * M)
        E = torch.arange(n, device=dev)
        mine = (m_mv.repeat_interleave(M, 1).reshape(n, 2, 5, 15, 15), m_fi.repeat_interleave(M, 1).reshape(n),
                m_wi.repeat_interleave(M, 1).reshape(n))
        theirs = (o_mv.repeat(1, N, 1, 1, 1, 1).reshape(n, 2, 5, 15, 15), o_fi.repeat(1, N).reshape(n),
                  o_wi.repeat(1, N).reshape(n))
        mv_t[E, e_me], fi_t[E, e_me], wi_t[E, e_me] = mine
        mv_t[E, 1 - e_me], fi_t[E, 1 - e_me], wi_t[E, 1 - e_me] = theirs
        sc0 = torch.stack([torch.where(sg.owner == t, sg.bscore, 0).sum(1) for t in (0, 1)], 1)
        res = sg.step([(mv_t[:, 0], fi_t[:, 0], wi_t[:, 0]), (mv_t[:, 1], fi_t[:, 1], wi_t[:, 1])])
        d0 = sc0[E, e_me] - sc0[E, 1 - e_me]
        d1 = sg.score[E, e_me] - sg.score[E, 1 - e_me]
        r = shape * (d1 - d0).float()
        vals = torch.zeros(n, device=dev)
        for t in (0, 1):
            idx = (e_me == t).nonzero().squeeze(1)
            if len(idx) == 0:
                continue
            o2, _, v2 = sg.observe(t)
            for s0 in range(0, len(idx), 4096):
                ii = idx[s0:s0 + 4096]
                vals[ii] = fwd(net, o2[ii], v2[ii])[3]
        term = torch.where(res == e_me, 1.0, torch.where(res == 2, 0.0, -1.0))
        q = torch.where(res >= 0, r + term, r + gamma * vals).view(S, N, M)
        qm = q.mean(2)
        best = qm.argmax(1)
    stats = {"search_prop_pick": round(float((best == 0).float().mean()), 3),
             "search_gain": round(float((qm.max(1).values - qm[:, 0]).mean()), 4)}
    return (mo, mc, mvld, m_mv[ar, best], m_fi[ar, best], m_wi[ar, best]), stats


# ---------------------------------------------------------------------------- 학습

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True)
    p.add_argument("--init", required=True, help="M·X 초기 가중치(= KL 교사, X 초기화 지점)")
    p.add_argument("--fixed", default="")
    p.add_argument("--envs", type=int, default=1536)
    p.add_argument("--g1", type=float, default=0.4)
    p.add_argument("--g2", type=float, default=0.25)
    p.add_argument("--steps", type=int, default=64)
    p.add_argument("--hours", type=float, default=12)
    p.add_argument("--maps", type=int, default=20000)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--gamma", type=float, default=0.995)
    p.add_argument("--lam", type=float, default=0.95)
    p.add_argument("--clip", type=float, default=0.2)
    p.add_argument("--ent", type=float, default=0.005)
    p.add_argument("--upgo", type=float, default=1.0)
    p.add_argument("--kl", type=float, default=0.02, help="교사 KL 시작 계수(→ 0)")
    p.add_argument("--shape", type=float, default=0.02, help="점수 보조 보상 시작 계수(→ 0)")
    p.add_argument("--anneal", type=int, default=1500, help="KL·보조 보상을 0 으로 줄이는 반복 수")
    p.add_argument("--search-states", type=int, default=256)
    p.add_argument("--search-n", type=int, default=8)
    p.add_argument("--search-m", type=int, default=8)
    p.add_argument("--search-coef", type=float, default=0.5)
    p.add_argument("--epochs", type=int, default=2)
    p.add_argument("--mb", type=int, default=2048)
    p.add_argument("--move-norm", type=float, default=16.0)
    p.add_argument("--target-kl", type=float, default=0.03)
    p.add_argument("--snap-every", type=int, default=20)
    p.add_argument("--pool-max", type=int, default=30)
    p.add_argument("--x-reset", type=int, default=200)
    p.add_argument("--x-win", type=float, default=0.7)
    p.add_argument("--eval-every", type=int, default=50)
    p.add_argument("--eval-opps", default="mid,v3,v6,v10")
    args = p.parse_args()
    dev = torch.device("cuda")
    out = ROOT / "out/rl" / args.name
    out.mkdir(parents=True, exist_ok=True)
    cache = ROOT / f"out/rl/maps_{args.maps}.npz"
    maps = dict(np.load(cache)) if cache.exists() else gen_maps(list(range(5_000_000, 5_000_000 + args.maps)), 24)

    ck = torch.load(ROOT / args.init, map_location=dev)
    arch = ck.get("arch", {})
    init_sd = copy.deepcopy(ck["net"])
    teacher = Net(**arch).to(dev).eval()
    teacher.load_state_dict(init_sd)
    Mn = Net(**arch).to(dev)
    Mn.load_state_dict(init_sd)
    Xn = Net(**arch).to(dev)
    Xn.load_state_dict(init_sd)
    L = {"M": Learner("M", Mn, args.lr), "X": Learner("X", Xn, args.lr)}
    opp = Net(**arch).to(dev).eval()
    fixed = []
    for f in [x for x in args.fixed.split(",") if x]:
        c2 = torch.load(ROOT / f, map_location=dev)
        fn = Net(**c2.get("arch", {})).to(dev).eval()
        fn.load_state_dict(c2["net"])
        fixed.append((Path(f).parent.name, fn))
    pool = [("m0", copy.deepcopy(init_sd))]                      # M 스냅샷
    xpool = []                                                   # X 스냅샷
    wr = {}

    n = args.envs
    g1, g2 = int(n * args.g1), int(n * (args.g1 + args.g2))
    vg = VecGame(maps, n, dev, rng=torch.Generator().manual_seed(7))
    S = args.search_states
    sg = VecGame(maps, S * args.search_n * args.search_m, dev)
    sb = VecGame(maps, S, dev)
    e = torch.arange(n, device=dev)
    par = e % 2
    # 누가 어느 (판, 팀) 을 두는가: 팀 t 마다 판 마스크
    who = {}
    for t in (0, 1):
        g1m, g2m, g3m = e < g1, (e >= g1) & (e < g2), e >= g2
        who[("M", t)] = e[g1m | (g2m & (par == t)) | (g3m & (par != t))]
        who[("X", t)] = e[g3m & (par == t)]
        who[("O", t)] = e[g2m & (par != t)]
    streams = {k: (torch.cat([who[(k, 0)], who[(k, 1)]]),
                   torch.cat([torch.zeros(len(who[(k, 0)]), dtype=torch.long, device=dev),
                              torch.ones(len(who[(k, 1)]), dtype=torch.long, device=dev)])) for k in ("M", "X")}
    phi = {k: torch.zeros(len(streams[k][0]), device=dev) for k in L}
    t_start, it, games = time.time(), 0, 0
    recent = {"x_vs_m": [], "m_vs_opp": []}
    evals = []
    x_age = 0
    while time.time() - t_start < args.hours * 3600:
        frac = max(0.0, 1 - it / args.anneal)
        shape, klc = args.shape * frac, args.kl * frac
        # G2 상대: 고정(35%), X 스냅샷(15%), M 스냅샷 PFSP(나머지)
        u = np.random.rand()
        if fixed and u < 0.35:
            k = np.random.randint(len(fixed))
            opp_name, opp_net, opp_prop = fixed[k][0], fixed[k][1], True
        elif xpool and u < 0.5:
            j = np.random.randint(len(xpool))
            opp.load_state_dict(xpool[j][1])
            opp_name, opp_net, opp_prop = xpool[j][0], opp, False
        else:
            w_ = np.array([(1 - wr.get(nm, 0.5)) ** 2 + 0.05 for nm, _ in pool])
            j = np.random.choice(len(pool), p=w_ / w_.sum())
            opp.load_state_dict(pool[j][1])
            opp_name, opp_net, opp_prop = pool[j][0], opp, False
        B = {k: {kk: [] for kk in KEYS} for k in L}
        opp_res, x_res = [], []
        snap_step = np.random.randint(args.steps)
        s_states = s_me = None
        t0 = time.time()
        for lr_ in L.values():
            lr_.net.eval()
        with torch.no_grad():
            for step in range(args.steps):
                ob = [vg.observe(t) for t in (0, 1)]
                if step == snap_step:                           # 탐색 증류용 상태(G1 판에서)
                    pick = torch.randint(0, g1, (S,), device=dev)
                    s_states = vg.snapshot(pick)
                    s_me = torch.randint(0, 2, (S,), device=dev)
                mv_t = torch.zeros(n, 2, 2, 5, 15, 15, device=dev)
                fi_t = torch.zeros(n, 2, dtype=torch.long, device=dev)
                wi_t = torch.zeros(n, 2, dtype=torch.long, device=dev)
                outs = {}
                for k, net in (("M", L["M"].net), ("X", L["X"].net), ("O", opp_net)):
                    E, Tm = streams[k] if k in streams else (torch.cat([who[("O", 0)], who[("O", 1)]]),
                                                             torch.cat([torch.zeros(len(who[("O", 0)]), dtype=torch.long, device=dev),
                                                                        torch.ones(len(who[("O", 1)]), dtype=torch.long, device=dev)]))
                    if len(E) == 0:
                        continue
                    o = torch.stack([ob[0][0], ob[1][0]], 1)[E, Tm]
                    c = torch.stack([ob[0][1], ob[1][1]], 1)[E, Tm]
                    vl = torch.stack([ob[0][2], ob[1][2]], 1)[E, Tm]
                    mv, fi, wi, extra = act_any(net, o, c, vl, prop=(k == "O" and opp_prop))
                    mv_t[E, Tm], fi_t[E, Tm], wi_t[E, Tm] = mv, fi, wi
                    outs[k] = (o, c, vl, mv, fi, wi, extra)
                res = vg.step([(mv_t[:, 0], fi_t[:, 0], wi_t[:, 0]), (mv_t[:, 1], fi_t[:, 1], wi_t[:, 1])])
                for k in L:
                    E, Tm = streams[k]
                    o, c, vl, mv, fi, wi, (lpm, lpf, lpw, v) = outs[k]
                    sc = vg.score[E]
                    me = sc.gather(1, Tm.unsqueeze(1)).squeeze(1)
                    op = sc.gather(1, (1 - Tm).unsqueeze(1)).squeeze(1)
                    nphi = shape * (me - op).float()
                    r = nphi - phi[k]
                    rs = res[E]
                    done = rs >= 0
                    r = r + torch.where(done, torch.where(rs == Tm, 1.0, torch.where(rs == 2, 0.0, -1.0)), 0.0)
                    phi[k] = torch.where(done, torch.zeros_like(nphi), nphi)
                    for kk, val in zip(KEYS, (o, c.to(torch.int16), vl, mv.to(torch.int16), fi, wi, lpm, lpf, lpw, v, r, done.float())):
                        B[k][kk].append(val)
                ended = (res >= 0).nonzero().squeeze(1)
                if len(ended):
                    games += len(ended)
                    for ee in ended.tolist():
                        rr = int(res[ee])
                        if g1 <= ee < g2:                       # M 대 상대: M 진영 = 판 홀짝
                            opp_res.append(1.0 if rr == ee % 2 else 0.5 if rr == 2 else 0.0)
                        elif ee >= g2:                          # X 대 M: X 진영 = 판 홀짝
                            x_res.append(1.0 if rr == ee % 2 else 0.5 if rr == 2 else 0.0)
                    vg.reset(ended)
            ob = [vg.observe(t) for t in (0, 1)]
            v_last = {}
            for k in L:
                E, Tm = streams[k]
                v_last[k] = fwd(L[k].net, torch.stack([ob[0][0], ob[1][0]], 1)[E, Tm], torch.stack([ob[0][2], ob[1][2]], 1)[E, Tm])[3]
        t_roll = time.time() - t0

        # 탐색 증류 목표(M)
        t1 = time.time()
        L["M"].net.eval()
        dist, sstats = search_targets(L["M"].net, sg, sb, s_states, s_me, args.search_n, args.search_m, args.gamma, max(shape, 1e-3))
        t_search = time.time() - t1

        st_all = {}
        for k, lrn in L.items():
            Bk = B[k]
            T_, Sk = len(Bk["r"]), len(streams[k][0])
            vs = torch.stack(Bk["v"])
            rs_ = torch.stack(Bk["r"])
            ds = torch.stack(Bk["d"])
            adv = torch.zeros(T_, Sk, device=dev)
            upg = torch.zeros(T_, Sk, device=dev)
            last = torch.zeros(Sk, device=dev)
            g_next = v_last[k]
            for t in reversed(range(T_)):
                nv = v_last[k] if t == T_ - 1 else vs[t + 1]
                nt = 1 - ds[t]
                delta = rs_[t] + args.gamma * nv * nt - vs[t]
                last = delta + args.gamma * args.lam * nt * last
                adv[t] = last
                # UPGO: 다음 상태 가치보다 실제 수익이 좋을 때만 그 수익을 끌어온다
                upg[t] = rs_[t] + args.gamma * nt * torch.maximum(nv, g_next)
                g_next = upg[t]
            ret = adv + vs
            a_up = upg - vs
            F = {kk: torch.stack(vv).flatten(0, 1) for kk, vv in Bk.items() if kk not in ("r", "d")}
            F["adv"], F["ret"], F["aup"] = adv.flatten(), ret.flatten(), a_up.flatten()
            del B[k]
            lrn.net.train()
            N_ = T_ * Sk
            st = {"pl": 0.0, "vl": 0.0, "ent": 0.0, "kl": 0.0, "tkl": 0.0, "sd": 0.0}
            nb, stop = 0, False
            for _ in range(args.epochs):
                perm = torch.randperm(N_, device=dev)
                for s0 in range(0, N_, args.mb):
                    idx = perm[s0:s0 + args.mb]
                    cnt = F["cnt"][idx].long()
                    ml, fl, wl, v = fwd(lrn.net, F["obs"][idx], F["val"][idx])
                    actv = (cnt > 0).float()
                    lpm = move_logp(ml, F["mv"][idx].float(), cnt)
                    rm = torch.exp(lpm - F["lpm"][idx])
                    fd, wd = torch.distributions.Categorical(logits=fl), torch.distributions.Categorical(logits=wl)
                    rf = torch.exp(fd.log_prob(F["fi"][idx]) - F["lpf"][idx])
                    rw = torch.exp(wd.log_prob(F["wi"][idx]) - F["lpw"][idx])
                    pol = 0
                    for a, wgt in ((F["adv"][idx], 1.0), (F["aup"][idx], args.upgo)):
                        a = (a - a.mean()) / (a.std() + 1e-8)
                        am = a.view(-1, 1, 1, 1)
                        pm_ = -(torch.min(rm * am, rm.clamp(1 - args.clip, 1 + args.clip) * am) * actv).sum((1, 2, 3)) / args.move_norm
                        ps_ = sum(-torch.min(r_ * a, r_.clamp(1 - args.clip, 1 + args.clip) * a) for r_ in (rf, rw))
                        pol = pol + wgt * (pm_ + ps_).mean()
                    pm = torch.softmax(ml, 2)
                    lsm = torch.log_softmax(ml, 2)
                    ent_m = (-(pm * lsm).sum(2) * actv).sum((1, 2, 3)) / actv.sum((1, 2, 3)).clamp_min(1)
                    ent = (ent_m + fd.entropy() + wd.entropy()).mean()
                    vloss = ((v - F["ret"][idx]) ** 2).mean()
                    loss = pol + 0.5 * vloss - args.ent * ent
                    if klc > 0:
                        with torch.no_grad():
                            tml, tfl, twl, _ = fwd(teacher, F["obs"][idx], F["val"][idx])
                        tkm = (torch.softmax(tml, 2) * (torch.log_softmax(tml, 2) - lsm)).sum(2)
                        tkm = (tkm * actv).sum((1, 2, 3)) / actv.sum((1, 2, 3)).clamp_min(1)
                        tks = sum((torch.softmax(a_, 1) * (torch.log_softmax(a_, 1) - torch.log_softmax(b_, 1))).sum(1)
                                  for a_, b_ in ((tfl, fl), (twl, wl)))
                        tkl = (tkm + tks).mean()
                        loss = loss + klc * tkl
                        st["tkl"] += tkl.item()
                    if k == "M" and args.search_coef > 0:
                        so, sc_, sv, smv, sfi, swi = dist
                        dml, dfl, dwl, _ = fwd(lrn.net, so, sv)
                        tot = smv.float().sum((1, 2, 3, 4)).clamp_min(1)
                        sd = (-(smv.float() * torch.log_softmax(dml, 2)).sum((1, 2, 3, 4)) / tot).mean() \
                            + 0.5 * (torch.nn.functional.cross_entropy(dfl, sfi) + torch.nn.functional.cross_entropy(dwl, swi))
                        loss = loss + args.search_coef * sd / (args.epochs * max(1, N_ // args.mb))
                        st["sd"] += sd.item()
                    lrn.opt.zero_grad()
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(lrn.net.parameters(), 0.5)
                    lrn.opt.step()
                    with torch.no_grad():
                        st["kl"] += (((F["lpm"][idx] - lpm) * actv).sum() / actv.sum().clamp_min(1)).item()
                    st["pl"] += float(pol); st["vl"] += vloss.item(); st["ent"] += ent.item()
                    nb += 1
                if args.target_kl and st["kl"] / nb > args.target_kl:
                    break
            st_all[k] = {kk: round(vv / nb, 4) for kk, vv in st.items()}
            del F

        # 리그 관리
        if opp_res:
            wr[opp_name] = 0.7 * wr.get(opp_name, 0.5) + 0.3 * (sum(opp_res) / len(opp_res))
        recent["x_vs_m"] = (recent["x_vs_m"] + x_res)[-300:]
        it += 1
        x_age += 1
        if it % args.snap_every == 0:
            pool.append((f"m{it}", copy.deepcopy(L["M"].net.state_dict())))
            del pool[:-args.pool_max]
        xw = sum(recent["x_vs_m"]) / len(recent["x_vs_m"]) if recent["x_vs_m"] else 0.5
        x_event = ""
        if x_age >= args.x_reset or (len(recent["x_vs_m"]) >= 200 and xw >= args.x_win):
            xpool.append((f"x{it}", copy.deepcopy(L["X"].net.state_dict())))
            del xpool[:-10]
            L["X"].reset_to(init_sd)
            x_age, recent["x_vs_m"] = 0, []
            x_event = f"X 스냅샷 x{it} 추가·초기화 (M 상대 {xw:.2f})"
        rec = {"it": it, "games": games, "sps": round(args.steps * n / (time.time() - t0)), "roll_s": round(t_roll, 1),
               "search_s": round(t_search, 1), **sstats, "opp": opp_name,
               "m_vs_opp": round(sum(opp_res) / len(opp_res), 3) if opp_res else None, "x_vs_m": round(xw, 3),
               "anneal": round(frac, 3), "M": st_all["M"], "X": st_all["X"],
               "vs_fixed": {kk: round(vv, 2) for kk, vv in wr.items() if not kk.startswith(("m", "x"))}}
        if x_event:
            rec["event"] = x_event
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        if it % args.eval_every == 0:
            ckp = out / f"it{it:05d}.pt"
            torch.save({"net": L["M"].net.state_dict(), "arch": L["M"].net.arch, "iter": it}, ckp)
            torch.save({"net": L["M"].net.state_dict(), "arch": L["M"].net.arch, "iter": it, "opt": L["M"].opt.state_dict()},
                       out / "latest.pt")
            evals = [p_ for p_ in evals if p_.poll() is None]
            if not evals:
                evals.append(subprocess.Popen(
                    [sys.executable, str(ROOT / "tools/vec/eval_ckpt.py"), "--ckpt", str(ckp.relative_to(ROOT)),
                     "--opps", args.eval_opps, "--out", str((out / "eval.jsonl").relative_to(ROOT)), "--tag", f"it{it}"],
                    cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))


if __name__ == "__main__":
    main()
