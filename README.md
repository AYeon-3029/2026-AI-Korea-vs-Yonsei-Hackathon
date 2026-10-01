# 2026 연고전 AI 해커톤 — 깃발 대항전 봇 (팀 어잌후)

최종 제출: **제출 v38 (`submissions/submission-Junghoon-v36.zip`)** — 봇 v36.

## 폴더 구조

| 경로 | 내용 |
|---|---|
| `Model/` | 최종 봇 v36 (`main.py` + 보조 모듈). 제출 ZIP과 동일 |
| `submissions/` | 최종 제출 ZIP, 최종 보고서 |
| `DEVLOG.md` | 버전별 문제 인식 → 변경 → 정량 검증 기록 |
| `tools/arena.py` | 두 봇을 여러 시드·양 진영으로 대전시켜 승률 집계 |
| `tools/tune_optuna.py` | Optuna 파라미터 탐색 |
| `tools/macro/` | 실제 리더보드 경기 분석·흉내 봇·실제 상태 분기 평가 도구 |
| `tools/lb_*.py`, `tools/real_*.py` | 리더보드 리플레이 분석 스크립트 |
| `tools/make_zip.py` | 서버 제출 ZIP 생성 (파일 권한 0644 고정) |
| `tools/viewer.html` | 리플레이 JSON 턴별 뷰어 |
| `BaseLines/` | 대회 제공 스타터 킷·개발 도구(엔진, 러너) — 도구들이 사용 |
| `Rules/` | 대회 규칙·공지·보고서 양식 |

대회가 끝난 뒤 저장소를 정리하면서 버전별 스냅샷(`Model/history`), 스파링 봇, 실험 산출물(`out/`),
실제 경기 리플레이, 중간 제출 ZIP은 제외했다. `DEVLOG.md`에 나오는 해당 경로는 기록용이다.

## 사용법 (WSL Ubuntu, 프로젝트 루트에서)

```bash
# 대전 평가: 시드 0~29, 양 진영, 대회 제공 예제 봇(lv1·lv2·main) 상대
python3 tools/arena.py --a "python3 Model/main.py" --b lv2 --seeds 0-29

# 파라미터를 바꿔 실험 (코드 수정 없이)
python3 tools/arena.py --a "BOT_PARAMS='{\"use_tele\":false}' python3 Model/main.py" --b lv2

# 제출 ZIP 생성 → submissions/submission-Junghoon-<버전>.zip
python3 tools/make_zip.py <버전>
```

## 주의

- 서버는 ZIP 항목에 실행 권한이 있으면 `EXECUTABLE_FILE` 로 거부한다. 반드시 `tools/make_zip.py` 로 만든다.
- 대회 규칙상 **팀 간 코드 공유 금지**. 이 저장소는 비공개로 유지한다.
