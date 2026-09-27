"""봇의 응답·명령을 자가 점검한다. 실제 채점 서버의 자원 격리를 대신하지 않는다."""

import argparse
import json
import shlex
import sys
import tempfile
import subprocess
import threading
import time
from pathlib import Path
from _support import KIT, turn_timeout_ms, first_turn_timeout_ms
from engine.config import load_config
from runner import InProcessBot, SubprocessBot, run_match
from runner.protocol import parse_commands
from engine.commands import Spawn, Move, Move2, Tele, Priority
from engine.commands import DIRECTIONS
from runner.bots import cb



from submission import inspect_zip, extract_zip
from output_usage import OutputUsage
from runner.bots import _EOF, _ReadFailure


class CheckedBot(SubprocessBot):
    """게임에서는 무시되는 잘못된 줄도 참가자에게 진단으로 보여준다."""

    def __init__(self, command, config):
        self.usage = OutputUsage(json.loads((KIT / "limits.json").read_text()))
        self._stderr_reader = None
        super().__init__(command, name="검사 대상", capture_stderr=True)
        self._stderr_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_reader.start()
        self.config = config
        self.issues = []
        self.turn = 0

    def _read_loop(self):
        """원시 바이트를 세면서 기존 러너와 같은 응답 큐에 줄을 전달한다."""
        stream = self.proc.stdout
        terminal = _EOF
        pending = b""
        try:
            while True:
                chunk = stream.buffer.read1(4096)
                if not chunk:
                    break
                self.usage.stdout(chunk)
                pending += chunk
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    self._q.put((time.monotonic(), line.rstrip(b"\r").decode(stream.encoding or "utf-8")))
            if pending:
                self._q.put((time.monotonic(), pending.decode(stream.encoding or "utf-8")))
        except Exception as exc:
            terminal = _ReadFailure(exc)
        finally:
            self._q.put((time.monotonic(), terminal))
            stream.close()

    def _read_stderr(self):
        stream = self.proc.stderr
        try:
            while True:
                chunk = stream.buffer.read1(4096)
                if not chunk:
                    break
                self.usage.stderr(chunk)
        finally:
            stream.close()

    def close(self):
        super().close()
        reader = self._stderr_reader
        if reader is not None and reader.ident is not None:
            reader.join(timeout=0.5)

    def send_init(self, text):
        self.init = cb.parse_init(text.splitlines()[:-1])
        return super().send_init(text)

    def send_turn(self, text, timeout_s):
        self.turn += 1
        self.view = cb.parse_turn(text.splitlines()[:-1], self.init)
        return super().send_turn(text, timeout_s)

    def collect_turn(self):
        lines, status = super().collect_turn()
        if status != "ok":
            return lines, status
        for line in lines:
            parsed = parse_commands([line])
            if not parsed:
                if line.strip():
                    self.issues.append(
                        {"turn": self.turn, "line": line, "issue": "무시될 명령 형식"}
                    )
                continue
            c = parsed[0]
            coords = []
            if isinstance(c, Priority):
                coords = c.coords
            elif isinstance(c, Spawn):
                if c.x is not None:
                    coords = [(c.x, c.y)]
            else:
                coords = [(c.x, c.y)]
                if isinstance(c, Tele):
                    coords.append((c.tx, c.ty))
            if any(
                not (
                    0 <= x < self.config["grid"]["width"] and 0 <= y < self.config["grid"]["height"]
                )
                for x, y in coords
            ):
                self.issues.append({"turn": self.turn, "line": line, "issue": "맵 밖 좌표"})
                continue
            destinations = []
            if isinstance(c, Move):
                dx, dy = DIRECTIONS[c.direction]
                destinations = [(c.x + dx, c.y + dy)]
            elif isinstance(c, Move2):
                dx, dy = DIRECTIONS[c.dir1]
                mx, my = c.x + dx, c.y + dy
                dx, dy = DIRECTIONS[c.dir2]
                destinations = [(mx, my), (mx + dx, my + dy)]
            if any(not self.init.passable(x, y) for x, y in destinations):
                self.issues.append(
                    {
                        "turn": self.turn,
                        "line": line,
                        "issue": "경유지 또는 도착지가 맵 밖이거나 장애물",
                    }
                )
            if isinstance(c, Spawn) and c.x is not None:
                b = self.view.building_at(c.x, c.y)
                if b is None or b["type"] != "HOSPITAL" or b["owner"] != self.init.team:
                    self.issues.append(
                        {
                            "turn": self.turn,
                            "line": line,
                            "issue": "명시적 생산 좌표는 소유 병원이어야 함",
                        }
                    )
        return lines, status


