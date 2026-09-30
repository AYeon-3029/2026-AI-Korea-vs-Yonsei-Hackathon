"""지휘관 명령을 여러 경기에 한꺼번에 기록한다(llm_batch.py step 과 함께 사용).

사용 (WSL): python3 tools/macro/llm_put.py <명령파일.json>
명령파일 = {"v170001": {"focus": [[9,4]], "defend": [], "posture": "balanced", "max_f": 5, "note": "..."}, "v170002": "=", ...}
  "=" 는 직전 명령을 그대로 반복한다. 각 경기의 다음 결정 턴(아직 cmd_<턴>.json 이 없는 가장 이른 10의 배수)에 기록한다.
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import llm_match as L  # noqa: E402


def main():
    cmds = json.load(open(sys.argv[1], encoding="utf-8"))
    for game, c in cmds.items():
        d = L.gdir(game)
        if os.path.exists(os.path.join(d, "result.json")):
            continue
        prev = sorted(glob.glob(os.path.join(d, "cmd_*.json")))
        t = int(os.path.basename(prev[-1])[4:7]) + L.EVERY if prev else 0
        if c == "=":
            c = json.load(open(prev[-1], encoding="utf-8"))
        json.dump(c, open(os.path.join(d, f"cmd_{t:03d}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"명령 {len(cmds)}개 기록")


if __name__ == "__main__":
    main()
