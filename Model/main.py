"""깃발 대항전 전략 봇 v11.

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
"""
import json
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
    "center_expect": 2.35,      # 중앙 건물 미공개 점수 기댓값(2~4) v6: 3.0 → 2.75 v9: 2.75 → 2.35
    "side_expect": 1.08,        # 신촌·안암 건물 미공개 점수 기댓값(1~2) v6: 1.5 → 1.1 v9: 1.1 → 1.08
    "hall_bonus": 9.15,         # 학생회관 기능 가치(남은 턴 비율을 곱함). v4 2.5 → 탐색 결과 5.0 v6: 5.0 → 7.15 v9: 7.15 → 9.15
    "depot_bonus": 1.75,        # 아직 받지 않은 보급소 보너스 가치 v6: 3.0 → 1.76 v9: 1.76 → 1.75
    "hosp_bonus": 3.11,         # 병원 전진 생산 가치(남은 턴 비율을 곱함) v6: 1.0 → 3.19 v9: 3.19 → 3.11
    "eng_bonus": 9.01,          # 공학관: W 비용 3→2 는 군비 상시 할인. v4 0.5 → 5.0 v6: 5.0 → 9.13 v9: 9.13 → 9.01
    "lib_bonus": 2.41,          # 도서관: 점령 비용 −1. v4 0.5 → 2.0 v6: 2.0 → 2.03 v9: 2.03 → 2.41
    "watch_bonus": 0.2,
    "station_scale": 0.0,      # 역 가치 = 맵 분석 단축 칸수 합 × scale (실험 결과 0.08은 역효과)
    "station_cap": 4.0,
    "station_solo": 0.5,       # 짝 역이 없을 때 역 가치 반영 비율
    # 적 소유 건물 탈취 보너스(상대가 누리던 효과를 빼앗는 가치)
    "deny": {"ENG": 2.0, "LIBRARY": 1.5, "HALL": 2.0, "HOSPITAL": 1.0},
    "enemy_owned_mult": 1.68,   # 적 건물은 빼앗으면 상대 점수도 줄어든다 v6: 1.3 → 1.85 v9: 1.85 → 1.68
    "enemy_f_penalty": 0.55,    # 적 깃발병이 서 있는 건물(경합) 감점 v6: 0.3 → 0.49 v9: 0.49 → 0.55
    "dist_offset": 4.52,        # 가치 / (거리 + offset). v4 2.0 → 5.0 (가까운 목표 편중 완화) v6: 5.0 → 4.36 v9: 4.36 → 4.52
    "max_f": 6,               # 동시에 유지할 깃발병 상한. v4 7 → 12 (점령 처리량이 병목) v6: 12 → 6
    "min_f": 5,                # 전투병보다 먼저 확보할 깃발병 수 v6: 3 → 5
    "min_w": 6,                # 3턴 이후 최소 전투병 수 v6: 2 → 5 v9: 5 → 6
    "w_margin": 26,            # 적 전투병 총수 대비 여유분. v4 1 → 12 v6: 12 → 19 v9: 19 → 26
    "escort_radius": 2,        # 적 F 호위 전투병으로 볼 거리
    "predict_top": 2,          # 적 F 목표 후보 수(가까운 순)
    "late_penalty": 0.5,       # 제때 도착 못 하는 요격 가치 배율
    "guard_radius": 14,         # 적 유닛이 이 거리 안에 있는 아군 건물만 경계. v4 4 → 9 v6: 9 → 14
    "siege_bld_bonus": 7.62,    # 공성 우선순위: 적 소유 건물 v6: 5.0 → 9.75 v9: 9.75 → 7.62
    "siege_ring_value": 4.61,   # 공성 우선순위: 적 생산 거점 둘레 칸 v6: 2.0 → 4.06 v9: 4.06 → 4.61
    "tele_min_gain": 2,        # TELE 가 일반 이동보다 이만큼 이상 가까워야 사용
    "use_tele": True,          # 역 경유 경로 탐색 + TELE (v4: 경로 탐색 수정 후 사용)
    "predict": False,          # 실험 스위치: 적 F 목표 예측 요격(False 면 v2 방식, 예측은 역효과)
    "pred_need_threat": False, # 예측 요격 인원에 목표 칸 위협도 반영
    "pred_deadline": True,     # 예측 요격에서 제때 도착 가능한 인원 우선
    "pred_chase": True,        # 예측 요격과 별도로 현재 위치 추격 작업 추가
    "chase_mult": 1.4,         # 추격 작업 가치 = 가장 가까운 목표 가치 × chase_mult v6: 0.8 → 1.33 v9: 1.33 → 1.4
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
    "smart_step": "w",             # 동거리 후보 선택 기준 적용 대상 off|f|w|both (F 는 역효과)
    "siege": True,                 # 남는 W 로 적 건물·생산 거점을 공격 (False 면 순수 수비)
    "f_center_pull": True,         # F 동거리 후보에서 중앙에 가까운 칸을 선호
    # --- v6 스위치 ---
    "endgame_turn": 151,           # 이 턴부터 후반 모드(가치 = 순수 점수, 기한 안 도달 목표만). 999 = 끔 v6: 150 → 151
    "eg_garrison": False,          # 후반 모드에서 적 본진 포위를 멈추고 내 건물 주둔으로 전환
    # 막판 F 증원(실제 경기 V10 패배: 152턴 광장 상실 후 F 3명으로 8턴간 탈환 실패, 상대는 F 3 → 9)
    "eg_f_turn": 999,              # 이 턴부터 F 상한·최소를 아래 값으로(목표는 160턴 안에 닿는 건물만 센다). 999 = 끔
    "eg_max_f": 10,
    "eg_min_f": 8,
    # 진입 차단(실제 경기 상실 112건 분석: 전부 적 F 가 전 턴 1칸 옆 → 그 턴 건물 칸 위 아군 W 0).
    # 적 F 가 k(≤ f_block) 턴 안에 들어올 수 있는 내 건물에, k 턴 안에 도착하는 W 로 (k 턴 안에 닿는 적 W + 1) 명을 올린다.
    "f_block": 2,                  # 0 = 끔, 1 = 1칸 옆 적 F 만, 2 = 2칸까지. v11: 0 → 2
    "block_worth": 3.0,            # 작업 가치 = block_worth + 건물 가치. 10 은 다른 작업을 과하게 밀어낸다. v11: 3.0
    "eg_risk_scale": 1.0,         # 후반 모드(endgame_turn~)의 목표 위험 배율 가중치 배율. 1.0 = v10 그대로, 0 = 막판엔 위험 무시
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
    "escort_dist": 2,              #   F 에서 이 거리 안의 미점령 건물. v7: 1 → 2
    "escort_bonus": 1.8,           #   작업 가치 = 건물 가치 + bonus. v8: 3.0 → 1.5 v9: 1.5 → 1.8
    "escort_extra": 2,             #   보낼 인원 = 위협 + extra. v8: 1 → 2
    "f_idle_off": True,           # 목표 없는 F 는 내 건물 위에 머물지 않고 옆 빈 칸으로 비킨다 v9: False → True
    "w_spawn": "enf",              # W 생산 거점 기준: enf(적 F 에 가까운 곳) | myf(아군 F 근처, 엄호용) | mix
    "max_f_early": 6,              # early_turn 까지의 깃발병 상한(중립 건물이 많은 초반 확장 경쟁용)
    "early_turn": 0,               # 0 = 끔
    # --- v9 이후 스위치 (사용자 리플레이 관찰) ---
    "risk_depth_w": 0.0,           # 목표가 적 진영 깊이(내 거점까지 − 적 거점까지 거리) 1칸마다 가치를 이 비율로 깎음. 0 = 끔
    "risk_local_w": 0.15,          # 목표 주변(risk_R 칸) 적 W 가 아군 W 보다 많은 만큼 가치를 깎음. 0 = 끔. v10: 0 → 0.15
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
    "spend_all": False,            # 예비비 외 남는 예산을 전부 전투병으로
    "spend_all_hard": False,       # 예비비까지 전부 전투병으로(점령비는 이번 턴 수입으로)
    # 전선 집결(사용자 제안): 후반에는 남는 W 를 전선 건물에 모으고, 뒤쪽 건물은 적이 다가올 때만 먼저 증원
    "front_mass_turn": 999,        # 이 턴부터 켠다. 999 = 끔
    "front_k": 3,                  # 전선 건물 수(내 건물 중 적 생산 거점 쪽으로 가장 깊은 순)
    "rear_R": 4,                   # 뒤쪽 건물 이 거리 안에 적 W 가 들어오면 그 수 + 1 을 그 거리 안에 도착할 병력으로 보낸다
    "fm_siege": False,             # 전선 집결 중에도 적 건물 공성(주변 위험 배율 적용, 본진 포위 제외)을 할지
    "siege_stage": 2,              # 공성 인원이 모자라면 목표 이 칸 안에서 대기(집결). -1 = 대기 없이 투입
    "reinforce_hot": False,        # 격전지(아군·적 W 가 2칸 안에서 맞선 칸)에 공성보다 먼저 증원
    "hot_radius": 2,
    "rapid_garrison": 2,           # rapid: 건물당 최소 주둔
    "rapid_horizon": 3,            # rapid: 이 턴 수 안에 닿는 적 W 보다 많이, 그 안에 도착할 아군으로 증원
    "lead_w": "reserve",           # 굳히기 중 W 배치: reserve(1-center 예비대) | pressure(공격 방향 예측 주둔) | rapid(주둔+신속 증원)
    "hold_horizon": 3,             # pressure: 이 턴 수 안에 닿는 적 W 를 그 건물의 압력으로 본다
    "hold_trend_w": 1.0,           # pressure: 지난 턴보다 늘어난 적 W(접근 중) 가중
}

