"""리더보드 변환 리플레이: 경기별 우리 지출(W·F·점령)·상대 W 생산(W 상쇄가 대칭이라 정확)·W 사망.
사용: python3 tools/lb_spend.py out/replays/leaderboard/V22_1001_8am [--until 80]
"""
import glob, json, os, sys

until = int(sys.argv[sys.argv.index("--until") + 1]) if "--until" in sys.argv else 999


def cnt(st, t, k):
    return sum(u[4] for u in st["units"] if u[0] == t and u[1] == k)


def run(path):
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    B = {b["id"]: b for b in r["map"]["buildings"]}
    pos = {(b["x"], b["y"]): b for b in r["map"]["buildings"]}
    T = r["turns"]
    S = dict(wsp=0, fsp=0, ssp=0, wcost=0, cap=0, wdie=0, fdie=0, opw=0, opfdie=0, mycapn=0, opcapn=0, myneu=0, opneu=0)
    for k in range(1, len(T)):
        if T[k]["turn"] > until:
            break
        a, b = T[k - 1]["state"], T[k]["state"]
        sp = {"W": 0, "F": 0, "S": 0}
        for line in T[k]["commands"].get(me, []):
            p = line.split()
            if p and p[0] == "SPAWN" and p[1] in sp:
                sp[p[1]] += int(p[2])
        eng = any(x["owner"] == me and B[x["id"]]["type"] == "ENG" for x in a["buildings"])
        lib = any(x["owner"] == me and B[x["id"]]["type"] == "LIBRARY" for x in a["buildings"])
        # 실제 생산된 수(자원 부족 시 줄어듦)는 유닛 수 변화로 확인: 사망 = 직전 + 생산 − 현재 ≥ 0
        wd = cnt(a, me, "W") + sp["W"] - cnt(b, me, "W")
        fd = cnt(a, me, "F") + sp["F"] - cnt(b, me, "F")
        S["wsp"] += sp["W"]; S["fsp"] += sp["F"]; S["ssp"] += sp["S"]
        S["wcost"] += sp["W"] * (2 if eng else 3)
        S["wdie"] += max(0, wd); S["fdie"] += max(0, fd)
        S["opw"] += cnt(b, op, "W") - cnt(a, op, "W") + max(0, wd)
        for e in T[k]["events"]:
            ty = e.get("type")
            bb = pos.get((e.get("x"), e.get("y")))
            if ty in ("capture", "neutralize") and bb:
                c = max(1, 2 * (2 if bb["type"] == "PLAZA" else 1) - (1 if lib else 0))
                if e.get("team") == me:
                    S["cap"] += c
                    S["mycapn" if ty == "capture" else "myneu"] += 1
                else:
                    S["opcapn" if ty == "capture" else "opneu"] += 1
    return me, S, r["result"], len(T)


def main():
    p = sys.argv[1]
    files = sorted(glob.glob(os.path.join(p, "vs*.json"))) if os.path.isdir(p) else [p]
    print(f"{'상대':<22}결과  턴 | 우리W생산 상대W생산 차 | 우리F생산(사망) | 점령비 점령/중립화 우리·상대")
    for f in files:
        me, S, res, n = run(f)
        w = "승" if res.get("winner") == me else "패"
        print(f"{os.path.basename(f)[2:-5]:<22}{w}  {n:3d} | {S['wsp']:5d} {S['opw']:6d} {S['wsp'] - S['opw']:+5d} | {S['fsp']:3d}({S['fdie']:3d}) | {S['cap']:4d} "
              f"{S['mycapn']}/{S['myneu']} · {S['opcapn']}/{S['opneu']}")


if __name__ == "__main__":
    main()
