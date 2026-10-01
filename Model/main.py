"""깃발 대항전 전략 봇 v36 = v35 + 갇힌 F 구조(f_rescue 1: 사방이 적 1턴 위협인 F 의 탈출 칸 중 우리 W 가 가장 쉽게 닿는 칸에 위협+1 명).
호위 진단: 엄호 없는 위험 이동은 전부 갇힘 탈출. 대 v35 0.537(1차), 흉내 9팀 −0.004.

기반: v35 = v34 + 동수 방어 F(fguard 3: 우리 건물에 적 F 1칸 안·W 동수면 우리 F 를 올려 경합) + F 목표 거리 보정 4.0(가까운 목표 비중↑, 팀원 cv-71 분산 전개).
대 v34 0.520/0.547/0.560, 흉내 9팀 +0.037/+0.063/+0.007, tAIger 실제 상태 +0.026, RS22 +0.002, RSold +0.014.

기반: v34 = v33 + 공학관 직전 W 보류(eng_wait 2): 공학관이 없고 우리 F 가 중립 공학관 2칸 안이면(15턴까지)
자원 상한으로 버려질 분 외에는 W 를 사지 않고 공학관 점령 뒤 2원에 일괄 생산(팀원 tAIger 분석). 대 v33 0.600/0.623/0.590, 흉내 9팀 −0.004/+0.007/+0.041.

기반: v33 = v32 + F 위험 모델(갇힘 탈출): 실제 리더보드 83경기 우리 F 결정으로 학습한 로지스틱(1칸 안 적 W 칸 수가 핵심)으로
갇힌 F 의 탈출 칸을 고른다. 실제 상태 2턴 F 사망 4.86→4.30%(V22)·4.28→3.88%(V29 홀드아웃), 대 v32 0.570/0.597/0.580.

기반: v32 = v31 + W 넓게 깔기(w_spread anti: 같은 거리 다음 칸 중 아군 W 가 적은 칸 우선). 사용자 관찰(tAIger·AIKU 는 W 를 넓게 깔아 빈칸을 없앤다).

기반: v31 = v29 + 기습 목표를 수비가 얇은 곳 순으로(raid_soft_a 1: 거리 + 목표 2칸 안 적 W). 상위 팀 약점(자기 진영 상실의 38~60% 가 수비 ≤1) 공략.

기반: v29 = v28 + cv_align 2. cv-52: v27 + 계획된 W 지원에 맞춘 F 목표 배정.

기반 설명: 깃발 대항전 전략 봇 v27 = v26 + 보급소 기습(AIKU형) + F 2턴 안전 여유 8(공격 중 F 손실 감소). 저돌형 메타 대응.

리더보드 V22 회차: 진 경기 우리 F 사망 125 중 ≈85% 가 이미 갇힌 F → 길 칸은 2턴 안 적 W 가 우리보다 8 넘게 많으면 들어가지 않는다.
AIKU 는 보급소를 W 13~22 로 반복 기습 → 기습 대상에 보급소 포함.
검증(v26 대비): 실제 상태 V22·V21 +0.016 · V12~16 −0.012 · 현실 −0.011 · 공세 +0.006 · 흉내 −0.006 · v26 직접 대결 0.533(300).

v26 설명:
깃발 대항전 전략 봇 v26 = v25 + tAIger형 공격 습관: 상시 경제 기습 + 맞교환 반격.

리더보드 상위 팀 전략 지문(tools/lb_profile.py): F 를 W 와 붙여 다니고 상대 진영 학관·공학관·보급소를 경기 내내 반복 기습한다
(tAIger 20·38·44·51턴 W 10~13). 우리 v22 는 경기당 0~1회. 사용자 교훈: 빼앗긴 경제 손실은 회복되지 않으니 적 경제도 같은 턴만큼 깎아야 한다.
- 상시 경제 기습: 15턴부터 끝까지, 우리 W 20명 이상이면 가장 가까운 적 학관·공학관에 (주변 적 W + 6) 공격대(eco_raid_*).
- 맞교환 반격: 우리 학관·공학관을 잃은 턴부터 10턴 동안 적 진영 학관·공학관을 공격대로(swap_*).
- 검증(v25 대비): 현실 +0.025 ± 0.012 · 공세 0 · 흉내 +0.001 · v25 직접 대결 0.527(300) · 실제 상태 V22·V21 −0.020 · V12~16 +0.004.

v25 설명:
깃발 대항전 전략 봇 v25 = v22 + 상시 F 호위(fesc_always, 최소 2명).

리더보드 V22 회차 분석: 상위 팀 F 호위율 81~100% vs 우리 50~80%. 이동 중 F 의 다음 칸에 적이 없어도 W 2명을 붙인다.
새 시드 현실 +0.003 · 공세 −0.011 · 흉내 +0.013 · 이번 회차 흉내 +0.008 · 실제 초반 상태 +0.016 · v22 직접 대결 0.533(300경기).
(dev39 의 다른 실험 스위치는 모두 꺼짐, 막판 수세 적용 위치만 decide 안으로 옮김 — eg_def_turn 999 라 동작 같음)

이전 설명(v22):

v19 + W 동수 상쇄 시 F가 생존하는 전투 규칙을 안전 판정에 반영.

전략 요약
1. 공개된 점수는 대칭 짝까지 함께 기억한다. 미공개 점수는 지역별 기댓값으로 추정한다.
2. 건물 가치 = 점수 + 기능 보너스. 적 소유 기능 건물(공학관·도서관·학생회관·병원·역)은
   상대가 누리는 효과를 빼앗는 '탈취 보너스'를 더한다.
3. 역 가치는 첫 턴 맵 분석으로 계산한다(역 경로로 본진→건물 거리가 얼마나 줄어드는가).
   아군 역이 2개 이상이면 TELE 로 병력을 전방으로 보낸다.
4. 깃발병(F)은 점령 후 곧바로 다음 목표로 이동하고, 적 전투병 위협 칸은 피한다.
   F 최소 인원을 먼저 확보해 전투병 군비 경쟁 중에도 재점령 인력을 잃지 않는다.
5. 전투병(W)은 적 깃발병의 다음 목표 건물을 예측해 적보다 먼저(또는 동시에) 도착하도록
   보내고, 점령 중인 아군 F 엄호, 위협받는 건물 경계, 남는 인원은 공성(적 건물·생산 거점 포위).
6. 정찰병은 쓰지 않는다.
7. v5: 위협 지도 보정(적 생산 자원은 공용 예산·적 TELE 반영), 점령 예비비를 F 수로 제한,
   군비 경쟁을 국지 기준으로 판단, 동거리 타이브레이크를 목적 있는 기준(위험·엄호·중앙)으로
   바꾸고 남는 동률은 진영 대칭으로 깨 미러전이 대칭이 되게 한다.
8. v6: 후반 모드(151턴~ 가치 = 순수 점수, 160턴 안에 닿는 목표만) + Optuna 자기 대전 리그 탐색으로
   찾은 파라미터(깃발병 6·전투병 여유 19·경계 반경 14, 공학관·학생회관·병원·적 건물 가치 상향).
   PLAN-frontier 스위치(frontier_targets 등)와 굳히기(lead_mode)는 실측 기각으로 기본값 끔.
9. v7: 깃발병 진입 엄호(escort_wait). F 가 2칸 안의 미점령 건물 앞에서 위협 때문에 기다리면 W 를
   위협+1 만큼 먼저 보내 그 칸을 정리하고, W 가 도착하는 턴에 F 가 같이 들어가 점령한다.
10. v8: 엄호 인원 위협+2, 엄호 우선도 1.5 (다른 W 작업을 덜 밀어내면서 확실히 이긴다).
11. v9: Optuna 2차 탐색(v6 리그, 새 스위치 포함) #181 파라미터 + v8 엄호 인원(위협+2).
    전투병 여유 19 → 26, 학생회관 가치 상향, 적 건물 배율·공성 가치 소폭 하향, F 건물 비키기 켬.
12. v10: 목표 위험 배율(risk_local_w 0.15). 목표 3칸 안에 적 W 가 아군 W 보다 많을수록 F 목표·공성 가치를
    깎아, 적 병력이 몰린 건물(적 진영 깊숙한 학관·공학관 등) 대신 이길 수 있는 곳부터 노린다.
13. v11: 진입 차단(f_block 2). 전투는 같은 칸에서만 일어나므로, 적 F 가 k(≤2) 턴 안에 들어올 수 있는 내 건물에
    k 턴 안에 도착하는 W 로 (k 턴 안에 닿는 적 W + 1) 명을 올린다(실제 경기 상실 217건 중 216건이 1턴 예고, 전부 건물 칸 W 0).
14. v12: Optuna 3차 탐색(v11 둘레, 진입 차단·엄호·위험 배율 포함) #112. F 상한 6 → 4·최소 5 → 3, 엄호 인원 위협+4,
    진입 차단 가치 6.28, 공학관 가치 ↑, 적 건물 배율·공성 가치 ↓ — F 를 줄이고 가진 건물을 더 단단히 지킨다.
15. v13: Optuna 4차(v12 둘레 + 엄호 거리·공성 집결 거리·TELE 이득·경계 여유, 상대 = v12·b72·모방 3종·v11) #131.
    실제 v12 회차(전체 팀 대전 7승 5패)에서 뒤진 채 교착·역전패 → F 5명(최소 5)으로 되돌리고 엄호 거리 3, TELE 이득 3,
    공학관 12.6, 적 건물 배율 1.77, 위험 배율 0.23. v12 상대 0.602(1200경기), 모방 풀 두 곳 모두 두 번 연속 우위.
16. v14: 실제 v12 패배 재분석(패배 4/5 = 우리 학생회관·공학관 상실 → 수입 열세, TELE 대기열 병목으로 W 최대 81% 역 위 대기)
    → 경제 건물 진입 차단 반경 확대(eco_block_extra), TELE 대기열 반영(tele_queue), 우리 쪽 경제 건물 탈환 가중(retake_*),
    초반 러시 대응(rush_k) + 한 프로세스 시뮬레이터 Optuna 5차 #171(차단 반경 일반 1·경제 4, 위험 배율 0.42, 공학관 8.2).
17. v15: v14 맞춤 공격자 탐색(수비적 경제형 #291·#239 가 v14 상대 0.56) → 현실 풀 + 공격자로 Optuna 8차 #153.
    F 상한 4(30턴까지 5), 학생회관 11.2·공학관 10.2, 경제 건물 차단 가치 4.4(반경 2), 탈환 가중 0.77, 전투병 여유 20,
    F 우리 건물 통과 회피(f_own_R 3)·역 대기 안 함. 현실 풀 새 시드 +0.017±0.007(7200쌍), 공격자 +0.037, 실제 상태 +0.004~0.008.
18. v16: 9/29 20시 실전 패배(상위 공세형 상대에게 학생회관·공학관을 잃고 탈환이 계속 늦춰짐, 사용자 관찰) → 경제 열세 공격대(eco_strike 3):
    우리 학생회관(공학관) 수가 상대보다 적으면 아군 W 에서 가장 가까운 적 소유 학생회관·공학관(진영 무관)에 '2칸 안 적 W + 3' 명을
    최우선 작업으로 모은다. v15 대비 현실 풀 새 시드 +0.033±0.005(7200쌍), 공세형 대리 풀 +0.030±0.008(3600쌍).
19. v17: 상위 팀 행동 분석(F 사망 우리 9.4 vs 상위 3.8 등) + Optuna 9차(v16 중심, 현실 풀 12 + 공세형 대리 6) #258.
    학생회관 14.7·공학관 13.7(경제 중시), 중앙 기댓값 1.58, 거리 보정 8.0, 공성 16.9·집결 4, 진입 차단 2칸, 경제 공격대 5명·반경 3,
    경제 열세 가중(eco_def 1.42/0.52), 대기 적 무리 타격 2, F 겹침 방지. v16 대비 현실 풀 +0.044±0.007(7200쌍), 공세형 +0.037±0.010(3600쌍).
20. v18: v17 + 이동 중 F 엄호(fesc_n 1, 상위 팀 관찰: 우리 F 사망 9.4 vs 상위 3.8 — 목표로 가는 F 의 다음 칸이 적 W 에 노출되면
    W 를 먼저 보내 같은 턴 도착) + 경제 공격대 home 모드(수 동률이어도 우리 진영 학생회관·공학관을 적이 가지면 발동).
    v17 대비 새 시드 91000·92000번대 현실 풀 +0.027±0.006·+0.044±0.006(7200쌍씩), 공세형 +0.036±0.010·+0.021±0.009(3600쌍씩).
21. v19: v18 + F 위험 탈출(F 사망 진단 tools/macro/fdeath.py: 사망 93% 가 이미 위험한 칸에 갇힌 F) — 목표 위 F 가 위험하면 안전한 옆 칸으로(f_goal_flee 1), 사방 위험이면 (위협−엄호) 최소 칸(f_trap_min). v18 대비 새 시드 101000번대 현실 풀 +0.071±0.007(4800쌍), 공세형 +0.089±0.010(2400쌍), 실제 상태 +0.046±0.010(1328쌍).
v20 = cv-3 + 탈환 F(recap_f 1, recap_R 1): 잃은 우리 쪽 학관·공학관 근처에 F 가 없으면 상한을 넘겨 가장 가까운 거점에서 F 1명을 뽑는다. 새 시드 2벌 x 현실/공세/흉내 모두 +0.004~+0.016
v21 = v20 + strike_neutral: 적 W 가 눌러 앉은 중립 상태의 우리 쪽 학관·공학관도 W 공격대 목표. 새 시드 2벌 현실/공세/흉내 +0.005~+0.031
v22 = cv-14 + spend_all(예비비 뺀 남는 예산 전부 W, 공격적 생산). 새 시드 3벌 현실 +0.004~+0.007 공세 −0.001~+0.009 흉내 +0.004~+0.008
"""
import json
import math
import os
import sys
import traceback
from collections import deque

from protocol import BALANCE, DIRS, spawn, move, move2, tele, priority, run
from tactical import rollout

CFG = BALANCE
INF = 10 ** 9
F_COST = CFG["units"]["F"]["cost"]
S_COST = CFG["units"]["S"]["cost"]
TOTAL_TURNS = CFG["total_turns"]
TELE_MAX = CFG["tele"]["max_units"]
TELE_MIN_ST = CFG["tele"]["min_stations"]

