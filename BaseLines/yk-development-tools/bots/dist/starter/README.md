# 깃발 대항전 스타터 킷

전체 규칙은 [공식 규칙서](../../../docs/rulebook.md)를 확인하세요.
`out/starter-kit.zip`은 엔진·로컬 대전 도구를 담은 개발용 묶음입니다.
서버에는 아래 스크립트로 만든 **언어별 제출 ZIP**을 업로드합니다.

## 빠른 시작

개발용 묶음을 풀고 `engine/`, `runner/`, `bots/`가 있는 루트에서 실행하세요.

```sh
python3 bots/dist/starter/play_local.py
python3 bots/dist/starter/make_submission.py --source bots/dist/starter/python --output out/submission-python.zip
python3 bots/dist/starter/run_tests.py --zip out/submission-python.zip
```

전략은 `python/main.py`의 `decide()`를 고칩니다. `protocol.py`와 `campus_bot.py`는
파싱·조회·명령 출력을, `search.py`는 BFS와 점령 자원 예약을 담당합니다.
보조 `.py` 모듈을 추가해도 됩니다. NumPy도 사용할 수 있습니다.
생성된 `_generated.py`는 원본 설정을 포함하므로 직접 수정하지 않습니다.

C++는 `cpp/main.cpp`를 수정하고 프로토콜·길찾기 헤더를 함께 제출합니다.

```sh
c++ -std=c++20 -O2 bots/dist/starter/cpp/main.cpp -o main
python3 bots/dist/starter/play_local.py --bot ./main
python3 bots/dist/starter/make_submission.py --source bots/dist/starter/cpp --output out/submission-cpp.zip
python3 bots/dist/starter/run_tests.py --zip out/submission-cpp.zip
```

`run_tests.py`는 ZIP을 검사한 뒤 빈 폴더에 풀어 실제 대전합니다. `--compiler g++`로
컴파일러를 지정할 수 있습니다. `--bot "실행 명령"`은 ZIP 검사 없이 응답과 출력량만 확인합니다.
`--self-test`는 정상·잘못된 좌표·END 누락·시간 초과 검출을 확인합니다.

## 제출 ZIP 구조

파이썬:

```text
submission.json
main.py
protocol.py
campus_bot.py
_generated.py
search.py
```

C++:

```text
submission.json
main.cpp
protocol.hpp
generated.hpp
search.hpp
```

루트의 `submission.json`은 언어에 따라 다음 중 하나입니다.

```json
{"schemaVersion": 1, "language": "python"}
```

```json
{"schemaVersion": 1, "language": "cpp"}
```

- 진입 파일명은 정확히 `main.py` / `main.cpp`입니다. 바깥 폴더로 한 번 더 감싸지 마세요.
- `submission.json` 외에 Python은 `.py`, C++는 `.cpp`·`.h`·`.hh`·`.hpp`만 허용합니다.
- 보조 파일의 하위 폴더를 허용합니다. 절대경로·상위 폴더 경로·심볼릭링크는 금지합니다.
- 생성기는 캐시·실행 파일·허용되지 않은 확장자를 제외합니다. C++는 선택한 진입 소스와
  헤더와 보조 `.cpp` 구현 파일을 묶으며, 선택하지 않은 기본 예제 진입 파일은 제외합니다.
- 외부 모듈 import 금지 검사는 제거했습니다. 사용할 라이브러리는 서버 제공 범위를 따르세요.

## 예제

`example_lv1`은 BFS로 가까운 중립 건물을 고르는 그리디 전략이고,
`example_lv2`는 자원을 배분하고 전투병으로 호위·저지하는 휴리스틱입니다.
미정찰 건물 점수 `-1`은 실제 음수 점수가 아닙니다.

```sh
python3 bots/dist/starter/make_submission.py --source bots/dist/starter/python --entry example_lv1.py --output out/python-lv1.zip
python3 bots/dist/starter/make_submission.py --source bots/dist/starter/cpp --entry example_lv2.cpp --output out/cpp-lv2.zip
```

선택한 예제는 ZIP 안에서 `main.py` 또는 `main.cpp`로 배치됩니다.

## 실행 환경과 출력 제한

턴 시간은 기존 규칙서 12장(실격·몰수)과 [자동 생성 제한](limits.json)을 그대로 사용합니다.
`play_local.py`와 `run_tests.py`도 `limits.json`에서 읽습니다. 이번 제출 환경 개정에서는
시간 제한 및 동시 오류 판정을 변경하지 않았습니다.

| 항목 | 환경 |
|---|---|
| 일반 턴 시간 | 규칙서 12장(실격·몰수) 및 `limits.json`의 기존 값 |
| 첫 턴 시간 | 규칙서 12장(실격·몰수) 및 `limits.json`의 기존 값, 기동·INIT·초기화·첫 응답 포함 |
| Python | 3.12.14 |
| NumPy | 2.3.3 사용 가능 |
| C++ | C++20, gcc 12.2.0 |
| 메모리 | 384 MiB |
| 프로세스 수 | 최대 32 |
| 연산 장치 | CPU 전용, GPU 사용 불가 |
| stdout 한 턴 | 64 KiB 및 4096줄 |
| stdout 한 줄 | 1 KiB |
| stderr 한 게임 | 1 MiB |

KiB는 1024바이트, MiB는 1024 KiB입니다. 디버그 로그는 stderr의 게임당 한도 내에서
사용하세요. 로컬 검사는 개행·END도 바이트와 줄 수에 포함합니다. END까지를 한 턴으로
세고, 개행 없는 긴 출력도 확인합니다. stderr는 기동 시점부터 게임 전체를 누적합니다.

`run_tests.py` 결과의 `output_usage`와 `warnings`를 확인하세요. 로컬 검사에서 출력 한도 초과는 경고로 표시되며 로컬 경기 결과는 바꾸지 않습니다.
**대회 서버에서는 출력 제한 초과 시 몰수 처리합니다.** 메모리·프로세스·장치 제한을 강제하는
서버 격리 환경은 로컬 도구에 포함되지 않습니다. 로컬 컴파일러·Python 버전은 서버와 다를 수 있습니다.

## 대회 서버 운영

[플랫폼 운영 안내](../../../docs/PLATFORM_OPERATIONS.md)를 확인하세요.
