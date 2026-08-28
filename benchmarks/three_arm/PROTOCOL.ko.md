# Direct vs v1 방식 vs Graphori v2 비교 방법

이 비교는 provider 순위가 아니라 orchestration 방식의 차이를 측정합니다. Codex와
Claude는 합치지 않고 별도로 보고합니다.

## 고정된 실행표

- Provider: Codex, Claude Code.
- 조건: Direct, v1 방식, Graphori v2.
- 과제: 작은 수정, 제한된 기능, 여러 파일 기능, 경계조건 버그 수정 각 1종.
- 반복: 각 조합을 새 Git 저장소와 새 provider 세션에서 3회.
- 합계: provider 2 × 조건 3 × 과제 4 × 반복 3 = 72회.
- 순서: seed `20260828`로 결정적으로 섞음.

같은 provider·과제 조합 안에서는 시작 Git tree, 요구사항, model, effort, 공개 검사,
숨은 검사, read/write scope, timeout과 network 조건이 같습니다. 숨은 검사는 각 조건이
끝난 뒤에만 파일로 만듭니다.

## 조건

- **Direct:** 구현 AI 세션 1개.
- **v1 방식:** 구현 AI 뒤에 같은 provider·model·effort의 새 read-only AI 리뷰 세션.
- **Graphori v2:** 같은 구현 route 뒤에 deterministic verifier, journal, scope 검사와
  terminal projection 실행.

v1 리뷰어는 파일을 고칠 수 없고 숨은 검사도 볼 수 없습니다. 리뷰 결과로 재작업을
시키지 않습니다. Graphori v2는 공개 deterministic 검사가 revise를 반환할 때만
재작업을 기록할 수 있습니다.

## 지표

숨은 검사, 완료 보고 일치, scope 위반과 재작업을 속도·비용보다 먼저 봅니다. TTUR은
새 fixture를 만든 시점부터 숨은 검사 완료까지의 wall time입니다. 전체·캐시·신규
입력 토큰과 출력 토큰을 나눕니다.

Claude의 cache creation 입력은 신규 입력, cache read 입력은 캐시 입력으로 셉니다.
Codex는 CLI가 보고한 전체·캐시 입력을 쓰고 둘의 차이를 신규 입력으로 계산합니다.
Provider가 비용을 주지 않으면 `null`이며 추정하지 않습니다.

원자료에는 prompt나 provider transcript 대신 hash와 제한된 metadata만 둡니다.
Infrastructure 실패는 성공이나 검사 실패로 추정하지 않고 `unknown`입니다.

```bash
PYTHONPATH=src python benchmarks/three_arm/run.py \
  --output benchmarks/three_arm/raw-results.jsonl
python benchmarks/three_arm/analyze.py
```

실행기는 JSONL record마다 `fsync`하며 완료된 조합은 건너뛰어 재개할 수 있습니다.
