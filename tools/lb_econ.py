"""리더보드 변환 리플레이: 양쪽 수입(10 + 2×학생회관)·W 단가(공학관)·보급소 보너스 누계와 상대 W 생산 비용 추정.
사용: python3 tools/lb_econ.py out/replays/leaderboard/V22_1001_8am
"""
import glob, json, os, sys


def cnt(st, t, k):
    return sum(u[4] for u in st["units"] if u[0] == t and u[1] == k)


def run(path):
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    B = {b["id"]: b for b in r["map"]["buildings"]}
    T = r["turns"]
    inc = {me: 0, op: 0}; engt = {me: 0, op: 0}; dep = {me: set(), op: set()}
    wcost = {me: 0, op: 0}; wn = {me: 0, op: 0}; halls = {me: 0, op: 0}
    for k in range(1, len(T)):
        a, b = T[k - 1]["state"], T[k]["state"]
        own = {t: [B[x["id"]]["type"] for x in a["buildings"] if x["owner"] == t] for t in (me, op)}
        sp = sum(int(l.split()[2]) for l in T[k]["commands"].get(me, []) if l.startswith("SPAWN W"))
        wd = max(0, cnt(a, me, "W") + sp - cnt(b, me, "W"))
        spawned = {me: sp, op: cnt(b, op, "W") - cnt(a, op, "W") + wd}
        for t in (me, op):
            h = own[t].count("HALL")
            inc[t] += 10 + 2 * h; halls[t] += h
            e = "ENG" in own[t]
            engt[t] += e
            c = 2 if e else 3
            wcost[t] += spawned[t] * c; wn[t] += spawned[t]
            for x in b["buildings"]:
                if x["owner"] == t and B[x["id"]]["type"] == "DEPOT":
                    dep[t].add(x["id"])
    n = len(T) - 1
    return me, op, n, inc, engt, halls, dep, wcost, wn, r["result"]


def main():
    p = sys.argv[1]
    files = sorted(glob.glob(os.path.join(p, "vs*.json"))) if os.path.isdir(p) else [p]
    print(f"{'상대':<22}결과 턴 | 수입 우리·상대(차) | 학관 평균 | 공학관 보유턴 | W 생산비 우리·상대 | W 평균단가")
    for f in files:
        me, op, n, inc, engt, halls, dep, wcost, wn, res = run(f)
        w = "승" if res.get("winner") == me else "패"
        print(f"{os.path.basename(f)[2:-5]:<22}{w} {n:3d} | {inc[me]:5d} {inc[op]:5d} ({inc[me] - inc[op]:+4d}) | {halls[me] / n:.2f} {halls[op] / n:.2f} | "
              f"{engt[me]:3d} {engt[op]:3d} | {wcost[me]:5d} {wcost[op]:5d} | {wcost[me] / max(1, wn[me]):.2f} {wcost[op] / max(1, wn[op]):.2f}")


if __name__ == "__main__":
    main()