# 튜닝 파라미터(오프라인 대전으로 조정)
P = {
    "cv_cost_scope": 0, "cv_critical_first": False, "cv_siege_cost": 0.0,
    "cv_job_cost": 0.0, "cv_workload": 0, "cv_source_cost": 0.0,
    "cv_urgent": False, "cv_arrival": 0.0, "cv_recap_assign": False,
    "cv_intercept": False, "cv_cut_link": False, "cv_neutral": False,
    "center_expect": 1.577,      # 중앙 건물 미공개 점수 기댓값(2~4) v6: 3.0 → 2.75 v9: 2.75 → 2.35 v12: 2.35 → 2.6779 v13: 2.6779 → 2.2857 v15: 2.2857 → 2.2431 v17: 2.2431 → 1.577
    "side_expect": 1.309,        # 신촌·안암 건물 미공개 점수 기댓값(1~2) v6: 1.5 → 1.1 v9: 1.1 → 1.08 v12: 1.08 → 1.2012 v13: 1.2012 → 1.2124 v15: 1.2124 → 1.2623 v17: 1.2623 → 1.309
    "hall_bonus": 14.735,         # 학생회관 기능 가치(남은 턴 비율을 곱함). v4 2.5 → 탐색 결과 5.0 v6: 5.0 → 7.15 v9: 7.15 → 9.15 v12: 9.15 → 9.23 v13: 9.23 → 9.6127 v14: 9.6127 → 8.7462 v15: 8.7462 → 11.241 v17: 11.241 → 14.735
    "depot_bonus": 1.273,        # 아직 받지 않은 보급소 보너스 가치 v6: 3.0 → 1.76 v9: 1.76 → 1.75 v12: 1.75 → 1.9094 v13: 1.9094 → 2.2573 v15: 2.2573 → 1.8659 v17: 1.8659 → 1.273
    "hosp_bonus": 3.777,         # 병원 전진 생산 가치(남은 턴 비율을 곱함) v6: 1.0 → 3.19 v9: 3.19 → 3.11 v12: 3.11 → 2.5374 v13: 2.5374 → 3.744 v15: 3.744 → 4.428 v17: 4.428 → 3.777
    "eng_bonus": 13.746,          # 공학관: W 비용 3→2 는 군비 상시 할인. v4 0.5 → 5.0 v6: 5.0 → 9.13 v9: 9.13 → 9.01 v12: 9.01 → 10.5943 v13: 10.5943 → 12.6092 v14: 12.6092 → 8.1937 v15: 8.1937 → 10.2462 v17: 10.2462 → 13.746
    "lib_bonus": 3.904,          # 도서관: 점령 비용 −1. v4 0.5 → 2.0 v6: 2.0 → 2.03 v9: 2.03 → 2.41 v12: 2.41 → 2.8522 v13: 2.8522 → 2.9107 v15: 2.9107 → 3.2902 v17: 3.2902 → 3.904
    "watch_bonus": 0.2,
    "station_scale": 0.0,      # 역 가치 = 맵 분석 단축 칸수 합 × scale (실험 결과 0.08은 역효과)
    "station_cap": 4.0,
    "station_solo": 0.5,       # 짝 역이 없을 때 역 가치 반영 비율
    # 적 소유 건물 탈취 보너스(상대가 누리던 효과를 빼앗는 가치)
    "deny": {"ENG": 2.0, "LIBRARY": 1.5, "HALL": 2.0, "HOSPITAL": 1.0},
    "enemy_owned_mult": 1.93,   # 적 건물은 빼앗으면 상대 점수도 줄어든다 v6: 1.3 → 1.85 v9: 1.85 → 1.68 v12: 1.68 → 1.3728 v13: 1.3728 → 1.7748 v14: 1.7748 → 1.7663 v15: 1.7663 → 1.5875 v17: 1.5875 → 1.93
    "enemy_f_penalty": 0.5725,    # 적 깃발병이 서 있는 건물(경합) 감점 v6: 0.3 → 0.49 v9: 0.49 → 0.55 v12: 0.55 → 0.7913 v13: 0.7913 → 0.9432 v15: 0.9432 → 0.6737 v17: 0.6737 → 0.5725
    "dist_offset": 8.028,        # 가치 / (거리 + offset). v4 2.0 → 5.0 (가까운 목표 편중 완화) v6: 5.0 → 4.36 v9: 4.36 → 4.52 v12: 4.52 → 4.7428 v13: 4.7428 → 4.9975 v15: 4.9975 → 5.7256 v17: 5.7256 → 8.028
    "max_f": 4,               # 동시에 유지할 깃발병 상한. v4 7 → 12 (점령 처리량이 병목) v6: 12 → 6 v12: 6 → 4 v13: 4 → 5 v15: 5 → 4
    "min_f": 5,                # 전투병보다 먼저 확보할 깃발병 수 v6: 3 → 5 v12: 5 → 3 v13: 3 → 5
    "min_w": 4,                # 3턴 이후 최소 전투병 수 v6: 2 → 5 v9: 5 → 6 v12: 6 → 4 v13: 4 → 6 v14: 6 → 5 v17: 5 → 4
    "w_margin": 21,            # 적 전투병 총수 대비 여유분. v4 1 → 12 v6: 12 → 19 v9: 19 → 26 v12: 26 → 27 v13: 27 → 23 v14: 23 → 27 v15: 27 → 20 v17: 20 → 21
    "escort_radius": 2,        # 적 F 호위 전투병으로 볼 거리
    "predict_top": 2,          # 적 F 목표 후보 수(가까운 순)
    "late_penalty": 0.5,       # 제때 도착 못 하는 요격 가치 배율
    "guard_radius": 15,         # 적 유닛이 이 거리 안에 있는 아군 건물만 경계. v4 4 → 9 v6: 9 → 14 v12: 14 → 15 v13: 15 → 19 v14: 19 → 15 v15: 15 → 14 v17: 14 → 15
    "siege_bld_bonus": 16.945,    # 공성 우선순위: 적 소유 건물 v6: 5.0 → 9.75 v9: 9.75 → 7.62 v12: 7.62 → 6.9113 v13: 6.9113 → 7.6216 v14: 7.6216 → 9.7066 v15: 9.7066 → 11.5744 v17: 11.5744 → 16.945
    "siege_ring_value": 1.644,   # 공성 우선순위: 적 생산 거점 둘레 칸 v6: 2.0 → 4.06 v9: 4.06 → 4.61 v12: 4.61 → 3.1722 v13: 3.1722 → 3.1323 v15: 3.1323 → 1.5388 v17: 1.5388 → 1.644
    "tele_min_gain": 2,        # TELE 가 일반 이동보다 이만큼 이상 가까워야 사용 v13: 2 → 3 v15: 3 → 2
    "use_tele": True,          # 역 경유 경로 탐색 + TELE (v4: 경로 탐색 수정 후 사용)
    "predict": False,          # 실험 스위치: 적 F 목표 예측 요격(False 면 v2 방식, 예측은 역효과)
    "pred_need_threat": False, # 예측 요격 인원에 목표 칸 위협도 반영
    "pred_deadline": True,     # 예측 요격에서 제때 도착 가능한 인원 우선
    "pred_chase": True,        # 예측 요격과 별도로 현재 위치 추격 작업 추가
    "chase_mult": 0.9358,         # 추격 작업 가치 = 가장 가까운 목표 가치 × chase_mult v6: 0.8 → 1.33 v9: 1.33 → 1.4 v12: 1.4 → 1.5098 v13: 1.5098 → 1.3194 v15: 1.3194 → 0.9053 v17: 0.9053 → 0.9358
    "pred_mult": 1.0,          # 예측(선점) 작업 가치 배율
    # --- v5 스위치 (all / False / 1.0 이면 v4 동작) ---
    "spawn_threat_mode": "all",    # 적 생산 가능 W 를 위협에 넣는 방식 all|split|half|off (실측 무차)
    "tele_threat": False,          # 적 역 TELE 위협 반영 (실측 역효과 −0.05 → 끔)
    "enf_count_fix": True,         # des_W 의 적 F 수를 칸 수(v4 버그) 대신 인원으로
    "reserve_by_f": True,          # 점령 예비비를 아군 F 수만큼의 건물로 제한
    "local_w": False,              # 군비 기준을 내 구역 근방 적 W 로 (실측 역효과 → 끔)
    "local_w_radius": 6,           # 내 건물·유닛에서 이 거리 안의 적 W 를 센다
    "local_w_floor": 0.5,          # 그래도 적 W 총수의 이 비율만큼은 유지
    "sym_tiebreak": True,          # 남는 동률을 진영 대칭으로 깨기(미러전 = 무승부)
    # dev51 사용자 관찰(tAIger·AIKU 전): 상대는 W 를 넓게 깔아 빈칸을 없앤다(진 경기 2칸 통제 58% vs 우리 37%, 칸당 W 3.0 vs 4.4).
    # w_spread: off(뭉치기, v31) | anti(아군 적은 칸 우선) | cap(이동 칸 아군이 w_cap 이상이면 뒤로)
    "w_spread": "anti", "w_cap": 4,
    "smart_step": "w",             # 동거리 후보 선택 기준 적용 대상 off|f|w|both (F 는 역효과)
    "siege": True,                 # 남는 W 로 적 건물·생산 거점을 공격 (False 면 순수 수비)
    "f_center_pull": True,         # F 동거리 후보에서 중앙에 가까운 칸을 선호
    # --- v6 스위치 ---
    "endgame_turn": 151,           # 이 턴부터 후반 모드(가치 = 순수 점수, 기한 안 도달 목표만). 999 = 끔 v6: 150 → 151 v12: 151 → 154 v13: 154 → 148 v15: 148 → 152 v17: 152 → 151
    "eg_garrison": False,          # 후반 모드에서 적 본진 포위를 멈추고 내 건물 주둔으로 전환
    # 막판 F 증원(실제 경기 V10 패배: 152턴 광장 상실 후 F 3명으로 8턴간 탈환 실패, 상대는 F 3 → 9)
    "eg_f_turn": 999,              # 이 턴부터 F 상한·최소를 아래 값으로(목표는 160턴 안에 닿는 건물만 센다). 999 = 끔
    "eg_max_f": 10,
    "eg_min_f": 8,
    # 진입 차단(실제 경기 상실 112건 분석: 전부 적 F 가 전 턴 1칸 옆 → 그 턴 건물 칸 위 아군 W 0).
    # 적 F 가 k(≤ f_block) 턴 안에 들어올 수 있는 내 건물에, k 턴 안에 도착하는 W 로 (k 턴 안에 닿는 적 W + 1) 명을 올린다.
    "f_block": 2,                  # 0 = 끔, 1 = 1칸 옆 적 F 만, 2 = 2칸까지. v11: 0 → 2 v14: 2 → 1 v17: 1 → 2
    "block_worth": 2.761,            # 작업 가치 = block_worth + 건물 가치. 10 은 다른 작업을 과하게 밀어낸다. v11: 3.0 v12: 3.0 → 6.2793 v13: 6.2793 → 3.5189 v14: 3.5189 → 2.868 v15: 2.868 → 1.9287 v17: 1.9287 → 2.761
    "block_spawn": False,          # 적 생산 거점이 k 칸 안이면 적이 이번 턴 뽑을 수 있는 W 도 센다(생산이 이동보다 먼저)
    "block_tele": False,           # 적 역이 k−1 칸 안이면 다른 적 역의 W(TELE 1회분, 최대 5)도 센다
    "block_extra": 0,              # 필요 인원 여유
    # dev42 tAIger전(V22 회차) 진단: 적 F 가 학관 옆에서 호위 W 13명이 모이기를 3턴 기다렸다 들어왔는데, 필요 인원은 F 거리 k 안의
    # 적 W 만 세어 1명이었다. 학관·공학관이면 block_wR 칸 안 적 W(곧 F 와 합류할 호위)도 센다. 0 = 끔
    "block_wR": 4,
    # dev42 같은 목표 칸에 작업이 여럿이면 가치가 큰 작업 하나만 실행되어 필요 인원이 작은 쪽(예측 1명)이 차단 작업(15명)을 지웠다.
    # 켜면 같은 목표의 작업들 중 가장 큰 필요 인원을 쓴다.
    "job_maxneed": True,
    "block_strict": False,         # 기한 안 인원으로 필요 인원을 못 채우면 보내지 않는다(동수 상쇄면 적 F 가 살아남는다)
    # 방어 범위 경로(사용자 관찰 seed 3608: 본진 병력이 방송국만 보고 돌아 나가는데, 광장 쪽으로 나가면 비슷한 거리로
    # 광장·방송국을 함께 지원 범위에 둔다). 칸의 방어 가치 = cov_R 칸 안 '적이 근처에 있는 내 건물' 가치 합.
    "cov_route": False,            # W 최단 경로 동률을 경로 전체 방어 가치 합으로 깬다
    "cov_R": 2,
    "cov_route_mode": "primary",   # primary = 방어 가치가 첫 기준(v11 구현) | secondary = 뭉쳐 다니기 다음 기준
    "cov_lane": 0.0,               # 급하지 않은 이동의 차선 변경 문턱(도착 칸 방어 가치 증가량). 0 = 끔
    "cov_side": False,             # 기한 없는 이동에서 방어 가치가 오르는 옆걸음(+1턴)을 허용
    "cov_lambda": 3.0,             # 옆걸음 비용(경로 방어 가치 합 단위)
    "cov_neutral": 0.0,            # 경합 중립 건물(양쪽 유닛이 6칸 안)도 이 배율로 방어 가치에 넣는다(seed 3608 광장). 0 = 내 건물만
    # 가망 없는 수비 포기(사용자 관찰 seed 3609): 주변 적 W − 아군 W 가 이 이상이면 경계·진입 차단을 보내지 않는다. 0 = 끔
    "def_hopeless": 0,
    "hopeless_gate": "always",     # 언제 켤지: always | outnumbered(전체 W 가 적보다 gate_margin 이상 적음) | behind(추정 점수 열세)
    "gate_margin": 0,
    # 새로 점령한 건물 수성(실제 비등 경기: 광장·역이 수십 번 주인이 바뀜). 점령 후 hold_new 턴 동안
    # 적 유닛이 hold_R 칸 안에 있으면 그 건물 칸에 (1턴 위협 + 1) 명을 먼저 올린다. 0 = 끔
    "hold_new": 0,
    "hold_R": 3,
    "hold_worth": 4.0,             # 작업 가치 = hold_worth + 건물 가치
    # 역전 모드: cb_turn 이후 추정 점수가 cb_margin 이상 뒤지면 F 상한·최소를 올리고 공성 가치↑·위험 배율↓. 999 = 끔
    "cb_turn": 999,
    "cb_margin": 4,
    "cb_max_f": 7,
    "cb_min_f": 5,
    "cb_siege_mult": 1.5,
    "cb_risk_scale": 0.5,
    "eg_risk_scale": 1.0,      # 후반 모드(endgame_turn~)의 목표 위험 배율 가중치 배율. 1.0 = v10 그대로, 0 = 막판엔 위험 무시
    "finish_k": 0,                 # 적 건물이 이 수 이하이고 내가 과반이면 즉시 승리 노림. 0 = 끔
    "finish_mult": 3.0,            # 그때 적 건물 목표 가치 배율
    "f_contest_wait": False,       # 적 F 가 있는 칸은 아군 W 엄호가 도착할 때 함께 들어간다(같은 턴 탈취)
    "siege_def_bonus": 0.0,        # 공성 우선순위: 수비 F 가 서 있는 적 건물 가산
    # --- PLAN-frontier 스위치 (기본값 = v5 동작) ---
    "frontier_targets": False,     # 2-1: 도착 시점에 버틸 수 없는 건물의 F 목표 가치를 깎는다
    "frontier_penalty": 0.3,       #      버틸 수 없는 건물 배율
    "region_bonus": 1.2,           #      내 영역(내가 먼저 닿는 칸) 안 건물 배율
    "frontier_extra": 2,           #      도착 후 이 턴 수 안에 적 F 가 닿을 수 있으면 '위험'
    "guard_horizon": 0,            # 2-2: 경계 인원을 H 턴 도달 전력 + 1 로. 0 = 끔(1턴 위협 기준)
    "guard_cap": 99,               #      건물당 경계 인원 상한
    "reserve_pos": False,          # 2-3: 남는 W 를 경합 건물들의 1-center 에 둔다
    "lead_mode": "off",            # 2-4: off | consolidate — 점수 우세 시 공성 중단·내 영역 굳히기
    "lead_margin": 6,
    "lead_min_turn": 100,
    "scout_n": 0,                  # 정찰병 유지 인원(미공개 점수가 남아 있는 동안). 0 = 쓰지 않음
    "scout_until": 60,             # 이 턴까지만 정찰병을 생산한다
    "scout_center_bonus": 3,       # 정찰 목표 선택: 중앙 건물(점수 2~4, 불확실성 큼)을 이 칸만큼 가깝게 본다
    "guard_extra": 0,              # 경계 인원 = 1턴 위협 + guard_extra (v6 까지 0 = 동수, 동수면 적 F 가 살아남는다)
    "escort_wait": True,           # 진입 대기 F 의 목표 건물(위협 있음)에 W 를 먼저 보낸다. v7: False → True
    "escort_dist": 3,              #   F 에서 이 거리 안의 미점령 건물. v7: 1 → 2 v13: 2 → 3
    "escort_bonus": 1.09,           #   작업 가치 = 건물 가치 + bonus. v8: 3.0 → 1.5 v9: 1.5 → 1.8 v12: 1.8 → 1.8612 v13: 1.8612 → 1.0011 v15: 1.0011 → 1.4596 v17: 1.4596 → 1.09
    "escort_extra": 5,             #   보낼 인원 = 위협 + extra. v8: 1 → 2 v12: 2 → 4 v14: 4 → 5 v15: 5 → 6 v17: 6 → 5
    "f_idle_off": True,           # 목표 없는 F 는 내 건물 위에 머물지 않고 옆 빈 칸으로 비킨다 v9: False → True
    "w_spawn": "enf",              # W 생산 거점 기준: enf(적 F 에 가까운 곳) | myf(아군 F 근처, 엄호용) | mix
    "max_f_early": 5,              # early_turn 까지의 깃발병 상한(중립 건물이 많은 초반 확장 경쟁용) v15: 6 → 5
    "early_turn": 30,               # 0 = 끔 v15: 0 → 30
    # --- v9 이후 스위치 (사용자 리플레이 관찰) ---
    "risk_depth_w": 0.0,           # 목표가 적 진영 깊이(내 거점까지 − 적 거점까지 거리) 1칸마다 가치를 이 비율로 깎음. 0 = 끔
    "risk_local_w": 0.4586,          # 목표 주변(risk_R 칸) 적 W 가 아군 W 보다 많은 만큼 가치를 깎음. 0 = 끔. v10: 0 → 0.15 v12: 0.15 → 0.1056 v13: 0.1056 → 0.2271 v14: 0.2271 → 0.4215 v15: 0.4215 → 0.4754 v17: 0.4754 → 0.4586
    "risk_R": 3,
    "risk_tele": False,            # 목표 R 칸 안에 적 역이 있으면 다른 적 역의 W(최대 5, TELE 1회분)를 주변 적 병력에 더한다
    # 적 반응 학습(사용자 제안): 우리 공격 목표 주변에 적 W 가 얼마나 몰려드는지 누적해 위험 가중치를 경기 중에 조정
    "adapt_k": 0.0,                # 가중치 = risk_local_w × (1 + k × (반응성 − adapt_mid)). 0 = 끔
    "adapt_mid": 0.3,
    "adapt_alpha": 0.1,            # 반응성 지수이동평균 계수
    "risk_decay_w": 0.0,           # 거리 감쇠 병력 균형(Σ W·γ^거리, 적 − 아군)만큼 추가 감점. 0 = 끔
    "risk_gamma": 0.7,
    "risk_spawn_w": 0.0,           # 목표 가까이 적 생산 거점(본진·병원)이 있으면 추가 감점(아군 거점이 가까우면 상쇄). 0 = 끔
    "risk_spawn_D": 4,
    # 전개 시뮬레이션(사용자 제안): 목표마다 앞으로 t 턴 동안 양쪽이 모을 수 있는 W 를 비교해 탈취·수성 가능성을 본다
    "lookahead": False,
    "tactical_rollout": False,    # 실제 이동·전투·점령을 전개하는 별도 실험(기존 lookahead와 독립)
    "tr_weight": 0.35,            # 목표 가치에 더하는 단기 예측 보정 강도
    "la_phi": 0.5,                 # 적 결집 비율(적 W·생산분 중 이 비율이 그 건물로 온다고 본다)
    "la_spawn_frac": 0.5,          # 양쪽 생산분 중 그 건물 쪽으로 보내는 비율
    "la_hold": 6,                  # 탈취 후 이 턴 수 동안 지킬 수 있는지 본다
    "la_fail": 0.3,                # 도착 턴에 전투에서 밀리면(탈취 불가) 가치 배율
    "la_floor": 0.4,               # 탈취는 되지만 전혀 지킬 수 없을 때 배율(수성 비율에 따라 1.0 까지)
    "la_siege": True,              # 공성 우선순위에도 적용
    # 미래 예측 2차 — 곱셈 감점 대신 좁고 구체적인 예측
    "la_race": False,              # 중립 목표에 적 F 가 나보다 먼저(또는 동시에) 닿으면 가치 배율
    "race_pen": 0.4,               #   적 F 가 먼저 도착
    "race_tie": 0.7,               #   동시 도착(경합 → 둘 다 점령 불가)
    "la_short": 0.0,               # 도착 시점 부족분(φ·적 W − 내 W, 현재 W 만)만큼 가치에서 뺀다. 0 = 끔
    "la_short_phi": 0.5,
    "f_wait_2step": False,         # 기다리는 F 는 2칸 안에 적 W 가 엄호보다 많이 모이면 미리 물러난다
    "siege_no_losing": False,      # 공성 이동에서만, 지금 있는 적 W(생산분 제외)보다 적으면 들어가지 않는다
    "w_no_losing": False,          # W 는 적이 더 많이 올 수 있는 칸으로 들어가지 않는다(지는 싸움 회피)
    "siege_ring_eco": False,       # 내 W 단가가 적보다 비싸면(공학관 열세) 적 거점 포위를 하지 않는다
    "plaza_hold": 0,               # 광장 보유 시 수비 작업을 최우선으로(인원 = 위협 + plaza_hold). 0 = 끔
    "cap_fix": False,              # 상한 초과 판정을 예비비 포함 실제 자원 기준으로(실제 경기: 상대는 상한에 거의 안 머묾)
    "spend_all": True,            # 예비비 외 남는 예산을 전부 전투병으로 v22: False → True
    "spend_all_hard": False,       # 예비비까지 전부 전투병으로(점령비는 이번 턴 수입으로)
    # 전선 집결(사용자 제안): 후반에는 남는 W 를 전선 건물에 모으고, 뒤쪽 건물은 적이 다가올 때만 먼저 증원
    "front_mass_turn": 999,        # 이 턴부터 켠다. 999 = 끔
    "front_k": 3,                  # 전선 건물 수(내 건물 중 적 생산 거점 쪽으로 가장 깊은 순)
    "rear_R": 4,                   # 뒤쪽 건물 이 거리 안에 적 W 가 들어오면 그 수 + 1 을 그 거리 안에 도착할 병력으로 보낸다
    "fm_siege": False,             # 전선 집결 중에도 적 건물 공성(주변 위험 배율 적용, 본진 포위 제외)을 할지
    "siege_stage": 4,              # 공성 인원이 모자라면 목표 이 칸 안에서 대기(집결). -1 = 대기 없이 투입 v13: 2 → 3 v15: 3 → 2 v17: 2 → 4
    "reinforce_hot": False,        # 격전지(아군·적 W 가 2칸 안에서 맞선 칸)에 공성보다 먼저 증원
    "hot_radius": 2,
    "rapid_garrison": 2,           # rapid: 건물당 최소 주둔
    "rapid_horizon": 3,            # rapid: 이 턴 수 안에 닿는 적 W 보다 많이, 그 안에 도착할 아군으로 증원
    "lead_w": "reserve",           # 굳히기 중 W 배치: reserve(1-center 예비대) | pressure(공격 방향 예측 주둔) | rapid(주둔+신속 증원)
    "hold_horizon": 3,             # pressure: 이 턴 수 안에 닿는 적 W 를 그 건물의 압력으로 본다
    "hold_trend_w": 1.0,           # pressure: 지난 턴보다 늘어난 적 W(접근 중) 가중
    # 막판 수세(같은 상태 분기 실험 tools/macro: 141턴부터 아래 값으로 바꾸면 두 번 독립 재현 +0.013·+0.009).
    # 이 턴 이후에는 eg_def 값을 덮어쓴다(공성 가치↓·경계 반경·전투병 여유↑). 999 = 끔
    # TELE 대기열(실제 v12 판정패 replay.json: 우리 W 의 81%·최대 426명이 역 위에서 턴당 1회·5명 TELE 를 기다림).
    # 역 경유 경로에 '역 위 대기 인원 ÷ 5' 턴을 더하고, 역에서 기다릴지도 실제 대기열로 판단한다. False = v13
    "tele_queue": True,  # v14: False → True
    # 실제 v12 패배 4/5 = 우리 진영 학생회관(공학관) 상실 후 방치(replay.json 94턴·(7) 136턴). 모두 0 이면 v13 과 같다.
    "retake_w": 1.071,               # 적이 가진 '우리 쪽' 학생회관·공학관의 F 목표·공성 가치 배율 (1 + retake_w) v14: 0.0 → 0.3904 v15: 0.3904 → 0.7693 v17: 0.7693 → 1.071
    "retake_risk": 0.305,            # 그 건물의 목표 위험 감점을 이 비율만큼 덜어낸다(1 = 위험 무시) v14: 0.0 → 0.0979 v15: 0.0979 → 0.3816 v17: 0.3816 → 0.305
    "eco_block_extra": 2,          # 우리 학생회관·공학관은 진입 차단 반경(f_block)을 이만큼 넓힌다((10): 빈 학생회관을 적 F 혼자 6번 뒤집음) v14: 0 → 3 v15: 3 → 2
    "eco_block_worth": 6.317,        # 그 차단 작업 가치 가산 v14: 0.0 → 2.8223 v15: 2.8223 → 4.3944 v17: 4.3944 → 6.317
    "rush_k": 0.3173,                 # rush_turn 까지 적 W − 아군 W 격차 1명당 최소 F 를 rush_k 명 줄인다((8) 초반 러시: 40턴 W 33 대 78) v14: 0.0 → 0.1173 v15: 0.1173 → 0.306 v17: 0.306 → 0.3173
    "rush_turn": 40,
    # 경제 기습(사용자 제안): 적 학생회관·공학관이 가까우면 광장 대치보다 먼저 빼앗아 수입·W 단가 우위로 광장을 되찾는다.
    # 깃발 뽑힘 방지(사용자 제안): 우리 건물 위 우리 F 는 적 W 하나에 죽으며 건물이 즉시 중립이 된다.
    # 실측(v14, 480경기): 뽑힘 경기당 0.27 = 이번 턴 진입 0.09 + 머물던 F 0.18(87% 역 — W 가 TELE 를 먼저 써 F 가 역에서 대기).
    "f_own_R": 5,                  # F 가 목표 아닌 우리 건물 칸을 지날 때, R 칸 안 적 W > 그 칸 엄호면 같은 거리의 다른 칸을 먼저 고른다. 0 = 끔 v15: 0 → 3 v17: 3 → 5
    "f_own_wait": False,           # 위의 경우 대안이 없으면 한 턴 기다린다(강한 버전)
    "f_no_station_wait": True,    # TELE 가 이미 쓰인 턴에 F 는 역 위에서 기다리지 않고 걷는다 v15: False → True
    # 방어 반응(적 F 요격·위협 건물 경계·진입 차단). False 는 실제 서버 상대 모방용(위협에 2턴 안 반응 12~24%, tools/real_react.py)
    "react": True,
    # 공학관 비대칭(초반 W 격차 분해: 주원인이 W 단가): 2개여도 할인은 겹치지 않고, 하나뿐인 것을 잃으면 단가 2 → 3.
    "eng_last_extra": 0,           # 우리 공학관이 하나뿐이면 진입 차단 반경을 이만큼 더 넓힌다
    "eng_last_w": 0.0,             # 그 차단 작업 가치 가산
    "eng_last_need": 0,            # 그 차단 인원 여유
    "eng_deny_w": 0.0,             # 상대 공학관이 하나뿐이면 그 공학관 F 목표·공성 가치 × (1 + eng_deny_w)
    "garrison_n": 0,               # 우리 건물 칸 최소 주둔 인원. 0 = 끔
    "garrison_types": "eco",       # eco = 학생회관·공학관만 | all = 모든 건물
    "garrison_w": 0.0,             # 주둔 작업 가치 가산(작업 가치 = garrison_w + 건물 가치)
    "plaza_bonus": 0.0,          # 광장 가치 가산(점수 3 고정·점령 비용 4). 0 = v14
    "siege_spread": 1,            # 남는 W 를 상위 몇 개 공성 목표(가장 가까운 곳)로 나눌지. 1 = v14(최우선 목표 하나)
    "early_eco_w": 0.0,            # early_eco_turn 까지 학생회관·공학관 F 목표 가치 × (1 + early_eco_w). 0 = 끔
    "early_eco_turn": 40,
    "hub_frac": 0.0,              # 거점 방어(사용자 제안): 남는 W 중 우리 건물 쌍 사이 거점에 둘 비율. 0 = 끔
    "hub_span": 3,                 # 짝지을 두 건물 사이 최대 거리 = 2 × hub_span
    "hub_alert": 8,                # 두 건물 중 하나라도 이 거리 안에 적 유닛이 있을 때만 거점을 운영
    "feint_n": 0,                # 미끼 W 인원(본대 공성 목표에서 feint_sep 칸 이상 떨어진 적 건물 옆에서 위협만 만든다). 0 = 끔
    "feint_sep": 3,  # v15: 5 → 3
    "raid_w": 0.0,                 # 적 소유 학생회관·공학관 가치 × (1 + raid_w × 근접도), 근접도 = max(0, 1 − 우리 생산 거점 거리 / raid_D)
    "raid_D": 10,
    "raid_from": "spawn",          # 근접도 기준: spawn(우리 생산 거점) | army(가장 가까운 아군 W)
    "plaza_standoff": 0.0,         # 광장 3칸 안 적 W 가 아군보다 많으면(대치) 광장 가치 × (1 − plaza_standoff)
    # --- dev12: 9/29 20시 실전 패배(신촌을못가·참새튀김기·AIKU) 사용자 관찰 대책. 모두 0/False = v15 ---
    # 경제 열세 탈환(사용자: 학생회관·공학관이 없을 때는 적 진영의 것이든 우리 진영의 것이든 되찾는 것이 먼저):
    # 우리 학생회관(공학관) 수가 상대보다 적으면 적 소유 학생회관(공학관) 전부의 F 목표·공성 가치 × (1 + eco_def_w), 위험 감점 × (1 − eco_def_risk)
    "eco_def_w": 1.421,  # v17: 0.0 → 1.421
    "eco_def_risk": 0.5229,  # v17: 0.0 → 0.5229
    # 그때 가장 가까운 적 소유 학생회관·공학관 하나에 공격대 작업(인원 = 2칸 안 적 W + eco_strike, 가치 = 건물 가치 + eco_strike_worth). 0 = 끔
    "eco_strike": 5,  # v16: 0 → 3 v17: 3 → 5
    "eco_strike_worth": 6.0,
    "eco_strike_stage": 2,         # 공격대가 모자라면 목표 이 칸 밖에서 모인다
    "eco_strike_R": 3,             # 목표 이 칸 안 적 W 를 필요 인원에 넣는다 v17: 2 → 3
    "eco_strike_mode": "home",    # short = 종류별 수 열세 | home = 열세 또는 우리 진영 학생회관·공학관을 적이 가짐 | sum = 둘의 합계 열세 v18: "short" → "home"
    "eco_strike_stick": False,     # 목표가 유효한 동안(적 소유) 같은 목표를 유지한다
    "eco_strike_min_turn": 0,      # 이 턴부터만 공격대를 보낸다
    "cv_align": 0, "cv_align_gain": 2.0,  # existing-W/F target alignment
    "eco_raid_t0": 15, "eco_raid_t1": 160,   # dev39 선제 경제 기습 구간(t1 = 0 이면 끔)
    "eco_raid_n": 6, "eco_raid_minw": 20,
    # dev48 상위 8팀 대비 적진 중립화 31~80턴 5.3 vs 2.5, 81~160턴 4.5 vs 1.7: 기습 목표 수(eco_raid_k)·적진 건물만(eco_raid_side "enemy")
    "eco_raid_k": 1, "eco_raid_side": "any",
    # dev49 상위 팀 약점 공략: 기습 목표를 '약한 곳' 순으로(거리 + raid_soft_a × 2칸 적W + raid_far_b × (적 주력 근접)). 0 = 가장 가까운 곳(v29)
    "raid_soft_a": 1.0, "raid_far_b": 0.0,
    # F 사냥: 호위(1칸 적 W) hunt_esc 명 이하인 적 F 가 우리 W 에서 hunt_R 칸 안이면 그 칸으로 호위+1 명. 0 = 끔
    "hunt_R": 0, "hunt_esc": 1, "hunt_worth": 6.0,
    "eco_raid_always": True, "eco_raid_types": "eco+depot", "eco_raid_fw": 0.0,   # dev40 상위 팀 모방 봇용
    "eg_center_turn": 0,           # dev39 막판 중앙 집결 시작 턴(0 = 끔)
    "f_safe2": True, "f_safe2_margin": 8,   # dev40 F 2턴 안전 여유(길 칸)
    "swap_turns": 10, "swap_n": 5, "swap_worth": 0.0,   # dev40 맞교환 반격(0 = 끔)
    "ledger_thr": 0, "ledger_eng": 4.0,   # dev40 경제 장부 문턱(자원 단위, 0 = 끔)·공학관 1턴 가치
    "eco_alert_R": 0, "eco_alert_min": 5, "eco_alert_worth": 6.0,   # dev39 경제 건물 조기 경보(0 = 끔)
    # 이동 중 F 엄호(상위 팀 관찰: F 사망 경기당 상위 3.8 · 우리 9.4, F 옆 W 동행 0.69 · 0.58): 지난 턴 목표로 가는 F 의 다음 칸 v 가
    # fesc_R 칸 안 적 W 에 노출되면 v 에 (1턴 위협 + fesc_n) 명을 이번 턴 도착으로 보내 F 가 같은 턴에 들어가게 한다. 0 = 끔
    "fesc_n": 1,  # v18: 0 → 1
    "fesc_R": 2,
    "fesc_worth": 3.0,
    "fesc_always": True,           # dev39 상위 팀 모방(F 호위율 81~100% vs 우리 50~80%): 적 W 가 없어도 F 다음 칸에 항상 W 를 붙인다
    "fesc_min": 2,                 #        그때 최소 인원
    "f_need_w": False,             # dev39: F 는 이번 턴 아군 W 가 함께 도착하는 칸으로만 이동(f_need_turn 이후)
    "f_need_turn": 0,
    # dev18(F 사망 진단 tools/macro/fdeath.py: 사망의 93% 가 이미 위험한 칸에 갇힌 F, 37% 가 목표 건물 위에서 안전한 옆 칸을 두고 버티다 죽음)
    "f_goal_flee": 1,              # 목표 위 F 가 위험하면 안전한 옆 칸으로 비킨다. 1 = 전체 위협(생산 가능분 포함), 2 = 실제 적 W 만 v19: 0 → 1
    # 끝내기: F 가 이미 서 있는 비소유 건물(중립 = 이번 턴 점령 / 적 = 이번 턴 중립화)의 가치 배수. 0 = 끔
    "finish_mult": 0.0, "finish_enemy": 0,
    # 재집결: 이미 위험한 칸의 F 가 목표 쪽 다음 칸(2칸 안 적W − 우리W 압력)이 f_regroup 를 넘으면 전진 대신 압력이 가장 낮은 안전한 옆 칸으로. −1 = 끔
    "f_regroup": -1, "f_regroup_base": 1,
    # 출구 규칙: 엄호(cover) 없는 F 는 '자기 칸+이웃 중 적 W 1칸 위협이 없는 칸' 이 f_exit_min 개 미만인 칸을 위험으로 본다. 0 = 끔
    # 근거(실제 리플레이 83경기): 단독 F 가 출구 1개 칸에 들어가면 2턴 안 사망 16.8~20.7%, 출구 3개+ 0.1~0.5%, 동행 시 ≤2.2%
    "f_exit_min": 0, "f_exit_road": 0,
    # F 위험 모델(실제 리더보드 83경기 우리 F 결정으로 학습한 로지스틱, out/macro/frisk_fit.py): 칸 v 로 가면 다음 상태에 적 W 가 있을 확률.
    # f_trap_model: 갇힘 탈출을 이 위험 최소 칸으로(검증 생존 41.5→47.0%, 53.6→59.1%). f_risk_max: 0 보다 크면 예측 위험이 이를 넘는 칸을 위험으로.
    "f_trap_model": True, "f_risk_max": 0.0,
    # 동수 방어 F(팀원 tAIger 분석): 우리 건물에 적 F 가 1칸 안이고 이동 후 우리 W 가 적 1턴 위협 W 와 같으면(상쇄 후 양쪽 F 만 남음)
    # 우리 F 를 그 칸에 두거나 1칸 옆에서 들여 경합(점령·중립화 불가)으로 만든다. 0 = 끔, 1 = 학관·공학관, 2 = + 보급소·광장, 3 = 모든 건물
    "fguard": 0, "fguard_slack": 0,
    # 갇힌 F 구조(호위 진단: 엄호 없는 위험 이동은 전부 갇힘 탈출 — W 배정이 F 결정보다 먼저라 탈출 칸에 W 가 없다).
    # F 칸과 이웃이 모두 적 1턴 위협 칸이면, (1칸 안 아군 W − 위협)이 가장 큰 탈출 칸에 위협+1 명을 기한 1 로 보낸다. 0 = 끔
    "f_rescue": 0, "f_rescue_worth": 8.0,
    # 공학관 직전 W 보류(팀원 tAIger 분석: 공학관 점령 다음 턴 W 11 명 일괄 생산): 공학관이 없고 우리 F 가 중립 공학관 eng_wait 칸 안이면
    # (eng_wait_turn 턴까지) 자원 상한으로 버려질 분 말고는 W 를 사지 않는다 — 다음 턴부터 W 단가 3 → 2. 0 = 끔
    "eng_wait": 2, "eng_wait_turn": 15,
    "f_trap_min": True,           # 사방이 위험하면 목표 쪽 전진 대신 (위협 − 엄호)가 가장 작은 칸(제자리 포함) v19: False → True
    "cv_safe_equal": True,       # cv-3: W 동수 상쇄 후 적 W가 없으면 F 생존
    "sticky_R": 0,                 # dev26: 적 F 가 이 거리 안인 우리 건물 위 W 는 다른 작업에 빼앗기지 않게 먼저 묶는다(0 = 끔)
    "guard_fplus": False,          # dev26: 경계 인원에 적 F 가 2칸 안이면 +1(동수 상쇄 뒤 적 F 생존 방지)
    "recap_f": 1,                  # dev26: 잃은 우리 쪽 학관·공학관 근처에 F 가 없으면 상한을 넘겨 F 를 이만큼 더 뽑는다 v20: 0 → 1
    "final_T": 0,                  # dev26: 남은 턴이 이 이하이면 적 F 가 남은 턴 안에 닿는 우리 건물 W 를 묶고(sticky) 차단 반경을 남은 턴까지 넓힌다
    "final_w": 0.0,                #        그 막판 차단 작업 가치 가산
    "recap_R": 1,  # v20: 3 → 1
    "recap_all": False,
    "long_T": 0,                   # dev28: 우리가 가졌던 건물을 빼앗긴 지 이 턴 이상이면 "오래 빼앗김"
    "long_f": 0,                   #        오래 빼앗긴 우리 쪽 학관·공학관: 칸 위협과 무관하게 탈환 F 를 이만큼(0 = 끔)
    "blob": False,                 # dev37 군단 운용: 작업(차단·요격 등) 뒤 남는 W 전부를 한 목표로(경계·분산 공성 대신). 1위 팀 소문 "방어 없이 돌진"
    "blob_turn": 0,                #        이 턴부터
    "blob_k": 4.0,                 #        목표 점수 = (가치 + blob_bonus) / (가장 큰 W 무리에서 거리 + blob_k)
    "blob_bonus": 4.0,
    "blob_stick": 1.3,             #        직전 목표 유지 배율
    "blob_neutral": False,         #        적 건물이 없을 때만이 아니라 중립 건물도 후보
    "strike_neutral": True,       #        오래 빼앗긴 중립(적 W 가 눌러 앉음) 우리 쪽 학관·공학관도 W 공격대(eco_strike) 목표에 넣는다 v21: False → True
            #        True 면 학관·공학관만이 아니라 우리 쪽(우리 본진이 더 가까운) 모든 건물
                  #        가장 가까운 F 가 (거점 거리 + recap_R) 보다 멀면 발동
    # 대기 중인 적 무리 타격(사용자: 참새튀김기전 23~24턴 공학관에 멈춘 병력이 바로 옆 안암역 싸움에 나서지 않음):
    # 지난 턴에도 거의 같은 수로 있던 적 W 무리(≥ strike_min)가 우리 건물 2칸 안이면, 이번 턴 닿는 아군으로 (그 칸 위협 + strike_w) 명이 되면 친다. 0 = 끔
    "strike_w": 2,  # v17: 0 → 2
    "strike_min": 3,
    "strike_worth": 8.0,
    "strike_dl": 1,                # 타격 도착 기한(턴). 2 면 2칸 떨어진 무리에도 한 칸 다가선다(다음 턴 다시 판단)
    # F 겹침 방지(사용자: 30턴부터 F 2명이 한 칸에 겹쳐 다님 — 적 W 하나에 둘 다 잡힌다): 같은 거리 다음 칸 중 이번 턴 다른 F 가 가는 칸을 피한다
    "f_spread": True,  # v17: False → True
    # 우리 쪽 빈 중립 건물 쓸기(사용자: AIKU 시드에서 구석 안암역을 끝까지 안 먹음): 우리 본진이 상대 본진보다 home_margin 이상 가깝고
    # 4칸 안에 적 유닛이 없는 중립 건물의 F 목표 가치 × (1 + home_neutral_w). 0 = 끔
    "home_neutral_w": 0.0,
    "home_margin": 3,
    "late_neutral_turn": 0,        # 이 턴부터만 위 중립 쓸기를 한다(사용자: 손해여도 최종 판정 점수를 위해 나중에는 먹어야 한다)
    # 적 병력 나눠 세기(사용자: 참새튀김기전 2칸 옆 적 14명을 공학관·역 차단이 각각 전부 세어 병력을 이중으로 묶음).
    # 적 W 칸 j 를 위협받는 우리 건물들에 BFS 거리 가중 exp(−λ·d) 로 나눠 센다(가까운 건물이 대부분 가져간다). 0 = 끔(각 건물이 전부 센다)
    "block_share": 0.0,            # 진입 차단 작업의 필요 인원에 적용하는 λ
    "guard_share": 0.0,            # 경계조(1턴 위협) 필요 인원에 적용하는 λ
    "threat_share": 0.0,           # 적 F 요격 작업의 1턴 위협(우리 건물)에 적용하는 λ — 한 무리가 인접한 우리 건물 여럿을 위협할 때
    "share_floor": 0.0,            # 몫의 하한(비율). 동률로 반씩 나뉠 때 과소 방어를 막는다
    "eg_def_turn": 999,
    "eg_def": {"w_margin": 32, "guard_radius": 25, "siege_bld_bonus": 4.0, "siege_ring_value": 1.5},
}

