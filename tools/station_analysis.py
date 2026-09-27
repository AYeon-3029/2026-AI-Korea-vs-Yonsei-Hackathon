"""시드별 역(STATION) 효용 분석.

역 2개(a, b)를 보유하면 a → b 순간이동이 한 턴(=한 칸 이동과 같은 비용)이다.
Y 본진에서 각 건물까지 가는 거리가 역 경로로 얼마나 줄어드는지 계산한다.
  절약 = d(본진, t) − (d(본진, a) + 1 + d(b, t))   (양수일 때만)
"""
import sys
from collections import deque
from itertools import permutations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "BaseLines/yk-development-tools"))
from engine.config import load_config  # noqa: E402
from mapgen import generate  # noqa: E402


def bfs(terrain, s):
    h, w = len(terrain), len(terrain[0])
    d = {s: 0}
    q = deque([s])
    while q:
        x, y = q.popleft()
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            n = (x + dx, y + dy)
            if 0 <= n[0] < w and 0 <= n[1] < h and terrain[n[1]][n[0]] != "#" and n not in d:
                d[n] = d[(x, y)] + 1
                q.append(n)
    return d


def main(seeds):
    cfg = load_config()
    for seed in seeds:
        g = generate(seed, cfg)
        base = g.bases["Y"]
        D = {}

        def dist(a, b):
            if a not in D:
                D[a] = bfs(g.terrain, a)
            return D[a][b]

        sts = [(b.x, b.y) for b in g.buildings if b.btype == "STATION"]
        targets = [(b.x, b.y) for b in g.buildings if b.btype != "STATION"]
        label = {}
        for s in sts:
            label[s] = "신촌역" if s[0] <= 4 else "안암역" if s[0] >= 10 else "서울역"
        rows = []
        for a, b in permutations(sts, 2):
            saves = [dist(base, t) - (dist(base, a) + 1 + dist(b, t)) for t in targets]
            good = [s for s in saves if s > 0]
            rows.append((sum(good), len(good), max(saves), a, b))
        rows.sort(reverse=True)
        print(f"seed {seed}: Y본진 {base}  역 " + ", ".join(f"{label[s]}{s} 본진거리 {dist(base, s)}" for s in sts))
        for tot, n, mx, a, b in rows[:3]:
            print(f"   {label[a]}{a} → {label[b]}{b}: 단축 건물 {n}개, 합계 {tot}칸, 최대 {mx}칸")


if __name__ == "__main__":
    main([int(s) for s in sys.argv[1:]] or range(10))
