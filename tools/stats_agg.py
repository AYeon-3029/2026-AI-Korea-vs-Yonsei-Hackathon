"""BOT_STATS 로 남긴 경기별 지표(<폴더>/<pid>.json)를 평균낸다 (PLAN-frontier 단계 0).

사용: python3 tools/stats_agg.py out/stats/run1/v5s [다른 폴더 ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

KEYS = ["my_pts", "opp_pts_known", "n_bld", "F", "W", "f_lost", "gained", "lost", "last20", "react"]


def summarize(folder: Path) -> str:
    rows = [json.loads(p.read_text()) for p in folder.glob("*.json")]
    if not rows:
        return f"{folder.name}: 기록 없음"
    cells = []
    for k in KEYS:
        vals = [r[k] for r in rows if r.get(k) is not None]
        cells.append(f"{k} {sum(vals) / len(vals):.2f}" if vals else f"{k} -")
    early = sum(1 for r in rows if r["turn"] < 160)
    return f"{folder.name:<8} n={len(rows):<4} 조기종료 {early:<3} " + "  ".join(cells)


def main() -> None:
    for arg in sys.argv[1:]:
        print(summarize(Path(arg)))


if __name__ == "__main__":
    main()
