"""리더보드 변환 리플레이의 특정 턴 맵을 글자로: 칸마다 '건물/본진 + 우리 W/F · 상대 W/F'.
표기: 건물 = 종류 한 글자(대문자 우리 소유·소문자 상대 소유·* 중립), 유닛 = W수 숫자(우리 +, 상대 -), F 는 f 표시.
사용: python3 tools/lb_map.py <파일> <턴…>
"""
import json, sys
SH = {"HALL": "H", "ENG": "E", "LIBRARY": "L", "PLAZA": "P", "STATION": "S", "HOSPITAL": "O", "WATCH": "W", "DEPOT": "D"}
path = sys.argv[1]
r = json.load(open(path, encoding="utf-8"))
me = r["result"]["our_side"]; op = "K" if me == "Y" else "Y"
B = {b["id"]: b for b in r["map"]["buildings"]}
terr = r["map"]["terrain"]
for tt in map(int, sys.argv[2:]):
    t = next(x for x in r["turns"] if x["turn"] == tt)
    st = t["state"]
    own = {(B[x["id"]]["x"], B[x["id"]]["y"]): (B[x["id"]]["type"], x["owner"]) for x in st["buildings"]}
    U = {}
    for u in st["units"]:
        U.setdefault((u[2], u[3]), {}).setdefault((u[0], u[1]), 0)
        U[(u[2], u[3])][(u[0], u[1])] += u[4]
    print(f"=== 턴 {tt}  우리={me}(+) 상대={op}(-)  우리 W {sum(u[4] for u in st['units'] if u[0] == me and u[1] == 'W')} 상대 W {sum(u[4] for u in st['units'] if u[0] == op and u[1] == 'W')}")
    print("     " + "".join(f"{x:>7d}" for x in range(15)))
    for y in range(15):
        row = []
        for x in range(15):
            c = terr[y][x]
            g = "#" if c == "#" else ("B" if c == "H" else ".")
            if (x, y) in own:
                ty, ow = own[(x, y)]
                g = SH[ty] if ow == me else SH[ty].lower() if ow == op else "*"
            u = U.get((x, y), {})
            w = u.get((me, "W"), 0) - u.get((op, "W"), 0)
            f = ("f" if u.get((me, "F")) else "") + ("g" if u.get((op, "F")) else "")
            cell = g + (f"{w:+d}" if (u.get((me, 'W')) or u.get((op, 'W'))) else "") + f
            if u.get((me, "W")) and u.get((op, "W")):
                cell = g + f"{u[(me, 'W')]}/{-u[(op, 'W')]}" + f
            row.append(f"{cell:>7s}")
        print(f"{y:>4d} " + "".join(row))
