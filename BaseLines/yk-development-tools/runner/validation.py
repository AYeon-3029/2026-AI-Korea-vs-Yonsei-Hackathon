"""경기 실행 옵션 검증. 설정 오류를 봇의 몰수 사유로 처리하지 않는다."""


def require_positive_int(name: str, value: object) -> None:
    # bool은 int의 하위 타입이지만 경기 수/시간으로 허용하지 않는다.
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer: {value!r}")


def validate_run_options(config: dict, turn_timeout_ms: int,
                         max_turns: int | None = None) -> None:
    require_positive_int("turn_timeout_ms", turn_timeout_ms)
    if max_turns is not None:
        require_positive_int("max_turns", max_turns)
    else:
        require_positive_int("total_turns", config.get("total_turns"))
    if "first_turn_timeout_ms" in config:
        require_positive_int("first_turn_timeout_ms", config["first_turn_timeout_ms"])
