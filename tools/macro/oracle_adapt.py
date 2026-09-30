"""상대 스타일 적응의 상한: 시드 A 에서 상대별 최선 변형(기본 포함)을 고르고, 시드 B 에서 그 선택의 이득을 잰다.
입력: out/macro/eco20/v<i>_<A>.txt, v<i>_<B>.txt (paired.py 전체 출력).
"""
import glob
import re
import sys
from collections import defaultdict

d = sys.argv[1] if len(sys.argv) > 1 else "out/macro/eco20"
A, B = "164000-164149", "165000-165149"
name, per = {}, defaultdict(dict)       # per[(i, set)][opp] = diff
tot = {}
for f in glob.glob(f"{d}/v*_*.txt"):
    m = re.search(r"v(\d+)_(.+)\.txt", f)
    i, s = int(m.group(1)), m.group(2)
    lines = open(f, encoding="utf-8").read().splitlines()
    if len(lines) < 3:
        continue
    name[i] = lines[0].split(" ")[1]
    tot[(i, s)] = re.search(r"차 ([+-][\d.]+) ± ([\d.]+)", lines[1]).groups()
    for ln in lines[2:]:
        mm = re.match(r"\s+(\S+)\s+A [\d.]+\s+B [\d.]+\s+([+-][\d.]+)", ln)
        if mm:
            per[(i, s)][mm.group(1)] = float(mm.group(2))
vs = sorted(name)
print("변형별 전체(시드 A / 시드 B):")
for i in vs:
    print(f"  v{i} {name[i]:45s} A {tot.get((i, A), ('?', '?'))[0]}±{tot.get((i, A), ('?', '?'))[1]}  B {tot.get((i, B), ('?', '?'))[0]}±{tot.get((i, B), ('?', '?'))[1]}")
opps = sorted(set().union(*[per[(i, A)].keys() for i in vs if (i, A) in per]))
ok = [i for i in vs if (i, A) in per and (i, B) in per]
if not ok:
    sys.exit()
choice, gainA, gainB = {}, [], []
for o in opps:
    cand = [(0.0, 0)] + [(per[(i, A)].get(o, 0.0), i) for i in ok]
    bestA, bi = max(cand)
    choice[o] = bi
    gainA.append(bestA)
    gainB.append(0.0 if bi == 0 else per[(bi, B)].get(o, 0.0))
n = len(opps)
print(f"\n상대 {n}종. 상대별 최선 선택(완벽한 상대 식별 가정)")
print(f"  시드 A 에서 고른 이득(과대평가) {sum(gainA) / n:+.4f}  →  새 시드 B 에서 {sum(gainB) / n:+.4f}")
best1 = max(ok, key=lambda i: sum(per[(i, A)].get(o, 0) for o in opps))
print(f"  단일 최선 변형 v{best1}: A {sum(per[(best1, A)].get(o, 0) for o in opps) / n:+.4f} → B {sum(per[(best1, B)].get(o, 0) for o in opps) / n:+.4f}")
flip = sum(1 for o in opps if choice[o] and per[(choice[o], B)].get(o, 0) < 0)
print(f"  A 에서 고른 변형이 B 에서 손해로 뒤집힌 상대 {flip}/{sum(1 for o in opps if choice[o])}")
for o in opps:
    c = choice[o]
    print(f"   {o:24s} 선택 v{c}  A {0.0 if c == 0 else per[(c, A)].get(o, 0):+.3f}  B {0.0 if c == 0 else per[(c, B)].get(o, 0):+.3f}")
