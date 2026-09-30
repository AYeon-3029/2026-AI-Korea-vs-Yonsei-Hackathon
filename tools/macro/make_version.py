"""개발 봇(dev) + 파라미터 json → 새 버전 스냅샷(Model/history/<ver>). P 의 각 줄 값을 바꾸고 '<ver>: 이전 → 새' 주석을 단다.

사용 (WSL): python3 tools/macro/make_version.py --src dev15 --params out/tune/s9/t258.json --ver v17 --doc "설명 줄" [--to-model]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def fmt(v):
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, float):
        return f"{v:.4g}" if abs(v) < 10 else f"{v:.5g}"
    if isinstance(v, str):
        return json.dumps(v)
    return str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--params", required=True)
    ap.add_argument("--ver", required=True)
    ap.add_argument("--doc", default="")
    ap.add_argument("--to-model", action="store_true")
    a = ap.parse_args()
    params = json.load(open(a.params))
    src = os.path.join(ROOT, "Model/history", a.src)
    dst = os.path.join(ROOT, "Model/history", a.ver)
    os.makedirs(dst, exist_ok=True)
    for f in ("campus_bot.py", "protocol.py", "_generated.py", "tactical.py"):
        shutil.copy(os.path.join(src, f), os.path.join(dst, f))
    shutil.copy(os.path.join(ROOT, "Model/submission.json"), os.path.join(dst, "submission.json"))
    lines = open(os.path.join(src, "main.py"), encoding="utf-8").read().split("\n")
    start = lines.index("P = {")
    end = start + lines[start:].index("}")
    done = set()
    for i in range(start + 1, end):
        m = re.match(r'^    "(\w+)": (.+?),(\s*#.*)?$', lines[i])
        if not m or m.group(1) not in params:
            continue
        k, old, com = m.group(1), m.group(2), m.group(3) or ""
        new = fmt(params[k])
        done.add(k)
        if new == old:
            continue
        com = (com.rstrip() + f" {a.ver}: {old} → {new}") if com else f"  # {a.ver}: {old} → {new}"
        lines[i] = f'    "{k}": {new},{com}'
    miss = set(params) - done
    assert not miss, f"P 에 없는 키: {miss}"
    s = "\n".join(lines)
    s = re.sub(r'^"""깃발 대항전 전략 봇 [\w-]+\.', f'"""깃발 대항전 전략 봇 {a.ver}.', s, count=1)
    if a.doc:
        doc_end = s.index('"""', 3)
        s = s[:doc_end] + a.doc.rstrip() + "\n" + s[doc_end:]
    open(os.path.join(dst, "main.py"), "w", encoding="utf-8").write(s)
    if a.to_model:
        open(os.path.join(ROOT, "Model/main.py"), "w", encoding="utf-8").write(s)
        for f in ("campus_bot.py", "protocol.py", "_generated.py", "tactical.py"):
            shutil.copy(os.path.join(src, f), os.path.join(ROOT, "Model", f))
    print(f"{a.ver}: {len(params)} 파라미터 적용")


if __name__ == "__main__":
    main()
