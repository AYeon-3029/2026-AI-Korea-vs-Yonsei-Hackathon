"""Platform SDK: read the pinned limits JSON independently of document headings."""
from pathlib import Path
import json
import sys

ROOT = next((p for p in Path(__file__).resolve().parents if (p / "engine/config.py").is_file()), None)
if ROOT is None:
    raise RuntimeError("배포 묶음 전체를 푼 뒤 실행하세요. 로컬 엔진이 없습니다.")
sys.path.insert(0, str(ROOT))
KIT = Path(__file__).resolve().parent

def _limit(key):
    value = json.loads((KIT / "limits.json").read_text(encoding="utf-8"))[key]
    if type(value) is not int or not 1 <= value <= 60000:
        raise ValueError("SDK 실행 제한이 올바르지 않습니다")
    return value

def turn_timeout_ms():
    return _limit("turn_timeout_ms")

def first_turn_timeout_ms():
    return _limit("first_turn_timeout_ms")
