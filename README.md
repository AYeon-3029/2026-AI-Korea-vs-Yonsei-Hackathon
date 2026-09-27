# 2026 연고전 AI 해커톤 — 깃발 대항전 봇

작성: Junghoon

## 폴더 구조

| 경로 | 내용 |
|---|---|
| `Model/main.py` | 현재 개발 중인 봇 (v5). 보조 모듈 `campus_bot.py`, `protocol.py`, `_generated.py` |
| `Model/history/v1~v5/` | 버전별 스냅샷 (각 폴더 단독 실행 가능) |
| `DEVLOG.md` | 버전별 문제 인식 → 변경 → 정량 검증 기록 (보고서 개발 과정용) |
| `tools/arena.py` | 두 봇을 여러 시드·양 진영으로 대전시켜 승률 집계 |
| `tools/make_zip.py` | 서버 제출 ZIP 생성 (파일 권한 0644 고정, `submission-Junghoon-<버전>.zip`) |
| `tools/viewer.html` | 리플레이 JSON 턴별 뷰어 (브라우저로 열기) |
| `tools/showmap.py`, `tools/station_analysis.py` | 시드별 맵 출력, 역 효용 분석 |
| `submissions/` | 제출 ZIP |
| `out/replays/` | 로컬 대전 리플레이 (뷰어로 열람) |
| `BaseLines/` | 대회 제공 스타터 킷·개발 도구(엔진, 러너) |
| `Rules/` | 대회 규칙 문서 |

## 현재 상태

- **v3**: 서버 공식 테스트 봇 하·중·상 모두 스윕. 제출본 `submissions/submission-Junghoon-v3.zip`
- **v4**: v3 + 역 경유 경로 탐색(TELE). 로컬에서 v3 상대 0.567, v2 상대 0.650 (각 60경기)
- **v5**: 제출본 `submissions/submission-Junghoon-v5.zip`. 진영 대칭 동률 처리 + 가치 함수 재조정.
  홀드아웃 시드(100~179) 1120경기 승점률 **0.970** (v4 는 같은 조건 0.787), v4 상대 148승 12패.
  미러전(v5 vs v5)은 전부 무승부 — 진영 편향이 없다는 확인이자 실험 노이즈 제거 장치.

## 사용법 (WSL Ubuntu, 프로젝트 루트에서)

```bash
# 대전 평가: 시드 0~29, 양 진영
python3 tools/arena.py --a "python3 Model/main.py" --b "python3 Model/history/v4/main.py" --seeds 0-29 --replays out/replays/test

# 미러전 대칭 확인: v5 끼리 붙이면 전부 무승부여야 한다(비대칭 동률 처리 회귀 감지)
python3 tools/arena.py --a "python3 Model/main.py" --b "python3 Model/main.py" --seeds 0-9 --sides Y

# 파라미터를 바꿔 실험 (코드 수정 없이)
python3 tools/arena.py --a "BOT_PARAMS='{\"use_tele\":false}' python3 Model/main.py" --b lv2

# 제출 ZIP 생성 → submissions/submission-Junghoon-v5.zip
python3 tools/make_zip.py v5
```

`--b` 에 `lv1`, `lv2`, `main` 을 주면 대회 제공 예제 봇을 뜻한다.

## 주의

- 서버는 ZIP 항목에 실행 권한이 있으면 `EXECUTABLE_FILE` 로 거부한다. 반드시 `tools/make_zip.py` 로 만든다.
- 대회 규칙상 **팀 간 코드 공유 금지**. 이 저장소는 비공개로 유지한다.
