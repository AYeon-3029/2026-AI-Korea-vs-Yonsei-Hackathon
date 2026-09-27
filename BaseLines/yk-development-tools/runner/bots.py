"""봇 드라이버.

같은 텍스트 프로토콜을 소비하는 두 종류:
- SubprocessBot: 실제 자식 프로세스(러너 CLI 용). 턴 타임아웃/크래시 처리.
- InProcessBot: decide 함수를 직접 호출(테스트/골든 리플레이 용, 타이밍 무관).

play_turn 반환: (출력 라인 리스트, status). 오류는 매치 러너가 기본적으로 몰수 처리한다.
시간 측정은 I/O 계층에만 있으며 결정적인 엔진 상태·리플레이에는 저장하지 않는다.
"""
from __future__ import annotations

import os
import queue
import selectors
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

# 스타터 킷(campus_bot) 을 공유 파서로 재사용
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "bots", "dist", "starter", "python"),
)
import campus_bot as cb  # noqa: E402

_EOF = object()
# 정상 응답 후 전송 스레드 정리의 운영상 상한. 봇의 응답 예산을 늘리지 않는다.
_IO_SETTLE_TIMEOUT_S = 1.0


class RunnerIOError(RuntimeError):
    """러너의 입력 전송/selector/출력 읽기 실패. 봇 몰수로 변환하지 않는다."""


@dataclass(frozen=True)
class _ReadFailure:
    error: Exception


class InProcessBot:
    """decide(view, init) 를 직접 호출. 타임아웃/크래시 없음."""

    def __init__(self, decide, name: str = "inproc"):
        self.decide = decide
        self.name = name
        self.dead = False
        self._init: Optional[cb.Init] = None

    def send_init(self, text: str) -> None:
        self._init = cb.parse_init(_block_lines(text))

    def send_turn(self, text: str, timeout_s: float) -> None:
        self._pending = text

    def collect_turn(self) -> Tuple[Optional[List[str]], str]:
        view = cb.parse_turn(_block_lines(self._pending), self._init)
        return list(self.decide(view, self._init)), "ok"

    def play_turn(self, text: str, timeout_s: float) -> Tuple[Optional[List[str]], str]:
        self.send_turn(text, timeout_s)
        return self.collect_turn()

    def close(self) -> None:
        pass


