"""리더보드 변환 리플레이: W 격차가 벌어지는 지점과 경제 장부(학관·공학관 보유 턴 누계 차).
- 장부: 학관턴차 = Σ(우리 학관 수 − 상대 학관 수), 공학관턴차 = Σ([우리 공학관 有] − [상대 공학관 有])
- 수입누계차 = Σ(우리 수입 − 상대 수입), W 생산비 이득 = 공학관 유무로 아낀 자원 차(근사: 생산 W × 단가 차)
- 갈림 턴: 우리 W − 상대 W 가 처음으로 −10 이하가 되고 이후 회복(−3 이상)하지 못한 턴
사용: python3 tools/lb_gap.py <폴더|파일…> [--detail]
"""
import glob, json, os, sys


def cnt(st, t, k):
    return sum(u[4] for u in st["units"] if u[0] == t and u[1] == k)


def run(path, detail):
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    B = {b["id"]: b for b in r["map"]["buildings"]}
    T = r["turns"]
    hall = eng = inc = 0
    rows = []
    for k in range(1, len(T)):
        a, b = T[k - 1]["state"], T[k]["state"]
        own = {t: [B[x["id"]]["type"] for x in a["buildings"] if x["owner"] == t] for t in (me, op)}
        h = own[me].count("HALL") - own[op].count("HALL")
        e = ("ENG" in own[me]) - ("ENG" in own[op])
        hall += h; eng += e; inc += 2 * h
        wd = cnt(b, me, "W") - cnt(b, op, "W")
        rows.append((T[k]["turn"], wd, hall, eng, inc, own[me].count("HALL"), own[op].count("HALL"), "ENG" in own[me], "ENG" in own[op]))
    split = None
    for i, x in enumerate(rows):
        if x[1] <= -10 and all(y[1] < -3 for y in rows[i:]):
            split = x
            break
    res = "승" if r["result"].get("winner") == me else "패"
    name = os.path.basename(path)[2:-5]
    if split:
        print(f"{name:<22}{res} 갈림 {split[0]:3d}턴 | 그때 학관턴차 {split[2]:+4d} 공학관턴차 {split[3]:+4d} 수입누계차 {split[4]:+4d} | 마지막 W차 {rows[-1][1]:+4d}")
    else:
        print(f"{name:<22}{res} 갈림 없음 | 마지막 학관턴차 {rows[-1][2]:+4d} 공학관턴차 {rows[-1][3]:+4d} W차 {rows[-1][1]:+4d}")
    if detail:
        for x in rows:
            if x[0] % 5 == 0 or (split and x[0] == split[0]):
                print(f"   {x[0]:3d} W차 {x[1]:+4d} 학관 {x[5]}:{x[6]} 공학관 {int(x[7])}:{int(x[8])} 학관턴차 {x[2]:+4d} 공학관턴차 {x[3]:+4d}")
    return res, split, rows


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    files = []
    for p in args:
        files += sorted(glob.glob(os.path.join(p, "vs*.json"))) if os.path.isdir(p) else [p]
    for f in files:
        run(f, "--detail" in sys.argv)


if __name__ == "__main__":
    main()
