"""맵(시드)별 패배 수와 맵 특징의 관계(대칭 맵이라 진 경기가 같은 시드 Y·K 짝으로 나온다).
입력: out/macro/v_eval_<ver>.json (v_eval.py). 특징은 mapgen 으로 만든 지도에서 Y 쪽 기준으로 잰다.
"""
import json, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from sim import CFG  # noqa: E402
from mapgen import generate, to_state  # noqa: E402

ver = sys.argv[1] if len(sys.argv) > 1 else "v21"
ev = json.load(open(f"out/macro/v_eval_{ver}.json", encoding="utf-8"))
loss = defaultdict(int)
for o, r in ev.items():
    if o.startswith(("mc16", "m16", "p_", "semi", "srv", "x_", "b72", "v9", "v10")):
        for s, side, why in r["loss"]:
            loss[s] += 1
seeds = range(181000, 181050)


def feats(seed):
    st = to_state(generate(seed, CFG))
    by, bk = st.bases["Y"], st.bases["K"]
    d = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
    B = list(st.buildings.values())
    mine = [b for b in B if d((b.x, b.y), by) < d((b.x, b.y), bk)]
    f = {"본진거리": d(by, bk)}
    for t in ("HALL", "ENG", "HOSPITAL", "STATION", "LIBRARY", "DEPOT", "PLAZA"):
        ds = [d((b.x, b.y), by) for b in B if b.btype == t and b in mine] or [d((b.x, b.y), by) for b in B if b.btype == t]
        f[f"{t}거리"] = min(ds)
    f["우리쪽 점수합"] = sum(b.score for b in mine)
    f["우리쪽 건물수"] = len(mine)
    f["중앙건물수"] = sum(1 for b in B if d((b.x, b.y), by) == d((b.x, b.y), bk))
    eco = [b for b in mine if b.btype in ("HALL", "ENG")]
    f["학공 본진거리 최대"] = max(d((b.x, b.y), by) for b in eco) if eco else 0
    f["학공 적본진거리 최소"] = min(d((b.x, b.y), bk) for b in eco) if eco else 0
    f["벽 수"] = sum(1 for x in range(15) for y in range(15) if not st.passable(x, y)) if hasattr(st, "passable") else 0
    return f


rows = [(s, loss.get(s, 0), feats(s)) for s in seeds]
hard = [r for r in rows if r[1] >= 4]
easy = [r for r in rows if r[1] == 0]
print(f"시드 50개: 패배 합 {sum(r[1] for r in rows)}, 4패 이상 {len(hard)}개, 무패 {len(easy)}개")
print("패배 많은 시드:", " ".join(f"{s}({n})" for s, n, _ in sorted(rows, key=lambda r: -r[1])[:12]))
keys = list(rows[0][2])
print(f"{'특징':16s} {'어려운 맵':>8s} {'쉬운 맵':>8s}  상관(패배 수)")
import statistics as S
for k in keys:
    xs = [r[2][k] for r in rows]; ys = [r[1] for r in rows]
    if len(set(xs)) < 2:
        continue
    c = S.correlation(xs, ys)
    print(f"{k:16s} {S.mean(r[2][k] for r in hard):8.2f} {S.mean(r[2][k] for r in easy):8.2f}  {c:+.2f}")
