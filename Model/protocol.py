"""기존 파서를 유지하는 참가자용 인터페이스. 명령 키워드는 참조에서 생성한다."""

from campus_bot import Init, View, DIRS, TEAMS, KINDS, parse_init, parse_turn, read_block, run
from _generated import CMD_SPAWN, CMD_MOVE, CMD_MOVE2, CMD_TELE, CMD_PRIORITY, BALANCE


def spawn(kind, count, x=None, y=None):
    """본진은 좌표를 생략하고, 소유 병원에서 생산할 때만 좌표를 준다."""
    parts = [CMD_SPAWN, kind, str(count)]
    if (x is None) != (y is None):
        raise ValueError("생산 좌표는 둘 다 주거나 둘 다 생략하세요")
    if x is not None:
        parts.extend((str(x), str(y)))
    return " ".join(parts)


def move(x, y, kind, count, direction):
    """한 칸 이동 명령을 만든다."""
    return " ".join(map(str, (CMD_MOVE, x, y, kind, count, direction)))


def move2(x, y, count, first, second):
    """정찰병 전용 두 칸 이동 명령을 만든다."""
    return " ".join(map(str, (CMD_MOVE2, x, y, "S", count, first, second)))


def tele(x, y, kind, count, tx, ty):
    """소유 역 사이 순간이동 명령을 만든다."""
    return " ".join(map(str, (CMD_TELE, x, y, kind, count, tx, ty)))


def priority(coords):
    """건물 좌표 쌍을 입력 순서대로 점령 우선순위로 지정한다."""
    return " ".join([CMD_PRIORITY, *[str(v) for pair in coords for v in pair]])