# 로컬 실험용: BOT_PARAMS='{"min_f": 0}' 처럼 파라미터를 덮어쓴다(제출 환경에서는 미설정)
if os.environ.get("BOT_PARAMS"):
    P.update(json.loads(os.environ["BOT_PARAMS"]))


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


GEO = None
MEM = None

# 진단 계측(PLAN-frontier 단계 0): BOT_STATS=<폴더> 이면 매 턴 누적 지표를 <폴더>/<pid>.json 에 덮어쓴다.
# 제출 환경에서는 설정되지 않으므로 아무 일도 하지 않는다.
STATS_DIR = os.environ.get("BOT_STATS", "")
STATS = {"f_lost": 0, "gained": 0, "lost": 0, "exp_f": 0, "owned": set(), "pts140": None}


# ------------------------------------------------------------------ 의사결정

def decide(view, init):
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
    n_goals = len(targets_all)
    eg_f = view.turn >= P["eg_f_turn"]
    if endgame or eg_f:
        # 지금 생산한 F 가 기한 안에 닿을 수 있는 건물만 센다
        n_goals = sum(1 for t in targets_all
                      if min(geo.dist[s][t] for s in spawn_me) <= left)
    cap_f = P["max_f_early"] if view.turn <= P["early_turn"] else P["max_f"]
    if eg_f:
        cap_f = P["eg_max_f"]
    des_F = min(cap_f, n_goals)
    min_F = min(P["eg_min_f"] if eg_f else P["min_f"], des_F)
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

    emit_spawn("F", nF, best_spawn(targets_all), myF)
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
        return 1.0 / (1.0 + P["risk_depth_w"] * max(0, depth) + eff_local_w * max(0, local) + extra)

    # 5. 이동 도우미(일반 이동 + 역 순간이동)
    moves = {}
    tele_cmds = []
    tele_state = {"used": False}

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
        return (-cover[v], geo.nkey(v))

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
        st = step_toward(i, goal, safe, pref_of(kind))
        if st is None:
            out.append((i, n))
        else:
            add_move(i, kind, n, st[0])
            out.append((st[1], n))

    def advance(i, kind, n, goal, safe=None):
        """n 명을 goal 쪽으로 보내고 [(도착 칸, 인원)] 을 돌려준다.
        역 경유가 빠르면 출발 역으로 걷고, 출발 역 위에서는 TELE(턴당 1회·최대 5명)한다."""
        out = []
        r = tele_route(i, goal, safe)
        if r is None:
            walk(i, kind, n, goal, safe, out)
            return out
        via, a, b = r
        if i != a:
            walk(i, kind, n, a, safe, out)       # 출발 역으로 이동
            return out
        if not tele_state["used"]:
            k = min(n, TELE_MAX)
            tele_cmds.append(tele(*geo.xy(i), kind, k, *geo.xy(b)))
            tele_state["used"] = True
            out.append((b, k))
            n -= k
        if n > 0:
            # 이번 턴 TELE 를 못 쓰면: 한 턴 기다렸다 TELE 하는 편이 여전히 빠르면 대기
            if 2 + geo.dist[b][goal] <= geo.dist[i][goal] - P["tele_min_gain"]:
                out.append((i, n))
            else:
                walk(i, kind, n, goal, safe, out)
        return out

    # 6. 전투병 배치
    w_pool = dict(myW)                 # 아직 명령받지 않은 전투병
    cover = [0] * (geo.w * geo.h)      # 이동 후 칸별 아군 전투병 수
    tr_groups = []                    # 이번 턴 도착 위치, 실제 W 임무, 인원

    wmode = {"siege": False}

    def send_w(g, need, stage_dist, deadline=INF):
        """w_pool 에서 g 에 가까운 순으로 need 명을 보낸다.
        deadline 안에 도착할 수 있는 인원만으로 need 를 채울 수 있으면 그 인원만 쓴다.
        모인 인원이 need 에 못 미치면 stage_dist 칸 밖에서 대기하며 모은다."""
        near_ws = sorted((eff_dist(i, g), geo.nkey(i), i)
                         for i, c in w_pool.items() if c > 0 and geo.dist[i][g] < INF)
        timely = [t for t in near_ws if t[0] <= deadline]
        if deadline < INF and sum(w_pool[t[2]] for t in timely) >= need:
            near_ws = timely
        enough = sum(w_pool[t[2]] for t in near_ws) >= need
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

    # 적 깃발병 요격: 다음 목표 건물을 예측해 적보다 먼저(또는 동시에) 도착한다
    jobs = []  # (가치, 목표 칸, 필요 인원, 도착 기한, 집결 거리)
    for e, c in enF.items():
        if not P["predict"]:
            # v2 방식: 가장 가까운 비적 건물 + 현재 위치
            cands = [i for i, b in bld.items() if b["owner"] != opp and enF.get(i, 0) == 0]
            g = e if (e in bld and bld[e]["owner"] != opp) else (
                min(cands, key=lambda i: (geo.dist[e][i], geo.nkey(i))) if cands else e)
            worth = 2.0 + (value(bld[g]) if g in bld else 0) + (1.0 if g in bld and bld[g]["owner"] == me else 0)
            jobs.append((worth, g, threat[g] + 1, INF, -1))
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
    if P["f_block"]:
        # 전투는 같은 칸에서만 일어난다. 적 F 가 도착하는 턴에 그 칸 위 아군 W 가 적 W 보다 많아야 건물이 산다.
        for b, bb in bld.items():
            if bb["owner"] != me or enF.get(b, 0):
                continue
            k = min((geo.dist[e][b] for e in enF), default=INF)
            if k > P["f_block"]:
                continue
            need = sum(c for j, c in enW.items() if geo.dist[j][b] <= k) + 1
            jobs.append((P["block_worth"] + value(bb), b, need, k, -1))
    if P["plaza_hold"]:
        for i, b in bld.items():
            if b["type"] == "PLAZA" and b["owner"] == me and threat[i] > 0:
                jobs.append((100.0, i, threat[i] + P["plaza_hold"], INF, -1))
    jobs.sort(key=lambda j: (-j[0], geo.nkey(j[1])))

    done_goals = set()
    for worth, g, need, deadline, stage in jobs:
        if g in done_goals:
            continue
        pool = sum(c for i, c in w_pool.items() if c > 0 and geo.dist[i][g] <= deadline)
        if deadline <= 1 and pool < need:
            continue
        done_goals.add(g)
        send_w(g, need, stage, deadline)

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
        if b["owner"] != me or p in done_goals:
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
    for _, _, p in ([] if hold or rapid or fm else sorted(guard_posts)):
        if not any(c > 0 for c in w_pool.values()):
            break
        # 같은 수면 1:1 상쇄로 모두 사라지고 적 F 가 살아남아 중립화한다 → 이기려면 적 + 1 이 필요하다
        need = (min(P["guard_cap"], wforce(p, H, False) + 1) if H > 0
                else max(1, threat[p] + P["guard_extra"]))
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
    siege.sort(key=lambda t: (-t[0], geo.nkey(t[1])))
    wmode["siege"] = True
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
    if siege:
        top = siege[0][1]
        for i in sorted(w_pool, key=geo.nkey):
            if w_pool[i] > 0:
                send_w(top, w_pool[i], -1)

    # 7. 깃발병 배치
    def safe(v):
        if P["f_contest_wait"] and enF.get(v, 0) and cover[v] <= threat[v]:
            return False           # 적 F 가 있는 칸에 엄호 없이 들어가면 경합으로 양쪽 모두 점령 불가
        return threat[v] == 0 or cover[v] > threat[v]

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
    race_eta = {}
    if P["la_race"]:
        # 적 F 도착 턴: 현재 적 F + (생산 가능하면) 적 생산 거점에서 새로 나오는 F
        srcs = list(enF) + (spawn_opp if view.opp_resource >= F_COST else [])
        for t in targets:
            race_eta[t] = min((geo.dist[x][t] for x in srcs), default=INF)
    free_units = sorted(f_units, key=geo.nkey)
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
        for dest, n in ([(u, 1)] if wait else advance(u, "F", 1, t, safe)):
            if P["f_wait_2step"] and dest == u and u != t:
                near_en = sum(c for i, c in enW.items() if geo.dist[i][u] <= 2)
                if near_en > sum(cover[j] for j in geo.near(u)):
                    side = sorted((sum(c for i, c in enW.items() if geo.dist[i][v] <= 2), geo.nkey(v), d, v)
                                  for d, v in geo.nbrs[u] if safe(v))
                    if side and side[0][0] < near_en:
                        add_move(u, "F", 1, side[0][2])
                        dest = side[0][3]
            final_F[dest] = final_F.get(dest, 0) + n

    # 목표가 없는 깃발병: 위협받으면 피하고 아니면 대기
    for u in free_units:
        if P["f_idle_off"] and u in bld and bld[u]["owner"] == me:
            # 이미 점령한 건물 위에 서 있을 이유가 없다(표적만 된다). 본진 쪽 안전한 빈 칸으로 비킨다.
            side = sorted(((geo.dist[v][base_me], geo.nkey(v)), d) for d, v in geo.nbrs[u]
                          if safe(v) and v not in bld)
            if side:
                add_move(u, "F", 1, side[0][1])
                continue
        if not safe(u):
            side = [(d, v) for d, v in geo.nbrs[u] if safe(v)]
            if pref_of("F") is not None:
                side.sort(key=lambda dv: prefer_f(dv[1]))
            if side:
                add_move(u, "F", 1, side[0][0])
                continue
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
