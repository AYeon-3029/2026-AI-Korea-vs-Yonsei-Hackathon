"""변환된 리더보드 리플레이(out/replays/leaderboard/...)의 10턴 요약: 점수·W·F·자원·학관/공학관 수, 학관·공학관 득실.
사용: python3 tools/lb_timeline.py <변환 파일 또는 폴더> [--events]
"""
import glob, json, os, sys
SH = {"HALL": "학", "ENG": "공", "LIBRARY": "도", "PLAZA": "광", "STATION": "역", "HOSPITAL": "병", "WATCH": "방", "DEPOT": "보"}


def run(path, events):
    r = json.load(open(path, encoding="utf-8"))
    me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
    B = {b["id"]: b for b in r["map"]["buildings"]}
    base = [(x, y) for y, row in enumerate(r["map"]["terrain"]) for x, c in enumerate(row) if c == "H"]
    print(f"#### {os.path.basename(path)}  우리={me}  결과 {r['result'].get('winner')} {r['result'].get('reason')} {r['result'].get('score')}  턴 {r['result']['turns']}")
    prev = {b["id"]: "N" for b in r["map"]["buildings"]}
    for t in r["turns"]:
        st = t["state"]
        own = {b["id"]: b["owner"] for b in st["buildings"]}
        if events:
            ch = []
            for i, o in own.items():
                if o != prev[i] and B[i]["type"] in ("HALL", "ENG", "PLAZA"):
                    who = "우리" if o == me else "적" if o == op else ("우리잃음" if prev[i] == me else "적잃음")
                    ch.append(f"{SH[B[i]['type']]}{B[i]['score']}({B[i]['x']},{B[i]['y']}){who}")
            if ch:
                print(f"   {t['turn']:3d}턴 " + " ".join(ch))
        prev = own
        if t["turn"] % 10 == 0 or t is r["turns"][-1]:
            sc = {tm: sum(B[i]["score"] for i, o in own.items() if o == tm) for tm in (me, op)}
            W = {tm: sum(u[4] for u in st["units"] if u[0] == tm and u[1] == "W") for tm in (me, op)}
            F = {tm: sum(u[4] for u in st["units"] if u[0] == tm and u[1] == "F") for tm in (me, op)}
            eco = {tm: sum(1 for i, o in own.items() if o == tm and B[i]["type"] in ("HALL", "ENG")) for tm in (me, op)}
            print(f"== {t['turn']:3d}턴 점수 {sc[me]}:{sc[op]}  W {W[me]}:{W[op]}  F {F[me]}:{F[op]}  자원 {st['resources'][me]}:{st['resources'][op]}  학·공 {eco[me]}:{eco[op]}")


if __name__ == "__main__":
    p = sys.argv[1]
    ev = "--events" in sys.argv
    for f in (sorted(glob.glob(os.path.join(p, "*.json"))) if os.path.isdir(p) else [p]):
        run(f, ev)
