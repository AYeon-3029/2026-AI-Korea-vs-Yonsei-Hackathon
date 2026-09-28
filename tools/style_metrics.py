"""경기 한 판에서 한 진영의 운영 스타일 지표를 뽑는다. 실제 서버 리플레이와 로컬 리플레이를 같은 기준으로 잰다.

지표(상대 모방 변형을 실제 상대에 맞추는 데 쓴다)
  W40·W80·W120·W150 : 그 턴의 전투병 수          F_mid : 20~100턴 평균 깃발병 수
  F_end : 145~160턴 평균 깃발병 수                  b10·b20·b40·b80 : 보유 건물 수
  fwd   : 20~120턴 전투병 중 상대 본진 쪽 칸 비율   eng·hall : 20~120턴 평균 공학관·학생회관 보유 수
  res   : 20~160턴 평균 잔액

사용 (WSL, 프로젝트 루트):
  python3 tools/style_metrics.py real 'Real Match Replay/V10_0928_8pm/replay (6).json' ...   # 상대 진영
  python3 tools/style_metrics.py local out/replays/xxx/seed1-AK.json ...                      # B 진영(상대 봇)
"""
import json
import sys
from collections import deque

KEYS = ["W40", "W80", "W120", "W150", "F_mid", "F_end", "b10", "b20", "b40", "b80", "fwd", "eng", "hall", "res"]


def bfs(terr, src):
    H, W = len(terr), len(terr[0]); d = {src: 0}; q = deque([src])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if 0 <= n[0] < W and 0 <= n[1] < H and terr[n[1]][n[0]] != "#" and n not in d:
                d[n] = d[(x, y)] + 1; q.append(n)
    return d


def metrics(frames, terr, btype, side):
    """frames: 턴 순서 [(turn, units[[team,kind,x,y,n]], owners{id: owner}, resources{side: r})]."""
    op = "Y" if side == "K" else "K"
    hs = [(x, y) for y, row in enumerate(terr) for x, ch in enumerate(row) if ch == "H"]
    first = next(((u[2], u[3]) for _, us, _, _ in frames for u in us if u[0] == side), hs[0])
    mine = min(hs, key=lambda h: abs(h[0] - first[0]) + abs(h[1] - first[1]))
    theirs = [h for h in hs if h != mine][0]
    dm, do = bfs(terr, mine), bfs(terr, theirs)
    at = {t: (us, ow, rs) for t, us, ow, rs in frames}
    last = max(at)

    def get(t):
        return at.get(t) or at[min(at, key=lambda k: abs(k - t))]

    def cnt(us, kind):
        return sum(u[4] for u in us if u[0] == side and u[1] == kind)

    def rng(a, b):
        return [at[t] for t in range(a, min(b, last) + 1) if t in at] or [get(last)]

    def blds(ow, kind=None):
        return sum(1 for i, o in ow.items() if o == side and (kind is None or btype[i] == kind))

    mid = rng(20, 120)
    tot = fw = 0
    for us, _, _ in mid:
        for u in us:
            if u[0] == side and u[1] == "W":
                tot += u[4]
                c = (u[2], u[3])
                if do.get(c, 99) < dm.get(c, 99):
                    fw += u[4]
    out = {f"W{t}": cnt(get(t)[0], "W") for t in (40, 80, 120, 150)}
    out["F_mid"] = sum(cnt(us, "F") for us, _, _ in rng(20, 100)) / len(rng(20, 100))
    end = rng(145, 160)
    out["F_end"] = sum(cnt(us, "F") for us, _, _ in end) / len(end)
    for t in (10, 20, 40, 80):
        out[f"b{t}"] = blds(get(t)[1])
    out["fwd"] = fw / max(1, tot)
    out["eng"] = sum(blds(ow, "ENG") for _, ow, _ in mid) / len(mid)
    out["hall"] = sum(blds(ow, "HALL") for _, ow, _ in mid) / len(mid)
    rr = rng(20, 160)
    out["res"] = sum(rs[side] for _, _, rs in rr) / len(rr)
    return out


def from_real(path):
    r = json.load(open(path))
    side = "Y" if r["side"] == "K" else "K"          # 상대 진영
    T = [t["observation"] for t in r["turns"] if t["turnIndex"] > 0]
    btype = {b["id"]: b["type"] for b in T[0]["buildings"]}
    frames = [(o["turn"], o["units"], {b["id"]: b["owner"] for b in o["buildings"]}, o["resources"]) for o in T]
    return metrics(frames, T[0]["map"], btype, side)


def from_local(path, side=None):
    r = json.load(open(path))
    if side is None:                                # 파일 이름 seedN-A{side}: A 진영의 반대 = B 진영
        a = path.rsplit("-A", 1)[1][0]
        side = "Y" if a == "K" else "K"
    m = r["map"]
    btype = {b["id"]: b["type"] for b in m["buildings"]}
    frames = [(t["turn"], t["state"]["units"], {b["id"]: b["owner"] for b in t["state"]["buildings"]},
               t["state"]["resources"]) for t in r["turns"]]
    return metrics(frames, m["terrain"], btype, side)


def mean(rows):
    return {k: sum(r[k] for r in rows) / len(rows) for k in KEYS}


def fmt(d):
    return " ".join(f"{k}={d[k]:.2f}" if isinstance(d[k], float) and d[k] < 5 else f"{k}={d[k]:.0f}" for k in KEYS)


if __name__ == "__main__":
    kind, paths = sys.argv[1], sys.argv[2:]
    rows = [(from_real if kind == "real" else from_local)(p) for p in paths]
    for p, r in zip(paths, rows):
        print(f"{p.split('/')[-2][:12]:<12} {p.split('/')[-1]:<18} {fmt(r)}")
    print("평균" + " " * 27, fmt(mean(rows)))