def check(command, seed=0):
    cfg = load_config()
    cfg["first_turn_timeout_ms"] = first_turn_timeout_ms()
    bot = CheckedBot(command, cfg)
    _, result = run_match(
        seed, cfg, bot, InProcessBot(lambda view, init: []), turn_timeout_ms=turn_timeout_ms()
    )
    return {
        "ok": not bot.issues and result["reason"] != "forfeit",
        "issues": bot.issues,
        "result": result,
        "output_usage": bot.usage.snapshot(),
        "warnings": bot.usage.snapshot()["warnings"],
    }


def self_test():
    """끝 표식 누락·범위 밖 좌표·시간 초과·정상 응답을 실제 프로세스로 검출한다."""
    sys.path.insert(0, str(KIT / "python"))
    import protocol as p

    cases = {
        "정상": ("def decide(v,i): return []\np.run(decide)\n", True, None),
        "잘못된 좌표": (
            "def decide(v,i): return [p.move(-1,0,'F',1,'R')]\np.run(decide)\n",
            False,
            None,
        ),
        "끝 표식 누락": (
            "p.read_block(sys.stdin)\np.read_block(sys.stdin)\nsys.exit(0)\n",
            False,
            "invalid_output",
        ),
        "시간 초과": (
            "p.read_block(sys.stdin)\np.read_block(sys.stdin)\nwhile True: pass\n",
            False,
            "timeout",
        ),
    }
    with tempfile.TemporaryDirectory() as folder:
        for name, (body, ok, cause) in cases.items():
            path = Path(folder) / "check.py"
            path.write_text(
                f"import sys\nsys.path.insert(0, {str(KIT / 'python')!r})\nimport protocol as p\n" + body
            )
            result = check(shlex.join([sys.executable, str(path)]))
            assert result["ok"] == ok, (name, result)
            if cause:
                assert result["result"]["forfeit"]["cause"] == cause, (name, result)
            print(f"{name}: 진단 검증 통과")


def check_submission(path, seed=0, compiler="c++"):
    report = inspect_zip(path)
    if not report['ok']:
        return report
    with tempfile.TemporaryDirectory(prefix="submission-check-") as folder:
        root = Path(folder)
        language = extract_zip(path, root)
        if language == 'python':
            argv = [sys.executable, str(root / 'main.py')]
        else:
            binary = root / 'bot'
            sources = sorted(str(p) for p in root.rglob('*.cpp'))
            process = subprocess.run([compiler, '-std=c++20', '-O2', '-I', str(root), *sources, '-o', str(binary)], capture_output=True, text=True)
            if process.returncode:
                return {'ok': False, 'issues': ['C++20 컴파일 실패'], 'compiler_output': process.stderr}
            argv = [str(binary)]
        command = 'cd ' + shlex.quote(str(root)) + ' && exec ' + shlex.join(argv)
        return {**report, **check(command, seed)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', type=Path, help='제출 ZIP 구성 검사 후 실제 대전')
    parser.add_argument('--bot', help='ZIP 검사 없이 로컬 명령의 응답·출력량만 확인')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--compiler', default='c++', help='로컬 C++20 컴파일러')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.zip:
        result = check_submission(args.zip, args.seed, args.compiler)
    elif args.bot:
        result = check(args.bot, args.seed)
    else:
        parser.error('--zip 또는 --bot을 지정하세요')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
