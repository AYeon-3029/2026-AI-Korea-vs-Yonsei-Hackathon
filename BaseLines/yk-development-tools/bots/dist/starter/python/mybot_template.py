"""이전 파일명을 위한 호환 실행기. 제출 진입 파일은 main.py다."""
from main import decide
from protocol import run

if __name__ == "__main__":
    run(decide)
