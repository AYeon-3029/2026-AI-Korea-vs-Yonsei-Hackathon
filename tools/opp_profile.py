"""실제 서버 경기 리플레이(Real Match Replay/*/*.json)에서 상대 팀의 행동 지표를 뽑는다.

지표: 20~100턴 평균 F·W, 최대 F·S, 10/20/40턴 보유 건물 수, 상대 W 중 우리 본진에 더 가까운 칸에 있는 비율(공격성),
우리 본진 4칸 안 비율(깊은 침투), 자원 38 이상 턴 비율(저축), 처음 점령한 건물 6개의 종류.

사용 (WSL, 프로젝트 루트): python3 tools/opp_profile.py
"""
import json, glob
from collections import deque
ab = {"PLAZA":"광장","HALL":"학관","LIBRARY":"도서","ENG":"공학","HOSPITAL":"병원","STATION":"역","WATCH":"방송","DEPOT":"보급"}
def bfs(terrain, src):
    H, W = len(terrain), len(terrain[0]); d = {src: 0}; q = deque([src])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            n = (x+dx, y+dy)
            if 0 <= n[0] < W and 0 <= n[1] < H and terrain[n[1]][n[0]] != "#" and n not in d:
                d[n] = d[(x, y)] + 1; q.append(n)
    return d
rows = []
for f in sorted(glob.glob("Real Match Replay/*/*.json")):
    r = json.load(open(f)); me = r["side"]; op = "Y" if me == "K" else "K"
    T = [t["observation"] for t in r["turns"] if t["turnIndex"] > 0]
    terr = T[0]["map"]
    hs = [(x, y) for y, row in enumerate(terr) for x, ch in enumerate(row) if ch == "H"]
    # 우리 본진 = 1턴 우리 유닛이 생긴 쪽
    first_me = next(((u[2], u[3]) for o in T for u in o["units"] if u[0] == me), hs[0])
    mb = min(hs, key=lambda h: abs(h[0]-first_me[0]) + abs(h[1]-first_me[1])); ob = [h for h in hs if h != mb][0]
    dm, do = bfs(terr, mb), bfs(terr, ob)
    def at(n): return next((o for o in T if o["turn"] == n), T[-1])
    def cnt(o, s, k): return sum(u[4] for u in o["units"] if u[0] == s and u[1] == k)
    mid = [o for o in T if 20 <= o["turn"] <= 100] or T
    eF = [cnt(o, op, "F") for o in mid]; eW = [cnt(o, op, "W") for o in mid]
    maxS = max(cnt(o, op, "S") for o in T)
    # 공격성: 적 W 중 우리 본진에 더 가까운 칸에 있는 비율, 우리 본진 4칸 안 비율
    tot = ours = deep = 0
    for o in mid:
        for u in o["units"]:
            if u[0] == op and u[1] == "W":
                c = (u[2], u[3]); tot += u[4]
                if dm.get(c, 99) < do.get(c, 99): ours += u[4]
                if dm.get(c, 99) <= 4: deep += u[4]
    # 점령 순서
    order, prev = [], {b["id"]: "N" for b in T[0]["buildings"]}
    for o in T:
        for b in o["buildings"]:
            if b["owner"] == op and prev[b["id"]] != op and len(order) < 6:
                order.append(ab[b["type"]])
            prev[b["id"]] = b["owner"]
    capr = sum(1 for o in T if o["resources"][op] >= 38) / len(T)
    blds = lambda n: sum(1 for b in at(n)["buildings"] if b["owner"] == op)
    res = "승" if r["result"]["winner"] == me else "패"
    rows.append(dict(game=f.split("Replay/")[1][:24], res=res, turns=T[-1]["turn"],
        F=round(sum(eF)/len(eF),1), Fmax=max(cnt(o, op, "F") for o in T), W=round(sum(eW)/len(eW)), S=maxS,
        b10=blds(10), b20=blds(20), b40=blds(40), agg=ours/max(1,tot), deep=deep/max(1,tot), cap=capr, order=" ".join(order)))
print(f"{'경기':<26}{'결과':<3}{'턴':>4} {'평균F':>5}{'최대F':>5}{'평균W':>6}{'S':>3} {'건10':>4}{'건20':>4}{'건40':>4} {'우리쪽W':>7}{'본진4칸':>7}{'상한':>5}  점령 순서")
for x in rows:
    print(f"{x['game']:<26}{x['res']:<3}{x['turns']:>4} {x['F']:>5}{x['Fmax']:>5}{x['W']:>6}{x['S']:>3} {x['b10']:>4}{x['b20']:>4}{x['b40']:>4} {x['agg']:>7.0%}{x['deep']:>7.0%}{x['cap']:>5.0%}  {x['order']}")