# cv-14: confirmed against v21 on 296000-296095.
P.update({'cv_job_cost': 0.021724022405676, 'cv_cost_scope': 2, 'dist_offset': 7.31129590395668, 'block_worth': 2.745990966387539})

# 로컬 실험용: BOT_PARAMS='{"min_f": 0}' 처럼 파라미터를 덮어쓴다(제출 환경에서는 미설정)
# cv-52: fixed settings passed independent confirmation.
P.update({'cv_align': 2, 'cv_align_gain': 2})  # v29: 지원 없는 적 목표 F 감점(cv-52 의 일부)
P.update({'fguard': 3, 'dist_offset': 4.0})  # v35: 동수 방어 F(모든 건물) + F 목표 거리 보정 7.31 → 4.0
P.update({'f_rescue': 1})  # v36: 갇힌 F 의 탈출 칸에 W(위협 + 1)를 기한 1 로 보낸다
if os.environ.get("BOT_PARAMS"):
    P.update(json.loads(os.environ["BOT_PARAMS"]))

# ------------------------------------------------------------------ 스위치 판단 신경망(게이트)
# 매 턴 판세 특징 GATE_IN 개 → tanh 은닉 GATE_H 개 → 스위치 GATE_OUT 개. 출력 > 0 이면 그 턴 스위치를 켠다.
# 가중치는 ES(tools/train_nn.py --head g)로 대전 승점률만 보고 학습해 아래 GATE_W 에 상수로 넣는다(대회 공지: 소스 안 상수 허용).
# GATE_W 가 비어 있으면 게이트를 쓰지 않는다(= 스위치 기본값 그대로). 로컬 학습은 환경변수 NN_GATE 로 덮어쓴다.
GATE_IN, GATE_H, GATE_OUT = 10, 6, 5
GATE_N = GATE_IN * GATE_H + GATE_H + GATE_H * GATE_OUT + GATE_OUT     # 101
GATE_BIAS0 = -1.0                  # 학습 시작점: 은닉·출력 가중치 0, 출력 편향 −1 → 모든 스위치 꺼짐(= 게이트 없는 봇)
GATE_W = []
if os.environ.get("NN_GATE"):
    GATE_W = json.loads(os.environ["NN_GATE"])


def gate_forward(x):
    """x: 특징 GATE_IN 개 → 출력 GATE_OUT 개(선형). 학습 파라미터 θ 는 시작점에서의 차이로 둔다(θ = 0 → 모두 꺼짐)."""
    w = GATE_W
    k = 0
    h = []
    for _ in range(GATE_H):
        s = sum(w[k + i] * x[i] for i in range(GATE_IN)) + w[k + GATE_IN]
        k += GATE_IN + 1
        h.append(math.tanh(s))
    out = []
    for _ in range(GATE_OUT):
        s = sum(w[k + i] * h[i] for i in range(GATE_H)) + w[k + GATE_H] + GATE_BIAS0
        k += GATE_H + 1
        out.append(s)
    return out


# 게이트 출력 순서별 스위치: 켜짐일 때·꺼짐일 때 P 값
GATE_SWITCHES = [
    ("역전 모드", {"cb_turn": 0, "cb_margin": -99}, {"cb_turn": 999}),
    ("새로 점령한 건물 수성", {"hold_new": 10}, {"hold_new": 0}),
    ("F 몰아치기", {"eg_f_turn": 0, "eg_max_f": 8, "eg_min_f": 6}, {"eg_f_turn": 999}),
    ("가망 없는 수비 포기", {"def_hopeless": 6, "hopeless_gate": "always"}, {"def_hopeless": 0}),
    ("방어 경로", {"cov_route": True, "cov_neutral": 1.0}, {"cov_route": False}),
]


# ------------------------------------------------------------------ 지형 전처리

