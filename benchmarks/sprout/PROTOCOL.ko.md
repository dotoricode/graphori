# Sprout 라우팅 모델 벤치마크 규약

이 실험은 provider, node, verifier를 실제 실행하는 성능 측정이 아니라 라우팅 정책의
결정론적 모델입니다. 후보 metadata가 의무 이름을 포함하면
`declared_proofs_closed`로 집계합니다. 테스트 통과나 실제 증거 생성 횟수가 아닙니다.

## 비교 행렬

- 조건: v1 target review, Graphori v2, 무조건 파일럿, adaptive Sprout, static oracle
- 서로 다른 구조의 workload: 지역 자료 수집, 저장소 감사, release preflight, API import
- 독립 대상 수: 1, 2, 4, 8, 16
- 반복: 동일 fixture를 공유하는 seeded variation 10회
- 전체: 5조건 × 4 workload × 5 대상 수 × 10회 = 1,000칸

같은 workload/repetition에서는 모든 조건이 정확히 같은 후보 비용과 review 비용을
받습니다. 분석기는 fixture digest가 다르거나 행렬이 빠지면 실패합니다.

## 조건의 의미

- `v1-target-review`: v2의 단일 의무별 노드 뒤 대상마다 AI review 하나를 둔 대조군입니다.
  과거 Graphori v1을 재현했다고 주장하지 않습니다.
- `graphori-v2`: 의무마다 미리 선언된 노드 하나를 실행합니다.
- `sprout-unconditional`: 실제 `ProofFrontier`가 고른 compound cover를 파일럿으로 한 번
  더 실행합니다. 파일럿 시간과 agent/process 노드를 모두 계산합니다.
- `graphori-sprout`: 같은 WIP 모델로 static 경로와 pilot 경로를 먼저 비교하고,
  모델링 지연이 줄면서 AI session이 늘지 않고 proof·scope gate를 모두 통과하는
  cell에서만 파일럿을 켭니다.
- `oracle-static`: 같은 compound cover를 처음부터 안다고 가정해 파일럿 비용을 빼는
  대조군입니다. 전역 이론적 하한도, 실제 Graphori 실행 모드도 아닙니다.

생성 결과는 추적하지 않고 `build/benchmarks/sprout/` 아래에 둡니다. 재현 명령은
[영문 규약](PROTOCOL.md)에 있습니다.