class SubprocessBot:
    """셸 커맨드로 실행되는 실제 봇 프로세스."""

    def __init__(self, cmd: str, name: str = "bot", *, capture_stderr: bool = False):
        self.name = name
        self.dead = False
        self.max_turn_ms = 0.0        # 이 봇의 턴당 최대 소요 시간(ms) — 스모크 테스트용
        self.proc = None
        self._q: "queue.Queue" = queue.Queue()
        self._start = 0.0        # 이번 턴 시간 측정 시작 시각
        self._deadline = 0.0     # 이번 턴 응답 마감 시각(monotonic)
        self._init_text = ""
        self._write_done = threading.Event()
        self._cancel_write = threading.Event()
        self._write_result = ("timeout", None)
        self._writer = None
        self._reader = None
        self._first_turn = True
        # 자식 프로세스 기동 전부터 첫 응답까지 측정한다.
        self._process_start = time.monotonic()
        try:
            self.proc = subprocess.Popen(
                cmd, shell=True,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE if capture_stderr else subprocess.DEVNULL,
                text=True, bufsize=1,
            )
            # stdin은 OS 수준 비차단 쓰기만 사용한다.
            os.set_blocking(self.proc.stdin.fileno(), False)
            self._reader = threading.Thread(target=self._read_loop, daemon=True)
            self._reader.start()
        except BaseException:
            # 호출자가 객체를 받기 전에 실패해도 생성된 프로세스를 회수한다.
            self.close()
            raise

    def _read_loop(self) -> None:
        terminal = _EOF
        stream = self.proc.stdout
        try:
            for line in stream:
                self._q.put((time.monotonic(), line.rstrip("\n")))
        except Exception as exc:
            terminal = _ReadFailure(exc)
        finally:
            self._q.put((time.monotonic(), terminal))
            # reader 자신이 닫으면 메인 스레드와 TextIO 잠금을 다투지 않는다.
            try:
                stream.close()
            except Exception:
                pass

    def send_init(self, text: str) -> None:
        """INIT을 보관하고 첫 send_turn에서 같은 제한 시간 내에 전송한다."""
        self._init_text += text

    def _write(self, text: str) -> None:
        """비차단 stdin 부분 쓰기. 제한 시간 또는 close 시 종료한다."""
        status, error = "timeout", None
        try:
            data = memoryview(text.encode(self.proc.stdin.encoding or "utf-8"))
            fd = self.proc.stdin.fileno()
            with selectors.DefaultSelector() as selector:
                selector.register(fd, selectors.EVENT_WRITE)
                while data and not self._cancel_write.is_set():
                    remaining = self._deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    if not selector.select(min(remaining, 0.05)):
                        continue
                    # 준비 이벤트를 기다리는 동안 마감/취소가 발생할 수 있다.
                    # 완료 통지가 늦어진 성공 쓰기와 달리, 지금 새 쓰기를 시작하면 안 된다.
                    if self._cancel_write.is_set() or time.monotonic() >= self._deadline:
                        break
                    try:
                        count = os.write(fd, data[:65536])
                    except BlockingIOError:
                        continue
                    data = data[count:]
                if not data:
                    status = "ok"
        except BrokenPipeError:
            status = "closed"
        except Exception as exc:
            status, error = "runner_error", exc
        finally:
            # 완료 통지 시각은 스케줄링 지연을 포함하므로 마감 판정에 사용하지 않는다.
            self._write_result = (status, error)
            self._write_done.set()

    def _write_failure(self) -> Optional[str]:
        if not self._write_done.is_set():
            return None
        status, error = self._write_result
        if status == "runner_error":
            raise RunnerIOError(f"{self.name}: input transport failed: {error}") from error
        if status == "closed":
            return self._exit_cause()
        return None if status == "ok" else "timeout"

    def _exit_cause(self) -> str:
        """프로세스 종료/스트림 종료 사유: 종료코드 0 = invalid_output(END 누락), 그 외 = crash."""
        try:
            self.proc.wait(timeout=0.3)
        except Exception:
            pass
        rc = self.proc.returncode
        return "invalid_output" if rc == 0 else "crash"

    def send_turn(self, text: str, timeout_s: float) -> None:
        """일반 턴은 입력 전송 시작부터 END 수신까지 하나의 시간 예산으로 측정한다.

        첫 턴에는 프로세스 기동부터 INIT 전송·초기화까지 포함한다. 쓰기는 별도 스레드에서 수행해 상대 전송을 막지 않는다.
        드라이버는 send_turn → collect_turn을 한 번씩 호출해야 한다.
        """
        self._start = self._process_start if self._first_turn else time.monotonic()
        self._first_turn = False
        self._deadline = self._start + timeout_s
        self._write_done.clear()
        payload = self._init_text + text
        self._init_text = ""
        self._writer = threading.Thread(target=self._write, args=(payload,), daemon=True)
        self._writer.start()

    def collect_turn(self) -> Tuple[Optional[List[str]], str]:
        """입력 전송 완료 및 각 줄 수신 시각으로 제한 시간을 판정한다."""
        lines: List[str] = []
        while True:
            # 마감 후 수집해도 기존 큐를 읽는다. 다만 늦게 도착한 줄은 거부한다.
            try:
                received_at, item = self._q.get(
                    timeout=max(0.0, self._deadline - time.monotonic())
                )
            except queue.Empty:
                self._cancel_write.set()
                return None, self._write_failure() or "timeout"
            if isinstance(item, _ReadFailure) and not isinstance(item.error, UnicodeDecodeError):
                self._cancel_write.set()
                raise RunnerIOError(f"{self.name}: output read failed: {item.error}") from item.error
            if received_at > self._deadline:
                self._cancel_write.set()
                return None, self._write_failure() or "timeout"
            if isinstance(item, _ReadFailure):
                self._cancel_write.set()
                return None, self._write_failure() or "invalid_output"
            if item is _EOF:
                return None, self._write_failure() or self._exit_cause()
            if item == "END":
                # 유효 응답을 받았을 때만 전송 종료를 확인한다. 비차단 writer는 자체
                # deadline에서 멈춘다. 완료 통지가 늦어도 이미 수신한 END는 유효하며,
                # 입력이 일부만 전달됐거나 내부 I/O 오류가 있으면 성공시키지 않는다.
                settle_budget = max(0.0, self._deadline - time.monotonic()) + _IO_SETTLE_TIMEOUT_S
                if not self._write_done.wait(settle_budget):
                    self._cancel_write.set()
                    raise RunnerIOError(f"{self.name}: input completion did not settle after timely END")
                failure = self._write_failure()
                if failure:
                    return None, failure
                # RULEBOOK §13: END가 있어도 이미 종료한 프로세스는 몰수 대상이다.
                # 정상 동작 중인 봇의 종료를 기다리거나 응답 예산을 늘리지 않는다.
                rc = self.proc.poll()
                if rc is not None:
                    return None, "invalid_output" if rc == 0 else "crash"
                self.max_turn_ms = max(self.max_turn_ms, (received_at - self._start) * 1000.0)
                return lines, "ok"
            lines.append(item)

    def play_turn(self, text: str, timeout_s: float) -> Tuple[Optional[List[str]], str]:
        """편의 래퍼(단일 봇 테스트용). 경기는 send_turn/collect_turn 을 쓴다."""
        self.send_turn(text, timeout_s)
        return self.collect_turn()

    def close(self) -> None:
        self._cancel_write.set()
        if self._writer is not None and self._writer.ident is not None:
            self._writer.join(timeout=0.2)
        if self.proc is None:
            return
        # 프로세스를 먼저 종료해야 reader 스레드의 stdout 읽기가 EOF 로 풀린다.
        # reader가 읽는 동안 메인 스레드에서 stdout을 닫으면 데드락이 발생한다.
        try:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    try:
                        self.proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        pass
        except Exception:
            pass
        if self._reader is not None and self._reader.ident is not None:
            self._reader.join(timeout=0.2)
        # 읽기 중인 stdout은 닫지 않는다. reader가 미시작/종료 상태일 때만 회수한다.
        if self._reader is None or not self._reader.is_alive():
            try:
                if self.proc.stdout and not self.proc.stdout.closed:
                    self.proc.stdout.close()
            except Exception:
                pass
        try:                                    # 종료 후 stdin 정리(BrokenPipe 잡음 방지)
            if self.proc.stdin and not self.proc.stdin.closed:
                self.proc.stdin.close()
        except Exception:
            pass


def _block_lines(text: str) -> List[str]:
    """블록 텍스트에서 END/빈 줄을 제외한 라인 목록."""
    return [ln for ln in text.split("\n") if ln and ln != "END"]