class Geo:
    """격자 인덱스(i = y*W + x), 이웃, 전체 쌍 최단거리를 미리 계산한다."""

    def __init__(self, init):
        self.w, self.h = init.width, init.height
        n = self.w * self.h
        self.n = n
        # 맵은 (7,7) 점대칭이다. 이웃 순서가 U·D·L·R 로 고정이면 양 팀이 똑같이 "위쪽 먼저"를
        # 선호해 미러전이 비대칭해진다. K 진영은 180° 회전한 순서를 써서 동률을 대칭으로 깬다.
        self.flip = bool(P["sym_tiebreak"]) and init.team == "K"
        order = ("D", "U", "R", "L") if self.flip else tuple(DIRS)
        self.passable = [init.passable(i % self.w, i // self.w) for i in range(n)]
        self.nbrs = [[] for _ in range(n)]
        for i in range(n):
            if not self.passable[i]:
                continue
            x, y = i % self.w, i // self.w
            for d in order:
                dx, dy = DIRS[d]
                if init.passable(x + dx, y + dy):
                    self.nbrs[i].append((d, (y + dy) * self.w + x + dx))
        self.dist = [self._bfs(i) if self.passable[i] else None for i in range(n)]

    def nkey(self, i):
        """내 본진 기준으로 정규화한 셀 순서(180° 회전 대칭). 동률 판정용."""
        return self.n - 1 - i if self.flip else i

    def _bfs(self, s):
        d = [INF] * (self.w * self.h)
        d[s] = 0
        q = deque([s])
        while q:
            u = q.popleft()
            for _, v in self.nbrs[u]:
                if d[v] == INF:
                    d[v] = d[u] + 1
                    q.append(v)
        return d

    def idx(self, x, y):
        return y * self.w + x

    def xy(self, i):
        return i % self.w, i // self.w

    def near(self, i):
        """i 자신과 한 칸 이웃(다음 턴에 i로 들어올 수 있는 칸)."""
        return [i] + [v for _, v in self.nbrs[i]]


class Memory:
    """턴을 넘어 유지하는 정보와 첫 턴 맵 분석 결과."""

    def __init__(self, init, geo):
        self.scores = {}          # 건물 id → 점수(공개 + 대칭 추론)
        self.depot_got = set()    # 내가 보너스를 받은 보급소 id
        self.prev_enW = {}        # 지난 턴 적 전투병 배치(접근 방향 추정용)
        self.react = P["adapt_mid"]   # 적 반응성(우리 공격 목표 주변 적 W 증가 ÷ 보낸 W) 지수이동평균
        self.last_goals = {}      # 지난 턴 W 를 보낸 공격 목표 → 보낸 인원
        self.prev_owner = {}      # 건물 id → 지난 턴 소유
        self.cap_turn = {}        # 건물 id → 내가 마지막으로 점령한 턴
        self.last_change = 0      # 마지막으로 건물 소유가 바뀐 턴(교착 판단용)
        pos = {(b["x"], b["y"]): b["id"] for b in init.buildings}
        self.mirror = {b["id"]: pos.get((geo.w - 1 - b["x"], geo.h - 1 - b["y"]), b["id"])
                       for b in init.buildings}
        lo, hi = CFG["regions"]["center"]
        self.central = {b["id"]: lo <= b["x"] <= hi for b in init.buildings}
        for b in init.buildings:
            if b["type"] == "PLAZA":
                self.scores[b["id"]] = CFG["buildings"]["plaza_score"]
        self.station_cells = [geo.idx(b["x"], b["y"]) for b in init.buildings if b["type"] == "STATION"]
        opp = "K" if init.team == "Y" else "Y"
        self.pair_gain = {t: self._pair_gains(init, geo, t) for t in (init.team, opp)}

    def _pair_gains(self, init, geo, team):
        """team 본진 기준, 역 짝 (a, b) 를 가졌을 때 본진→건물·적 본진 거리 단축 칸수 합.
        a→b 와 b→a 중 큰 값을 쓴다. 키는 정렬된 (a, b)."""
        base = geo.idx(*init.bases[team])
        opp_base = geo.idx(*init.bases["K" if team == "Y" else "Y"])
        goals = [geo.idx(b["x"], b["y"]) for b in init.buildings if b["type"] != "STATION"] + [opp_base]
        db = geo.dist[base]
        out = {}
        for a in self.station_cells:
            for b in self.station_cells:
                if a == b:
                    continue
                total = sum(max(0, db[t] - (db[a] + 1 + geo.dist[b][t])) for t in goals)
                key = (min(a, b), max(a, b))
                out[key] = max(out.get(key, 0), total)
        return out

    def station_worth(self, team, cell, owned_cells):
        """team 이 cell 역을 (추가로) 가질 때의 단축 가치.
        이미 가진 다른 역이 있으면 그 짝의 실제 가치, 없으면 최선 짝 가치의 절반."""
        gains = self.pair_gain[team]
        partners = [s for s in owned_cells if s != cell]
        if partners:
            g = max(gains[(min(cell, s), max(cell, s))] for s in partners)
        else:
            g = P["station_solo"] * max((v for k, v in gains.items() if cell in k), default=0)
        return min(P["station_cap"], g * P["station_scale"])


RAID_TYPES = {"eco": ("HALL", "ENG"), "eco+depot": ("HALL", "ENG", "DEPOT"), "depot": ("DEPOT",),
              "all": ("HALL", "ENG", "DEPOT", "LIBRARY", "STATION", "WATCH", "HOSPITAL", "PLAZA")}   # dev48 상위 팀: 30턴 뒤 적진 건물을 종류 없이 끊는다
GEO = None
MEM = None
DBG_TURNS = set()
DBG = []   # 진단용(tools/macro/rerun.py --dump): W 작업 배정 기록. 대회 동작과 무관

# 진단 계측(PLAN-frontier 단계 0): BOT_STATS=<폴더> 이면 매 턴 누적 지표를 <폴더>/<pid>.json 에 덮어쓴다.
# 제출 환경에서는 설정되지 않으므로 아무 일도 하지 않는다.
STATS_DIR = os.environ.get("BOT_STATS", "")
FRISK_W = [-1.885, -0.0037, -0.0012, 1.3366, 0.0186, -0.6529, -0.523, 0.1297, 0.2624, 0.0343, 0.4573, -0.1838]
FRISK_MU = [0.4119, 1.855, 0.6312, 5.4409, 1.1173, 4.346, 0.1262, 0.2198, 10.2326, 0.7378, 0.1557]
FRISK_SD = [1.5978, 4.3287, 0.8015, 7.9233, 3.7704, 8.3984, 0.3321, 0.4141, 3.9663, 5.3724, 0.3625]
FDBG = None                # 진단용: list 를 넣으면 F 판단 사유 (턴, 출발, 도착, 사유, 출발 안전, 도착 안전)
STATS = {"f_lost": 0, "gained": 0, "lost": 0, "exp_f": 0, "owned": set(), "pts140": None}


# ------------------------------------------------------------------ 의사결정

def decide(view, init):
    """dev39: 막판 수세(eg_def)를 decide 안에서 적용한다(시뮬레이터는 safe_decide 를 거치지 않아 v22 까지는 실험에 반영되지 않았다)."""
    saved = None
    if view.turn > P["eg_def_turn"]:
        saved = {k: P[k] for k in P["eg_def"]}
        P.update(P["eg_def"])
    try:
        return _decide(view, init)
    finally:
        if saved:
            P.update(saved)


def _decide(view, init):
    global GEO, MEM
    if GEO is None:
        GEO = Geo(init)
        MEM = Memory(init, GEO)
    geo, mem = GEO, MEM
    me, opp = view.team, view.opp
    remain = (TOTAL_TURNS - view.turn + 1) / TOTAL_TURNS
    # 이번 턴을 포함해 남은 이동 횟수. d 칸 떨어진 목표에는 turn + d - 1 턴에 도착하므로
    # d <= left 여야 160턴 스냅샷에 반영된다.
    left = TOTAL_TURNS - view.turn + 1
    endgame = view.turn >= P["endgame_turn"]

    # 1. 점수 기억(대칭 포함), 보급소 수령 기록
    for b in view.buildings:
        if b["score"] >= 0:
            mem.scores[b["id"]] = b["score"]
            mem.scores[mem.mirror[b["id"]]] = b["score"]
        if b["type"] == "DEPOT" and b["owner"] == me:
            mem.depot_got.add(b["id"])
        if b["owner"] == me and mem.prev_owner.get(b["id"], me) != me:
            mem.cap_turn[b["id"]] = view.turn
        if b["id"] in mem.prev_owner and mem.prev_owner[b["id"]] != b["owner"]:
            mem.last_change = view.turn
        mem.prev_owner[b["id"]] = b["owner"]
    lost_since = getattr(mem, "lost_since", None)
    if lost_since is None:
        lost_since = mem.lost_since = {}
    for b in view.buildings:
        if b["owner"] == me:
            lost_since.pop(b["id"], None)
        elif b["id"] in mem.cap_turn and b["id"] not in lost_since:
            lost_since[b["id"]] = view.turn

    bld = {geo.idx(b["x"], b["y"]): b for b in view.buildings}

    def score_of(b):
        if b["id"] in mem.scores:
            return mem.scores[b["id"]]
        return P["center_expect"] if mem.central[b["id"]] else P["side_expect"]

    def value(b):
        v = score_of(b)
        if endgame:
            # 점수는 160턴 스냅샷이다. 기능 효과(할인·수입·보급·역)는 남은 턴에 거의 쓰이지 않는다.
            return v
        t = b["type"]
        if t == "PLAZA":
            v += P["plaza_bonus"]          # 초반 진단: 진 경기에서 상대가 광장을 먼저 잡는다(22.1 vs 이긴 경기 24.6)
        if t == "HALL":
            v += P["hall_bonus"] * remain
        elif t == "DEPOT" and b["id"] not in mem.depot_got:
            v += P["depot_bonus"]
        elif t == "HOSPITAL":
            v += P["hosp_bonus"] * remain
        elif t == "ENG":
            v += P["eng_bonus"]
        elif t == "LIBRARY":
            v += P["lib_bonus"]
        elif t == "WATCH":
            v += P["watch_bonus"]
        elif t == "STATION":
            c = geo.idx(b["x"], b["y"])
            v += mem.station_worth(me, c, owned(me, "STATION"))
        if b["owner"] == opp:
            deny = P["deny"].get(t, 0)
            if t in ("HALL", "HOSPITAL"):
                deny *= remain
            elif t == "STATION":
                # 적이 짝을 이룬 역이면 그 수송로를 끊는 가치
                c = geo.idx(b["x"], b["y"])
                others = [s for s in owned(opp, "STATION") if s != c]
                deny = mem.station_worth(opp, c, others) if others else 0
            v += deny
        return v

    # 2. 유닛 집계: cell → count
    myF, myW, enF, enW, myS = {}, {}, {}, {}, {}
    for u in view.units:
        i = geo.idx(u["x"], u["y"])
        table = {("F", True): myF, ("W", True): myW, ("F", False): enF, ("W", False): enW,
                 ("S", True): myS}.get(
            (u["kind"], u["team"] == me))
        if table is not None:
            table[i] = table.get(i, 0) + u["count"]

    def owned(team, btype):
        return [i for i, b in bld.items() if b["owner"] == team and b["type"] == btype]

    def w_cost(team):
        floor = CFG["buildings"]["eng_cost_floor"]
        disc = len(owned(team, "ENG")) * CFG["buildings"]["eng_discount_per"]
        return max(floor, CFG["units"]["W"]["cost"] - disc)

    base_me = geo.idx(*init.bases[me])
    base_opp = geo.idx(*init.bases[opp])
    spawn_me = [base_me] + owned(me, "HOSPITAL")
    spawn_opp = [base_opp] + owned(opp, "HOSPITAL")
    my_stations = sorted(owned(me, "STATION"), key=geo.nkey)

    def raid_mult(b):
        """적이 가진 학생회관·공학관이 우리 생산 거점에 가까울수록 커지는 배율."""
        if not P["raid_w"] or bld[b]["owner"] != opp or bld[b]["type"] not in ("HALL", "ENG"):
            return 1.0
        src = list(myW) if P["raid_from"] == "army" and myW else spawn_me
        d = min(geo.dist[x][b] for x in src)
        return 1.0 + P["raid_w"] * max(0.0, 1.0 - d / P["raid_D"])

    def standoff_mult(b):
        """광장 대치(3칸 안 적 W > 아군 W)면 광장 가치를 낮춘다."""
        if not P["plaza_standoff"] or bld[b]["type"] != "PLAZA":
            return 1.0
        en = sum(c for i, c in enW.items() if geo.dist[i][b] <= 3)
        my = sum(c for i, c in myW.items() if geo.dist[i][b] <= 3)
        return 1.0 - P["plaza_standoff"] if en > my else 1.0

    def home_eco(b):
        """우리 본진 쪽(본진까지 거리 < 적 본진까지 거리)의 학생회관·공학관."""
        return bld[b]["type"] in ("HALL", "ENG") and geo.dist[base_me][b] < geo.dist[base_opp][b]
    eco_short = {t for t in ("HALL", "ENG") if len(owned(me, t)) < len(owned(opp, t))} if (
        P["eco_def_w"] or P["eco_def_risk"] or P["eco_strike"]) else set()
    # dev40 경제 장부(사용자: 학관·공학관을 빼앗겨 잃은 몫은 되찾아도 회복되지 않는다 — 균형을 맞추려면 적의 학관·공학관도 같은 턴만큼 잃게 해야 한다).
    # 리더보드 V22 회차: 이긴 경기는 모두 학관 턴 차 +36 ~ +132, 진 경기는 W 격차가 갈리는 시점에 −2 ~ −10.
    # 장부(자원 단위) = Σ 2 × (학관 수 차) + Σ eng_val × (공학관 보유 차) ± 15(보급소 첫 점령). 장부가 −ledger_thr 이하면
    # 지금 수가 같아도 경제 열세로 보고 적 학관·공학관을 친다(가치 가중·경제 공격대).
    if P["ledger_thr"]:
        led = getattr(mem, "ledger", 0.0)
        if getattr(mem, "ledger_turn", -1) != view.turn:
            led += 2 * (len(owned(me, "HALL")) - len(owned(opp, "HALL")))
            led += P["ledger_eng"] * ((1 if owned(me, "ENG") else 0) - (1 if owned(opp, "ENG") else 0))
            seen = getattr(mem, "opp_depot", None)
            if seen is None:
                seen = mem.opp_depot = set()
            for i, b in bld.items():
                if b["type"] == "DEPOT" and b["owner"] == opp and b["id"] not in seen:
                    seen.add(b["id"]); led -= 15
            if len(mem.depot_got) > getattr(mem, "ledger_dep", 0):
                led += 15 * (len(mem.depot_got) - getattr(mem, "ledger_dep", 0))
                mem.ledger_dep = len(mem.depot_got)
            mem.ledger, mem.ledger_turn = led, view.turn
        if led <= -P["ledger_thr"]:
            eco_short = eco_short | {"HALL", "ENG"}
    if P["eco_strike"] and P["eco_strike_mode"] == "sum":
        n_me = len(owned(me, "HALL")) + len(owned(me, "ENG"))
        n_op = len(owned(opp, "HALL")) + len(owned(opp, "ENG"))
        eco_short = {"HALL", "ENG"} if n_me < n_op else set()

    def eco_def(b):
        """경제 열세 탈환 대상: 우리가 수에서 밀리는 종류의 적 소유 학생회관·공학관(위치 무관)."""
        return bld[b]["owner"] == opp and bld[b]["type"] in eco_short

    def home_neutral(b):
        if not P["home_neutral_w"] or bld[b]["owner"] != "N" or view.turn < P["late_neutral_turn"]:
            return False
        if geo.dist[base_me][b] + P["home_margin"] > geo.dist[base_opp][b]:
            return False
        return not any(geo.dist[e][b] <= 4 for e in list(enF) + list(enW))
    can_tele = P["use_tele"] and len(my_stations) >= TELE_MIN_ST

    # 2b. 도달 지도(PLAN-frontier 단계 1): 누가 먼저 갈 수 있는가. 스위치가 모두 꺼져 있으면 계산하지 않는다.
    use_frontier = (P["frontier_targets"] or P["guard_horizon"] > 0 or P["reserve_pos"]
                    or P["lead_mode"] != "off")
    if use_frontier:
        def reach(sources):
            d = [INF] * geo.n
            q = deque()
            for s in sources:
                if d[s]:
                    d[s] = 0
                    q.append(s)
            while q:
                u = q.popleft()
                for _, v in geo.nbrs[u]:
                    if d[v] == INF:
                        d[v] = d[u] + 1
                        q.append(v)
            return d

        t_me = reach(list(myF) + list(myW) + spawn_me)
        t_opp = reach(list(enF) + list(enW) + spawn_opp)
        # 생산이 이동보다 먼저이므로 거점은 거리 0 의 공급원. 단 자원은 거점 전체가 공유하는 상한이다.
        units_me = view.my_resource // w_cost(me)
        units_opp = view.opp_resource // w_cost(opp)
        _wf = {}

        def wforce(b, k, mine):
            """k 턴 안에 b 에 올릴 수 있는 전투병 수(현재 W + 생산 가능분)."""
            key = (b, k, mine)
            if key not in _wf:
                cells, spawns, units = (myW, spawn_me, units_me) if mine else (enW, spawn_opp, units_opp)
                v = sum(c for i, c in cells.items() if geo.dist[i][b] <= k)
                if any(geo.dist[s][b] <= k for s in spawns):
                    v += units
                _wf[key] = v
            return _wf[key]

        def opp_f_reach(b, k):
            """적 깃발병(현재 또는 새로 생산)이 k 턴 안에 b 에 닿는가 = 중립화 위험."""
            return any(geo.dist[i][b] <= k for i in list(enF) + spawn_opp)

    # 3. 위협 지도: 다음 턴 각 칸에 도달 가능한 적 전투병 수(생산 가능분 포함)
    threat = [0] * (geo.w * geo.h)
    for i, c in enW.items():
        for j in geo.near(i):
            threat[j] += c
    threat_w = list(threat)            # 실제로 있는 적 W 만의 1턴 위협(생산 가능분 제외)
    # 적 자원으로 즉시 뽑을 수 있는 W. 자원은 한 번만 쓸 수 있는 공용 예산이므로 거점마다
    # 전액을 더하면(v4) 적 본진·병원 둘레가 항상 위험으로 보여 F 가 끝까지 진입하지 못한다.
    opp_spawnable = view.opp_resource // w_cost(opp)
    mode = P["spawn_threat_mode"]
    if mode == "off":
        opp_spawnable = 0
    elif mode == "half":
        opp_spawnable //= 2
    elif mode == "split":
        opp_spawnable //= len(spawn_opp)
    if opp_spawnable:
        cells = set()
        for s in spawn_opp:
            cells.update(geo.near(s))
        for j in cells:
            threat[j] += opp_spawnable
    # 적도 TELE 를 쓴다. 적 역에 있는 W 는 다음 턴 다른 적 역에 그대로 나타날 수 있어,
    # 적 역을 중립화하려고 올려둔 아군 F 가 저격당한다.
    opp_st = owned(opp, "STATION")
    # 적 반응성 갱신: 지난 턴 우리가 W 를 보낸 공격 목표 주변 적 W 가 얼마나 늘었는가
    if mem.last_goals:
        Rr = P["risk_R"]
        for g, n in mem.last_goals.items():
            now = sum(c for i, c in enW.items() if geo.dist[i][g] <= Rr)
            prev = sum(c for i, c in mem.prev_enW.items() if geo.dist[i][g] <= Rr)
            sample = max(-1.0, min(2.0, (now - prev) / max(1, n)))
            mem.react = (1 - P["adapt_alpha"]) * mem.react + P["adapt_alpha"] * sample
    mem.last_goals = {}
    eff_local_w = P["risk_local_w"]
    if P["adapt_k"]:
        eff_local_w = max(0.0, P["risk_local_w"] * (1 + P["adapt_k"] * (mem.react - P["adapt_mid"])))
    if endgame:
        eff_local_w *= P["eg_risk_scale"]
    tele_pool = 0
    if len(opp_st) >= TELE_MIN_ST:
        tele_pool = {st: min(TELE_MAX, sum(enW.get(o, 0) for o in opp_st if o != st)) for st in opp_st}
    if P["tele_threat"] and len(opp_st) >= TELE_MIN_ST:
        for b in opp_st:
            threat[b] += min(TELE_MAX, sum(enW.get(a, 0) for a in opp_st if a != b))

    commands = []

    # 4. 생산 결정
    my_w_cost = w_cost(me)
    income = CFG["resource"]["base_income"] + CFG["resource"]["hall_bonus"] * len(owned(me, "HALL"))
    has_lib = bool(owned(me, "LIBRARY"))

    def cap_cost(b):
        c = CFG["capture"]["capture_cost"]
        if b["type"] == "PLAZA":
            c *= CFG["capture"]["plaza_multiplier"]
        if has_lib:
            c -= CFG["buildings"]["library_discount"]
        return max(CFG["capture"]["min_capture_cost"], c)

    # 이번 턴 점령할 수 있는 건물(아군 F가 올라가 있거나 한 칸 옆) 비용 합 - 수입
    reachable = set()
    for i in myF:
        for j in geo.near(i):
            if j in bld and bld[j]["owner"] != me:
                reachable.add(j)
    # F 한 명은 한 건물에만 올라갈 수 있으므로 인접 건물을 모두 세면(v4) 예비비가 과다해진다
    costs = sorted((cap_cost(bld[j]) for j in reachable), reverse=True)
    if P["reserve_by_f"]:
        costs = costs[:sum(myF.values())]
    reserve = max(0, sum(costs) - income)
    budget = max(0, view.my_resource - reserve)

    targets_all = [i for i, b in bld.items() if b["owner"] != me]
    # 즉시 승리 추적: 적 보유 점수가 0 이 되는 순간 내 점수가 맵 총점의 과반이면 그 턴에 끝난다.
    # 적 건물이 몇 개 남지 않았고 내가 이미 과반이면 남은 적 건물 중립화에 가치를 몰아준다.
    opp_blds = [i for i, b in bld.items() if b["owner"] == opp]
    total_pts = sum(score_of(b) for b in bld.values())
    my_pts = sum(score_of(b) for b in bld.values() if b["owner"] == me)
    finishing = 0 < len(opp_blds) <= P["finish_k"] and 2 * my_pts > total_pts
    # 2-4 우세 굳히기: 점수 차가 벌어지면 공성을 멈추고 내 영역을 지킨다(조건이 깨지면 즉시 복귀)
    opp_pts = sum(score_of(bld[i]) for i in opp_blds)
    leading = (P["lead_mode"] == "consolidate" and view.turn >= P["lead_min_turn"]
               and my_pts - opp_pts >= P["lead_margin"])
    n_myF, n_myW = sum(myF.values()), sum(myW.values())
    n_enW = sum(enW.values())
    if GATE_W:
        # 스위치 판단 신경망: 이번 턴 판세 → 스위치별 켬/끔(P 를 턴마다 덮어쓴다)
        dm, do = geo.dist[base_me], geo.dist[base_opp]
        fwd = sum(c for i, c in enW.items() if dm[i] < do[i]) / max(1, n_enW)
        n_mb = sum(1 for b in bld.values() if b["owner"] == me)
        n_ob = len(opp_blds)
        x = [view.turn / TOTAL_TURNS, (my_pts - opp_pts) / 10.0, (n_myW - n_enW) / 50.0, (n_mb - n_ob) / 8.0,
             n_myF / 8.0, sum(enF.values()) / 8.0, (view.my_resource - view.opp_resource) / 40.0, fwd,
             min(1.0, (view.turn - mem.last_change) / 30.0), my_pts / max(1.0, total_pts)]
        for (_, on, off), o in zip(GATE_SWITCHES, gate_forward(x)):
            P.update(on if o > 0 else off)
    n_goals = len(targets_all)
    eg_f = view.turn >= P["eg_f_turn"]
    if endgame or eg_f:
        # 지금 생산한 F 가 기한 안에 닿을 수 있는 건물만 센다
        n_goals = sum(1 for t in targets_all
                      if min(geo.dist[s][t] for s in spawn_me) <= left)
    cap_f = P["max_f_early"] if view.turn <= P["early_turn"] else P["max_f"]
    if eg_f:
        cap_f = P["eg_max_f"]
    # 역전 모드(실제 v12 패배: 7점 뒤진 채 60턴 교착, F 4명으로 뒤집을 수단이 없었다)
    comeback = view.turn >= P["cb_turn"] and opp_pts - my_pts >= P["cb_margin"]
    if comeback:
        cap_f = max(cap_f, P["cb_max_f"])
        eff_local_w *= P["cb_risk_scale"]
    if P["cv_workload"] and n_myW >= n_enW:
        uncovered = sum(1 for t in targets_all
            if myW.get(t, 0) >= max(1, threat[t])
            and min((geo.dist[f][t] for f in myF), default=INF) > 3
            and min(geo.dist[z][t] for z in spawn_me) <= min(8, left))
        if uncovered:
            cap_f += min(P["cv_workload"], uncovered)
    des_F = min(cap_f, n_goals)
    recap_goal = None
    recap_n = P["recap_f"]

    def long_lost(b):
        i = bld[b]["id"]
        return i in lost_since and view.turn - lost_since[i] >= P["long_T"]
    if P["recap_f"] or P["long_f"]:
        def _rc(b):
            return (geo.dist[base_me][b] < geo.dist[base_opp][b]) if P["recap_all"] else home_eco(b)
        for b in sorted((b for b in bld if _rc(b) and bld[b]["owner"] != me and not enF.get(b, 0)),
                        key=lambda b: (-value(bld[b]), geo.nkey(b))):
            dF = min((geo.dist[i][b] for i in myF), default=INF)
            ds = min(geo.dist[s][b] for s in spawn_me)
            lg = P["long_f"] and home_eco(b) and long_lost(b)
            if dF > ds + P["recap_R"] and (lg or (P["recap_f"] and threat_w[b] <= sum(c for i, c in myW.items() if geo.dist[i][b] <= 1))):
                recap_goal = b
                recap_n = max(P["recap_f"], P["long_f"]) if lg else P["recap_f"]
                break
        if recap_goal is not None:
            des_F = max(des_F, min(n_goals, n_myF + recap_n))
    min_F = min(max(P["eg_min_f"] if eg_f else P["min_f"], P["cb_min_f"] if comeback else 0), des_F)
    if P["rush_k"] and view.turn <= P["rush_turn"]:
        min_F = max(1, min_F - int(P["rush_k"] * max(0, sum(enW.values()) - sum(myW.values()))))
    n_enF = sum(enF.values())
    if P["local_w"]:
        # 전투는 국지적 수 우위만 의미가 있다. 적 총수를 그대로 따라가면 상대가 내 생산
        # 계획을 정하게 되므로, 내 건물·유닛 근방에 실제로 와 있는 적 W 를 기준으로 삼는다.
        zone = list(myF) + [i for i, b in bld.items() if b["owner"] == me] + [base_me]
        near_enW = sum(c for j, c in enW.items()
                       if min((geo.dist[j][z] for z in zone), default=INF) <= P["local_w_radius"])
        rival = max(near_enW, int(n_enW * P["local_w_floor"]))
    else:
        rival = n_enW
    des_W = max(P["min_w"] if view.turn > 3 else 0, rival + P["w_margin"],
                n_enF if P["enf_count_fix"] else len(enF))
    nF = nW = 0
    while True:
        wantW = n_myW + nW < des_W
        wantF = n_myF + nF < des_F
        needF = n_myF + nF < min_F          # 재점령 인력은 군비 경쟁보다 먼저
        behind = n_myW + nW <= rival
        if needF:
            if budget < F_COST:
                break                        # 깃발병 비용을 모은다
            nF += 1
            budget -= F_COST
        elif wantW and (behind or not wantF) and budget >= my_w_cost:
            nW += 1
            budget -= my_w_cost
        elif wantF and budget >= F_COST:
            nF += 1
            budget -= F_COST
        elif wantW and budget >= my_w_cost:
            nW += 1
            budget -= my_w_cost
        else:
            break
    # 정찰병: F·W 생산 뒤 남는 자원으로만(여유 있을 때) 미공개 점수를 확인한다.
    # 대칭 짝은 점수가 같으므로 한쪽만 보면 된다(mem.scores 에 짝까지 기록된다).
    unknown = [i for i, b in bld.items() if b["id"] not in mem.scores]
    nS = 0
    if (P["scout_n"] and unknown and view.turn <= P["scout_until"]
            and sum(myS.values()) < P["scout_n"] and budget >= S_COST):
        nS = 1
        budget -= S_COST
    # 다음 턴 상한(40) 초과로 버려질 자원은 전투병으로 바꾼다
    cap = CFG["resource"]["resource_cap"]
    while budget >= my_w_cost and budget + income > cap:
        nW += 1
        budget -= my_w_cost
    if P["cap_fix"]:
        # 수입 단계에서 상한을 넘는 돈은 점령 단계 전에 사라진다. 예비비로 잡아 둔 돈도 예외가 아니므로
        # 예산이 아니라 실제 남는 자원 기준으로 넘칠 분을 전투병으로 바꾼다.
        left_res = view.my_resource - nF * F_COST - nW * my_w_cost - nS * S_COST
        while left_res >= my_w_cost and left_res + income > cap:
            nW += 1
            left_res -= my_w_cost
            budget -= my_w_cost
    if P["spend_all"]:
        # 실제 서버 상대들처럼 예비비를 뺀 남는 예산은 전부 전투병으로 쓴다(목표 병력 수에 도달해도 저축하지 않음)
        while budget >= my_w_cost:
            nW += 1
            budget -= my_w_cost
    if P["spend_all_hard"]:
        # 점령 예비비까지 쓴다. 수입이 점령보다 먼저 들어오므로 이번 턴 점령비는 이번 턴 수입으로 낸다.
        left_res = view.my_resource - nF * F_COST - nW * my_w_cost - nS * S_COST
        while left_res >= my_w_cost:
            nW += 1
            left_res -= my_w_cost

    def best_spawn(goals):
        if not goals:
            return base_me
        return min(spawn_me,
                   key=lambda s: (min(geo.dist[s][g] for g in goals), s != base_me, geo.nkey(s)))

    def emit_spawn(kind, n, cell, table):
        if n <= 0:
            return
        if cell == base_me:
            commands.append(spawn(kind, n))
        else:
            commands.append(spawn(kind, n, *geo.xy(cell)))
        table[cell] = table.get(cell, 0) + n

    recap_source = None
    if recap_goal is not None and nF:
        recap_source = best_spawn([recap_goal])
        emit_spawn("F", 1, recap_source, myF)
        nF -= 1
    emit_spawn("F", nF, best_spawn(targets_all), myF)
    if (P["eng_wait"] and view.turn <= P["eng_wait_turn"] and not owned(me, "ENG") and nW
            and not any(geo.dist[e][base_me] <= 3 for e in enW)
            and any(b["type"] == "ENG" and b["owner"] == "N" and any(geo.dist[f][i] <= P["eng_wait"] for f in myF)
                    for i, b in bld.items())):
        left_res = view.my_resource - nF * F_COST - nS * S_COST
        keep = 0
        while left_res - keep * my_w_cost + income > cap and left_res - keep * my_w_cost >= my_w_cost:
            keep += 1
        nW = min(nW, keep)
    w_goals = {"enf": list(enF), "myf": list(myF), "mix": list(enF) + list(myF)}[P["w_spawn"]]
    emit_spawn("W", nW, best_spawn(w_goals or list(enF) or [base_opp]), myW)
    emit_spawn("S", nS, best_spawn(unknown), myS)

    # 목표 위험 배율(사용자 관찰 seed 2: 적 진영 깊숙한 학관·공학관을 노리다 병력이 잘림).
    # 깊이 = 내 생산 거점까지 거리 − 적 생산 거점까지 거리(클수록 적 쪽). 주변 우세 = 반경 안 적 W − 아군 W.
    # 전개 시뮬레이션: prof[t] = t 턴 안에 b 에 모을 수 있는 W (현재 W + 생산 거점에서 수입으로 뽑아 보내는 W)
    LA_MAX = 30
    _prof = {}

    def la_profile(b, mine):
        key = (b, mine)
        if key not in _prof:
            cells, spawns = (myW, spawn_me) if mine else (enW, spawn_opp)
            res = view.my_resource if mine else view.opp_resource
            team = me if mine else opp
            inc = CFG["resource"]["base_income"] + CFG["resource"]["hall_bonus"] * len(owned(team, "HALL"))
            cost = w_cost(team)
            prof = [0.0] * (LA_MAX + 1)
            for i, c in cells.items():
                d = geo.dist[i][b]
                if d <= LA_MAX:
                    prof[d] += c
            for t in range(1, LA_MAX + 1):
                prof[t] += prof[t - 1]
            ds = min(geo.dist[x][b] for x in spawns)
            for t in range(ds, LA_MAX + 1):
                prof[t] += P["la_spawn_frac"] * ((res + inc * (t - ds)) // cost)
            _prof[key] = prof
        return _prof[key]

    def la_mult(b, ta):
        """ta 턴에 도착해 탈취할 수 있는가, 그 뒤 la_hold 턴 동안 지킬 수 있는가."""
        if not P["lookahead"]:
            return 1.0
        ta = min(int(ta), LA_MAX)
        M, E = la_profile(b, True), la_profile(b, False)
        phi = P["la_phi"]
        if phi * E[ta] >= M[ta] and E[ta] > 0:
            return P["la_fail"]
        ts = range(ta + 1, min(LA_MAX, ta + P["la_hold"]) + 1)
        hold = sum(1 for t in ts if M[t] > phi * E[t]) / max(1, len(ts))
        return P["la_floor"] + (1 - P["la_floor"]) * hold

    _wwin = {}

    def w_within(b, k, mine):
        key = (b, k, mine)
        if key not in _wwin:
            cells = myW if mine else enW
            _wwin[key] = sum(c for i, c in cells.items() if geo.dist[i][b] <= k)
        return _wwin[key]

    def shortfall(b, ta):
        """ta 턴 뒤 b 에서 모자랄 W (적은 φ 만큼만 온다고 본다, 생산분 제외)."""
        return max(0.0, P["la_short_phi"] * w_within(b, ta, False) - w_within(b, ta, True))

    _rm = {}

    def risk_mult(b):
        if b in _rm:
            return _rm[b]
        _rm[b] = _risk_mult(b)
        return _rm[b]

    def _risk_mult(b):
        if not (P["risk_depth_w"] or eff_local_w or P["risk_decay_w"] or P["risk_spawn_w"]):
            return 1.0
        extra = 0.0
        if P["risk_decay_w"]:
            g = P["risk_gamma"]
            en = sum(c * g ** geo.dist[i][b] for i, c in enW.items() if geo.dist[i][b] <= 10)
            my = sum(c * g ** geo.dist[i][b] for i, c in myW.items() if geo.dist[i][b] <= 10)
            extra += P["risk_decay_w"] * max(0.0, en - my)
        if P["risk_spawn_w"]:
            D = P["risk_spawn_D"]
            near = lambda sp: max((D + 1 - geo.dist[x][b]) / (D + 1) for x in sp) if sp else 0.0
            extra += P["risk_spawn_w"] * max(0.0, max(0.0, near(spawn_opp)) - max(0.0, near(spawn_me)))
        depth = min(geo.dist[s][b] for s in spawn_me) - min(geo.dist[s][b] for s in spawn_opp)
        R = P["risk_R"]
        if P["risk_tele"] and tele_pool:
            extra += eff_local_w * max((tele_pool[st] for st in opp_st if geo.dist[st][b] <= R), default=0)
        local = (sum(c for i, c in enW.items() if geo.dist[i][b] <= R)
                 - sum(c for i, c in myW.items() if geo.dist[i][b] <= R))
        lw = eff_local_w
        if P["retake_risk"] and bld.get(b, {}).get("owner") == opp and home_eco(b):
            lw *= max(0.0, 1.0 - P["retake_risk"])
        if P["eco_def_risk"] and b in bld and eco_def(b):
            lw *= max(0.0, 1.0 - P["eco_def_risk"])
        return 1.0 / (1.0 + P["risk_depth_w"] * max(0, depth) + lw * max(0, local) + extra)

    # 5. 이동 도우미(일반 이동 + 역 순간이동)
    moves = {}
    tele_cmds = []
    tele_state = {"used": False, "wait": {}, "commit": {}}
    # 역별 대기 인원(턴 시작 시 역 칸 위 아군 F·W) — TELE 는 턴당 1회·최대 TELE_MAX 명뿐이다
    tele_q = {a: myW.get(a, 0) + myF.get(a, 0) for a in my_stations} if P["tele_queue"] else {}

    f_dest = {}                        # 이번 턴 F 가 도착할 칸(겹침 방지용)

    def add_move(i, kind, n, d):
        key = (i, kind, d)
        moves[key] = moves.get(key, 0) + n

    center = geo.idx(geo.w // 2, geo.h // 2)

    def prefer_f(v):
        """F 동거리 후보: 위험이 적고(필요하면) 중앙에 가까운 칸."""
        if P["f_center_pull"]:
            return (max(0, threat[v] - cover[v]), geo.dist[v][center], geo.nkey(v))
        return (max(0, threat[v] - cover[v]), geo.nkey(v))

    def prefer_w(v):
        """W 동거리 후보: 아군 W 가 모이는 칸. 전투는 수가 전부이므로 뭉쳐 다닌다."""
        if P["w_spread"] == "anti":
            return (cover[v], geo.nkey(v))
        if P["w_spread"] == "cap":
            return (cover[v] >= P["w_cap"], -cover[v], geo.nkey(v))
        return (-cover[v], geo.nkey(v))

    def f_own_risky(v, goal):
        """F 가 목표 아닌 우리 건물 칸 v 에 서면 적 W 에 잡혀 깃발이 뽑힐 위험이 있는가."""
        if v == goal or v not in bld or bld[v]["owner"] != me:
            return False
        R = P["f_own_R"]
        danger = sum(c for j, c in enW.items() if geo.dist[j][v] <= R)
        guard = cover[v] + sum(c for j, c in myW.items() if geo.dist[j][v] <= 1)
        return danger > guard

    def pref_of(kind):
        m = P["smart_step"]
        if kind == "F":
            return prefer_f if m in ("both", "f") else None
        return prefer_w if m in ("both", "w") else None

    def step_toward(i, goal, safe=None, prefer=None):
        """goal 쪽 최단 경로 다음 (방향, 칸). safe 가 주어지면 안전한 칸을 우선한다.
        prefer 가 있으면 같은 거리의 후보 중 그 기준이 좋은 칸을 고른다."""
        if i == goal or geo.dist[i][goal] >= INF:
            return None
        cur = geo.dist[i][goal]
        options = [(d, v) for d, v in geo.nbrs[i] if geo.dist[v][goal] == cur - 1]
        if prefer is not None and len(options) > 1:
            options.sort(key=lambda dv: prefer(dv[1]))
        if safe is not None:
            good = [(d, v) for d, v in options if safe(v)]
            if good:
                return good[0]
            if safe(i):
                return None          # 안전한 경로가 없으면 제자리 대기
            side = [(d, v) for d, v in geo.nbrs[i] if safe(v)]
            if prefer is not None:
                side.sort(key=lambda dv: prefer(dv[1]))
            return side[0] if side else (options[0] if options else None)
        return options[0] if options else None

    def tele_route(i, goal, safe=None):
        """역 경유 최선 경로 (총 턴 수, 출발 역 a, 도착 역 b). 걸어가기보다
        tele_min_gain 이상 빠르지 않으면 None. 총 턴 = i→a 걷기 + TELE 1턴 + b→goal 걷기."""
        if not can_tele or i == goal:
            return None
        direct = geo.dist[i][goal]
        best = None
        for a in my_stations:
            da = geo.dist[i][a]
            if da >= INF:
                continue
            for b in my_stations:
                if b == a or (safe is not None and not safe(b)):
                    continue
                via = da + 1 + geo.dist[b][goal]
                if tele_q:
                    via += tele_q.get(a, 0) // TELE_MAX
                if best is None or via < best[0]:
                    best = (via, a, b)
        if best is None or best[0] > direct - P["tele_min_gain"]:
            return None
        return best

    def eff_dist(i, goal):
        """역 순간이동을 고려한 거리(목표 선택용)."""
        r = tele_route(i, goal)
        return min(geo.dist[i][goal], r[0]) if r else geo.dist[i][goal]

    def walk(i, kind, n, goal, safe, out):
        prefer = pref_of(kind)
        if kind == "F" and P["f_spread"]:
            base_s = prefer
            # 이번 턴 다른 F 가 가기로 한 칸을 뒤로(안정 정렬 — 나머지 동률 처리는 그대로)
            prefer = lambda v: (f_dest.get(v, 0) > 0,) + (base_s(v) if base_s else ())
        if kind == "F" and P["f_own_R"]:
            base_f = prefer
            # 위험 여부만 앞에 둔다. 정렬은 안정적이므로 위험하지 않은 후보끼리는 원래 순서(대칭 동률 처리)가 그대로 유지된다.
            prefer = lambda v: (f_own_risky(v, goal),) + (base_f(v) if base_f else ())
            if P["f_own_wait"]:
                base_safe = safe
                safe = lambda v: (base_safe is None or base_safe(v)) and not f_own_risky(v, goal)
        if kind == "W" and P["cov_route"] and geo.dist[i][goal] < INF:
            pv = path_cov(goal)
            base_pref = prefer
            if P["cov_route_mode"] == "secondary" and base_pref:
                # 뭉쳐 다니기(아군 W 가 모이는 칸)를 먼저, 방어 가치는 그다음 기준
                prefer = lambda v: base_pref(v)[:1] + (-pv[v],) + base_pref(v)[1:]
            else:
                prefer = (lambda v: (-pv[v],) + base_pref(v)) if base_pref else (lambda v: (-pv[v], geo.nkey(v)))
        st = step_toward(i, goal, safe, prefer)
        if kind == "W" and P["cov_lane"] and wmode.get("side_ok") and st is not None and geo.dist[i][goal] < INF:
            # 차선 변경(사용자 제안: 급하지 않은 이동은 여러 건물을 지원할 수 있는 칸을 지나간다). 격자는 이웃 칸의 목표 거리가 반드시 ±1 이라
            # 같은 거리의 옆걸음이 없다 → 한 칸 비켰다가(+1) 다음 턴 옆 줄로 전진(−1) = 2턴 추가. 도착 칸 방어 가치가 cov_lane 이상
            # 엄격히 오를 때만 한다(순환 없음). 다음 턴 이동(v → u)은 mem.lane_next 에 약속해 둔다.
            cur = geo.dist[i][goal]
            lane = lane_prev.get(i)
            if lane is not None and any(v == lane for _, v in geo.nbrs[i]) and geo.dist[lane][goal] < cur:
                st = next((d, v) for d, v in geo.nbrs[i] if v == lane)
            else:
                best = None
                for d1, v in geo.nbrs[i]:
                    if geo.dist[v][goal] != cur + 1 or (safe is not None and not safe(v)):
                        continue
                    for _, u in geo.nbrs[v]:
                        if u == i or geo.dist[u][goal] != cur:
                            continue
                        gain = cov_val[u] - cov_val[i]
                        if gain > P["cov_lane"] and (best is None or gain > best[0]):
                            best = (gain, d1, v, u)
                if best:
                    st = (best[1], best[2])
                    mem.lane_next[best[2]] = best[3]
        if kind == "W" and P["cov_side"] and wmode.get("side_ok") and st is not None:
            # 옆걸음: 거리는 그대로, 방어 가치는 엄격히 오르는 칸만(같은 거리에서 방어 가치가 계속 올라야 하므로 순환 없음)
            pv = path_cov(goal)
            cur = geo.dist[i][goal]
            side = [(pv[v], geo.nkey(v), d, v) for d, v in geo.nbrs[i]
                    if geo.dist[v][goal] == cur and cov_val[v] > cov_val[i] and (safe is None or safe(v))]
            if side:
                best = max(side, key=lambda s: (s[0], -s[1]))
                if best[0] - P["cov_lambda"] > pv[st[1]]:
                    st = (best[2], best[3])
        if st is None:
            out.append((i, n))
        else:
            add_move(i, kind, n, st[0])
            out.append((st[1], n))
        if kind == "F":
            dst = i if st is None else st[1]
            f_dest[dst] = f_dest.get(dst, 0) + n

    def advance(i, kind, n, goal, safe=None):
        """n 명을 goal 쪽으로 보내고 [(도착 칸, 인원)] 을 돌려준다.
        역 경유가 빠르면 출발 역으로 걷고, 출발 역 위에서는 TELE(턴당 1회·최대 5명)한다."""
        out = []
        r = tele_route(i, goal, safe)
        if r is None:
            walk(i, kind, n, goal, safe, out)
            return out
        via, a, b = r
        if P["tele_queue"]:
            # 용량 예약: 이번 턴 이 역에 배정한 인원(역 위 대기 + 역으로 향하는 인원)이 앞에 있으면 그만큼 늦어진다.
            ahead = tele_state["commit"].get(a, 0)
            if via + ahead // TELE_MAX > geo.dist[i][goal] - P["tele_min_gain"]:
                walk(i, kind, n, goal, safe, out)
                return out
            tele_state["commit"][a] = ahead + n
        if i != a:
            walk(i, kind, n, a, safe, out)       # 출발 역으로 이동
            return out
        if not tele_state["used"]:
            k = min(n, TELE_MAX)
            tele_cmds.append(tele(*geo.xy(i), kind, k, *geo.xy(b)))
            tele_state["used"] = True
            out.append((b, k))
            n -= k
        if n > 0 and kind == "F" and P["f_no_station_wait"]:
            walk(i, kind, n, goal, safe, out)      # 역 위 F 는 적 W 하나에 깃발이 뽑힌다 — 기다리지 않는다
            n = 0
        if n > 0:
            # 이번 턴 TELE 를 못 쓰면: 한 턴 기다렸다 TELE 하는 편이 여전히 빠르면 대기
            waited = tele_state["wait"].get(i, 0) if P["tele_queue"] else 0
            if 2 + waited // TELE_MAX + geo.dist[b][goal] <= geo.dist[i][goal] - P["tele_min_gain"]:
                out.append((i, n))
                tele_state["wait"][i] = waited + n
            else:
                walk(i, kind, n, goal, safe, out)
        return out

    # 6. 전투병 배치
    w_pool = dict(myW)                 # 아직 명령받지 않은 전투병
    cover = [0] * (geo.w * geo.h)      # 이동 후 칸별 아군 전투병 수
    tr_groups = []                    # 이번 턴 도착 위치, 실제 W 임무, 인원

    wmode = {"siege": False}

    # 방어 가치 지도: 칸마다 cov_R 칸 안 '적 유닛이 6칸 안에 있는 내 건물' 가치 합
    cov_val = [0.0] * geo.n
    lane_prev = getattr(mem, "lane_next", {}) if P["cov_lane"] else {}
    mem.lane_next = {}
    if P["cov_route"] or P["cov_side"] or P["cov_lane"]:
        en_cells = list(enF) + list(enW)
        my_cells = list(myF) + list(myW)
        for p, b in bld.items():
            if not any(geo.dist[p][e] <= 6 for e in en_cells):
                continue
            if b["owner"] == me:
                v = value(b)
            elif b["owner"] == "N" and P["cov_neutral"] and any(geo.dist[p][e] <= 6 for e in my_cells):
                v = P["cov_neutral"] * value(b)      # 경합 중립 건물: 지나가며 견제하면 적 F 진입을 막는다
            else:
                continue
            if v:
                dp = geo.dist[p]               # 장애물 칸의 거리표는 None 이므로 건물 쪽 행을 쓴다
                for c in range(geo.n):
                    if dp[c] <= P["cov_R"]:
                        cov_val[c] += v
    _pcov = {}
    # 수비 포기는 상황 조건을 만족할 때만 자동으로 켠다(상시 켜면 지킬 수 있던 건물까지 버린다)
    gate = P["hopeless_gate"]
    hope_on = bool(P["def_hopeless"]) and (
        gate == "always"
        or (gate == "outnumbered" and n_myW + P["gate_margin"] <= n_enW)
        or (gate == "behind" and my_pts + P["gate_margin"] < opp_pts))

    def hopeless(b):
        """주변(risk_R 칸) 적 W 가 아군 W 보다 def_hopeless 이상 많으면 수비를 포기한다."""
        if not hope_on:
            return False
        R = P["risk_R"]
        gap = (sum(c for i, c in enW.items() if geo.dist[i][b] <= R)
               - sum(c for i, c in myW.items() if geo.dist[i][b] <= R))
        return gap >= P["def_hopeless"]

    def path_cov(g):
        """pv[c] = c 에서 g 까지 최단 경로 중 방어 가치 합(g 제외)이 가장 큰 값."""
        if g not in _pcov:
            dg = geo.dist[g]
            pv = [0.0] * geo.n
            for c in sorted((c for c in range(geo.n) if dg[c] < INF and c != g), key=lambda c: dg[c]):
                pv[c] = cov_val[c] + max((pv[u] for _, u in geo.nbrs[c] if dg[u] == dg[c] - 1), default=0.0)
            _pcov[g] = pv
        return _pcov[g]

    def send_w(g, need, stage_dist, deadline=INF):
        """w_pool 에서 g 에 가까운 순으로 need 명을 보낸다.
        deadline 안에 도착할 수 있는 인원만으로 need 를 채울 수 있으면 그 인원만 쓴다.
        모인 인원이 need 에 못 미치면 stage_dist 칸 밖에서 대기하며 모은다."""
        near_ws = sorted((eff_dist(i, g), geo.nkey(i), i)
                         for i, c in w_pool.items() if c > 0 and geo.dist[i][g] < INF)
        if DBG is not None and view.turn in DBG_TURNS:
            DBG.append((wmode.get("tag", "?"), geo.xy(g), bld[g]["type"][:4] if g in bld else "", need,
                        sum(w_pool[t[2]] for t in near_ws), [(geo.xy(t[2]), w_pool[t[2]], t[0]) for t in near_ws[:4]]))
        if P["cv_source_cost"]:
            def source_key(item):
                d, tie, i = item
                penalty = 0
                if i != g and i in bld and bld[i]["owner"] == me:
                    eta = min((geo.dist[e][i] for e in enF), default=INF)
                    if eta <= 3 and w_pool[i] + cover[i] <= threat[i] + 1:
                        penalty = P["cv_source_cost"] * value(bld[i]) / max(1, eta)
                return (d + penalty, tie)
            near_ws.sort(key=source_key)
        timely = [t for t in near_ws if t[0] <= deadline]
        if deadline < INF and sum(w_pool[t[2]] for t in timely) >= need:
            near_ws = timely
        enough = sum(w_pool[t[2]] for t in near_ws) >= need
        wmode["side_ok"] = deadline >= INF and wmode["siege"]   # 공성·잔여 이동만(요격·경계·차단은 서둘러야 한다)
        left = need
        for d, _, i in near_ws:
            if left <= 0:
                break
            n = min(left, w_pool[i])
            w_pool[i] -= n
            left -= n
            if not enough and d <= stage_dist:
                cover[i] += n
                if P["tactical_rollout"]:
                    tr_groups.append((i, g, n))
                continue
            wsafe = None
            if P["w_no_losing"]:
                wsafe = (lambda n: lambda v: threat[v] == 0 or cover[v] + n > threat[v])(n)
            elif P["siege_no_losing"] and wmode["siege"]:
                wsafe = (lambda n: lambda v: threat_w[v] == 0 or cover[v] + n > threat_w[v])(n)
            if g in bld and bld[g]["owner"] != me:
                mem.last_goals[g] = mem.last_goals.get(g, 0) + n
            for dest, k in advance(i, "W", n, g, wsafe):
                cover[dest] += k
                if P["tactical_rollout"]:
                    tr_groups.append((dest, g, k))

    def w_eta(g):
        """g 까지 가장 가까운 대기 전투병의 거리."""
        return min((geo.dist[i][g] for i, c in w_pool.items() if c > 0), default=INF)

    # 1턴 위협 나눠 세기: 적 W 칸 i 가 다음 턴 닿는 우리 건물이 둘 이상이면 exp(−λ·d) 비율만 그 건물 위협으로 센다
    thr_sh = {}
    if P["threat_share"]:
        lam = P["threat_share"]
        for i, c in enW.items():
            B = [b for b in geo.near(i) if b in bld and bld[b]["owner"] == me]
            if len(B) < 2:
                continue
            ws = {b: math.exp(-lam * geo.dist[i][b]) for b in B}
            tot = sum(ws.values())
            for b, w in ws.items():
                thr_sh[b] = thr_sh.get(b, 0.0) + c * (1.0 - max(w / tot, P["share_floor"]))

    def thr(b):
        return threat[b] - int(thr_sh.get(b, 0.0)) if thr_sh else threat[b]

    # 적 깃발병 요격: 다음 목표 건물을 예측해 적보다 먼저(또는 동시에) 도착한다
    jobs = []  # (가치, 목표 칸, 필요 인원, 도착 기한, 집결 거리)
    for e, c in (enF.items() if P["react"] else ()):
        if not P["predict"]:
            # v2 방식: 가장 가까운 비적 건물 + 현재 위치
            cands = [i for i, b in bld.items() if b["owner"] != opp and enF.get(i, 0) == 0]
            g = e if (e in bld and bld[e]["owner"] != opp) else (
                min(cands, key=lambda i: (geo.dist[e][i], geo.nkey(i))) if cands else e)
            worth = 2.0 + (value(bld[g]) if g in bld else 0) + (1.0 if g in bld and bld[g]["owner"] == me else 0)
            jobs.append((worth, g, thr(g) + 1, INF, -1))
            if g != e:
                jobs.append((worth * 0.8, e, threat[e] + 1, INF, -1))
            continue
        escort = sum(n for j, n in enW.items() if geo.dist[e][j] <= P["escort_radius"])
        need = escort + 1
        if e in bld and bld[e]["owner"] != opp:
            # 이미 건물 위: 점령·중립화 진행 중이므로 곧바로 제거
            worth = 3.0 + value(bld[e]) + (1.5 if bld[e]["owner"] == me else 0)
            jobs.append((worth, e, max(need, threat[e] + 1), INF, -1))
            continue
        cands = [i for i, b in bld.items() if b["owner"] != opp and enF.get(i, 0) == 0]
        cands.sort(key=lambda i: (geo.dist[e][i], geo.nkey(i)))
        if P["pred_chase"] and cands:
            g0 = cands[0]
            chase = (2.0 + value(bld[g0]) + (1.0 if bld[g0]["owner"] == me else 0)) * P["chase_mult"]
            jobs.append((chase, e, max(need, threat[e] + 1), INF, -1))   # 적 F 직접 추격
        for rank, g in enumerate(cands[:P["predict_top"]]):
            ta = geo.dist[e][g]
            # 아군 건물은 중립화(1턴) 뒤 점령되므로 한 턴 여유가 있다
            deadline = ta + (1 if bld[g]["owner"] == me else 0)
            worth = P["pred_mult"] * (2.0 + value(bld[g]) + (1.5 if bld[g]["owner"] == me else 0)) / (1 + rank)
            if w_eta(g) > deadline:
                worth *= P["late_penalty"]
            gneed = max(need, threat[g] + 1) if P["pred_need_threat"] else need
            jobs.append((worth, g, gneed, deadline if P["pred_deadline"] else INF, -1))
    # 점령 중인 아군 깃발병 엄호(한 칸 이내 인원만 의미 있음)
    for i, c in myF.items():
        if i in bld and bld[i]["owner"] != me and threat[i] > 0:
            jobs.append((value(bld[i]) + 3.0, i, threat[i] + 1, 1, INF))
    # 진입 대기 중인 깃발병의 목표 칸 정리: F 가 옆에서 엄호를 기다리다 죽는 일이 가장 많았다.
    # W 가 이번 턴 그 칸에 도착해 적보다 많아지면 F 가 같은 턴에 들어가 점령한다(7번 safe 판정이 cover 를 본다).
    if P["escort_wait"]:
        seen = set()
        for i in myF:
            for b in bld:
                if (b in seen or bld[b]["owner"] == me or threat[b] == 0
                        or geo.dist[i][b] > P["escort_dist"]):
                    continue
                seen.add(b)
                jobs.append((value(bld[b]) + P["escort_bonus"], b, threat[b] + P["escort_extra"], INF, -1))
    def shared_count(cands, lam):
        """cands = {건물 칸: 반경 k}. 반경 안 적 W 를 exp(−λ·BFS 거리) 비율로 나눠 센 건물별 인원(실수)."""
        out = {b: 0.0 for b in cands}
        for j, c in enW.items():
            ws = {b: math.exp(-lam * geo.dist[j][b]) for b, k in cands.items() if geo.dist[j][b] <= k}
            tot = sum(ws.values())
            for b, w in ws.items():
                out[b] += c * max(w / tot, P["share_floor"])
        return out

    if P["f_block"] and P["react"]:
        # 전투는 같은 칸에서만 일어난다. 적 F 가 도착하는 턴에 그 칸 위 아군 W 가 적 W 보다 많아야 건물이 산다.
        blk = []
        for b, bb in bld.items():
            if bb["owner"] != me or enF.get(b, 0) or hopeless(b):
                continue
            k = min((geo.dist[e][b] for e in enF), default=INF)
            eco = P["eco_block_extra"] and bb["type"] in ("HALL", "ENG")
            # 마지막 공학관: 잃으면 W 단가 2 → 3(50%↑). 20~40턴 W 격차의 주원인이 단가 차(이긴 경기 2.05:2.18, 진 경기 2.20:2.06)
            last_eng = bb["type"] == "ENG" and len(owned(me, "ENG")) == 1
            fin = bool(P["final_T"]) and left <= P["final_T"] and k <= left
            if k > P["f_block"] + (P["eco_block_extra"] if eco else 0) + (P["eng_last_extra"] if last_eng else 0) and not fin:
                continue
            blk.append((b, bb, k, eco, last_eng, fin))
        shared = shared_count({b: k for b, _, k, _, _, _ in blk}, P["block_share"]) if P["block_share"] else None
        for b, bb, k, eco, last_eng, fin in blk:
            if shared is not None:
                need = math.ceil(shared[b] - 1e-9) + 1 + P["block_extra"]
            else:
                need = sum(c for j, c in enW.items() if geo.dist[j][b] <= k) + 1 + P["block_extra"]
            if P["block_wR"] and eco:
                need = max(need, sum(c for j, c in enW.items() if geo.dist[j][b] <= max(k, P["block_wR"])) + 1 + P["block_extra"])
            if P["block_spawn"] and any(geo.dist[s][b] <= k for s in spawn_opp):
                need += view.opp_resource // w_cost(opp)
            if P["block_tele"] and tele_pool:
                need += max((tele_pool[st] for st in opp_st if geo.dist[st][b] <= k - 1), default=0)
            if P["block_strict"]:
                timely = sum(c for i, c in w_pool.items() if c > 0 and geo.dist[i][b] <= k)
                if timely < need:
                    continue
            jobs.append((P["block_worth"] + value(bb) + (P["eco_block_worth"] if eco else 0.0)
                         + (P["eng_last_w"] if last_eng else 0.0) + (P["final_w"] if fin else 0.0), b, need + (P["eng_last_need"] if last_eng else 0), k, -1))
    if P["hold_new"]:
        en_cells = list(enF) + list(enW)
        for b, bb in bld.items():
            ct = mem.cap_turn.get(bb["id"])
            if (bb["owner"] != me or ct is None or view.turn - ct > P["hold_new"]
                    or not any(geo.dist[b][e] <= P["hold_R"] for e in en_cells)):
                continue
            jobs.append((P["hold_worth"] + value(bb), b, threat[b] + 1, INF, -1))
    if P["plaza_hold"]:
        for i, b in bld.items():
            if b["type"] == "PLAZA" and b["owner"] == me and threat[i] > 0:
                jobs.append((100.0, i, threat[i] + P["plaza_hold"], INF, -1))
    if P["garrison_n"]:
        # 후방 최소 주둔(팀원 관찰: 상대는 격전지가 아닌 자기 건물에 W 1명을 둬 우리 F 의 단독 진입을 막는다 / 야르렁전 88턴 우리 학생회관을
        # 적 F 혼자 점령). 우리 건물 칸에 garrison_n 명을 둔다. types: eco = 학생회관·공학관, all = 모든 건물.
        for i, b in bld.items():
            if b["owner"] == me and (P["garrison_types"] == "all" or b["type"] in ("HALL", "ENG")):
                jobs.append((P["garrison_w"] + value(b), i, P["garrison_n"], INF, -1))
    def neutral_lost(b):
        return P["strike_neutral"] and bld[b]["owner"] == "N" and home_eco(b) and long_lost(b)
    home_lost = P["eco_strike_mode"] == "home" and any(
        (bb["owner"] == opp or neutral_lost(b)) and home_eco(b) for b, bb in bld.items())
    if P["swap_turns"]:
        # dev40 맞교환 반격(사용자 교훈: 빼앗긴 경제 손실은 회복되지 않으니 적 경제도 같은 턴만큼 잃게 해야 한다):
        # 우리 학관·공학관을 잃은 턴부터 swap_turns 동안, 적 진영 학관·공학관 중 가장 가까운 곳을 공격대로 친다(적 주력은 우리 쪽에 와 있다).
        prev_own = getattr(mem, "swap_prev", {})
        for b, bb in bld.items():
            if bb["type"] in ("HALL", "ENG") and prev_own.get(b) == me and bb["owner"] != me:
                mem.swap_until = view.turn + P["swap_turns"]
        mem.swap_prev = {b: bb["owner"] for b, bb in bld.items()}
        if view.turn <= getattr(mem, "swap_until", -1) and myW:
            sc = [b for b, bb in bld.items() if bb["owner"] == opp and bb["type"] in ("HALL", "ENG")
                  and geo.dist[base_opp][b] <= geo.dist[base_me][b]]
            if sc:
                g = min(sc, key=lambda b: (min(geo.dist[w][b] for w in myW), geo.nkey(b)))
                en = sum(c for j, c in enW.items() if geo.dist[j][g] <= P["eco_strike_R"])
                jobs.append((value(bld[g]) + P["eco_strike_worth"] + P["swap_worth"], g, max(threat[g], en) + P["swap_n"], INF,
                             P["eco_strike_stage"]))
    raid = (P["eco_raid_t1"] and P["eco_raid_t0"] <= view.turn <= P["eco_raid_t1"]
            and (P["eco_raid_always"] or not (eco_short or home_lost))
            and myW and sum(myW.values()) >= P["eco_raid_minw"])
    if raid:
        # dev39 상위 팀 모방: 경제가 동률이어도 15~25턴에 적 학생회관·공학관 하나를 공격대로 선제 기습
        # dev40 상위 팀 모방 봇: eco_raid_always 면 경기 내내, 대상 종류는 eco_raid_types
        rc = [b for b, bb in bld.items() if bb["owner"] == opp and bb["type"] in RAID_TYPES[P["eco_raid_types"]]
              and (P["eco_raid_side"] != "enemy" or geo.dist[base_opp][b] < geo.dist[base_me][b])]
        if enW:
            _tot = sum(enW.values())
            _mass = lambda b: sum(c * geo.dist[j][b] for j, c in enW.items()) / _tot      # 적 W 평균 거리(클수록 주력에서 멀다)
        else:
            _mass = lambda b: 0.0
        def _rkey(b):
            k = min(geo.dist[w][b] for w in myW)
            if P["raid_soft_a"]:
                k += P["raid_soft_a"] * sum(c for j, c in enW.items() if geo.dist[j][b] <= 2)
            if P["raid_far_b"]:
                k -= P["raid_far_b"] * _mass(b)
            return (k, geo.nkey(b))
        for g in sorted(rc, key=_rkey)[:max(1, P["eco_raid_k"])]:
            en = sum(c for j, c in enW.items() if geo.dist[j][g] <= P["eco_strike_R"])
            jobs.append((value(bld[g]) + P["eco_strike_worth"], g, max(threat[g], en) + P["eco_raid_n"], INF,
                         P["eco_strike_stage"]))
    if P["eco_strike"] and (eco_short or home_lost) and myW and view.turn >= P["eco_strike_min_turn"]:
        # 경제 열세: 가장 가까운(아군 W 기준) 적 소유 학생회관·공학관 하나에 이길 수 있는 공격대를 모은다(집결 2칸)
        cands = [b for b in bld if eco_def(b) or (home_lost and (bld[b]["owner"] == opp or neutral_lost(b)) and home_eco(b))]
        if cands:
            prev = getattr(mem, "eco_tgt", None)
            if P["eco_strike_stick"] and prev in cands:
                g = prev
            else:
                g = min(cands, key=lambda b: (min(geo.dist[w][b] for w in myW), geo.nkey(b)))
            mem.eco_tgt = g
            en = sum(c for j, c in enW.items() if geo.dist[j][g] <= P["eco_strike_R"])
            jobs.append((value(bld[g]) + P["eco_strike_worth"], g, max(threat[g], en) + P["eco_strike"], INF,
                         P["eco_strike_stage"]))
    if P["strike_w"] and P["react"]:
        # 대기 중인 적 무리: 지난 턴에도 같은 칸에 비슷한 수(절반 이상)가 있었고 우리 건물 2칸 안. 이번 턴 닿는 아군만으로 이길 때만 친다.
        mine_b = [b for b, bb in bld.items() if bb["owner"] == me]
        for e, c in enW.items():
            if c < P["strike_min"] or 2 * mem.prev_enW.get(e, 0) < c:
                continue
            near_b = [b for b in mine_b if geo.dist[e][b] <= 2]
            if not near_b:
                continue
            worth = P["strike_worth"] + max(value(bld[b]) for b in near_b) + (1.0 if enF.get(e, 0) else 0.0)
            jobs.append((worth, e, threat[e] + P["strike_w"], P["strike_dl"], -1))
    if P["eco_alert_R"]:
        # dev39 경제 건물 조기 경보(리더보드 V22 회차 tAIger 전 17턴: 적 W 14 + F 가 측면으로 우리 학관 2~3칸 앞, 우리 주력 33 은 광장 대치,
        # 학관 위 1명 → 19턴 상실). 적 W 가 eco_alert_R 칸 안에 eco_alert_min 이상이고 지난 턴보다 가까워졌으면 (그 수 + 1) 명을 미리 보낸다.
        for b, bb in bld.items():
            if bb["owner"] != me or bb["type"] not in ("HALL", "ENG"):
                continue
            en_now = sum(c for j, c in enW.items() if geo.dist[j][b] <= P["eco_alert_R"])
            if en_now < P["eco_alert_min"]:
                continue
            en_prev = sum(c for j, c in mem.prev_enW.items() if geo.dist[j][b] <= P["eco_alert_R"])
            d_now = sum(geo.dist[j][b] * c for j, c in enW.items() if geo.dist[j][b] <= P["eco_alert_R"]) / en_now
            d_prev = (sum(geo.dist[j][b] * c for j, c in mem.prev_enW.items() if geo.dist[j][b] <= P["eco_alert_R"]) / en_prev
                      if en_prev else P["eco_alert_R"] + 1)
            if d_now >= d_prev and en_now <= en_prev:
                continue
            jobs.append((value(bb) + P["eco_alert_worth"], b, en_now + 1, INF, -1))
    if P["f_rescue"] and P["react"]:
        for c in myF:
            if c in bld and bld[c]["owner"] == me:
                continue
            opts = [c] + [v for _, v in geo.nbrs[c]]
            if any(threat_w[v] == 0 for v in opts):
                continue
            v = max(opts, key=lambda v: (sum(n for i, n in myW.items() if geo.dist[i][v] <= 1) - threat_w[v], -threat_w[v], geo.nkey(v)))
            if sum(n for i, n in myW.items() if geo.dist[i][v] <= 1) <= threat_w[v]:
                continue                     # 이번 턴 이길 만큼 닿지 못한다
            jobs.append((P["f_rescue_worth"] * myF[c], v, threat_w[v] + 1, 1, -1))
    if P["fesc_n"] and P["react"]:
        for c in myF:
            t = getattr(mem, "f_plan", {}).get(c)
            if t is None or c == t or t not in bld or bld[t]["owner"] == me:
                continue
            st = step_toward(c, t)
            if st is None:
                continue
            v = st[1]
            if not any(geo.dist[j][v] <= P["fesc_R"] for j in enW):
                if P["fesc_always"]:
                    jobs.append((value(bld[t]) + P["fesc_worth"], v, max(threat[v] + P["fesc_n"], P["fesc_min"] * min(myF[c], 2)), 1, -1))
                continue
            jobs.append((value(bld[t]) + P["fesc_worth"], v, max(threat[v] + P["fesc_n"], P["fesc_min"] if P["fesc_always"] else 0), 1, -1))
    if P["cv_intercept"]:
        # Predicted approach to our building occupied by enemy W. Prediction is
        # a hypothesis, not a guaranteed opponent move; only locally feasible raids.
        for e in sorted(enF, key=geo.nkey):
            goals = [t for t, b in bld.items() if b["owner"] == me
                     and enW.get(t, 0) and 1 <= geo.dist[e][t] <= 4]
            if not goals:
                continue
            t = min(goals, key=lambda t: (geo.dist[e][t], -value(bld[t]), geo.nkey(t)))
            options = [v for _, v in geo.nbrs[e] if geo.dist[v][t] < geo.dist[e][t]]
            for v in options:
                need = threat[v] + 1
                if sum(n for u, n in w_pool.items() if geo.dist[u][v] <= 1) >= need:
                    jobs.append((value(bld[t]) + 2, v, need, 1, -1))
    if P["cv_cut_link"] and len(opp_st) >= TELE_MIN_ST:
        home = [t for t,b in bld.items() if b["owner"] == me]
        for t in opp_st:
            incoming = sum(enW.get(q, 0) + enF.get(q, 0) for q in opp_st if q != t)
            if incoming and min((geo.dist[t][g] for g in home), default=INF) <= 4:
                fd = min((geo.dist[f][t] for f in myF), default=INF)
                if fd <= 4:
                    jobs.append((value(bld[t]) + min(8, incoming), t, threat[t] + 1, INF, -1))
    if P["cv_neutral"]:
        for t,b in bld.items():
            if b["owner"] == "N" and min((geo.dist[f][t] for f in myF), default=INF) <= 2:
                need = max(1, threat[t])
                if sum(n for u,n in w_pool.items() if geo.dist[u][t] <= 2) >= need:
                    jobs.append((value(b) + 2, t, need, 2, -1))
    urgent_done = set()
    if P["cv_urgent"]:
        # Reserve only a feasible imminent defense, not a permanent garrison.
        urgent=[]
        for t,b in bld.items():
            if b["owner"] == me and b["type"] in ("HALL", "ENG"):
                eta = min((geo.dist[e][t] for e in enF), default=INF)
                if eta <= 2:
                    horizon = max(1, eta)
                    need = sum(n for e,n in enW.items() if geo.dist[e][t] <= horizon) + 1
                    if horizon == 1:
                        need = max(need, threat[t] + 1)
                    urgent.append((horizon, -value(b), geo.nkey(t), t, need))
        for horizon, _, _, t, need in sorted(urgent):
            if sum(n for u,n in w_pool.items() if geo.dist[u][t] <= horizon) >= need:
                send_w(t, need, -1, horizon)
                urgent_done.add(t)
    def job_key(job):
        worth, t, need, deadline, stage = job
        cost = 0
        coefficient = P["cv_job_cost"]
        scope = P["cv_cost_scope"]
        if (scope == 1 and deadline < INF
                or scope == 2 and t in bld and bld[t]["owner"] == me
                or scope == 3 and (t not in bld or bld[t]["owner"] != opp)):
            coefficient = 0
        if coefficient:
            remaining = max(0, need - cover[t])
            for d, _, n in sorted((geo.dist[u][t], geo.nkey(u), n) for u,n in w_pool.items() if n):
                used = min(n, remaining)
                cost += used * (1 + d)
                remaining -= used
                if not remaining: break
            cost += remaining * 100
        critical = (P["cv_critical_first"] and t in bld and bld[t]["owner"] == me
                    and deadline <= 2
                    and sum(n for u,n in w_pool.items() if geo.dist[u][t] <= deadline) >= need)
        return (-int(critical), -worth / (1 + coefficient * cost), geo.nkey(t))
    if P["hunt_R"] and P["react"] and myW:
        for e, c in enF.items():
            esc = sum(n for j, n in enW.items() if geo.dist[e][j] <= 1)
            if esc > P["hunt_esc"] or min(geo.dist[w][e] for w in myW) > P["hunt_R"]:
                continue
            jobs.append((P["hunt_worth"] + 2.0 * c, e, esc + 1, INF, -1))
    if P["job_maxneed"]:
        mx = {}
        for _, t, nd, _, _ in jobs:
            mx[t] = max(mx.get(t, 0), nd)
        jobs = [(w, t, mx[t], dl, st) for w, t, _, dl, st in jobs]
    jobs.sort(key=job_key)

    sR = max(P["sticky_R"], left if P["final_T"] and left <= P["final_T"] else 0)
    if sR and enF:
        for p, bb in bld.items():
            onp = w_pool.get(p, 0)
            if bb["owner"] != me or onp <= 0 or hopeless(p):
                continue
            dF = min(geo.dist[e][p] for e in enF)
            if dF > sR:
                continue
            k = min(onp, sum(c for j, c in enW.items() if geo.dist[j][p] <= dF) + 1)
            w_pool[p] -= k                 # 명령 없는 W 는 제자리에 남는다
            cover[p] += k
    done_goals = urgent_done
    wmode["tag"] = "job"
    for worth, g, need, deadline, stage in jobs:
        if g in done_goals:
            continue
        pool = sum(c for i, c in w_pool.items() if c > 0 and geo.dist[i][g] <= deadline)
        if (deadline <= 1 or (P["strike_w"] and deadline <= P["strike_dl"] and g in enW)) and pool < need:
            continue
        done_goals.add(g)
        send_w(g, need, stage, deadline)

    if P["blob"] and view.turn >= P["blob_turn"] and any(c > 0 for c in w_pool.values()):
        left_w = [(i, c) for i, c in w_pool.items() if c > 0]
        core = max(left_w, key=lambda t: (t[1], -geo.nkey(t[0])))[0]          # 가장 큰 무리
        prev = getattr(mem, "blob_goal", None)
        cands = [i for i, b in bld.items() if b["owner"] == opp or (P["blob_neutral"] and b["owner"] == "N")]
        if not cands:
            cands = [i for i, b in bld.items() if b["owner"] != me] or [base_opp]

        def bscore(i):
            v = (value(bld[i]) + P["blob_bonus"]) if i in bld else P["blob_bonus"]
            return v / (geo.dist[core][i] + P["blob_k"]) * (P["blob_stick"] if i == prev else 1.0)
        g = max(cands, key=lambda i: (bscore(i), -geo.nkey(i)))
        mem.blob_goal = g
        wmode["siege"] = True
        wmode["tag"] = "blob"
        send_w(g, sum(c for _, c in left_w), -1)
        wmode["siege"] = False

    # 굳히기(pressure): 적 W 의 접근을 관측해 공격받을 건물에 주둔을 몰아준다. 공성은 하지 않는다.
    hold = leading and P["lead_w"] == "pressure"
    rapid = leading and P["lead_w"] == "rapid"
    if rapid:
        # 사용자 설계: 건물마다 소수 주둔 + 인근 주력. 적이 H 턴 안에 모을 수 있는 수보다 많이
        # 가장 가까운(= 적보다 먼저 닿는) 아군부터 보낸다. 남는 병력은 아래 예비대(1-center)로 간다.
        Hd = P["rapid_horizon"]
        mine_b = sorted((p for p, b in bld.items() if b["owner"] == me),
                        key=lambda p: (-value(bld[p]), geo.nkey(p)))
        for p in mine_b:
            if not any(c > 0 for c in w_pool.values()):
                break
            send_w(p, max(P["rapid_garrison"], threat[p] + 1), 0)
        for p in mine_b:
            if not any(c > 0 for c in w_pool.values()):
                break
            incoming = sum(c for i, c in enW.items() if geo.dist[i][p] <= Hd)
            if incoming:
                send_w(p, incoming + 1, -1, deadline=Hd)
    if hold:
        Hh = P["hold_horizon"]

        def near_enw(b, cells):
            return sum(c for i, c in cells.items() if geo.dist[i][b] <= Hh)

        press = []
        for p, b in bld.items():
            if b["owner"] != me:
                continue
            now = near_enw(p, enW)
            trend = max(0, now - near_enw(p, mem.prev_enW))   # 늘었으면 이쪽으로 오는 중
            danger = now + P["hold_trend_w"] * trend
            if danger > 0 or opp_f_reach(p, Hh):
                press.append((-danger, -value(b), geo.nkey(p), p, danger))
        press.sort()
        for _, _, _, p, danger in press:
            if not any(c > 0 for c in w_pool.values()):
                break
            send_w(p, int(danger) + 1, 0)
        # 남는 병력은 압력 비율대로 나눠 증원한다
        total = sum(t[4] for t in press)
        left_w = sum(c for c in w_pool.values() if c > 0)
        if total > 0 and left_w:
            for _, _, _, p, danger in press:
                extra = -(-left_w * danger // total)
                if extra > 0 and any(c > 0 for c in w_pool.values()):
                    send_w(p, int(extra), -1)

    # 경계조: 적 유닛이 가까운 아군 건물에만 인원을 둔다
    enemy_cells = list(enF) + list(enW)
    guard_posts = []
    for p, b in bld.items():
        if b["owner"] != me or p in done_goals or hopeless(p):
            continue
        danger = min((geo.dist[p][e] for e in enemy_cells), default=INF)
        if danger <= P["guard_radius"]:
            guard_posts.append((-value(b), geo.nkey(p), p))
    H = P["guard_horizon"]
    if H > 0:
        # 1턴 위협 대신 H 턴 도달 전력 기준. 적 F 가 H 턴 안에 닿지 못하는 건물은 지킬 필요가 없다.
        guard_posts = [(-value(b), geo.nkey(p), p) for p, b in bld.items()
                       if b["owner"] == me and p not in done_goals and opp_f_reach(p, H)]
    fm = view.turn >= P["front_mass_turn"] and not (hold or rapid)
    g_sh = shared_count({p: 1 for _, _, p in guard_posts}, P["guard_share"]) if P["guard_share"] and guard_posts else None
    wmode["tag"] = "guard"
    for _, _, p in ([] if hold or rapid or fm or not P["react"] else sorted(guard_posts)):
        if not any(c > 0 for c in w_pool.values()):
            break
        # 같은 수면 1:1 상쇄로 모두 사라지고 적 F 가 살아남아 중립화한다 → 이기려면 적 + 1 이 필요하다
        # (나눠 세기: 1턴 위협 중 적 W 몫만 나누고 생산 가능분은 그대로 둔다)
        thr = threat[p] if g_sh is None else threat[p] - sum(c for j, c in enW.items() if geo.dist[j][p] <= 1) + math.ceil(g_sh[p] - 1e-9)
        need = (min(P["guard_cap"], wforce(p, H, False) + 1) if H > 0
                else max(1, thr + P["guard_extra"]
                         + (1 if P["guard_fplus"] and any(geo.dist[e][p] <= 2 for e in enF) else 0)))
        send_w(p, need, 0)

    # 격전지 증원: 적 W 무리 가운데 아군 W 가 hot_radius 안에 있는 곳. 전투는 1:1 상쇄라 뒤에서 기다려도
    # 병력이 보존되지 않는다 — 수가 모자라 밀리는 곳에 먼저 보내 그 칸을 이긴다.
    if P["reinforce_hot"]:
        hot = []
        for e, c in enW.items():
            mine_near = sum(n for i, n in myW.items() if geo.dist[i][e] <= P["hot_radius"])
            if mine_near:
                hot.append((-c, geo.nkey(e), e))
        for _, _, e in sorted(hot):
            if not any(c > 0 for c in w_pool.values()):
                break
            send_w(e, threat[e] + 1, -1)

    # 전선 집결: 전선 건물 = 내 건물 중 (내 거점까지 − 적 거점까지 거리) 가 큰 순 front_k 개
    front = []
    if fm:
        def depth(p):
            return min(geo.dist[x][p] for x in spawn_me) - min(geo.dist[x][p] for x in spawn_opp)
        mine_b = sorted((p for p, b in bld.items() if b["owner"] == me), key=lambda p: (-depth(p), geo.nkey(p)))
        front = mine_b[:P["front_k"]]
        for p in sorted(mine_b[P["front_k"]:], key=lambda p: (-value(bld[p]), geo.nkey(p))):
            if not any(c > 0 for c in w_pool.values()):
                break
            en = sum(c for i, c in enW.items() if geo.dist[i][p] <= P["rear_R"])
            if en:
                send_w(p, en + 1, -1, deadline=P["rear_R"])

    # 공성조: 적 소유 건물 장악 → 적 생산 거점(본진·병원)과 그 둘레 포위
    siege = []
    if fm:
        if P["fm_siege"]:
            for i, b in bld.items():
                if b["owner"] == opp:
                    siege.append(((P["siege_bld_bonus"] + value(b)) * risk_mult(i), i))
    elif leading:
        pass                           # 굳히기: 공성하지 않는다. 남는 W 는 아래 예비대 배치로 간다
    elif endgame and P["eg_garrison"]:
        # 후반: 적 깃발병이 올라온 적 건물(제거하면 즉시 중립) + 내 건물 주둔. 본진 포위는 멈춘다.
        for i, b in bld.items():
            if b["owner"] == opp and enF.get(i, 0):
                siege.append((P["siege_bld_bonus"] + value(b), i))
            elif b["owner"] == me:
                siege.append((value(b), i))
    elif P["siege"]:
        for i, b in bld.items():
            if b["owner"] == opp:
                # 수비 F 가 서 있으면 전투로 제거하는 순간 깃발이 뽑혀 중립이 된다(상대 점수 즉시 −)
                bonus = P["siege_def_bonus"] if enF.get(i, 0) else 0.0
                la = la_mult(i, min((geo.dist[w][i] for w in myW), default=LA_MAX)) if P["la_siege"] else 1.0
                sv = (P["siege_bld_bonus"] + bonus + value(b)) * risk_mult(i) * la
                if P["retake_w"] and home_eco(i):
                    sv *= 1.0 + P["retake_w"]
                if P["eco_def_w"] and eco_def(i):
                    sv *= 1.0 + P["eco_def_w"]
                sv *= raid_mult(i) * standoff_mult(i)
                if P["eng_deny_w"] and b["type"] == "ENG" and len(owned(opp, "ENG")) == 1:
                    sv *= 1.0 + P["eng_deny_w"]   # 상대의 마지막 공학관: 빼앗으면 상대 W 단가 2 → 3
                if comeback:
                    sv *= P["cb_siege_mult"]
                if P["la_short"]:
                    ta = min((geo.dist[w][i] for w in myW), default=0)
                    sv = max(0.05 * sv, sv - P["la_short"] * shortfall(i, ta))
                siege.append((sv, i))
        ring = set()
        if not (P["siege_ring_eco"] and w_cost(me) > w_cost(opp)):
            for s in spawn_opp:
                ring.update(geo.near(s))
        for c in ring:
            if c not in bld or bld[c]["owner"] != opp:
                siege.append((P["siege_ring_value"], c))
    else:
        # 순수 수비: 남는 W 는 내 건물에 가치 순으로 주둔한다
        for i, b in bld.items():
            if b["owner"] == me:
                siege.append((value(b), i))
    # 거점 방어(사용자 제안 그림): 건물마다 병력을 붙이지 않고, 우리 건물 두 개 사이의 1-중심 빈 칸(거점)에 W 를 모아
    # 어느 쪽이 공격받든 짧은 시간에 지원한다. 적 유닛이 hub_alert 칸 안에 온 건물 쌍만, 남는 W 의 hub_frac 을 가치 비율로 나눈다.
    if P["hub_frac"] > 0 and any(c > 0 for c in w_pool.values()):
        en_cells = list(enF) + list(enW)
        mine_b = sorted((p for p, b in bld.items() if b["owner"] == me), key=lambda p: (-value(bld[p]), geo.nkey(p)))
        used, hubs = set(), []
        for p in mine_b:
            if p in used:
                continue
            others = [q for q in mine_b if q != p and q not in used and geo.dist[p][q] <= 2 * P["hub_span"]]
            if not others:
                continue
            q = min(others, key=lambda q: (geo.dist[p][q], geo.nkey(q)))
            if not any(min(geo.dist[e][p], geo.dist[e][q]) <= P["hub_alert"] for e in en_cells):
                continue
            used.update((p, q))
            cells = [c for c in range(geo.n) if geo.passable[c] and c not in bld]
            h = min(cells, key=lambda c: (max(geo.dist[c][p], geo.dist[c][q]), geo.dist[c][base_me], geo.nkey(c)))
            hubs.append((value(bld[p]) + value(bld[q]), h))
        if hubs:
            total = int(sum(c for c in w_pool.values() if c > 0) * P["hub_frac"])
            tv = sum(v for v, _ in hubs)
            for v, h in hubs:
                share = int(total * v / tv)
                if share > 0 and any(c > 0 for c in w_pool.values()):
                    send_w(h, share, -1)
    def siege_key(item):
        worth, t = item
        cost = 0
        if P["cv_siege_cost"]:
            remaining = max(0, threat[t] + 1 - cover[t])
            for d, _, n in sorted((eff_dist(u,t), geo.nkey(u), n) for u,n in w_pool.items() if n):
                used = min(n, remaining)
                cost += used * (1 + d)
                remaining -= used
                if not remaining: break
            cost += remaining * 100
        return (-worth / (1 + P["cv_siege_cost"] * cost), geo.nkey(t))
    siege.sort(key=siege_key)
    wmode["siege"] = True
    # 미끼(사용자 제안): 규칙 봇은 위협받는 건물에 '위협 + 1' 명을 보내 지킨다. 본대 공성 목표 T 에서 멀리 떨어진 적 건물 D 옆 칸에
    # feint_n 명을 세워 위협만 만들고(들어가지 않는다) 적 수비를 D 로 끌어내 T 를 얇게 만든다. D 는 유효한 동안 유지한다.
    if P["feint_n"] and siege and any(c > 0 for c in w_pool.values()):
        T = siege[0][1]
        dec = [i for i, b in bld.items() if b["owner"] == opp and i != T and geo.dist[i][T] >= P["feint_sep"]]
        if dec:
            def near_w(i):
                return min((geo.dist[w][i] for w, c in w_pool.items() if c > 0), default=INF)
            prev = getattr(mem, "feint", None)
            D = prev if prev in dec else min(dec, key=lambda i: (near_w(i), geo.nkey(i)))
            mem.feint = D
            spots = [v for _, v in geo.nbrs[D] if v not in bld]
            if spots and near_w(D) < INF:
                spot = min(spots, key=lambda v: (near_w(v), geo.nkey(v)))
                send_w(spot, P["feint_n"], -1)
        else:
            mem.feint = None
    # 막판 중앙 집결은 공성보다 먼저(공성이 남는 W 를 다 써서 뒤에서는 실행되지 않았다)
    if P["eg_center_turn"] and view.turn >= P["eg_center_turn"]:
        # dev39 막판 중앙 집결(리더보드 V22 회차 점수형 패배 5판: 상대가 157~160턴에 광장·방송국·보급소를 가져감, 그때 상대 W 중앙 77~81% vs 우리 12~39%)
        # 남는 W 를 160턴 안에 닿는 중앙 건물로(점수 ÷ (거리 + 2), 적 소유는 × 2)
        cen = [b for b in bld if mem.central[bld[b]["id"]]]
        for i in sorted(w_pool, key=geo.nkey):
            if w_pool[i] <= 0:
                continue
            cand = [b for b in cen if geo.dist[i][b] <= left - 1]
            if not cand:
                continue
            g = max(cand, key=lambda b: (score_of(bld[b]) * (2 if bld[b]["owner"] == opp else 1) / (geo.dist[i][b] + 2), -geo.nkey(b)))
            send_w(g, w_pool[i], -1)
    wmode["tag"] = "siege"
    for _, g in siege:
        if not any(c > 0 for c in w_pool.values()):
            break
        send_w(g, threat[g] + 1, P["siege_stage"])

    # 전선 집결: 남는 W 전부를 전선 건물에 가치 비율로 나눈다
    if fm and front:
        left_w = sum(c for c in w_pool.values() if c > 0)
        tot_v = sum(value(bld[p]) for p in front) or 1.0
        for p in front:
            share = -(-left_w * value(bld[p]) // tot_v)
            if share > 0 and any(c > 0 for c in w_pool.values()):
                send_w(p, int(share), -1)

    # 2-3 예비대: 남는 W 를 경합 건물 전체에 가장 빨리 증원할 수 있는 칸(1-center)에 둔다
    wmode["siege"] = False
    rest = any(c > 0 for c in w_pool.values())
    if rest and (P["reserve_pos"] or leading):
        Hr = P["guard_horizon"] or 3
        contested = [p for p, b in bld.items() if b["owner"] == me and wforce(p, Hr, False) > 0]
        if not contested and rapid:
            contested = [p for p, b in bld.items() if b["owner"] == me]
        if contested:
            cand = [c for c in range(geo.n) if geo.passable[c] and t_me[c] < t_opp[c]] or contested
            center = min(cand, key=lambda c: (max(geo.dist[c][p] for p in contested), geo.nkey(c)))
            for i in sorted(w_pool, key=geo.nkey):
                if w_pool[i] > 0:
                    send_w(center, w_pool[i], -1)
    # 그래도 남은 전투병은 가장 가치 높은 공성 목표에 합류
    wmode["tag"] = "rest"
    if siege:
        top = siege[0][1]
        # 동시 다발 공성: 남는 병력을 상위 siege_spread 개 목표 중 가장 가까운 곳으로 나눈다(1 = v14, 최우선 목표 하나로 전부).
        # 실제 상대는 우리 계보보다 덜 지킨다(F 1칸 옆 도착 → 3턴 안 탈취 0.50) — 여러 곳을 동시에 누르면 더 많이 뺏을 수 있다.
        tops = [g for _, g in siege[:max(1, P["siege_spread"])]]
        for i in sorted(w_pool, key=geo.nkey):
            if w_pool[i] > 0:
                g = top if len(tops) == 1 else min(tops, key=lambda t: (geo.dist[i][t], geo.nkey(t)))
                send_w(g, w_pool[i], -1)

    # 7. 깃발병 배치
    def frisk(v, u):
        """F 가 u 에서 v 로 가면(제자리 포함) 다음 상태 v 에 적 W 가 있을 예측 확률."""
        ev = enW.get(v, 0); e1 = threat_w[v]
        k1 = sum(1 for i in enW if geo.dist[i][v] <= 1)
        f = [ev, e1, k1, w_within(v, 2, False), cover[v], w_within(v, 1, True), v in bld, v == u, geo.dist[base_opp][v], e1 - cover[v], ev > 0]
        z = FRISK_W[0] + sum(wk * (x - m) / s for wk, x, m, s in zip(FRISK_W[1:], f, FRISK_MU, FRISK_SD))
        return 1 / (1 + math.exp(-z))

    def safe(v):
        if P["f_contest_wait"] and enF.get(v, 0) and cover[v] <= threat[v]:
            return False           # 적 F 가 있는 칸에 엄호 없이 들어가면 경합으로 양쪽 모두 점령 불가
        if P["f_need_w"] and view.turn >= P["f_need_turn"] and cover[v] < 1 and not (v in bld and bld[v]["owner"] == me):
            return False           # dev39: 호위 W 없이는 움직이지 않는다(우리 건물 칸 제외)
        if (P["f_safe2"] and v not in bld
                and w_within(v, 2, False) > w_within(v, 2, True) + P["f_safe2_margin"]):
            return False           # dev40 2턴 안전 여유: 리더보드 V22 회차 F 사망 125 중 ≈85% 가 이미 갇힌 F(출발 칸부터 적 W 우세) — 갇힐 길 칸에 들어가지 않는다
        if (P["f_exit_min"] and cover[v] == 0 and not (P["f_exit_road"] and v in bld)
                and not (v in bld and bld[v]["owner"] == me)
                and sum(1 for c in [v] + [x for _, x in geo.nbrs[v]] if threat_w[c] == 0) < P["f_exit_min"]):
            return False
        if P["f_risk_max"] and not (v in bld and bld[v]["owner"] == me) and frisk(v, None) > P["f_risk_max"]:
            return False
        return threat[v] == 0 or cover[v] > threat[v] or (P["cv_safe_equal"] and cover[v] == threat[v])

    f_plan = {}           # 이번 턴 F 도착 칸 → 목표(다음 턴 이동 중 엄호용)
    f_units = []          # 명령을 기다리는 깃발병 1명 단위(칸)
    holding = set()       # 이번 턴 점령을 위해 머무는 건물
    for i, c in myF.items():
        if i in bld and bld[i]["owner"] != me and safe(i) and enF.get(i, 0) == 0:
            holding.add(i)
            if c > 1:
                f_units.extend([i] * (c - 1))
        else:
            f_units.extend([i] * c)

    targets = {}
    for i in targets_all:
        if i in holding:
            continue
        v = value(bld[i])
        if endgame:
            pass                       # 도달 기한은 배정 단계에서 거리로 반영한다
        elif bld[i]["owner"] == opp:
            v *= P["enemy_owned_mult"]
            if P["retake_w"] and home_eco(i):
                v *= 1.0 + P["retake_w"]
            if P["eco_def_w"] and eco_def(i):
                v *= 1.0 + P["eco_def_w"]
            v *= raid_mult(i)
            if P["eng_deny_w"] and bld[i]["type"] == "ENG" and len(owned(opp, "ENG")) == 1:
                v *= 1.0 + P["eng_deny_w"]
        v *= standoff_mult(i)
        if home_neutral(i):
            v *= 1.0 + P["home_neutral_w"]
        if P["early_eco_w"] and view.turn <= P["early_eco_turn"] and bld[i]["type"] in ("HALL", "ENG"):
            # 초반 경제 건물 선점: 승패가 15~40턴에 갈리고 패배의 93% 가 수입 열세(tools/macro/diagnose.py)
            v *= 1.0 + P["early_eco_w"]
        if P["eco_raid_fw"] and bld[i]["owner"] == opp and bld[i]["type"] in RAID_TYPES[P["eco_raid_types"]]:
            v *= 1.0 + P["eco_raid_fw"]    # dev40 모방 봇: 기습 대상 종류의 적 건물을 F 도 우선
        if finishing and bld[i]["owner"] == opp:
            v *= P["finish_mult"]
        if enF.get(i, 0) and cover[i] <= threat[i]:
            v *= P["enemy_f_penalty"]
        if leading and not (bld[i]["owner"] != opp and t_me[i] < t_opp[i]):
            v *= 0.05                  # 굳히기: 내 영역 안 중립 건물로 마진을 벌린다
        targets[i] = v * risk_mult(i)

    def hold_mult(t, ta):
        """2-1: 도착 시점 ta 에 그 건물을 버틸 수 있는가에 따른 목표 배율."""
        risky = opp_f_reach(t, ta + P["frontier_extra"])
        if risky and wforce(t, ta, True) < wforce(t, ta, False) + 1:
            return P["frontier_penalty"]
        return P["region_bonus"] if t_me[t] < t_opp[t] else 1.0

    final_F = {i: 1 for i in holding}

    def fdbg(u, dest, why):
        if FDBG is not None:
            FDBG.append((view.turn, geo.xy(u), geo.xy(dest), why, safe(u), safe(dest), any(safe(v) for _, v in geo.nbrs[u])))
    for i in holding:
        fdbg(i, i, 'hold')
    race_eta = {}
    if P["la_race"]:
        # 적 F 도착 턴: 현재 적 F + (생산 가능하면) 적 생산 거점에서 새로 나오는 F
        srcs = list(enF) + (spawn_opp if view.opp_resource >= F_COST else [])
        for t in targets:
            race_eta[t] = min((geo.dist[x][t] for x in srcs), default=INF)
    free_units = sorted(f_units, key=geo.nkey)
    if P["fguard"] and not endgame:
        gtypes = {1: ("HALL", "ENG"), 2: ("HALL", "ENG", "DEPOT", "PLAZA")}.get(P["fguard"])
        for b in sorted(bld, key=geo.nkey):
            if bld[b]["owner"] != me or (gtypes and bld[b]["type"] not in gtypes):
                continue
            if not any(geo.dist[e][b] <= 1 for e in enF) or threat_w[b] == 0:
                continue
            if not (threat_w[b] - P["fguard_slack"] <= cover[b] <= threat_w[b]):
                continue
            if b in free_units:
                free_units.remove(b); fdbg(b, b, 'fguard')
                final_F[b] = final_F.get(b, 0) + 1
                continue
            near = [u for u in free_units if geo.dist[u][b] == 1]
            if near:
                u = near[0]; free_units.remove(u)
                d = next(dd for dd, v in geo.nbrs[u] if v == b)
                add_move(u, "F", 1, d); fdbg(u, b, 'fguard')
                final_F[b] = final_F.get(b, 0) + 1
    tr_left = 3  # 고정 계산 상한: 후보 3개 × (진입/1턴 대기/계속 대기) × 대응 3개 × 최대 5턴
    tr_cache = {}

    def tactical_score(u, t, d, base):
        nonlocal tr_left
        # 미래 TELE는 이 국소 모델 밖이다. 관련 역이 활성화된 판은 기존 판단을 쓴다.
        if d > 3 or can_tele or len(opp_st) >= TELE_MIN_ST or left < 2:
            return base, False
        key = (u, t)
        if key not in tr_cache:
            if not tr_left:
                return base, False
            tr_left -= 1
            st = step_toward(u, t, safe, pref_of("F"))
            first = st[1] if st else u
            H = min(5, left)
            radius = H + 2
            groups = [(c, g, n) for c, g, n in tr_groups if geo.dist[c][t] <= radius]
            groups += [(c, c, n) for c, n in w_pool.items() if n and geo.dist[c][t] <= radius]
            mf = {c: n for c, n in myF.items() if geo.dist[c][t] <= radius}
            ew = {c: n for c, n in enW.items() if geo.dist[c][t] <= radius}
            ef = {c: n for c, n in enF.items() if geo.dist[c][t] <= radius}
            owner = 0 if bld[t]["owner"] == me else 1 if bld[t]["owner"] == opp else -1
            opp_cap = CFG["capture"]["capture_cost"] * (CFG["capture"]["plaza_multiplier"]
                       if bld[t]["type"] == "PLAZA" else 1)
            opp_cap = max(CFG["capture"]["min_capture_cost"], opp_cap -
                          (CFG["buildings"]["library_discount"] if owned(opp, "LIBRARY") else 0))
            scores = []
            for wait in (False, True, "hold"):
                outcomes = [rollout(geo, t, u, first, groups, mf, ew, ef,
                            (budget, view.opp_resource),
                            (income, CFG["resource"]["base_income"] +
                             CFG["resource"]["hall_bonus"] * len(owned(opp, "HALL"))),
                            (my_w_cost, w_cost(opp)), (cap_cost(bld[t]), opp_cap),
                            (spawn_me, spawn_opp), owner, bld[t]["type"], value(bld[t]), H,
                            policy, wait, {"eng": [len(owned(s, "ENG")) for s in (me, opp)],
                            "lib": [len(owned(s, "LIBRARY")) for s in (me, opp)],
                            "depot": [bld[t]["id"] in mem.depot_got, True]})
                            for policy in ("hold", "reinforce", "hunt")]
                vals = [r["gain"] - (r["losses"][0][0] * my_w_cost -
                        r["losses"][1][0] * w_cost(opp) +
                        F_COST * (not r["actor_alive"])) / H for r in outcomes]
                # 평균은 확률 추정이 아니다. 3개 가정의 평균과 최악을 반씩 반영한다.
                scores.append(0.5 * (sum(vals) / len(vals) + min(vals)))
            choose_wait = safe(u) and scores[1] > scores[0] + 0.1
            # 같은 W 명령 아래 F가 계속 기다리는 반사실과 비교한다.
            # 이미 예정된 W 전투/중립화의 이득을 F 진입의 이득으로 중복 계산하지 않는다.
            tr_cache[key] = (P["tr_weight"] * (scores[choose_wait] - scores[2]) /
                             (d + P["dist_offset"]), choose_wait)
        delta, wait = tr_cache[key]
        return base + delta, wait

    if P["cv_recap_assign"] and recap_source in free_units and recap_goal in targets:
        free_units.remove(recap_source)
        targets.pop(recap_goal)
        for dest, n in advance(recap_source, "F", 1, recap_goal, safe):
            if dest != recap_goal:
                f_plan[dest] = recap_goal
            fdbg(recap_source, dest, 'recap')
            final_F[dest] = final_F.get(dest, 0) + n
    # After all W commands, estimate actual next-cell support, not idle W stock.
    align_support = {}
    if P["cv_align"] and not endgame:
        for t in targets:
            if bld[t]["owner"] == opp and bld[t]["type"] in ("HALL", "ENG", "DEPOT"):
                ours = sum(n for w,n in enumerate(cover) if n > 0 and geo.dist[w][t] <= 2)
                enemy = sum(n for w,n in enW.items() if geo.dist[w][t] <= 2)
                align_support[t] = ours >= max(4, enemy + 2)
    arrival_cache = {}
    def arrival_mult(t, d):
        # ponytail: bounded arrival-force estimate; ignores future enemy production
        # and competing orders. Replace with rollout only if this proxy validates.
        horizon = min(6, max(2, int(d)))
        key = (t, horizon)
        if key not in arrival_cache:
            enemy = sum(n for e,n in enW.items() if geo.dist[e][t] <= horizon)
            ours = sum(n for u,n in myW.items() if geo.dist[u][t] <= horizon)
            gap = max(0, enemy - ours)
            arrival_cache[key] = 1 / (1 + P["cv_arrival"] * gap)
        return arrival_cache[key]
    while free_units and targets:
        best = None
        ranked = []
        order = sorted(targets, key=geo.nkey)
        for k, u in enumerate(free_units):
            du = geo.dist[u]
            for t in order:
                d = du[t]
                if d >= INF:
                    continue
                if can_tele:
                    d = eff_dist(u, t)
                s = targets[t]
                if endgame:
                    if d > left:
                        continue           # 160턴 안에 닿지 못한다
                    if bld[t]["owner"] == opp and d < left:
                        s *= 2             # 중립화(상대 −) 후 점령(나 +)까지 기한 안에 끝난다
                if P["lookahead"]:
                    s *= la_mult(t, d)
                if P["la_race"] and bld[t]["owner"] == "N":
                    ea = race_eta[t]
                    if ea < d:
                        s *= P["race_pen"]
                    elif ea == d:
                        s *= P["race_tie"]
                if P["la_short"]:
                    s = max(0.05 * s, s - P["la_short"] * shortfall(t, int(d)))
                if P["frontier_targets"]:
                    s *= hold_mult(t, d)
                if P["cv_arrival"] and not endgame:
                    s *= arrival_mult(t, d)
                if P["cv_align"] and not endgame and bld[t]["owner"] == opp:
                    if P["cv_align"] in (1, 3) and align_support.get(t) and d <= 6:
                        s *= P["cv_align_gain"]
                    if P["cv_align"] in (2, 3):
                        # Downweight unsupported penetration, but retain escape and safe movement.
                        fronts = [w for w,n in enumerate(cover) if n >= 3 and geo.dist[w][t] <= 4]
                        if not fronts:
                            s *= 0.5
                if P["finish_mult"] and d == 0 and (bld[t]["owner"] == "N" or (P["finish_enemy"] and bld[t]["owner"] == opp)):
                    s *= P["finish_mult"]
                s /= d + P["dist_offset"]
                key = (-s, geo.nkey(u), geo.nkey(t))
                if P["tactical_rollout"]:
                    ranked.append((key, k, t, d, s))
                if best is None or key < best[0]:
                    best = (key, k, t)
        if best is None:
            break
        wait = False
        if P["tactical_rollout"]:
            choices = []
            seen = set()
            for key, k, t, d, s in sorted(ranked):
                pair = (free_units[k], t)
                if pair in seen:
                    continue
                seen.add(pair)
                score, delay = tactical_score(free_units[k], t, d, s)
                choices.append(((-score, key[1], key[2]), k, t, delay))
                if len(choices) == 3:
                    break
            key, k, t, wait = min(choices)
            best = (key, k, t)
        _, k, t = best
        u = free_units.pop(k)
        del targets[t]
        if not wait and not safe(u):
            if P["f_goal_flee"] and u == t and (P["f_goal_flee"] == 1 or 0 < threat_w[u] >= cover[u]):
                side = [(d, v) for d, v in geo.nbrs[u] if safe(v)]
                if pref_of("F") is not None:
                    side.sort(key=lambda dv: prefer_f(dv[1]))
                if side:
                    add_move(u, "F", 1, side[0][0])
                    fdbg(u, side[0][1], 'flee')
                    final_F[side[0][1]] = final_F.get(side[0][1], 0) + 1
                    continue
            if P["f_trap_min"] and u != t and not any(safe(v) for _, v in geo.nbrs[u]):
                if P["f_trap_model"]:
                    cand = [(frisk(u, u), 1, geo.dist[u][t], geo.nkey(u), None, u)]
                    cand += [(frisk(v, u), 0, geo.dist[v][t], geo.nkey(v), d, v) for d, v in geo.nbrs[u]]
                else:
                    cand = [(threat[u] - cover[u], 1, geo.dist[u][t], geo.nkey(u), None, u)]
                    cand += [(threat[v] - cover[v], 0, geo.dist[v][t], geo.nkey(v), d, v) for d, v in geo.nbrs[u]]
                _, _, _, _, d, v = min(cand)
                if d is not None:
                    add_move(u, "F", 1, d)
                fdbg(u, v, 'trap')
                final_F[v] = final_F.get(v, 0) + 1
                continue
        if P["f_regroup"] >= 0 and not wait and u != t and not safe(u):
            press = lambda v: w_within(v, 2, False) - w_within(v, 2, True)
            fwd = [press(v) for _, v in geo.nbrs[u] if safe(v) and geo.dist[v][t] < geo.dist[u][t]]
            if not fwd or min(fwd) > P["f_regroup"]:
                side = sorted((press(v), geo.dist[base_me][v] if P["f_regroup_base"] else 0, geo.nkey(v), d, v)
                              for d, v in geo.nbrs[u] if safe(v))
                if side and (not fwd or side[0][0] < min(fwd)):
                    add_move(u, "F", 1, side[0][3])
                    fdbg(u, side[0][4], 'regroup')
                    final_F[side[0][4]] = final_F.get(side[0][4], 0) + 1
                    continue
        for dest, n in ([(u, 1)] if wait else advance(u, "F", 1, t, safe)):
            if dest != t:
                f_plan[dest] = t
            if P["f_wait_2step"] and dest == u and u != t:
                near_en = sum(c for i, c in enW.items() if geo.dist[i][u] <= 2)
                if near_en > sum(cover[j] for j in geo.near(u)):
                    side = sorted((sum(c for i, c in enW.items() if geo.dist[i][v] <= 2), geo.nkey(v), d, v)
                                  for d, v in geo.nbrs[u] if safe(v))
                    if side and side[0][0] < near_en:
                        add_move(u, "F", 1, side[0][2])
                        dest = side[0][3]
            fdbg(u, dest, 'wait' if wait else ('tele' if geo.dist[u][dest] > 1 else 'adv'))
            final_F[dest] = final_F.get(dest, 0) + n

    # 목표가 없는 깃발병: 위협받으면 피하고 아니면 대기
    for u in free_units:
        if P["f_idle_off"] and u in bld and bld[u]["owner"] == me:
            # 이미 점령한 건물 위에 서 있을 이유가 없다(표적만 된다). 본진 쪽 안전한 빈 칸으로 비킨다.
            side = sorted(((geo.dist[v][base_me], geo.nkey(v)), d) for d, v in geo.nbrs[u]
                          if safe(v) and v not in bld)
            if side:
                add_move(u, "F", 1, side[0][1])
                fdbg(u, next(v for d, v in geo.nbrs[u] if d == side[0][1]), 'idle_off')
                continue
        if not safe(u):
            side = [(d, v) for d, v in geo.nbrs[u] if safe(v)]
            if pref_of("F") is not None:
                side.sort(key=lambda dv: prefer_f(dv[1]))
            if side:
                add_move(u, "F", 1, side[0][0])
                fdbg(u, side[0][1], 'idle_flee')
                continue
        fdbg(u, u, 'idle_stay')
        final_F[u] = final_F.get(u, 0) + 1

    # 정찰병 이동: 가까운 미공개 건물로 두 칸씩(MOVE2). 도착 칸에서만 전투가 나므로 도착 칸만 안전하면 된다.
    if myS:
        def scout_key(u, t):
            d = geo.dist[u][t]
            return d - (P["scout_center_bonus"] if mem.central[bld[t]["id"]] else 0), geo.nkey(t)

        goals = set(unknown)
        for u in sorted(myS, key=geo.nkey):
            for _ in range(myS[u]):
                goal = min(goals, key=lambda t: scout_key(u, t)) if goals else None
                if goal is not None:
                    goals.discard(goal)
                    goals.discard(next((i for i, b in bld.items()
                                        if b["id"] == mem.mirror[bld[goal]["id"]]), None))
                plan = None
                if goal is not None and u != goal:
                    cur = geo.dist[u][goal]
                    opts = []
                    for d1, v1 in geo.nbrs[u]:
                        if geo.dist[v1][goal] != cur - 1:
                            continue
                        if v1 == goal:
                            opts.append((0, geo.nkey(v1), (d1,), v1))
                        for d2, v2 in geo.nbrs[v1]:
                            if geo.dist[v2][goal] == cur - 2:
                                opts.append((0, geo.nkey(v2), (d1, d2), v2))
                    opts = [o for o in opts if safe(o[3])]
                    if opts:
                        plan = min(opts, key=lambda o: (-len(o[2]), o[1]))
                if plan is None and not safe(u):
                    side = [((d,), v) for d, v in geo.nbrs[u] if safe(v)]
                    if side:
                        plan = (0, 0, side[0][0], side[0][1])
                if plan is None:
                    continue
                x, y = geo.xy(u)
                if len(plan[2]) == 2:
                    commands.append(move2(x, y, 1, *plan[2]))
                else:
                    add_move(u, "S", 1, plan[2][0])

    commands.extend(tele_cmds)
    for (i, kind, d), n in sorted(moves.items(), key=lambda kv: (geo.nkey(kv[0][0]), kv[0][1:])):
        x, y = geo.xy(i)
        commands.append(move(x, y, kind, n, d))

    # 8. 점령 우선순위: 이번 턴 깃발병이 올라갈 건물을 가치 순으로
    caps = [i for i in final_F if i in bld and bld[i]["owner"] != me]
    if caps:
        caps.sort(key=lambda i: (-value(bld[i]), geo.nkey(i)))
        commands.append(priority([geo.xy(i) for i in caps]))
    mem.prev_enW = enW
    mem.f_plan = f_plan
    if STATS_DIR:
        record_stats(view, bld, score_of, n_myF, sum(myF.values()), n_myW + nW)
    return commands


def record_stats(view, bld, score_of, f_now, f_after_spawn, w_now):
    """깃발병 손실·건물 득실·점수 추이를 누적해 파일로 남긴다(경기 도중 끝나도 마지막 턴 값이 남는다)."""
    s = STATS
    s["f_lost"] += max(0, s["exp_f"] - f_now)          # 지난 턴 끝 인원 − 이번 턴 시작 인원
    s["exp_f"] = f_after_spawn
    mine = {i for i, b in bld.items() if b["owner"] == view.team}
    s["gained"] += len(mine - s["owned"])
    s["lost"] += len(s["owned"] - mine)
    s["owned"] = mine
    my_pts = sum(score_of(b) for b in bld.values() if b["owner"] == view.team)
    opp_known = sum(b["score"] for b in bld.values() if b["owner"] == view.opp and b["score"] >= 0)
    if view.turn == 140:
        s["pts140"] = my_pts
    out = {"turn": view.turn, "team": view.team, "my_pts": my_pts, "opp_pts_known": opp_known,
           "n_bld": len(mine), "F": f_after_spawn, "W": w_now, "f_lost": s["f_lost"],
           "gained": s["gained"], "lost": s["lost"],
           "last20": None if s["pts140"] is None else my_pts - s["pts140"], "react": round(MEM.react, 3)}
    with open(os.path.join(STATS_DIR, f"{os.getpid()}.json"), "w") as f:
        json.dump(out, f)


_errors = 0


def safe_decide(view, init):
    """예외가 나도 END는 출력되도록(몰수패 방지) 빈 명령으로 대체한다."""
    global _errors
    try:
        return decide(view, init)
    except Exception:
        _errors += 1
        if _errors <= 5:
            traceback.print_exc(file=sys.stderr)
        return []


if __name__ == "__main__":
    run(safe_decide)
