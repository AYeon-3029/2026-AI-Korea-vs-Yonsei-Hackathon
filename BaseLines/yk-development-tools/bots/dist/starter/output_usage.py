"""봇 출력의 실제 바이트 사용량을 계산한다. 초과는 경고하며 승패를 바꾸지 않는다."""

import threading


class OutputUsage:
    def __init__(self, limits):
        self.limits = limits
        self.lock = threading.Lock()
        self.warnings = []
        self.turns = []
        self.turn = 1
        self.turn_bytes = self.turn_lines = self.line_bytes = 0
        self.prefix = b''
        self.stdout_bytes = self.stderr_bytes = 0
        self.max_line_bytes = 0
        self.warned = set()

    def warn(self, kind, value, limit):
        key = (kind, self.turn if kind != 'stderr_game_bytes' else 0)
        if value > limit and key not in self.warned:
            self.warned.add(key)
            self.warnings.append({'turn': key[1] or None, 'kind': kind,
                                  'bytes_or_lines': value, 'limit': limit,
                                  'message': '출력 한도 초과'})

    def stdout(self, data):
        """개행도 바이트에 포함하고 END 행까지 한 응답으로 센다."""
        with self.lock:
            self.stdout_bytes += len(data)
            parts = data.split(b"\n")
            for index, part in enumerate(parts):
                self._part(part + b"\n" if index < len(parts) - 1 else part)

    def _part(self, part):
        if not part:
            return
        if self.line_bytes == 0:
            self.turn_lines += 1
        self.turn_bytes += len(part)
        self.line_bytes += len(part)
        self.prefix = (self.prefix + part)[:8]
        self.max_line_bytes = max(self.max_line_bytes, self.line_bytes)
        for kind, value in [('stdout_turn_bytes', self.turn_bytes),
                            ('stdout_turn_lines', self.turn_lines),
                            ('stdout_line_bytes', self.line_bytes)]:
            self.warn(kind, value, self.limits[kind])
        if part.endswith(b'\n'):
            end = self.line_bytes <= 5 and self.prefix.rstrip(b'\r\n') == b'END'
            self.line_bytes = 0
            self.prefix = b''
            if end:
                self.turns.append({'turn': self.turn, 'bytes': self.turn_bytes, 'lines': self.turn_lines})
                self.turn += 1
                self.turn_bytes = self.turn_lines = 0

    def stderr(self, data):
        with self.lock:
            self.stderr_bytes += len(data)
            self.warn('stderr_game_bytes', self.stderr_bytes, self.limits['stderr_game_bytes'])

    def snapshot(self):
        with self.lock:
            return {'stdout_bytes': self.stdout_bytes, 'stderr_bytes': self.stderr_bytes,
                    'max_line_bytes': self.max_line_bytes, 'turns': list(self.turns),
                    'unfinished_turn': {'turn': self.turn, 'bytes': self.turn_bytes, 'lines': self.turn_lines},
                    'warnings': list(self.warnings)}
