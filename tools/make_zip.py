"""Model/ 의 제출 파일만 모아 서버 제출용 ZIP을 만든다.

WSL에서 /mnt/c 파일은 실행 권한(rwxrwxrwx)으로 보이고, 그대로 압축하면 서버가
EXECUTABLE_FILE 로 거부한다. 모든 항목을 일반 파일 권한(0644)으로 기록한다.

사용: python3 tools/make_zip.py v4 [작성자]   → submissions/submission-Junghoon-v4.zip
"""
import stat
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "BaseLines/yk-development-tools/bots/dist/starter"))
from submission import inspect_zip  # noqa: E402

AUTHOR = "Junghoon"   # 파일 이름에 붙는 작성자(팀 내 구분용)
FILES = ["submission.json", "main.py", "campus_bot.py", "protocol.py", "_generated.py", "tactical.py"]


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "latest"
    author = sys.argv[2] if len(sys.argv) > 2 else AUTHOR
    out = ROOT / "submissions" / f"submission-{author}-{version}.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 27, 0, 0, 0))
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, (ROOT / "Model" / name).read_bytes())

    result = inspect_zip(out)
    bad = []
    with zipfile.ZipFile(out) as z:
        for i in z.infolist():
            mode = i.external_attr >> 16
            print(f"  {i.filename:<18}{i.file_size:>7} B  {stat.filemode(mode)}")
            if mode & 0o111:
                bad.append(i.filename)
    if bad:
        result["ok"] = False
        result["issues"].append(f"실행 권한이 남은 파일: {bad}")
    print(f"{out}\n공식 구조 검사: {'통과' if result['ok'] else '실패'} {result['issues']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
