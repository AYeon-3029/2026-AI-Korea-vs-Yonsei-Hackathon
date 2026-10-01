"""리더보드 변환 리플레이 한 경기의 타임라인: 점수·건물·W·F 흐름과 건물 소유 변화 순간.
- 구간 줄(--step 턴마다): 점수(공개 점수 기준) 우리:상대, 종류별 건물 수, W 수·W 칸 수, F 수, 누적 F 사망(우리 = 이전 + 생산 − 현재)
- 변화 줄: 건물이 중립화·점령된 턴, 종류, 누가, 그 칸 2칸 안 우리/상대 W
- 주둔 낭비: 우리 W 가 같은 칸에 3턴 이상 머문 W·턴 중 '적 소유 건물 위(우리 F 없음)' 몫
사용: python3 tools/lb_flow.py <파일> [--step 10] [--from 1 --to 160] [--changes]
"""
import ast
import json
import sys

SH = {"HALL": "학", "ENG": "공", "LIBRARY": "도", "PLAZA": "광", "STATION": "역", "HOSPITAL": "병", "WATCH": "방", "DEPOT": "보"}
d = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])


def P(v):
    return ast.literal_eval(v) if isinstance(v, str) else v


def arg(k, dv):
    return int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else dv


def main(path):
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    B = {b["id"]: b for b in r["map"]["buildings"]}
    T = [dict(turn=int(t["turn"]), st=P(t["state"]), ev=P(t["events"]), cm=P(t["commands"])) for t in r["turns"]]
    step, lo, hi = arg("--step", 10), arg("--from", 1), arg("--to", 999)
    show_ch = "--changes" in sys.argv
    nm = path.replace("\\", "/").split("/")[-1][2:-5]
    print(f"### {nm} 우리 {me} · 결과 {r['result']}")

    def own(st):
        o = {}
        for x in st["buildings"]:
            o[x["id"]] = x["owner"]
        return o

    def units(st, tm, k):
        u = {}
        for x in st["units"]:
            if x[0] == tm and x[1] == k:
                u[(x[2], x[3])] = u.get((x[2], x[3]), 0) + x[4]
        return u

    fdead = {me: 0, op: 0}
    idle = {"bld_enemy": 0, "bld_neutral": 0, "own_bld": 0, "field": 0}
    stay = {}
    prev = None
    for k, t in enumerate(T):
        st = t["st"]; o = own(st)
        Wm, Wo = units(st, me, "W"), units(st, op, "W")
        Fm, Fo = units(st, me, "F"), units(st, op, "F")
        if prev is not None:
            pst = prev["st"]
            spF = sum(int(l.split()[2]) for l in t["cm"].get(me, []) if l.startswith("SPAWN F"))
            fdead[me] += max(0, sum(units(pst, me, "F").values()) + spF - sum(Fm.values()))
            # 상대 F: 줄어든 칸 수(생산은 본진/병원 칸 증가로만 나타나므로 감소분만)
            pF = units(pst, op, "F")
            fdead[op] += max(0, sum(pF.values()) - sum(Fo.values()))
            po = own(pst)
            for bid, ow in o.items():
                if po.get(bid) != ow and lo <= t["turn"] <= hi and show_ch:
                    b = B[bid]; c = (b["x"], b["y"])
                    who = ("우리" if ow == me else "상대") if ow in (me, op) else ("중립←" + ("우리" if po.get(bid) == me else "상대"))
                    wm = sum(n for x, n in units(pst, me, "W").items() if d(x, c) <= 2)
                    wo = sum(n for x, n in units(pst, op, "W").items() if d(x, c) <= 2)
                    print(f"   {t['turn']:3d}턴 {SH[b['type']]}{c} → {who:7s} 직전 2칸 W 우리 {wm} 상대 {wo}")
        # 주둔 낭비
        pos_b = {(B[i]["x"], B[i]["y"]): i for i in B}
        ns = {}
        for c, n in Wm.items():
            ns[c] = stay.get(c, 0) + 1
            if ns[c] >= 3:
                bid = pos_b.get(c)
                if bid is None:
                    idle["field"] += n
                elif o.get(bid) == op and c not in Fm:
                    idle["bld_enemy"] += n
                elif o.get(bid) not in (me, op) and c not in Fm:
                    idle["bld_neutral"] += n
                else:
                    idle["own_bld"] += n
        stay = ns
        if t["turn"] % step == 0 and lo <= t["turn"] <= hi or k == len(T) - 1:
            sc = {me: 0, op: 0}; cnt = {me: {}, op: {}}
            for bid, ow in o.items():
                if ow in (me, op):
                    sc[ow] += B[bid].get("score", 0) or 0
                    cnt[ow][SH[B[bid]["type"]]] = cnt[ow].get(SH[B[bid]["type"]], 0) + 1
            fmt = lambda c: "".join(f"{k}{v}" for k, v in sorted(c.items()))
            print(f"{t['turn']:3d} 점수 {sc[me]:2d}:{sc[op]:2d} | 건물 {fmt(cnt[me]):14s} : {fmt(cnt[op]):14s} | "
                  f"W {sum(Wm.values()):3d}:{sum(Wo.values()):3d} 칸 {len(Wm):2d}:{len(Wo):2d} | F {sum(Fm.values()):2d}:{sum(Fo.values()):2d} "
                  f"| F사망 {fdead[me]:2d}:{fdead[op]:2d} | 자원 {st['resources'][me]}:{st['resources'][op]}")
        prev = t
    tot = sum(idle.values()) or 1
    print(f"   3턴+ 정지 우리 W·턴: 적 건물 위 {idle['bld_enemy']} ({idle['bld_enemy'] / tot:.0%}) · 중립 건물 {idle['bld_neutral']} · "
          f"자기 건물/F 동반 {idle['own_bld']} · 들판 {idle['field']}")


if __name__ == "__main__":
    for f in [a for a in sys.argv[1:] if a.endswith(".json")]:
        main(f)
