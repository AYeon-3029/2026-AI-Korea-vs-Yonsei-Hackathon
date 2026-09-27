"""서버에 제출할 ZIP을 만든다. 로컬 대전 도구 묶음과 별개다."""

import argparse
from pathlib import Path
from submission import build_zip


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='submission.json이 있는 언어별 소스 폴더')
    parser.add_argument('--entry', help='예제를 진입 파일로 선택할 때 지정')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(f'제출 ZIP: {build_zip(args.source, args.output, args.entry).resolve()}')


if __name__ == '__main__':
    main()
